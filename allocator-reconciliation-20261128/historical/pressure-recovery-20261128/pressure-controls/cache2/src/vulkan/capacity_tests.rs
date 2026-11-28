use super::*;
use core::cell::RefCell;

const MIB: u64 = 1024 * 1024;

#[derive(Default)]
struct Driver {
    calls: Vec<(u32, u64)>,
    freed: usize,
    fail: bool,
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
        if state.fail {
            vk::Result::ERROR_OUT_OF_DEVICE_MEMORY
        } else {
            use ash::vk::Handle;
            unsafe { *memory = vk::DeviceMemory::from_raw(state.calls.len() as u64) };
            vk::Result::SUCCESS
        }
    })
}
unsafe extern "system" fn free(
    _: vk::Device,
    _: vk::DeviceMemory,
    _: *const vk::AllocationCallbacks<'_>,
) {
    DRIVER.with(|state| state.borrow_mut().freed += 1);
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

#[test]
#[allow(clippy::unwrap_used)]
fn shared_blocks_fit_small_and_non_quantized_heaps() {
    for size in [1, 2 * MIB, 4 * MIB - 1, 214 * MIB + 123] {
        let mut allocator = fixture(&[(size, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
        let allocation = allocator
            .allocate(&request(size, MemoryLocation::GpuOnly))
            .unwrap();
        assert_eq!(allocation.size(), size);
        assert_eq!(DRIVER.with(|d| d.borrow().calls.clone()), vec![(0, size)]);
        allocator.free(allocation).unwrap();
        drop(allocator);
        assert_eq!(DRIVER.with(|d| d.borrow().freed), 1);
    }
}

#[test]
fn oversized_resources_never_reach_driver() {
    let mut allocator = fixture(&[(2 * MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    assert!(matches!(
        allocator.allocate(&request(2 * MIB + 1, MemoryLocation::GpuOnly)),
        Err(AllocationError::OutOfMemory)
    ));
    assert!(DRIVER.with(|d| d.borrow().calls.is_empty()));
}

#[test]
fn fallback_resource_capacity_is_checked_before_api_call() {
    let host = vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT;
    let mut allocator = fixture(
        &[
            (8 * MIB, host),
            (64 * MIB, host | vk::MemoryPropertyFlags::DEVICE_LOCAL),
        ],
        true,
    );
    assert!(matches!(
        allocator.allocate(&request(16 * MIB, MemoryLocation::CpuToGpu)),
        Err(AllocationError::OutOfMemory)
    ));
    assert_eq!(
        DRIVER.with(|d| d.borrow().calls.clone()),
        vec![(1, 64 * MIB)]
    );
}

#[test]
fn fallback_shared_block_is_capped_to_its_own_heap() {
    let host = vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT;
    let mut allocator = fixture(
        &[
            (8 * MIB, host),
            (64 * MIB, host | vk::MemoryPropertyFlags::DEVICE_LOCAL),
        ],
        true,
    );
    assert!(matches!(
        allocator.allocate(&request(MIB, MemoryLocation::CpuToGpu)),
        Err(AllocationError::OutOfMemory)
    ));
    assert_eq!(
        DRIVER.with(|d| d.borrow().calls.clone()),
        vec![(1, 64 * MIB), (0, 8 * MIB)]
    );
}

#[test]
#[allow(clippy::unwrap_used)]
fn cached_block_is_reused_while_another_block_remains_live() {
    let mut allocator = fixture(&[(256 * MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    allocator.memory_types[0].block_sizes = AllocationSizes::new(8 * MIB, 4 * MIB)
        .with_max_device_memblock_size(64 * MIB)
        .block_sizes_for(false);
    let anchor = allocator
        .allocate(&request(1024, MemoryLocation::GpuOnly))
        .unwrap();
    for _ in 0..4 {
        let mut burst = Vec::new();
        for _ in 0..8 {
            burst.push(
                allocator
                    .allocate(&request(2 * MIB + MIB / 4, MemoryLocation::GpuOnly))
                    .unwrap(),
            );
        }
        for allocation in burst {
            allocator.free(allocation).unwrap();
        }
        assert!(allocator.memory_types[0].empty_block_index.is_some());
    }
    assert_eq!(DRIVER.with(|d| d.borrow().calls.len()), 2);
    allocator.free(anchor).unwrap();
    assert_eq!(allocator.capacity(), 16 * MIB);
    assert_eq!(allocator.memory_types[0].active_general_blocks, 1);
}

#[test]
#[allow(clippy::unwrap_used)]
fn trim_preserves_live_allocations_and_allows_regrowth() {
    let mut allocator = fixture(&[(256 * MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    allocator.memory_types[0].block_sizes = AllocationSizes::new(8 * MIB, 4 * MIB)
        .with_max_device_memblock_size(64 * MIB)
        .block_sizes_for(false);
    let anchor = allocator
        .allocate(&request(1024, MemoryLocation::GpuOnly))
        .unwrap();
    let mut burst = Vec::new();
    for _ in 0..8 {
        burst.push(
            allocator
                .allocate(&request(2 * MIB + MIB / 4, MemoryLocation::GpuOnly))
                .unwrap(),
        );
    }
    for allocation in burst {
        allocator.free(allocation).unwrap();
    }
    assert_eq!(allocator.trim(), 16 * MIB);
    assert_eq!(allocator.generate_report().total_allocated_bytes, 1024);
    assert_eq!(allocator.memory_types[0].active_general_blocks, 1);
    assert!(allocator.memory_types[0].empty_block_index.is_none());
    let another = allocator
        .allocate(&request(MIB, MemoryLocation::GpuOnly))
        .unwrap();
    allocator.free(another).unwrap();
    allocator.free(anchor).unwrap();
    assert_eq!(allocator.trim(), 8 * MIB);
    assert_eq!(allocator.trim(), 0);
    assert_eq!(allocator.capacity(), 0);
    assert_eq!(allocator.memory_types[0].active_general_blocks, 0);
    let allocation = allocator
        .allocate(&request(MIB, MemoryLocation::GpuOnly))
        .unwrap();
    allocator.free(allocation).unwrap();
    assert_eq!(allocator.trim(), 8 * MIB);
    assert_eq!(DRIVER.with(|d| d.borrow().calls.len()), 3);
}

#[test]
#[allow(clippy::unwrap_used)]
fn cache_invariants_hold_under_churn_and_different_free_orders() {
    let mut allocator = fixture(&[(256 * MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    allocator.memory_types[0].block_sizes = AllocationSizes::new(8 * MIB, 4 * MIB)
        .with_max_device_memblock_size(64 * MIB)
        .block_sizes_for(false);
    for round in 0..32 {
        let mut live = Vec::new();
        for i in 0..20 {
            let size = ((i * 17 + round * 7) % 25 + 1) * MIB / 2;
            live.push(
                allocator
                    .allocate(&request(size, MemoryLocation::GpuOnly))
                    .unwrap(),
            );
        }
        if round % 2 == 0 {
            live.reverse();
        }
        for allocation in live {
            allocator.free(allocation).unwrap();
            let ty = &allocator.memory_types[0];
            let empty: Vec<_> = ty
                .memory_blocks
                .iter()
                .enumerate()
                .filter_map(|(i, block)| {
                    block
                        .as_ref()
                        .filter(|b| b.sub_allocator.is_empty())
                        .map(|b| (i, b.size))
                })
                .collect();
            assert!(empty.len() <= 1);
            if let Some(&(i, size)) = empty.first() {
                assert_eq!(ty.empty_block_index, Some(i));
                assert!(size <= 16 * MIB);
            } else {
                assert!(ty.empty_block_index.is_none());
            }
        }
        assert_eq!(allocator.generate_report().total_allocated_bytes, 0);
        assert_eq!(allocator.memory_types[0].active_general_blocks, 1);
    }
}

#[test]
#[allow(clippy::unwrap_used)]
fn geometric_request_advancement_respects_heap_capacity() {
    let host = vk::MemoryPropertyFlags::HOST_VISIBLE
        | vk::MemoryPropertyFlags::HOST_COHERENT
        | vk::MemoryPropertyFlags::DEVICE_LOCAL;
    let mut allocator = fixture(&[(214 * MIB, host)], false);
    allocator.memory_types[0].block_sizes = AllocationSizes::new(4 * MIB, 4 * MIB)
        .with_max_host_memblock_size(256 * MIB)
        .block_sizes_for(true)
        .capped_to_heap(214 * MIB);
    let allocation = allocator
        .allocate(&request(192 * MIB, MemoryLocation::CpuToGpu))
        .unwrap();
    assert_eq!(
        DRIVER.with(|d| d.borrow().calls.clone()),
        vec![(0, 214 * MIB)]
    );
    allocator.free(allocation).unwrap();
    assert_eq!(allocator.capacity(), 0);
}
