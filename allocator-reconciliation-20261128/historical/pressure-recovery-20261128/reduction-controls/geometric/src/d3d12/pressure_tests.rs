#![allow(clippy::unwrap_used)]

use super::*;
use alloc::collections::VecDeque;
use core::cell::RefCell;
use core::{cell::Cell, ffi::c_void, mem::MaybeUninit};
use std::sync::OnceLock;
use windows::core::{Interface, GUID, HRESULT};

const MIB: u64 = 1024 * 1024;

#[derive(Default)]
struct Driver {
    calls: Vec<u64>,
    errors: VecDeque<HRESULT>,
    live_bytes: u64,
    destroyed: usize,
    limit: Option<u64>,
}
thread_local! { static DRIVER: RefCell<Driver> = RefCell::new(Driver::default()); }

#[repr(C)]
struct Object {
    vtable: *const usize,
    refs: Cell<u32>,
    heap_size: u64,
}

unsafe extern "system" fn query(_: *mut c_void, _: *const GUID, _: *mut *mut c_void) -> HRESULT {
    HRESULT(0x80004002_u32 as i32)
}
unsafe extern "system" fn add_ref(this: *mut c_void) -> u32 {
    let object = unsafe { &*this.cast::<Object>() };
    object.refs.set(object.refs.get() + 1);
    object.refs.get()
}
unsafe extern "system" fn release(this: *mut c_void) -> u32 {
    let object = unsafe { &*this.cast::<Object>() };
    let refs = object.refs.get() - 1;
    object.refs.set(refs);
    if refs == 0 {
        let object = unsafe { Box::from_raw(this.cast::<Object>()) };
        if object.heap_size != 0 {
            DRIVER.with(|d| {
                let mut d = d.borrow_mut();
                d.live_bytes -= object.heap_size;
                d.destroyed += 1;
            });
        }
    }
    refs
}
fn unknown_table() -> &'static [usize] {
    static TABLE: OnceLock<Vec<usize>> = OnceLock::new();
    TABLE.get_or_init(|| {
        let mut table =
            vec![query as *const () as usize; size_of::<ID3D12Heap_Vtbl>() / size_of::<usize>()];
        table[..3].copy_from_slice(&[
            query as *const () as usize,
            add_ref as *const () as usize,
            release as *const () as usize,
        ]);
        table
    })
}
unsafe extern "system" fn create_heap(
    _: *mut c_void,
    desc: *const D3D12_HEAP_DESC,
    _: *const GUID,
    heap: *mut *mut c_void,
) -> HRESULT {
    let size = unsafe { (*desc).SizeInBytes };
    DRIVER.with(|d| {
        let mut d = d.borrow_mut();
        d.calls.push(size);
        if let Some(error) = d.errors.pop_front() {
            return error;
        }
        if d.limit.is_some_and(|limit| d.live_bytes + size > limit) {
            return E_OUTOFMEMORY;
        }
        d.live_bytes += size;
        let object = Box::new(Object {
            vtable: unknown_table().as_ptr(),
            refs: Cell::new(1),
            heap_size: size,
        });
        unsafe {
            *heap = Box::into_raw(object).cast();
        }
        HRESULT(0)
    })
}

fn fixture() -> Allocator {
    DRIVER.with(|d| *d.borrow_mut() = Driver::default());
    // Only IUnknown and CreateHeap are called. Allocate full pointer tables with non-null
    // entries; unused methods are never invoked. Field offsets come from the bindings.
    static DEVICE_TABLE: OnceLock<Vec<usize>> = OnceLock::new();
    let table = DEVICE_TABLE.get_or_init(|| {
        let mut table =
            vec![query as *const () as usize; size_of::<ID3D12Device_Vtbl>() / size_of::<usize>()];
        table[..3].copy_from_slice(&unknown_table()[..3]);
        let layout = MaybeUninit::<ID3D12Device_Vtbl>::uninit();
        let base = layout.as_ptr();
        let offset = unsafe { core::ptr::addr_of!((*base).CreateHeap) as usize - base as usize };
        table[offset / size_of::<usize>()] = create_heap as *const () as usize;
        table
    });
    let object = Box::new(Object {
        vtable: table.as_ptr(),
        refs: Cell::new(1),
        heap_size: 0,
    });
    let device = unsafe { ID3D12Device::from_raw(Box::into_raw(object).cast()) };
    let memory_types = [MemoryLocation::GpuOnly, MemoryLocation::CpuToGpu]
        .into_iter()
        .enumerate()
        .map(|(index, location)| MemoryType {
            memory_blocks: Vec::new(),
            committed_allocations: CommittedAllocationStatistics {
                num_allocations: 0,
                total_size: 0,
            },
            memory_location: location,
            heap_category: HeapCategory::All,
            heap_properties: D3D12_HEAP_PROPERTIES::default(),
            memory_type_index: index,
            active_general_blocks: 0,
            empty_block_index: None,
            block_sizes: AllocationSizes::new(8 * MIB, 8 * MIB)
                .with_max_device_memblock_size(64 * MIB)
                .block_sizes_for(false),
        })
        .collect();
    Allocator {
        device: ID3D12DeviceVersion::Device(device),
        debug_settings: AllocatorDebugSettings::default(),
        memory_types,
    }
}
fn request(size: u64, location: MemoryLocation) -> AllocationCreateDesc<'static> {
    AllocationCreateDesc {
        name: "pressure test",
        location,
        size,
        alignment: 65536,
        resource_category: ResourceCategory::Buffer,
    }
}

