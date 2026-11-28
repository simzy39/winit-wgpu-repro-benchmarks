import pathlib
H=pathlib.Path(__file__).resolve().parent
s=(H/"bench.rs").read_text()
s=s.replace("    fn report(&self) -> gpu_allocator::AllocatorReport;",'''    fn report(&self) -> gpu_allocator::AllocatorReport;
    fn fragmentation(&self) -> Value { fragmentation(&self.report()) }''')
s=s.replace('fragmentation(&b.report())','b.fragmentation()')
a=s.index("mod vkb {")
b=s.index("// D3D12",a)
v=s[a:b]
v=v.replace("use gpu_allocator::vulkan::*;","use vk_mem::Alloc as _;")
v=v.replace("alloc: Option<Allocator>,","alloc: Option<vk_mem::Allocator>,")
x=v.index("    impl Backend for Vk {")
y=v.index("\n    impl Drop for Vk {",x)
v=v[:x]+'''    pub struct VmaAllocation {
        handle: vk_mem::Allocation,
        size: u64,
        memory_type: u32,
    }
    impl Backend for Vk {
        type A = VmaAllocation;
        fn reset(&mut self, sizes: Option<AllocationSizes>) {
            self.alloc=None;
            if sizes.is_some() {
                let mut info=vk_mem::AllocatorCreateInfo::new(&self.instance, &self.device, self.pd);
                info.vulkan_api_version=vk::API_VERSION_1_2;
                info.flags=vk_mem::AllocatorCreateFlags::EXTERNALLY_SYNCHRONIZED;
                if self.has_budget { info.flags |= vk_mem::AllocatorCreateFlags::EXT_MEMORY_BUDGET; }
                self.alloc=Some(unsafe { vk_mem::Allocator::new(info) }.unwrap());
            }
        }
        fn prepare(&mut self, _loc: Loc, res: Res) { let _=self.requirements(res); }
        fn alloc(&mut self, loc: Loc, res: Res) -> Self::A {
            let requirements=self.reqs[&res];
            let mp=unsafe {self.instance.get_physical_device_memory_properties(self.pd)};
            let flags=match loc {
                Loc::GpuOnly=>vk::MemoryPropertyFlags::DEVICE_LOCAL,
                Loc::CpuToGpu=>vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT | vk::MemoryPropertyFlags::DEVICE_LOCAL,
                Loc::GpuToCpu=>vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT | vk::MemoryPropertyFlags::HOST_CACHED,
            };
            let memory_type=mp.memory_types_as_slice().iter().enumerate()
                .find(|(i,t)| requirements.memory_type_bits & (1<<i) != 0 && t.property_flags.contains(flags)).unwrap().0 as u32;
            let info=vk_mem::AllocationCreateInfo {
                memory_type_bits:1<<memory_type,
                flags:if loc==Loc::GpuOnly {vk_mem::AllocationCreateFlags::empty()} else {vk_mem::AllocationCreateFlags::MAPPED},
                ..Default::default()
            };
            let allocator=self.alloc.as_ref().unwrap();
            let handle=unsafe {allocator.allocate_memory(&requirements,&info)}.unwrap();
            Self::A {handle,size:requirements.size,memory_type}
        }
        fn size_of(a: &Self::A) -> u64 {a.size}
        fn memtype_of(&self,a:&Self::A)->String {
            let mp=unsafe {self.instance.get_physical_device_memory_properties(self.pd)};
            format!("{:?}",mp.memory_types[a.memory_type as usize].property_flags)
        }
        fn free(&mut self,mut a:Self::A) {unsafe {self.alloc.as_ref().unwrap().free_memory(&mut a.handle)};}
        fn report(&self)->gpu_allocator::AllocatorReport {panic!("VMA uses its native detailed statistics")}
        fn fragmentation(&self)->Value {
            let st=self.alloc.as_ref().unwrap().calculate_statistics().unwrap().total;
            let unused=st.statistics.blockBytes-st.statistics.allocationBytes;
            json!({"unused_bytes":unused,"largest_gap_bytes":st.unusedRangeSizeMax,
                "external_fragmentation":if unused>0 {1.0-st.unusedRangeSizeMax as f64/unused as f64} else {0.0}})
        }
        fn capacity(&self)->u64 { self.alloc.as_ref().unwrap().calculate_statistics().unwrap().total.statistics.blockBytes }
        fn driver_usage(&self)->u64 {
            if !self.has_budget {return 0}
            let mut budget=vk::PhysicalDeviceMemoryBudgetPropertiesEXT::default();
            let mut mp2=vk::PhysicalDeviceMemoryProperties2::default().push_next(&mut budget);
            unsafe {self.instance.get_physical_device_memory_properties2(self.pd,&mut mp2)};
            let n=mp2.memory_properties.memory_heap_count as usize;
            budget.heap_usage[..n].iter().sum()
        }
        fn info(&self)->Value {json!({"adapter":self.name,"memory_budget_ext":self.has_budget,"allocator":"VMA via vk-mem 0.5.0; native defaults; same forced memory type; externally synchronized"})}
    }
''' +v[y:]
s=s[:a]+v+s[b:]
(H/"work/vma/src/main.rs").write_text(s)
print("Wrote actual VMA reference adapter")

