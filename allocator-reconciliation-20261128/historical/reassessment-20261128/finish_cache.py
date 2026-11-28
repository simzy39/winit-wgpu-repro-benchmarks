"""Finish the bounded-cache candidate with explicit trim and behavioral tests."""
import pathlib
H=pathlib.Path(__file__).resolve().parent
R=H/"work/cache2/gpu-allocator"
p=R/"src/lib.rs"
s=p.read_text()
s=s.replace("/// Clamped between 4MB and 256MB, and rounds up to the nearest multiple of 4MB for alignment reasons.",
"""/// Configured sizes are clamped between 4MB and 256MB and rounded up to a multiple of 4MB.
/// Vulkan additionally limits shared block sizes to the capacity of the selected memory heap.""")
s=s.replace("""/// tracked independently for each memory type. The block size also decreases
/// when blocks are deallocated, and empty blocks larger than the minimum block
/// size are released rather than retained.""","""/// tracked independently for each memory type and decreases as blocks are released.
/// Each memory type can cache one empty shared block, including while other blocks
/// remain in use. Its size is limited to the smaller of twice the minimum and the
/// maximum block size. Larger empty blocks are released. Backend `Allocator::trim`
/// methods release cached empty blocks at an application-selected boundary.""")
s=s.replace("/// The initial size for device memory blocks.","/// The initial shared block size for memory types the CPU cannot access.")
s=s.replace("/// The maximum size for device memory blocks.","/// The maximum shared block size for memory types the CPU cannot access.")
s=s.replace("/// The initial size for host memory blocks.","""/// The initial shared block size for CPU-visible memory types, including
    /// CPU-visible device-local memory on BAR, resizable BAR and unified-memory systems.""")
s=s.replace("/// The maximum size for host memory blocks.","/// The maximum shared block size for CPU-visible memory types.")
s=s.replace("    /// existing allocations. The more blocks there already are","    /// existing shared blocks. The more blocks there already are")
s=s.replace("    /// device range (memory types the CPU cannot access).","""    /// device range (memory types the CPU cannot access).
    /// This returns the configured growth step before backend hardware limits.""")
a=s.index("    /// Whether an empty shared block")
b=s.index("\n}\n\nimpl Default",a)
s=s[:a]+s[b:]
a=s.index("    #[test]\n    fn empty_general_block_retention_releases_oversized_blocks()")
s=s[:a]+'''    #[test]
    fn empty_cache_is_bounded_and_prefers_the_larger_block() {
        let range = AllocationSizes::new(8 * MB, 4 * MB)
            .with_max_device_memblock_size(64 * MB).block_sizes_for(false);
        assert!(range.should_cache_empty_block(8 * MB, None));
        assert!(range.should_cache_empty_block(16 * MB, Some(8 * MB)));
        assert!(!range.should_cache_empty_block(8 * MB, Some(16 * MB)));
        assert!(!range.should_cache_empty_block(16 * MB, Some(16 * MB)));
        assert!(!range.should_cache_empty_block(16 * MB + 1, None));
        let fixed = AllocationSizes::default().block_sizes_for(true);
        assert!(fixed.should_cache_empty_block(64 * MB, None));
        assert!(!fixed.should_cache_empty_block(64 * MB + 1, None));
    }

    #[test]
    fn heap_caps_preserve_every_fitting_request_and_bound_growth() {
        for capacity in [0, 1, 2 * MB, 4 * MB - 1, 214 * MB + 123, u64::MAX] {
            for minimum in [4 * MB, 12 * MB, 256 * MB] {
                let range = AllocationSizes::new(minimum, minimum)
                    .with_max_device_memblock_size(256 * MB)
                    .block_sizes_for(false).capped_to_heap(capacity);
                assert!(range.min <= range.max && range.max <= capacity);
                if range.max == 0 { continue; }
                for request in [1, range.min, range.max] {
                    for count in [0, 1, 7, usize::MAX] {
                        let size = range.shared_block_size(count, request);
                        assert!(size >= request && size >= range.min && size <= range.max);
                    }
                }
            }
        }
    }
}
'''
p.write_text(s)
for backend in ["vulkan","d3d12","metal"]:
    p=R/"src"/backend/"mod.rs"
    s=p.read_text()
    a=s.index("    pub fn free(")
    trim='''    /// Releases all empty memory blocks and returns the bytes removed from allocator capacity.
    ///
    /// Live allocations and their indices remain valid. This does not wait for GPU work;
    /// resources must already have been freed through this allocator.
    pub fn trim(&mut self) -> u64 {
        let mut released = 0;
        for memory_type in &mut self.memory_types {
            for slot in &mut memory_type.memory_blocks {
                if !slot.as_ref().is_some_and(|block| block.sub_allocator.is_empty()) {
                    continue;
                }
                if let Some(block) = slot.take() {
                    released += block.size;
                    if block.sub_allocator.supports_general_allocations() {
                        memory_type.active_general_blocks -= 1;
                    }
'''
    if backend=="vulkan":
        trim+="                    block.destroy(&self.device);\n"
    elif backend=="metal":
        trim+='''                    if let Some(rs) = &memory_type.global_residency_set {
                        rs.removeAllocation(block.heap.as_ref());
                    }
'''
    trim+='''                }
            }
            memory_type.empty_block_index = None;
        }
        released
    }

'''
    s=s[:a]+trim+s[a:]
    if backend=="metal":
        a=s.index("/// Whether the shared blocks of a heap")
        b=s.index("\nfn memory_location_to_metal",a)
        s=s[:a]+'''/// Shared placement heaps use the CPU-visible range; Private heaps use the GPU-only range.
fn uses_host_block_sizes(storage_mode: MTLStorageMode) -> bool {
    storage_mode == MTLStorageMode::Shared
}
'''+s[b:]
    p.write_text(s)
