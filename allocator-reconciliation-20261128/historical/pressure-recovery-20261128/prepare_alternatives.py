"""Keep complete, separate implementations of cache-policy alternatives."""
import pathlib,subprocess,shutil
H=pathlib.Path(__file__).resolve().parent
for name in ['smallcache','heapcap','packed']:
    folder=H/'work'/name;repo=folder/'gpu-allocator'
    folder.mkdir(parents=True,exist_ok=True)
    if not repo.exists(): subprocess.run(['git','-C',str(H.parent/'repo'),'worktree','add','--detach',str(repo),'179ea43f05332c2809addd7922cd056220efc36b'],check=True)
    shutil.copytree(H/'work/recovery/gpu-allocator/src',repo/'src',dirs_exist_ok=True)
    for path in ['Cargo.toml','Cargo.lock']:
        shutil.copyfile(H/'work/recovery'/path,folder/path)
    shutil.copytree(H/'work/recovery/bench',folder/'bench',dirs_exist_ok=True)
    if name=='smallcache':
        p=repo/'src/lib.rs';s=p.read_text().replace('cached_size.map_or(true, |cached| size > cached)','cached_size.map_or(true, |cached| size < cached)');p.write_text(s)
    elif name=='packed':
        for backend in ['vulkan','d3d12','metal']:
            p=repo/'src'/backend/'mod.rs';s=p.read_text()
            old='''            for (index, slot) in self.memory_blocks.iter_mut().enumerate().rev() {'''
            new='''            let cached = self.empty_block_index;
            for index in (0..self.memory_blocks.len()).rev().filter(|index| Some(*index) != cached).chain(cached) {
                let slot = &mut self.memory_blocks[index];'''
            assert old in s,backend;s=s.replace(old,new,1);p.write_text(s)
    else:
        for backend in ['vulkan','d3d12']:
            p=repo/'src'/backend/'mod.rs';s=p.read_text()
            a=s.index('    pub fn free(&mut self, allocation: Allocation)');b=s.index('        Ok(())',a)
            if backend=='vulkan':
                code='''
        // Experimental bound: one largest per-type cache allowance per physical heap.
        for heap in 0..self.memory_heaps.len() {
            let bound = self.memory_types.iter().filter(|ty|ty.heap_index==heap)
                .map(|ty|ty.block_sizes.min.saturating_mul(2).min(ty.block_sizes.max)).max().unwrap_or(0);
            loop {
                let cached: u64 = self.memory_types.iter().filter(|ty|ty.heap_index==heap).map(MemoryType::cached_size).sum();
                if cached<=bound {break;}
                let index=self.memory_types.iter().enumerate().filter(|(_,ty)|ty.heap_index==heap)
                    .max_by_key(|(_,ty)|ty.cached_size()).map(|(i,_)|i).unwrap();
                self.memory_types[index].release_cached(&self.device);
            }
        }
'''
            else:
                code='''
        // Experimental D3D12 analogue: bound each explicit L0/L1 memory pool separately.
        for pool in [D3D12_MEMORY_POOL_L0,D3D12_MEMORY_POOL_L1] {
            let bound = self.memory_types.iter().filter(|ty|ty.heap_properties.MemoryPoolPreference==pool)
                .map(|ty|ty.block_sizes.min.saturating_mul(2).min(ty.block_sizes.max)).max().unwrap_or(0);
            loop {
                let cached: u64=self.memory_types.iter().filter(|ty|ty.heap_properties.MemoryPoolPreference==pool).map(MemoryType::cached_size).sum();
                if cached<=bound {break;}
                let index=self.memory_types.iter().enumerate().filter(|(_,ty)|ty.heap_properties.MemoryPoolPreference==pool)
                    .max_by_key(|(_,ty)|ty.cached_size()).map(|(i,_)|i).unwrap();
                self.memory_types[index].release_cached();
            }
        }
'''
            s=s[:b]+code+s[b:];p.write_text(s)
    subprocess.run(['cargo','fmt','--manifest-path',str(folder/'Cargo.toml'),'-p','gpu-allocator'],check=True)
print('Created smallest-cache selection and aggregate-heap-bound alternatives')
