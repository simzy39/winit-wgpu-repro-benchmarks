#![allow(clippy::unwrap_used)]
use super::*;
use alloc::collections::{BTreeMap, VecDeque};
use ash::vk::Handle;
use core::cell::RefCell;

const MIB: u64 = 1024 * 1024;

#[derive(Default)]
struct Driver {
    calls: Vec<(u32, u64)>,
    dedicated: Vec<Option<(vk::Buffer, vk::Image)>>,
    allocation_flags: Vec<vk::MemoryAllocateFlags>,
    freed: usize,
    fail: bool,
    limit: Option<u64>,
    live: BTreeMap<u64, u64>,
    errors: VecDeque<vk::Result>,
    map_errors: VecDeque<vk::Result>,
    map_fail: Option<vk::Result>,
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
        let mut dedicated = None;
        let mut flags = vk::MemoryAllocateFlags::empty();
        let mut next = info.p_next.cast::<vk::BaseInStructure<'_>>();
        while !next.is_null() {
            let base = unsafe { &*next };
            match base.s_type {
                vk::StructureType::MEMORY_DEDICATED_ALLOCATE_INFO => {
                    let info = unsafe { &*next.cast::<vk::MemoryDedicatedAllocateInfo<'_>>() };
                    dedicated = Some((info.buffer, info.image));
                }
                vk::StructureType::MEMORY_ALLOCATE_FLAGS_INFO => {
                    flags = unsafe { (*next.cast::<vk::MemoryAllocateFlagsInfo<'_>>()).flags };
                }
                _ => {}
            }
            next = base.p_next;
        }
        state.dedicated.push(dedicated);
        state.allocation_flags.push(flags);
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
        if let Some(error) = state.map_errors.pop_front().or(state.map_fail) {
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
fn comparative_reduction_stream() {
    for scenario in ["count_limited","no_memory","large_resource"] {
        let mut allocator=fixture(&[(256*MIB,vk::MemoryPropertyFlags::DEVICE_LOCAL)],false);
        growable(&mut allocator,64*MIB,64*MIB);
        allocator.max_memory_allocation_count=if scenario=="count_limited" {2} else {4096};
        let budget=if scenario=="count_limited" {48*MIB} else if scenario=="no_memory" {0} else {12*MIB};
        DRIVER.with(|d|d.borrow_mut().limit=Some(budget));
        let count=if scenario=="count_limited" {48} else {1};
        let size=if scenario=="large_resource" {9*MIB} else {MIB};
        let mut live=Vec::new();
        for _ in 0..count {
            match allocator.allocate(&request(size,MemoryLocation::GpuOnly)) {
                Ok(allocation)=>live.push(allocation), Err(_)=>break,
            }
        }
        let calls=DRIVER.with(|d|d.borrow().calls.iter().map(|(_,size)|size/MIB).collect::<Vec<_>>());
        println!("REDUCTION_JSON {{\"scenario\":\"{}\",\"successes\":{},\"calls_mib\":{:?},\"capacity_mib\":{}}}",scenario,live.len(),calls,allocator.capacity()/MIB);
        for allocation in live {allocator.free(allocation).unwrap();}
        allocator.trim();
        assert!(DRIVER.with(|d|d.borrow().live.is_empty()));
    }
}
