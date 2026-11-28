#![allow(clippy::unwrap_used)]
use super::*;
use alloc::collections::{BTreeMap, VecDeque};
use ash::vk::Handle;
use core::cell::RefCell;

const MIB: u64 = 1024 * 1024;

#[derive(Default)]
struct Driver {
    calls: Vec<(u32, u64)>,
    freed: usize,
    fail: bool,
    limit: Option<u64>,
    live: BTreeMap<u64, u64>,
    errors: VecDeque<vk::Result>,
    map_errors: VecDeque<vk::Result>,
    mappings: BTreeMap<u64, Vec<u8>>,
    null_map: bool,
    unmapped: usize,
}
thread_local! {
    static DRIVER: RefCell<Driver> = RefCell::new(Driver::default());
}
unsafe extern "system" fn allocate(
    _: vk::Device,
    info: *const vk::MemoryAllocateInfo<'_>,
    _: *const vk::AllocationCallbacks<'_>,
    memory: *mut vk::DeviceMemory,
) -> vk::Result {
    DRIVER.with(|state| {
        let mut state = state.borrow_mut();
        let info = unsafe { &*info };
        state
            .calls
            .push((info.memory_type_index, info.allocation_size));
        if let Some(error) = state.errors.pop_front() {
            return error;
        }
        let used: u64 = state.live.values().sum();
        if state.fail
            || state
                .limit
                .is_some_and(|limit| used + info.allocation_size > limit)
        {
            vk::Result::ERROR_OUT_OF_DEVICE_MEMORY
        } else {
            let id = state.calls.len() as u64;
            unsafe { *memory = vk::DeviceMemory::from_raw(id) };
            state.live.insert(id, info.allocation_size);
            vk::Result::SUCCESS
        }
    })
}
unsafe extern "system" fn free(
    _: vk::Device,
    memory: vk::DeviceMemory,
    _: *const vk::AllocationCallbacks<'_>,
) {
    DRIVER.with(|state| {
        let mut state = state.borrow_mut();
        assert!(state.live.remove(&memory.as_raw()).is_some());
        assert!(!state.mappings.contains_key(&memory.as_raw()));
        state.freed += 1;
    });
}
unsafe extern "system" fn map(
    _: vk::Device,
    memory: vk::DeviceMemory,
    _: u64,
    _: u64,
    _: vk::MemoryMapFlags,
    pointer: *mut *mut core::ffi::c_void,
) -> vk::Result {
    DRIVER.with(|state| {
        let mut state = state.borrow_mut();
        if let Some(error) = state.map_errors.pop_front() {
            return error;
        }
        let ptr = if state.null_map {
            core::ptr::null_mut()
        } else {
            let size = state.live[&memory.as_raw()] as usize;
            state.mappings.insert(memory.as_raw(), vec![0; size]);
            state
                .mappings
                .get_mut(&memory.as_raw())
                .unwrap()
                .as_mut_ptr()
                .cast()
        };
        unsafe {
            *pointer = ptr;
        }
        vk::Result::SUCCESS
    })
}
unsafe extern "system" fn unmap(_: vk::Device, memory: vk::DeviceMemory) {
    DRIVER.with(|state| {
        let mut state = state.borrow_mut();
        state.mappings.remove(&memory.as_raw());
        state.unmapped += 1;
    });
}
fn fixture(heaps: &[(u64, vk::MemoryPropertyFlags)], fail: bool) -> Allocator {
    DRIVER.with(|state| {
        *state.borrow_mut() = Driver {
            fail,
            ..Default::default()
        }
    });
    let device = unsafe {
        ash::Device::load_with(
            |name| match name.to_bytes() {
                b"vkAllocateMemory" => (allocate as *const ()).cast::<core::ffi::c_void>(),
                b"vkMapMemory" => (map as *const ()).cast::<core::ffi::c_void>(),
                b"vkUnmapMemory" => (unmap as *const ()).cast::<core::ffi::c_void>(),
                b"vkFreeMemory" => (free as *const ()).cast::<core::ffi::c_void>(),
                _ => core::ptr::null(),
            },
            vk::Device::null(),
        )
    };
    let memory_types = heaps
        .iter()
        .enumerate()
        .map(|(i, &(size, flags))| MemoryType {
            memory_blocks: Vec::new(),
            memory_properties: flags,
            memory_type_index: i,
            heap_index: i,
            heap_size: size,
            // These tests intercept API allocation without exposing CPU pointers.
            mappable: false,
            active_general_blocks: 0,
            active_blocks: 0,
            empty_block_index: None,
            block_sizes: AllocationSizes::new(256 * MIB, 256 * MIB)
                .block_sizes_for(flags.contains(vk::MemoryPropertyFlags::HOST_VISIBLE))
                .capped_to_heap(size),
            buffer_device_address: false,
        })
        .collect();
    Allocator {
        memory_types,
        memory_heaps: heaps
            .iter()
            .map(|&(size, properties)| vk::MemoryHeap {
                size,
                flags: if properties.contains(vk::MemoryPropertyFlags::DEVICE_LOCAL) {
                    vk::MemoryHeapFlags::DEVICE_LOCAL
                } else {
                    vk::MemoryHeapFlags::empty()
                },
            })
            .collect(),
        device,
        max_memory_allocation_count: 4096,
        buffer_image_granularity: 1,
        debug_settings: AllocatorDebugSettings::default(),
    }
}
fn request(size: u64, location: MemoryLocation) -> AllocationCreateDesc<'static> {
    AllocationCreateDesc {
        name: "capacity test",
        requirements: vk::MemoryRequirements {
            size,
            alignment: 1,
            memory_type_bits: u32::MAX,
        },
        location,
        linear: true,
        allocation_scheme: AllocationScheme::GpuAllocatorManaged,
    }
}
fn growable(allocator: &mut Allocator, min: u64, max: u64) {
    for ty in &mut allocator.memory_types {
        ty.block_sizes = AllocationSizes::new(min, min)
            .with_max_device_memblock_size(max)
            .with_max_host_memblock_size(max)
            .block_sizes_for(ty.mappable)
            .capped_to_heap(ty.heap_size);
    }
}

