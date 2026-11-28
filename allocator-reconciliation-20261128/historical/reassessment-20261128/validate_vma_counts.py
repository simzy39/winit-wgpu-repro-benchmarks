"""Validate native VMA shared/dedicated counters separately; discard timing values."""
import pathlib,subprocess,shutil,os,json,hashlib
H=pathlib.Path(__file__).resolve().parent
assert (H/"DIRECT_COMPLETE").exists(), "Complete the main latency suite before compiling the counter check"
source=(H/"work/vma/src/main.rs").read_text()
source=source.replace("    fn report(&self) -> gpu_allocator::AllocatorReport;",'''    fn report(&self) -> gpu_allocator::AllocatorReport;
    fn is_dedicated(&self, a:&Self::A, delta:u64, steps:&[u64]) -> bool {
        delta==Self::size_of(a) && !steps.contains(&delta)
    }''')
source=source.replace("if delta == size && !steps.contains(&delta) {","if b.is_dedicated(&a,delta,steps) {")
needle="        type A = VmaAllocation;"
source=source.replace(needle,needle+'''
        fn is_dedicated(&self, a:&Self::A, _delta:u64, _steps:&[u64])->bool {
            self.alloc.as_ref().unwrap().get_allocation_info2(&a.handle).dedicated_memory
        }''')
folder=H/"work/vma-counts";(folder/"src").mkdir(parents=True,exist_ok=True)
m=(H/"work/vma/Cargo.toml").read_text().replace('name = "gpua-policy-bench"','name = "gpua-policy-counts"')
(folder/"Cargo.toml").write_text(m)
(folder/"src/main.rs").write_text(source)
shutil.copyfile(H/"work/vma/Cargo.lock",folder/"Cargo.lock")
target=(H/"target-vma-counts").resolve()
assert target.parent==H.resolve()
if not target.exists():shutil.copytree(H/"target-vma",target)
env=os.environ.copy();env["BENCH_VARIANT"]="vma-counts"
p=subprocess.run(["cargo","build","--release","--offline","--target-dir",str(target)],cwd=folder,env=env,capture_output=True,text=True)
(H/"logs/build-vma-counts.log").write_text(p.stdout+p.stderr)
if p.returncode:raise SystemExit(p.stderr)
exe=target/"release/gpua-policy-counts.exe"
p=subprocess.run([str(exe),"vulkan","default","1","vma-native-count-validation"],capture_output=True,text=True)
(H/"vma-native-counts.json").write_text(p.stdout)
(H/"vma-native-counts.receipt.json").write_text(json.dumps({"rc":p.returncode,"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
    "timings_not_comparable":True,"stderr":p.stderr},indent=2))
if p.returncode:raise SystemExit(p.stderr)
print("Validated native VMA counters")

