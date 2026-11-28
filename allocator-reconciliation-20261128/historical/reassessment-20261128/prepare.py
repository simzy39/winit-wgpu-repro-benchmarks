"""Prepare isolated, detached worktrees and a common benchmark. Never edits historical files."""
import pathlib, subprocess, shutil, json, hashlib
HERE=pathlib.Path(__file__).resolve().parent
OLD=HERE.parent
PR="179ea43f05332c2809addd7922cd056220efc36b"
def run(*args,cwd=None):
    subprocess.run(args,cwd=cwd,check=True)
def replace(s,old,new):
    assert old in s, old[:120]
    return s.replace(old,new)
VARIANTS=["main","pr323","proposal","retain2","demand2","request","vma-policy"]
for name in VARIANTS:
    folder=HERE/"work"/name
    repo=folder/"gpu-allocator"
    folder.mkdir(parents=True,exist_ok=True)
    if repo.exists():
        print(f"Preserving existing {name}")
        continue
    if not repo.exists():
        run("git","-C",str(OLD/"repo"),"worktree","add","--detach",str(repo),
            "fc22df05140b15ed6d764beabd12a1b807011bc5" if name=="main" else PR)
        if name not in {"main","pr323"}:
            run("git","apply",str(OLD/"patches/proposal-on-pr323-179ea43.patch"),cwd=repo)
    if name not in {"main","pr323","proposal"}:
        p=repo/"src/lib.rs"
        s=p.read_text()
        s=replace(s,"active_general_blocks > 1 || block_size > self.min",
                  "active_general_blocks > 1 || block_size > self.min.saturating_mul(2).min(self.max)"
                  if name!="vma-policy" else "active_general_blocks > 1")
        insert='''    /// Hardware capacity is a hard limit, including on heaps smaller than 4 MiB.
    pub(crate) fn capped_to_heap(self, capacity: u64) -> Self {
        Self { min: self.min.min(capacity), max: self.max.min(capacity) }
    }

'''
        s=replace(s,"    /// Allocations larger than this are placed in a dedicated block.",insert+"    /// Allocations larger than this are placed in a dedicated block.")
        start=s.index("        let mut block_size = self.step_size(active_general_blocks);")
        end=s.index("\n    }",start)
        if name=="demand2":
            s=s[:start]+'''        const QUANTUM: u64 = 4 * 1024 * 1024;
        let demand = allocation_size.saturating_mul(2).saturating_add(QUANTUM - 1)
            / QUANTUM * QUANTUM;
        self.step_size(active_general_blocks)
            .max(allocation_size.saturating_add(QUANTUM - 1) / QUANTUM * QUANTUM)
            .min(demand.max(self.min))
            .min(self.max)'''+s[end:]
        elif name=="request":
            s=s[:start]+'''        const QUANTUM: u64 = 4 * 1024 * 1024;
        let rounded = allocation_size.saturating_add(QUANTUM - 1) / QUANTUM * QUANTUM;
        let _ = active_general_blocks;
        self.min.max(rounded).min(self.max)'''+s[end:]
        elif name=="vma-policy":
            s=s[:start]+'''        let shift = 3usize.saturating_sub(active_general_blocks);
        (self.max >> shift).max(self.min).max(allocation_size).min(self.max)'''+s[end:]
            s=replace(s,"        self.max\n    }\n\n    /// Size of a new shared block","        self.max / 2\n    }\n\n    /// Size of a new shared block")
        p.write_text(s)
        p=repo/"src/d3d12/mod.rs"
        s=p.read_text()
        a=s.index("    if heap_properties.Type == D3D12_HEAP_TYPE_DEFAULT {")
        b=s.index("\n}\n",a)
        s=s[:a]+'''    match heap_properties.Type {
        D3D12_HEAP_TYPE_UPLOAD | D3D12_HEAP_TYPE_READBACK | D3D12_HEAP_TYPE_GPU_UPLOAD => true,
        D3D12_HEAP_TYPE_CUSTOM => matches!(
            heap_properties.CPUPageProperty,
            D3D12_CPU_PAGE_PROPERTY_WRITE_COMBINE | D3D12_CPU_PAGE_PROPERTY_WRITE_BACK
        ),
        _ => false,
    }'''+s[b:]
        s=s.replace("D3D12_HEAP_TYPE(5)","D3D12_HEAP_TYPE_GPU_UPLOAD")
        p.write_text(s)
        p=repo/"src/vulkan/mod.rs"
        s=p.read_text()
        a=s.index("/// Whether the shared blocks of a memory type")
        b=s.index("#[derive(Copy",a)
        s=s[:a]+s[b:]
        s=replace(s,"    pub(crate) heap_index: usize,","    pub(crate) heap_index: usize,\n    pub(crate) heap_size: u64,")
        s=s.replace("        let alignment = desc.requirements.alignment;","        let alignment = desc.requirements.alignment;\n        if size > self.heap_size {\n            return Err(AllocationError::OutOfMemory);\n        }",1)
        s=replace(s,"            .map(|(i, mem_type)| MemoryType {","            .map(|(i, mem_type)| {\n                let mappable = mem_type.property_flags.contains(vk::MemoryPropertyFlags::HOST_VISIBLE);\n                let heap_size = memory_heaps[mem_type.heap_index as usize].size;\n                MemoryType {")
        s=replace(s,"                heap_index: mem_type.heap_index as usize,","                heap_index: mem_type.heap_index as usize,\n                heap_size,")
        s=replace(s,"                mappable: mem_type\n                    .property_flags\n                    .contains(vk::MemoryPropertyFlags::HOST_VISIBLE),","                mappable,")
        s=replace(s,".block_sizes_for(uses_host_block_sizes(mem_type.property_flags)),",".block_sizes_for(mappable)\n                    .capped_to_heap(heap_size),")
        s=replace(s,"                buffer_device_address: desc.buffer_device_address,\n            })","                buffer_device_address: desc.buffer_device_address,\n            }})")
        p.write_text(s)
    (folder/"Cargo.toml").write_text('[workspace]\nmembers = ["gpu-allocator", "bench"]\nresolver = "2"\n')
    bench=folder/"bench"
    (bench/"src").mkdir(parents=True,exist_ok=True)
    manifest=(OLD/"bench/Cargo.toml").read_text()
    manifest=manifest.replace("../ws/pr323/gpu-allocator","../gpu-allocator")
    (bench/"Cargo.toml").write_text(manifest)
    source=(HERE/"bench.rs").read_text()
    (bench/"src/main.rs").write_text(source)
    # Pin the same versions as the original harness for all variants.
    shutil.copyfile(OLD/"Cargo.lock",folder/"Cargo.lock")
print(json.dumps({"variants":VARIANTS,"root":str(HERE/"work")}))