#[test]
fn pressure_reclaims_other_type_and_retries() {
    let mut allocator = fixture();
    let anchor = allocator
        .allocate(&request(MIB, MemoryLocation::GpuOnly))
        .unwrap();
    let cached = allocator
        .allocate(&request(MIB, MemoryLocation::CpuToGpu))
        .unwrap();
    allocator.free(cached).unwrap();
    DRIVER.with(|d| d.borrow_mut().limit = Some(24 * MIB));
    let allocation = allocator
        .allocate(&request(8 * MIB, MemoryLocation::GpuOnly))
        .unwrap();
    assert_eq!(
        DRIVER.with(|d| d.borrow().calls.clone()),
        vec![8 * MIB, 8 * MIB, 16 * MIB, 16 * MIB]
    );
    assert_eq!(DRIVER.with(|d| d.borrow().destroyed), 1);
    allocator.free(allocation).unwrap();
    allocator.free(anchor).unwrap();
    drop(allocator);
    assert_eq!(DRIVER.with(|d| d.borrow().live_bytes), 0);
}

#[test]
fn minimum_fallback_respects_heap_alignment_and_fatal_errors_do_not_retry() {
    let mut allocator = fixture();
    DRIVER.with(|d| d.borrow_mut().limit = Some(12 * MIB));
    let allocation = allocator
        .allocate(&request(9 * MIB, MemoryLocation::GpuOnly))
        .unwrap();
    assert_eq!(
        DRIVER.with(|d| d.borrow().calls.clone()),
        vec![16 * MIB, 12 * MIB]
    );
    allocator.free(allocation).unwrap();
    DRIVER.with(|d| {
        d.borrow_mut()
            .errors
            .push_back(HRESULT(0x887A0005_u32 as i32))
    });
    assert!(matches!(
        allocator.allocate(&request(13 * MIB, MemoryLocation::GpuOnly)),
        Err(AllocationError::Internal(_))
    ));
    assert_eq!(allocator.cached_capacity(), 12 * MIB);
    assert_eq!(DRIVER.with(|d| d.borrow().calls.len()), 3);
}

#[test]
fn failed_first_suballocation_releases_heap_and_preserves_slots() {
    let mut allocator = fixture();
    let desc = request(8 * MIB, MemoryLocation::GpuOnly);
    assert!(allocator
        .allocate_type(0, &desc, &Arc::new(Backtrace::disabled()), Some(MIB))
        .is_err());
    assert!(allocator.memory_types[0].memory_blocks.is_empty());
    assert_eq!(allocator.memory_types[0].active_general_blocks, 0);
    assert_eq!(DRIVER.with(|d| d.borrow().destroyed), 1);
}

#[test]
fn trim_reports_allocator_capacity_while_external_heap_reference_delays_release() {
    let mut allocator = fixture();
    let allocation = allocator
        .allocate(&request(MIB, MemoryLocation::GpuOnly))
        .unwrap();
    let heap = unsafe { allocation.heap() }.clone();
    allocator.free(allocation).unwrap();
    assert_eq!(allocator.trim(), 8 * MIB);
    assert_eq!(allocator.capacity(), 0);
    assert_eq!(DRIVER.with(|d| d.borrow().destroyed), 0);
    drop(heap);
    assert_eq!(DRIVER.with(|d| d.borrow().destroyed), 1);
}
