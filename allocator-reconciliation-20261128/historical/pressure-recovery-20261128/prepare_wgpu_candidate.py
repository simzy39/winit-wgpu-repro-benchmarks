"""Preserve earlier wgpu changes, and isolate new downstream alternatives."""
import pathlib,subprocess,shutil
H=pathlib.Path(__file__).resolve().parent;P=H.parent/'reassessment-20261128'
source=P/'downstream/trees/both'
patch=subprocess.check_output(['git','-C',str(source),'diff','--binary'])
(H/'sources/wgpu-prior-both.patch').write_bytes(patch)
for name in ['candidate','singlepool']:
    repo=H/'wgpu'/name
    assert not repo.exists()
    subprocess.run(['git','-C',str(H/'wgpu/upstream'),'worktree','add','--detach',str(repo),'60cef2be828e03ba54e2e1598001b4625c0c2163'],check=True)
    subprocess.run(['git','-C',str(repo),'apply',str(H/'sources/wgpu-prior-both.patch')],check=True)
    p=repo/'wgpu-hal/src/dx12/suballocation.rs';s=p.read_text()
    if name=='singlepool':
        s=s.replace('if flags.contains(crate::MemoryFlags::TRANSIENT) {','if false && flags.contains(crate::MemoryFlags::TRANSIENT) {')
        p.write_text(s);continue
    a=s.index('    fn sizes(&self, pool: MemoryPool)')
    s=s[:a]+'''    fn trim(&self) -> u64 {
        let general = self.inner.general.lock().trim();
        let transient = self.inner.transient.lock().trim();
        general + transient
    }

    fn allocate(
        &self,
        pool: MemoryPool,
        desc: &AllocationCreateDesc<'_>,
    ) -> Result<gpu_allocator::d3d12::Allocation, gpu_allocator::AllocationError> {
        let result = self.allocator(pool).lock().allocate(desc);
        if !matches!(&result, Err(gpu_allocator::AllocationError::OutOfMemory)) {
            return result;
        }
        let other = match pool {
            MemoryPool::General => MemoryPool::Transient,
            MemoryPool::Transient => MemoryPool::General,
        };
        if self.allocator(other).lock().trim() == 0 {
            return result;
        }
        self.allocator(pool).lock().allocate(desc)
    }

    fn finish_placed_resource(
        &self,
        pool: MemoryPool,
        allocation: gpu_allocator::d3d12::Allocation,
        resource: Option<Direct3D12::ID3D12Resource>,
        result: Result<(), crate::DeviceError>,
        ty: AllocationType,
    ) -> Result<(Direct3D12::ID3D12Resource, Allocation), crate::DeviceError> {
        match result.and_then(|()| resource.as_ref().ok_or(crate::DeviceError::Unexpected).map(|_| ())) {
            Ok(()) => Ok((resource.unwrap(), Allocation::placed(pool, allocation, ty))),
            Err(error) => {
                drop(resource);
                self.allocator(pool).lock().free(allocation)?;
                Err(error)
            }
        }
    }

'''+s[a:]
    s=s.replace('        let mut allocator = self.mem_allocator.allocator(pool).lock();\n\n','')
    s=s.replace('        let allocation = allocator.allocate(&allocation_desc)?;','        let allocation = self.mem_allocator.allocate(pool, &allocation_desc)?;')
    for label,ty in [('buffer','Buffer'),('texture','Texture'),('acceleration structure','AccelerationStructure')]:
        start=s.index('        let allocation = self.mem_allocator.allocate(pool, &allocation_desc)?;',s.index('    fn create_placed_'+label.replace(' ','_')+'('))
        a=s.index('        unsafe {',start);b=s.index('\n    }',a)
        body=s[a:b]
        body=body[:body.index('.into_device_result(')]+'.into_device_result("Placed '+label+' creation");\n\n        self.mem_allocator.finish_placed_resource(pool, allocation, resource, result, AllocationType::'+ty+')'
        body=body.replace('        unsafe {','        let result = unsafe {',1)
        s=s[:a]+body+s[b:]
    # Before the approximate existing budget policy refuses a request, reclaim both caches
    # and requery actual process usage. This deliberately does not invent an allocation planner.
    a=s.index('        let info = self',s.index('    fn error_if_would_oom_on_resource_allocation('))
    s=s[:a]+s[a:].replace('        let info = self','        let mut info = self',1)
    a=s.index('        if info\n',a);b=s.index('\n        Ok(allocation_info)',a)
    s=s[:a]+'''        let exceeds_budget = |info: &Dxgi::DXGI_QUERY_VIDEO_MEMORY_INFO| {
            info.CurrentUsage.checked_add(allocation_info.SizeInBytes.max(memblock_size))
                .is_none_or(|usage| usage >= info.Budget / 100 * threshold as u64)
        };
        if exceeds_budget(&info) {
            self.mem_allocator.trim();
            info = self.shared.adapter.query_video_memory_info(memory_segment_group)?;
            if exceeds_budget(&info) { return Err(crate::DeviceError::OutOfMemory); }
        }
'''+s[b:]
    # Naming happens before counters are charged. Roll back resource and allocation together.
    old='''        if let Some(label) = desc.label {
            resource.set_name(label)?;
        }'''
    new='''        if let Some(label) = desc.label {
            if let Err(error) = resource.set_name(label) {
                drop(resource);
                if let AllocationInner::Placed { pool, inner } = allocation.inner {
                    self.mem_allocator.allocator(pool).lock().free(inner)?;
                }
                return Err(error);
            }
        }'''
    assert s.count(old)==3;s=s.replace(old,new)
    p.write_text(s)
    subprocess.run(['cargo','fmt','--manifest-path',str(repo/'Cargo.toml'),'-p','wgpu-hal'],check=True)
print('Prepared independent-lock recovery and single-pool downstream alternatives')