#[test]
fn comparative_pressure_stream() {
    for scenario in ["cross_type_cache","minimum_fallback","fatal_error"] {
        let flags=vk::MemoryPropertyFlags::DEVICE_LOCAL;
        let host=vk::MemoryPropertyFlags::HOST_VISIBLE|vk::MemoryPropertyFlags::HOST_COHERENT;
        let mut allocator=fixture(&[(256*MIB,flags),(256*MIB,host)],false);
        growable(&mut allocator,8*MIB,64*MIB);
        let anchor=if scenario=="cross_type_cache" {
            let anchor=allocator.allocate(&request(MIB,MemoryLocation::GpuOnly)).unwrap();
            let cached=allocator.allocate(&request(MIB,MemoryLocation::CpuToGpu)).unwrap();
            allocator.free(cached).unwrap();Some(anchor)
        } else {None};
        DRIVER.with(|d| {
            let mut d=d.borrow_mut();d.limit=Some(if scenario=="cross_type_cache" {24*MIB} else {12*MIB});
            if scenario=="fatal_error" {d.errors.push_back(vk::Result::ERROR_DEVICE_LOST);}
        });
        let size=if scenario=="cross_type_cache" {8*MIB} else {9*MIB};
        let result=allocator.allocate(&request(size,MemoryLocation::GpuOnly));
        let (calls,freed,live) = DRIVER.with(|d| {let d=d.borrow();(d.calls.clone(),d.freed,d.live.values().sum::<u64>())});
        println!("PRESSURE_JSON {{\"scenario\":\"{}\",\"success\":{},\"calls\":{:?},\"freed\":{},\"native_live_bytes\":{}}}",scenario,result.is_ok(),calls,freed,live);
        if let Ok(allocation)=result {allocator.free(allocation).unwrap();}
        if let Some(anchor)=anchor {allocator.free(anchor).unwrap();}
        drop(allocator);
        assert!(DRIVER.with(|d|d.borrow().live.is_empty()));
    }
}
