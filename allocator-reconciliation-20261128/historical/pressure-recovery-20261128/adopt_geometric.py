"""Select the measured typed-OOM reduction policy; preserve the earlier candidate."""
import pathlib,shutil,json
H=pathlib.Path(__file__).resolve().parent;R=H/'work/recovery/gpu-allocator'
data=json.loads((H/'reduction-actual.json').read_text())
assert data[0]['successes']==2 and data[3]['successes']==48
snapshot=H/'measurement-sources/exact-final';assert not snapshot.exists()
shutil.copytree(R/'src',snapshot/'src')
for file in ['README.md','Cargo.toml']:shutil.copyfile(R/file,snapshot/file)
shutil.copytree(H/'patches',H/'patches-exact-stage')
shutil.copyfile(H/'ARCHITECTURE_SELECTED.json',H/'architecture-exact-stage.json')
shutil.copytree(H/'work/geometric/gpu-allocator/src',R/'src',dirs_exist_ok=True)
p=R/'src/vulkan/capacity_tests.rs';s=p.read_text();s+='''
#[test]
fn pressure_backoff_keeps_useful_capacity_before_the_allocation_count_limit() {
    let mut allocator=fixture(&[(256*MIB,vk::MemoryPropertyFlags::DEVICE_LOCAL)],false);
    growable(&mut allocator,64*MIB,64*MIB);
    allocator.max_memory_allocation_count=2;
    DRIVER.with(|d|d.borrow_mut().limit=Some(48*MIB));
    let mut live=Vec::new();
    for _ in 0..48 {live.push(allocator.allocate(&request(MIB,MemoryLocation::GpuOnly)).unwrap());}
    assert_eq!(allocator.capacity(),48*MIB);
    assert_eq!(allocator.memory_types[0].active_blocks,2);
    assert_eq!(DRIVER.with(|d|d.borrow().calls.clone()),vec![(0,64*MIB),(0,32*MIB),(0,64*MIB),(0,32*MIB),(0,16*MIB)]);
    for allocation in live {allocator.free(allocation).unwrap();}
    allocator.trim();
    assert!(DRIVER.with(|d|d.borrow().live.is_empty()));
}
''';p.write_text(s)
p=R/'src/d3d12/pressure_tests.rs';s=p.read_text()
s=s.replace('    live_bytes: u64,','    live_bytes: u64,\n    live_heaps: usize,\n    count_limit: Option<usize>,')
s=s.replace('                d.live_bytes -= object.heap_size;','                d.live_bytes -= object.heap_size;\n                d.live_heaps -= 1;')
s=s.replace('        if d.limit.is_some_and(|limit| d.live_bytes + size > limit) {','        if d.limit.is_some_and(|limit| d.live_bytes + size > limit)\n            || d.count_limit.is_some_and(|limit| d.live_heaps >= limit) {')
s=s.replace('        d.live_bytes += size;','        d.live_bytes += size;\n        d.live_heaps += 1;')
s+='''
#[test]
fn pressure_backoff_avoids_many_minimum_heaps() {
    let mut allocator=fixture();
    for ty in &mut allocator.memory_types {ty.block_sizes=AllocationSizes::new(64*MIB,64*MIB).block_sizes_for(false);}
    DRIVER.with(|d|{let mut d=d.borrow_mut();d.limit=Some(48*MIB);d.count_limit=Some(2);});
    let mut live=Vec::new();
    for _ in 0..48 {live.push(allocator.allocate(&request(MIB,MemoryLocation::GpuOnly)).unwrap());}
    assert_eq!(allocator.capacity(),48*MIB);
    assert_eq!(DRIVER.with(|d|d.borrow().live_heaps),2);
    assert_eq!(DRIVER.with(|d|d.borrow().calls.clone()),vec![64*MIB,32*MIB,64*MIB,32*MIB,16*MIB]);
    for allocation in live {allocator.free(allocation).unwrap();}
    allocator.trim();
    assert_eq!(DRIVER.with(|d|d.borrow().live_bytes),0);
    assert_eq!(DRIVER.with(|d|d.borrow().live_heaps),0);
}
''';p.write_text(s)
p=R/'README.md';s=p.read_text().replace('including below the configured minimum. Fatal backend errors are returned immediately.','including below the configured minimum. Vulkan and D3D12 reduce shared-block sizes\ngeometrically down to the resource floor (aligned to 4 MiB for D3D12), retaining useful\nsharing capacity under pressure. Metal tries the resource floor directly because heap\ncreation failure provides no reason code. Fatal backend errors are returned immediately.');p.write_text(s)
record=json.loads((H/'ARCHITECTURE_SELECTED.json').read_text())
record.update(recovery='Typed Vulkan/D3D12 memory failures: reclaim/retry then geometric reduction to the aligned resource floor; count/fatal errors never shrink. Metal: conservative exact-floor fallback for ambiguous nil and residency commit.',reduction_evidence='reduction-actual.json',reduction_reason='Exact-size fallback served only2 of48 1MiB requests under a48MiB budget and2-block limit; geometric served48 using32+16MiB blocks. Tradeoff: seven failed calls instead of two when no size fits. Finite u64/alignment bound, no arbitrary retry cap.')
(H/'ARCHITECTURE_SELECTED.json').write_text(json.dumps(record,indent=2))
print('Selected geometric Vulkan/D3D12 backoff; earlier exact implementation and patches preserved')