p=R/"src/vulkan/capacity_tests.rs"
s=p.read_text().replace("use std::cell::RefCell;", "use core::cell::RefCell;")+'''
#[test]
#[allow(clippy::unwrap_used)]
fn trim_preserves_live_allocations_and_allows_regrowth() {
    let mut allocator = fixture(&[(256 * MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    allocator.memory_types[0].block_sizes = AllocationSizes::new(8 * MIB, 4 * MIB)
        .with_max_device_memblock_size(64 * MIB).block_sizes_for(false);
    let anchor = allocator.allocate(&request(1024, MemoryLocation::GpuOnly)).unwrap();
    let mut burst = Vec::new();
    for _ in 0..8 {
        burst.push(allocator.allocate(&request(2 * MIB + MIB / 4, MemoryLocation::GpuOnly)).unwrap());
    }
    for allocation in burst { allocator.free(allocation).unwrap(); }
    assert_eq!(allocator.trim(), 16 * MIB);
    assert_eq!(allocator.generate_report().total_allocated_bytes, 1024);
    assert_eq!(allocator.memory_types[0].active_general_blocks, 1);
    assert!(allocator.memory_types[0].empty_block_index.is_none());
    let another = allocator.allocate(&request(MIB, MemoryLocation::GpuOnly)).unwrap();
    allocator.free(another).unwrap();
    allocator.free(anchor).unwrap();
    assert_eq!(allocator.trim(), 8 * MIB);
    assert_eq!(allocator.trim(), 0);
    assert_eq!(allocator.capacity(), 0);
    assert_eq!(allocator.memory_types[0].active_general_blocks, 0);
    let allocation = allocator.allocate(&request(MIB, MemoryLocation::GpuOnly)).unwrap();
    allocator.free(allocation).unwrap();
    assert_eq!(allocator.trim(), 8 * MIB);
    assert_eq!(DRIVER.with(|d| d.borrow().calls.len()), 3);
}

#[test]
#[allow(clippy::unwrap_used)]
fn cache_invariants_hold_under_churn_and_different_free_orders() {
    let mut allocator = fixture(&[(256 * MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    allocator.memory_types[0].block_sizes = AllocationSizes::new(8 * MIB, 4 * MIB)
        .with_max_device_memblock_size(64 * MIB).block_sizes_for(false);
    for round in 0..32 {
        let mut live = Vec::new();
        for i in 0..20 {
            let size = ((i * 17 + round * 7) % 25 + 1) * MIB / 2;
            live.push(allocator.allocate(&request(size, MemoryLocation::GpuOnly)).unwrap());
        }
        if round % 2 == 0 { live.reverse(); }
        for allocation in live {
            allocator.free(allocation).unwrap();
            let ty = &allocator.memory_types[0];
            let empty: Vec<_> = ty.memory_blocks.iter().enumerate()
                .filter_map(|(i, block)| block.as_ref().filter(|b| b.sub_allocator.is_empty()).map(|b| (i, b.size)))
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
'''
p.write_text(s)
p=R/"src/d3d12/mod.rs"
s=p.read_text()
i=s.rfind("\n}")
s=s[:i]+'''
    #[test]
    fn unknown_heap_and_page_properties_are_not_assumed_mappable() {
        assert!(!uses_host_block_sizes(&props(
            D3D12_HEAP_TYPE(1234),
            D3D12_CPU_PAGE_PROPERTY_WRITE_BACK,
            D3D12_MEMORY_POOL_L0,
        )));
        for page in [D3D12_CPU_PAGE_PROPERTY_UNKNOWN, D3D12_CPU_PAGE_PROPERTY(1234)] {
            assert!(!uses_host_block_sizes(&props(D3D12_HEAP_TYPE_CUSTOM, page, D3D12_MEMORY_POOL_L0)));
        }
    }
'''+s[i:]
p.write_text(s)
print("Added trim, cache boundary and churn tests, and corrected accessibility documentation")

