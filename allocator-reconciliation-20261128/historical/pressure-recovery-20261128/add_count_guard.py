from pathlib import Path
root=Path(__file__).parent/'work/recovery/gpu-allocator/src'
p=root/'result.rs';s=p.read_text().replace('    pub(crate) fn fatal(error:', '''    pub(crate) fn memory(error: AllocationError) -> Self {
        Self { error, kind: FailureKind::Memory }
    }
    pub(crate) fn fatal(error:''');p.write_text(s)
p=root/'metal/mod.rs';s=p.read_text();s=s.replace('ok_or(AllocationError::OutOfMemory)?','ok_or_else(|| AllocationFailure::memory(AllocationError::Internal("No MTLHeap could be created with the given size".into())))?');p.write_text(s)
p=root/'vulkan/mod.rs';s=p.read_text()
s=s.replace('    pub(crate) active_general_blocks: usize,','    pub(crate) active_general_blocks: usize,\n    active_blocks: usize,')
s=s.replace('                    active_general_blocks: 0,','                    active_general_blocks: 0,\n                    active_blocks: 0,')
s=s.replace('    device: ash::Device,\n    pub(crate) buffer_image_granularity:', '    device: ash::Device,\n    max_memory_allocation_count: usize,\n    pub(crate) buffer_image_granularity:')
s=s.replace('            buffer_image_granularity: granularity,','            max_memory_allocation_count: physical_device_properties.limits.max_memory_allocation_count as usize,\n            buffer_image_granularity: granularity,')
s=s.replace('            self.active_general_blocks -= 1;\n            block.destroy(device);','            self.active_general_blocks -= 1;\n            self.active_blocks -= 1;\n            block.destroy(device);')
s=s.replace('        new_block_size: Option<u64>,\n    ) -> AllocationResult<Allocation>', '        new_block_size: Option<u64>,\n        allocation_limit_reached: bool,\n    ) -> AllocationResult<Allocation>')
s=s.replace('        let mut block = MemoryBlock::new(', '''        if allocation_limit_reached {
            return Err(AllocationFailure::allocation_limit(AllocationError::Internal(
                "Allocator reached maxMemoryAllocationCount".into(),
            )));
        }
        let mut block = MemoryBlock::new(''',1)
s=s.replace('        if !dedicated {\n            self.active_general_blocks += 1;', '        self.active_blocks += 1;\n        if !dedicated {\n            self.active_general_blocks += 1;',1)
s=s.replace('            block.destroy(device);\n        }\n\n        Ok(())','            self.active_blocks -= 1;\n            block.destroy(device);\n        }\n\n        Ok(())',1)
a=s.index('    fn allocate_type(');b=s.index('    pub fn allocate(',a);part=s[a:b]
part=part.replace('        self.memory_types[index].allocate(', '''        // Other users of this VkDevice remain responsible for their own allocations.
        let limit_reached = self.memory_types.iter().map(|ty|ty.active_blocks).sum::<usize>()
            >= self.max_memory_allocation_count;
        self.memory_types[index].allocate(''')
part=part.replace('            block_size,\n','            block_size,\n            limit_reached,\n');s=s[:a]+part+s[b:];p.write_text(s)
p=root/'vulkan/capacity_tests.rs';s=p.read_text().replace('            active_general_blocks: 0,','            active_general_blocks: 0,\n            active_blocks: 0,').replace('        buffer_image_granularity: 1,','        max_memory_allocation_count: 4096,\n        buffer_image_granularity: 1,')
s+='''
#[test]
fn allocation_count_guard_runs_before_driver_and_reuses_existing_blocks() {
    let flags=vk::MemoryPropertyFlags::DEVICE_LOCAL;
    let mut allocator=fixture(&[(256*MIB,flags)],false);
    growable(&mut allocator,8*MIB,64*MIB);
    allocator.max_memory_allocation_count=1;
    let first=allocator.allocate(&request(MIB,MemoryLocation::GpuOnly)).unwrap();
    let second=allocator.allocate(&request(MIB,MemoryLocation::GpuOnly)).unwrap();
    assert!(allocator.allocate(&request(9*MIB,MemoryLocation::GpuOnly)).is_err());
    assert_eq!(DRIVER.with(|d|d.borrow().calls.len()),1);
    allocator.free(first).unwrap();allocator.free(second).unwrap();
    let larger=allocator.allocate(&request(9*MIB,MemoryLocation::GpuOnly)).unwrap();
    assert_eq!(DRIVER.with(|d|d.borrow().calls.len()),2);
    assert_eq!(allocator.memory_types[0].active_blocks,1);
    allocator.free(larger).unwrap();allocator.trim();
    assert_eq!(allocator.memory_types[0].active_blocks,0);
}
''';p.write_text(s)
print('Guarded owned Vulkan allocation count before native calls')
