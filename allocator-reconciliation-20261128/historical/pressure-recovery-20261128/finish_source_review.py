"""Archive measured implementations, then apply the final failure/lifetime corrections."""
from pathlib import Path
import shutil,json,hashlib
H=Path(__file__).resolve().parent
assert (H/'DIRECT_COMPLETE').exists()
for name in ['main','pr323','cache2','recovery','smallcache','heapcap','packed']:
    source=H/'work'/name/'gpu-allocator';snapshot=H/'measurement-sources'/name
    assert not snapshot.exists()
    shutil.copytree(source/'src',snapshot/'src')
    for file in ['README.md','Cargo.toml']:shutil.copyfile(source/file,snapshot/file)
    receipt=json.loads((H/'bin-isolated'/(name+'.json')).read_text())
    for relative,digest in receipt['allocator_source_files'].items():assert hashlib.sha256((snapshot/relative).read_bytes()).hexdigest()==digest,(name,relative)
root=H/'work/recovery/gpu-allocator/src'
p=root/'result.rs';s=p.read_text()
s=s.replace('    pub(crate) fn fatal(error: AllocationError) -> Self {\n        Self {', '''    pub(crate) fn fatal(error: AllocationError) -> Self {
        let error = match error {
            AllocationError::OutOfMemory => AllocationError::Internal(
                "Allocation from a new memory block failed".into(),
            ),
            error => error,
        };
        Self {''');p.write_text(s)
p=root/'d3d12/pressure_tests.rs';s=p.read_text()
a=s.index('fn unknown_table()');b=s.index('unsafe extern "system" fn create_heap',a)
s=s[:a]+'''fn unknown_table() -> &'static [usize] {
    static TABLE: OnceLock<Vec<usize>> = OnceLock::new();
    TABLE.get_or_init(|| {
        let mut table = vec![query as *const () as usize; size_of::<ID3D12Heap_Vtbl>() / size_of::<usize>()];
        table[..3].copy_from_slice(&[query as *const () as usize, add_ref as *const () as usize, release as *const () as usize]);
        table
    })
}
'''+s[b:]
s=s.replace('vec![0; size_of::<ID3D12Device_Vtbl>() / size_of::<usize>()]','vec![query as *const () as usize; size_of::<ID3D12Device_Vtbl>() / size_of::<usize>()]')
s=s.replace('table[..3].copy_from_slice(unknown_table());','table[..3].copy_from_slice(&unknown_table()[..3]);')
s=s.replace('Only IUnknown and CreateHeap are called. Use pointer storage, so unused entries\n    // never construct invalid Rust function pointers. Field offsets come from the bindings.','Only IUnknown and CreateHeap are called. Allocate full pointer tables with non-null\n    // entries; unused methods are never invoked. Field offsets come from the bindings.')
p.write_text(s)
p=root/'vulkan/capacity_tests.rs';s=p.read_text().replace('assert!(!result.err().unwrap().is_memory_pressure());','let error = result.err().unwrap();\n    assert!(!error.is_memory_pressure());\n    assert!(matches!(error.error, AllocationError::Internal(_)));');p.write_text(s)
p=root/'metal/mod.rs';s=p.read_text()
s=s.replace('    empty_block_index: Option<usize>,','    empty_block_index: Option<usize>,\n    pending_residency_removals: bool,')
s=s.replace('                empty_block_index: None,','                empty_block_index: None,\n                pending_residency_removals: false,')
s=s.replace('                rs.removeAllocation(block.heap.as_ref());','                rs.removeAllocation(block.heap.as_ref());\n                self.pending_residency_removals = true;')
s=s.replace('                rs.removeAllocation(block.heap.as_ref())\n','                rs.removeAllocation(block.heap.as_ref());\n                self.pending_residency_removals = true;\n')
s=s.replace('        if self.trim() != 0 {','''        let pending_removals = self.memory_types.iter().any(|ty| ty.pending_residency_removals);
        if self.trim() != 0 || pending_removals {''',1)
a=s.index('    /// Releases cached empty blocks and returns bytes removed')
s=s[:a]+'''    fn commit_pending_removals(&mut self) {
        if self.memory_types.iter().any(|ty| ty.pending_residency_removals) {
            if let Some(set) = &self.global_residency_set {
                set.commit();
            }
            for ty in &mut self.memory_types {
                ty.pending_residency_removals = false;
            }
        }
    }

'''+s[a:]
a=s.index('    pub fn trim(&mut self)');b=s.index('    /// Releases largest cached blocks',a)
s=s[:a]+'''    pub fn trim(&mut self) -> u64 {
        let released = self.memory_types.iter_mut().map(|ty| ty.release_cached()).sum();
        self.commit_pending_removals();
        released
    }

'''+s[b:]
s=s.replace('        before - cached\n    }','        self.commit_pending_removals();\n        before - cached\n    }',1)
s=s.replace('    /// Live indices remain valid. This does not wait for GPU work or release external references.','''    /// Live indices remain valid. This does not wait for GPU work or release external references.
    /// Applies pending changes to this allocator's residency set, including earlier removals.''',1)
s=s.replace('    /// The target applies to empty cached capacity, not live allocations or an OS memory budget.','''    /// The target applies to empty cached capacity, not live allocations or an OS memory budget.
    /// Applies pending changes to this allocator's residency set, including earlier removals.''',1)
p.write_text(s)
assert s.count('pending_residency_removals: false')==1
assert s.count('self.pending_residency_removals = true')==2
print('Archived exact measured sources and completed final failure/lifetime corrections')
