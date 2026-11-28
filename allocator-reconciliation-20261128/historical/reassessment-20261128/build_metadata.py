"""Separate Rust metadata accounting. Timings from these binaries are deliberately excluded."""
import pathlib,subprocess,shutil,os,json,hashlib
H=pathlib.Path(__file__).resolve().parent
instrumentation='''
use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
static META_TRACK: AtomicBool=AtomicBool::new(false);
static META_CURRENT: AtomicI64=AtomicI64::new(0);
static META_PEAK: AtomicI64=AtomicI64::new(0);
struct Counted;
#[global_allocator]
static SYSTEM_ALLOCATOR: Counted=Counted;
unsafe impl std::alloc::GlobalAlloc for Counted {
    unsafe fn alloc(&self, layout:std::alloc::Layout)->*mut u8 {
        let p=unsafe {std::alloc::GlobalAlloc::alloc(&std::alloc::System,layout)};
        if !p.is_null() && META_TRACK.load(Ordering::Relaxed) {
            let n=META_CURRENT.fetch_add(layout.size() as i64,Ordering::Relaxed)+layout.size() as i64;
            META_PEAK.fetch_max(n,Ordering::Relaxed);
        }
        p
    }
    unsafe fn dealloc(&self,p:*mut u8,layout:std::alloc::Layout) {
        if META_TRACK.load(Ordering::Relaxed) {META_CURRENT.fetch_sub(layout.size() as i64,Ordering::Relaxed);}
        unsafe {std::alloc::GlobalAlloc::dealloc(&std::alloc::System,p,layout)}
    }
    unsafe fn realloc(&self,p:*mut u8,layout:std::alloc::Layout,new_size:usize)->*mut u8 {
        let q=unsafe {std::alloc::GlobalAlloc::realloc(&std::alloc::System,p,layout,new_size)};
        if !q.is_null() && META_TRACK.load(Ordering::Relaxed) {
            let delta=new_size as i64-layout.size() as i64;
            let n=META_CURRENT.fetch_add(delta,Ordering::Relaxed)+delta;
            META_PEAK.fetch_max(n,Ordering::Relaxed);
        }
        q
    }
}
'''
source=(H/"bench.rs").read_text()
at=source.index("use std::collections")
source=source[:at]+instrumentation+"\n"+source[at:]
source=source.replace("    b.reset(Some(sizes));",'''    META_CURRENT.store(0,Ordering::Relaxed);
    META_PEAK.store(0,Ordering::Relaxed);
    META_TRACK.store(true,Ordering::Relaxed);
    b.reset(Some(sizes));
    META_TRACK.store(false,Ordering::Relaxed);''')
source=source.replace("                let a = b.alloc(loc, res);",'''                META_TRACK.store(true,Ordering::Relaxed);
                let a = b.alloc(loc, res);
                META_TRACK.store(false,Ordering::Relaxed);''')
source=source.replace("        b.free(a);",'''        META_TRACK.store(true,Ordering::Relaxed);
        b.free(a);
        META_TRACK.store(false,Ordering::Relaxed);''')
source=source.replace('    let out = json!({','    let mut out = json!({')
source=source.replace('    b.reset(None);\n    out','''    out["metadata_peak_rust_bytes"]=json!(META_PEAK.load(Ordering::Relaxed));
    out["metadata_retained_rust_bytes"]=json!(META_CURRENT.load(Ordering::Relaxed));
    META_TRACK.store(true,Ordering::Relaxed);
    b.reset(None);
    META_TRACK.store(false,Ordering::Relaxed);
    out["metadata_after_allocator_drop_bytes"]=json!(META_CURRENT.load(Ordering::Relaxed));
    out["timings_not_comparable"]=json!(true);
    out''')
for name in ["main","pr323","cache2"]:
    folder=H/"metadata"/name
    (folder/"src").mkdir(parents=True,exist_ok=True)
    m=(H/"work"/name/"bench/Cargo.toml").read_text()
    m=m.replace('name = "gpua-policy-bench"','name = "gpua-policy-meta"')
    m=m.replace('path = "../gpu-allocator"', 'path = "'+str(H/"work"/name/"gpu-allocator").replace("\\","/")+'"')
    m+="\n[workspace]\n"
    (folder/"Cargo.toml").write_text(m)
    (folder/"src/main.rs").write_text(source)
    target=(H/("target-meta-"+name)).resolve()
    assert target.parent==H.resolve()
    if not target.exists():
        shutil.copytree(H/("target-"+name),target)
    subprocess.run(["cargo","clean","--target-dir",str(target),"-p","gpu-allocator"],cwd=folder,check=True,capture_output=True)
    env=os.environ.copy()
    env["BENCH_VARIANT"]="metadata-"+name
    p=subprocess.run(["cargo","build","--release","--offline","--target-dir",str(target)],cwd=folder,env=env,capture_output=True,text=True)
    (H/"logs"/f"build-meta-{name}.log").write_text(p.stdout+p.stderr)
    if p.returncode:raise SystemExit(p.stderr)
    dest=H/"bin-metadata"
    dest.mkdir(exist_ok=True)
    exe=dest/f"{name}.exe"
    shutil.copyfile(target/"release/gpua-policy-meta.exe",exe)
    (dest/f"{name}.json").write_text(json.dumps({"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),"timings_not_comparable":True,
        "scope":"Rust allocation bytes during allocator construction, allocate, free and destruction; GPU heaps and driver/C++ metadata are excluded."},indent=2))
    print("built metadata",name,flush=True)

