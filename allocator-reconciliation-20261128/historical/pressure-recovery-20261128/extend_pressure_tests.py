from pathlib import Path
root = Path(__file__).parent / 'work/recovery/gpu-allocator/src'
p = root / 'vulkan/capacity_tests.rs'
s = p.read_text().replace('use core::cell::RefCell;', 'use core::cell::RefCell;\nuse std::collections::{BTreeMap, VecDeque};\nuse ash::vk::Handle;')
s = s.replace('    fail: bool,', '''    fail: bool,
    limit: Option<u64>,
    live: BTreeMap<u64, u64>,
    errors: VecDeque<vk::Result>,
    map_errors: VecDeque<vk::Result>,
    mappings: BTreeMap<u64, Vec<u8>>,
    null_map: bool,
    unmapped: usize,''', 1)
a=s.index('        if state.fail {'); b=s.index('\n    })',a)
s=s[:a]+'''        if let Some(error) = state.errors.pop_front() { return error; }
        let used: u64 = state.live.values().sum();
        if state.fail || state.limit.is_some_and(|limit| used + info.allocation_size > limit) {
            vk::Result::ERROR_OUT_OF_DEVICE_MEMORY
        } else {
            let id = state.calls.len() as u64;
            unsafe { *memory = vk::DeviceMemory::from_raw(id) };
            state.live.insert(id, info.allocation_size);
            vk::Result::SUCCESS
        }'''+s[b:]
a=s.index('unsafe extern "system" fn free(');b=s.index('fn fixture(',a)
s=s[:a]+'''unsafe extern "system" fn free(
    _: vk::Device, memory: vk::DeviceMemory, _: *const vk::AllocationCallbacks<'_>,
) {
    DRIVER.with(|state| {
        let mut state = state.borrow_mut();
        assert!(state.live.remove(&memory.as_raw()).is_some());
        assert!(!state.mappings.contains_key(&memory.as_raw()));
        state.freed += 1;
    });
}
unsafe extern "system" fn map(
    _: vk::Device, memory: vk::DeviceMemory, _: u64, _: u64, _: vk::MemoryMapFlags,
    pointer: *mut *mut core::ffi::c_void,
) -> vk::Result {
    DRIVER.with(|state| {
        let mut state = state.borrow_mut();
        if let Some(error) = state.map_errors.pop_front() { return error; }
        let ptr = if state.null_map { core::ptr::null_mut() } else {
            let size = state.live[&memory.as_raw()] as usize;
            state.mappings.insert(memory.as_raw(), vec![0; size]);
            state.mappings.get_mut(&memory.as_raw()).unwrap().as_mut_ptr().cast()
        };
        unsafe { *pointer = ptr; }
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
'''+s[b:]
s=s.replace('b"vkFreeMemory" =>', '''b"vkMapMemory" => (map as *const ()).cast::<core::ffi::c_void>(),
                b"vkUnmapMemory" => (unmap as *const ()).cast::<core::ffi::c_void>(),
                b"vkFreeMemory" =>''')
