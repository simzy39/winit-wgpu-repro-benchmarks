"""Experimental bounded cache of one empty block, including while other blocks are live."""
import pathlib,subprocess,shutil,re
H=pathlib.Path(__file__).resolve().parent
folder=H/"work/cache2"
repo=folder/"gpu-allocator"
if repo.exists(): raise SystemExit("Preserving existing cache2 worktree")
folder.mkdir(parents=True)
subprocess.run(["git","-C",str(H.parent/"repo"),"worktree","add","--detach",str(repo),"179ea43"],check=True)
shutil.copytree(H/"work/retain2/gpu-allocator/src",repo/"src",dirs_exist_ok=True)
for backend in ["vulkan","d3d12","metal"]:
    p=repo/"src"/backend/"mod.rs"
    s=p.read_text()
    # The field's visibility matches its surrounding backend type.
    visibility="pub(crate) " if backend=="vulkan" else ""
    token=f"    {visibility}active_general_blocks: usize,"
    assert token in s
    s=s.replace(token,token+f"\n    {visibility}empty_block_index: Option<usize>,",1)
    s=re.sub(r'(?m)^( +)active_general_blocks: 0,$',
        lambda match: match.group(1) + 'active_general_blocks: 0,\n'
        + match.group(1) + 'empty_block_index: None,', s)
    # Every successful allocation from an existing block consumes its empty-cache state.
    token="                    Ok((offset, chunk_id)) => {"
    if token not in s: token="                    Ok((offset, chunk_id)) => {"
    assert token in s,backend
    s=s.replace(token,token+"""
                        if self.empty_block_index == Some(mem_block_i) {
                            self.empty_block_index = None;
                        }""",1)
    a=s.index("        // We only want to destroy this now-empty block")
    b=s.index("            let block = self.memory_blocks[block_idx]",a)
    s=s[:a]+'''        if !mem_block.sub_allocator.is_empty() {
            return Ok(());
        }
        let mut block_idx = block_idx;
        let general = mem_block.sub_allocator.supports_general_allocations();
        let block_size = mem_block.size;
        if general {
            let cached_size = self.empty_block_index
                .and_then(|i| self.memory_blocks[i].as_ref())
                .map(|block| block.size);
            if self.block_sizes.should_cache_empty_block(block_size, cached_size) {
                let previous = self.empty_block_index.replace(block_idx);
                if let Some(previous) = previous {
                    block_idx = previous;
                } else {
                    return Ok(());
                }
            }
        }
        {
''' +s[b:]
    p.write_text(s)
p=repo/"src/lib.rs"
s=p.read_text()
at=s.index("    /// Whether an empty shared block")
s=s[:at]+'''    /// Keep the largest empty block within one growth step of the configured minimum.
    pub(crate) fn should_cache_empty_block(&self, size: u64, cached_size: Option<u64>) -> bool {
        size <= self.min.saturating_mul(2).min(self.max)
            && cached_size.map_or(true, |cached| size > cached)
    }

'''+s[at:]
p.write_text(s)
p=repo/"src/vulkan/capacity_tests.rs"
s=p.read_text().replace("        active_general_blocks: 0,","        active_general_blocks: 0,\n        empty_block_index: None,")
s+='''
#[test]
#[allow(clippy::unwrap_used)]
fn cached_block_is_reused_while_another_block_remains_live() {
    let mut allocator = fixture(&[(256 * MIB, vk::MemoryPropertyFlags::DEVICE_LOCAL)], false);
    allocator.memory_types[0].block_sizes = AllocationSizes::new(8 * MIB, 4 * MIB)
        .with_max_device_memblock_size(64 * MIB).block_sizes_for(false);
    let anchor = allocator.allocate(&request(1024, MemoryLocation::GpuOnly)).unwrap();
    for _ in 0..4 {
        let mut burst = Vec::new();
        for _ in 0..8 {
            burst.push(allocator.allocate(&request(2 * MIB + MIB / 4, MemoryLocation::GpuOnly)).unwrap());
        }
        for allocation in burst { allocator.free(allocation).unwrap(); }
        assert!(allocator.memory_types[0].empty_block_index.is_some());
    }
    assert_eq!(DRIVER.with(|d| d.borrow().calls.len()), 2);
    allocator.free(anchor).unwrap();
    assert_eq!(allocator.capacity(), 16 * MIB);
    assert_eq!(allocator.memory_types[0].active_general_blocks, 1);
}
'''
p.write_text(s)
(folder/"Cargo.toml").write_text('[workspace]\nmembers=["gpu-allocator","bench"]\nresolver="2"\n')
shutil.copytree(H/"work/retain2/bench",folder/"bench")
shutil.copyfile(H/"work/retain2/Cargo.lock",folder/"Cargo.lock")
print("Prepared cache2 candidate")

