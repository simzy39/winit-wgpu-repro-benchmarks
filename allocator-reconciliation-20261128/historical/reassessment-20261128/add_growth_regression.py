"""Add a direct regression for PR growth crossing a smaller Vulkan heap."""
import pathlib
H=pathlib.Path(__file__).resolve().parent
assert (H/"DIRECT_COMPLETE").exists(),"Wait for the latency suite"
p=H/"work/cache2/gpu-allocator/src/vulkan/capacity_tests.rs"
s=p.read_text()
assert "geometric_request_advancement_respects_heap_capacity" not in s
s=s.replace(".map(|&(size, _)| vk::MemoryHeap {",".map(|&(size, properties)| vk::MemoryHeap {")
s=s.replace("flags: vk::MemoryHeapFlags::empty(),","flags: if properties.contains(vk::MemoryPropertyFlags::DEVICE_LOCAL) { vk::MemoryHeapFlags::DEVICE_LOCAL } else { vk::MemoryHeapFlags::empty() },")
s+='''
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
    let allocation = allocator.allocate(&request(192 * MIB, MemoryLocation::CpuToGpu)).unwrap();
    assert_eq!(DRIVER.with(|d| d.borrow().calls.clone()), vec![(0, 214 * MIB)]);
    allocator.free(allocation).unwrap();
    assert_eq!(allocator.capacity(), 0);
}
'''
p.write_text(s)
print("Added growth-induced heap-capacity regression")