s=s.replace('vec![(1, 64 * MIB)]','vec![(1, 64 * MIB), (1, 16 * MIB)]')
s=s.replace('vec![(1, 64 * MIB), (0, 8 * MIB)]','vec![(1, 64 * MIB), (1, MIB), (0, 8 * MIB), (0, MIB)]')
s+='''

fn growable(allocator: &mut Allocator, min: u64, max: u64) {
    for ty in &mut allocator.memory_types {
        ty.block_sizes = AllocationSizes::new(min, min)
            .with_max_device_memblock_size(max).with_max_host_memblock_size(max)
            .block_sizes_for(ty.mappable).capped_to_heap(ty.heap_size);
    }
}

#[test]
fn pressure_reclaims_other_type_and_preserves_live_indices() {
    let host = vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT;
    let mut allocator = fixture(&[(256*MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL), (256*MIB, host)], false);
    allocator.memory_types[1].heap_index = 0; // Both types consume the same physical heap.
    growable(&mut allocator, 8*MIB, 64*MIB);
    let anchor = allocator.allocate(&request(MIB, MemoryLocation::GpuOnly)).unwrap();
    let index = anchor.memory_block_index;
    let cached = allocator.allocate(&request(MIB, MemoryLocation::CpuToGpu)).unwrap();
    allocator.free(cached).unwrap();
    DRIVER.with(|d| d.borrow_mut().limit = Some(24*MIB));
    let allocation = allocator.allocate(&request(8*MIB, MemoryLocation::GpuOnly)).unwrap();
    assert_eq!(DRIVER.with(|d| d.borrow().calls.clone()), vec![(0,8*MIB),(1,8*MIB),(0,16*MIB),(0,16*MIB)]);
    assert_eq!(anchor.memory_block_index, index);
    assert_eq!(allocator.cached_capacity(), 0);
    assert_eq!(allocator.capacity(), 24*MIB);
    allocator.free(allocation).unwrap(); allocator.free(anchor).unwrap();
}

#[test]
fn smaller_block_recovers_when_preferred_growth_does_not_fit() {
    let mut allocator = fixture(&[(256*MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    growable(&mut allocator, 8*MIB, 64*MIB);
    DRIVER.with(|d| d.borrow_mut().limit = Some(12*MIB));
    let allocation = allocator.allocate(&request(9*MIB, MemoryLocation::GpuOnly)).unwrap();
    assert_eq!(allocator.capacity(), 9*MIB);
    allocator.free(allocation).unwrap();
    let reused = allocator.allocate(&request(9*MIB, MemoryLocation::GpuOnly)).unwrap();
    allocator.free(reused).unwrap();
    let larger = allocator.allocate(&request(11*MIB, MemoryLocation::GpuOnly)).unwrap();
    assert_eq!(DRIVER.with(|d| d.borrow().calls.clone()), vec![(0,16*MIB),(0,9*MIB),(0,16*MIB),(0,16*MIB),(0,11*MIB)]);
    assert_eq!(allocator.capacity(), 11*MIB);
    allocator.free(larger).unwrap();
}

#[test]
fn fatal_errors_do_not_reclaim_caches_or_retry() {
    let mut allocator = fixture(&[(256*MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    growable(&mut allocator, 8*MIB, 64*MIB);
    let cached = allocator.allocate(&request(MIB, MemoryLocation::GpuOnly)).unwrap();
    allocator.free(cached).unwrap();
    DRIVER.with(|d| d.borrow_mut().errors.push_back(vk::Result::ERROR_DEVICE_LOST));
    assert!(matches!(allocator.allocate(&request(9*MIB, MemoryLocation::GpuOnly)), Err(AllocationError::Internal(_))));
    assert_eq!(allocator.cached_capacity(), 8*MIB);
    assert_eq!(DRIVER.with(|d| d.borrow().calls.len()), 2);
    assert_eq!(DRIVER.with(|d| d.borrow().freed), 0);
}

#[test]
fn allocation_count_limit_reclaims_but_never_shrinks_or_switches_types() {
    let flags = vk::MemoryPropertyFlags::DEVICE_LOCAL;
    let mut allocator = fixture(&[(256*MIB, flags),(256*MIB,flags)], false);
    growable(&mut allocator, 8*MIB, 64*MIB);
    DRIVER.with(|d| d.borrow_mut().errors.push_back(vk::Result::ERROR_TOO_MANY_OBJECTS));
    assert!(allocator.allocate(&request(MIB, MemoryLocation::GpuOnly)).is_err());
    assert_eq!(DRIVER.with(|d| d.borrow().calls.len()), 1);
    let cached = allocator.allocate(&request(MIB, MemoryLocation::GpuOnly)).unwrap();
    allocator.free(cached).unwrap();
    DRIVER.with(|d| d.borrow_mut().errors.push_back(vk::Result::ERROR_TOO_MANY_OBJECTS));
    let recovered = allocator.allocate(&request(9*MIB, MemoryLocation::GpuOnly)).unwrap();
    assert_eq!(DRIVER.with(|d| d.borrow().calls.len()), 4);
    assert_eq!(DRIVER.with(|d| d.borrow().freed), 1);
    allocator.free(recovered).unwrap();
}

#[test]
fn host_oom_and_mapping_pressure_recover_and_clean_up() {
    for error in [vk::Result::ERROR_OUT_OF_HOST_MEMORY, vk::Result::ERROR_MEMORY_MAP_FAILED] {
        let host = vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT;
        let mut allocator = fixture(&[(256*MIB,host)], false);
        growable(&mut allocator, 8*MIB, 64*MIB);
        allocator.memory_types[0].mappable = true;
        DRIVER.with(|d| d.borrow_mut().map_errors.push_back(error));
        let allocation = allocator.allocate(&request(MIB, MemoryLocation::CpuToGpu)).unwrap();
        assert_eq!(DRIVER.with(|d| d.borrow().calls.clone()), vec![(0,8*MIB),(0,MIB)]);
        assert_eq!(DRIVER.with(|d| d.borrow().freed), 1);
        assert!(allocation.mapped_ptr().is_some());
        allocator.free(allocation).unwrap();
        drop(allocator);
        assert_eq!(DRIVER.with(|d| d.borrow().freed), 2);
        assert_eq!(DRIVER.with(|d| d.borrow().unmapped), 1);
        assert!(DRIVER.with(|d| d.borrow().live.is_empty()));
    }
}

#[test]
fn fatal_mapping_and_null_pointer_roll_back_without_retry() {
    for null_map in [false,true] {
        let host = vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT;
        let mut allocator = fixture(&[(256*MIB,host)], false);
        allocator.memory_types[0].mappable = true;
        DRIVER.with(|d| {
            let mut d = d.borrow_mut(); d.null_map = null_map;
            if !null_map { d.map_errors.push_back(vk::Result::ERROR_DEVICE_LOST); }
        });
        assert!(matches!(allocator.allocate(&request(MIB, MemoryLocation::CpuToGpu)), Err(AllocationError::Internal(_))));
        assert_eq!(allocator.capacity(), 0);
        assert!(allocator.memory_types[0].memory_blocks.is_empty());
        assert_eq!(DRIVER.with(|d| d.borrow().freed), 1);
        assert_eq!(DRIVER.with(|d| d.borrow().unmapped), usize::from(null_map));
    }
}

#[test]
fn cached_blocks_do_not_advance_growth() {
    let mut allocator = fixture(&[(256*MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    growable(&mut allocator, 4*MIB, 64*MIB);
    let first = allocator.allocate(&request(3*MIB, MemoryLocation::GpuOnly)).unwrap();
    let second = allocator.allocate(&request(5*MIB, MemoryLocation::GpuOnly)).unwrap();
    allocator.free(first).unwrap();
    let third = allocator.allocate(&request(5*MIB, MemoryLocation::GpuOnly)).unwrap();
    assert_eq!(DRIVER.with(|d| d.borrow().calls.clone()), vec![(0,4*MIB),(0,8*MIB),(0,8*MIB)]);
    allocator.free(second).unwrap(); allocator.free(third).unwrap();
}

#[test]
fn trim_to_bounds_aggregate_cache_and_ignores_historical_slots() {
    let flags=vk::MemoryPropertyFlags::DEVICE_LOCAL;
    let mut allocator = fixture(&[(256*MIB,flags),(256*MIB,flags),(256*MIB,flags)],false);
    growable(&mut allocator, 4*MIB,64*MIB);
    for (index,size) in [(0,MIB),(1,5*MIB),(2,7*MIB)] {
        let mut desc=request(size,MemoryLocation::GpuOnly); desc.requirements.memory_type_bits=1<<index;
        let allocation=allocator.allocate(&desc).unwrap(); allocator.free(allocation).unwrap();
        allocator.memory_types[index].memory_blocks.resize_with(100_000, || None);
    }
    assert_eq!(allocator.cached_capacity(),20*MIB);
    assert_eq!(allocator.trim_to(12*MIB),8*MIB);
    assert_eq!(allocator.trim_to(12*MIB),0);
    assert_eq!(allocator.trim_to(5*MIB),8*MIB);
    assert_eq!(allocator.trim(),4*MIB);
    assert_eq!(allocator.trim(),0);
    assert_eq!(DRIVER.with(|d|d.borrow().freed),3);
}

#[test]
fn first_suballocation_failure_is_atomic() {
    let mut allocator=fixture(&[(256*MIB,vk::MemoryPropertyFlags::DEVICE_LOCAL)],false);
    let desc=request(8*MIB,MemoryLocation::GpuOnly);
    let result=allocator.allocate_type(0,&desc,&Arc::new(Backtrace::disabled()),Some(MIB));
    assert!(result.is_err());
    assert!(!result.err().unwrap().is_memory_pressure());
    assert!(allocator.memory_types[0].memory_blocks.is_empty());
    assert_eq!(allocator.memory_types[0].active_general_blocks,0);
    assert_eq!(allocator.cached_capacity(),0);
    assert_eq!(DRIVER.with(|d|d.borrow().freed),1);
}

#[test]
fn compatible_cache_is_reused_before_global_reclamation() {
    let host=vk::MemoryPropertyFlags::HOST_VISIBLE|vk::MemoryPropertyFlags::HOST_COHERENT;
    let mut allocator=fixture(&[(256*MIB,host),(256*MIB,host|vk::MemoryPropertyFlags::DEVICE_LOCAL)],false);
    growable(&mut allocator,8*MIB,64*MIB);
    let mut desc=request(MIB,MemoryLocation::CpuToGpu); desc.requirements.memory_type_bits=1;
    let cached=allocator.allocate(&desc).unwrap(); allocator.free(cached).unwrap();
    DRIVER.with(|d|d.borrow_mut().errors.push_back(vk::Result::ERROR_OUT_OF_DEVICE_MEMORY));
    desc.requirements.memory_type_bits=3;
    let allocation=allocator.allocate(&desc).unwrap();
    assert_eq!(allocation.memory_type_index,0);
    assert_eq!(DRIVER.with(|d|d.borrow().calls.len()),2);
    assert_eq!(DRIVER.with(|d|d.borrow().freed),0);
    allocator.free(allocation).unwrap();
}
'''
s='#![allow(clippy::unwrap_used)]\n'+s
p.write_text(s)
for backend in ['d3d12','metal']:
    p=root/backend/'mod.rs';s=p.read_text();a=s.index('        if can_shrink',s.index('    pub fn allocate('));s=s[:a]+s[a:].replace('                    can_shrink = error.may_shrink();','',1);p.write_text(s)
print('Added fault-injection regression scenarios')
