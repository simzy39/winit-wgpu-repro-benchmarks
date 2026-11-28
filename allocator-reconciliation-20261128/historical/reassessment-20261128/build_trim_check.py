import pathlib,shutil,subprocess,os
H=pathlib.Path(__file__).resolve().parent
source=(H/"bench.rs").read_text().replace("fn main() {","fn unused_benchmark_main() {")
source=source.replace("    fn reset(&mut self, sizes: Option<AllocationSizes>);","""    fn reset(&mut self, sizes: Option<AllocationSizes>);
    fn trim(&mut self) -> u64;
    fn check_anchor(&self, _a: &Self::A, _initialize: bool) {}""")
source=source.replace("        type A = Allocation;","""        type A = Allocation;
        fn trim(&mut self) -> u64 { self.alloc.as_mut().unwrap().trim() }""")
at=source.index("    impl Backend for Vk {")
a=source.index("        fn reset",at)
source=source[:a]+'''        fn check_anchor(&self, a: &Self::A, initialize: bool) {
            let ptr=a.mapped_ptr().unwrap().as_ptr() as *mut u8;
            unsafe {
                if initialize {ptr.write(0xA7);}
                assert_eq!(ptr.read(),0xA7);
            }
        }
'''+source[a:]
source+='''
fn verify_trim<B: Backend>(mut b: B, backend:&str)->Value {
    let sizes=config("memory_usage").0;
    b.reset(Some(sizes));
    b.prepare(Loc::CpuToGpu,Res::Buffer(64*KIB));
    b.prepare(Loc::CpuToGpu,Res::Buffer(2304*KIB));
    let anchor=b.alloc(Loc::CpuToGpu,Res::Buffer(64*KIB));
    b.check_anchor(&anchor,true);
    let mut burst=Vec::new();
    for _ in 0..8 {burst.push(b.alloc(Loc::CpuToGpu,Res::Buffer(2304*KIB)));}
    for allocation in burst {b.free(allocation);}
    let before=b.capacity();
    let released=b.trim();
    let after=b.capacity();
    assert_eq!(before-after,released);
    assert!(released>0);
    assert_eq!(b.report().total_allocated_bytes,B::size_of(&anchor));
    b.check_anchor(&anchor,false);
    b.free(anchor);
    let final_released=b.trim();
    assert_eq!(b.capacity(),0);
    assert_eq!(b.trim(),0);
    let again=b.alloc(Loc::CpuToGpu,Res::Buffer(64*KIB));
    b.check_anchor(&again,true);
    b.free(again);
    assert!(b.trim()>0);
    let out=json!({"backend":backend,"before_bytes":before,"released_bytes":released,
                  "after_bytes":after,"final_released_bytes":final_released,"capacity_after_trim":b.capacity(),
                  "live_allocation_preserved":true,"vulkan_mapped_contents_preserved":backend=="vulkan"});
    b.reset(None);
    out
}
fn main() {
    println!("{}",json!({"checks":[verify_trim(vkb::Vk::new(),"vulkan"),verify_trim(dxb::Dx::new(),"d3d12")]}));
}
'''
folder=H/"trim-check"
(folder/"src").mkdir(parents=True,exist_ok=True)
m=(H/"work/cache2/bench/Cargo.toml").read_text().replace('name = "gpua-policy-bench"','name = "gpua-trim-check"')
m=m.replace('path = "../gpu-allocator"', 'path = "'+str(H/"work/cache2/gpu-allocator").replace("\\","/")+'"')
m+="\n[workspace]\n"
(folder/"Cargo.toml").write_text(m)
(folder/"src/main.rs").write_text(source)
env=os.environ.copy();env["BENCH_VARIANT"]="trim-check"
p=subprocess.run(["cargo","build","--release","--offline","--target-dir",str(H/"target-cache2")],cwd=folder,env=env,capture_output=True,text=True)
(H/"logs/build-trim-check.log").write_text(p.stdout+p.stderr)
if p.returncode:raise SystemExit(p.stderr)
print("Built hardware trim check")

