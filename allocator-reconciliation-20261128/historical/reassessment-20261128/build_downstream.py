"""Build wgpu combinations. Explicitly invalidate every crate that differs between source trees."""
import pathlib,subprocess,json,hashlib,shutil,sys
H=pathlib.Path(__file__).resolve().parent
names=sys.argv[1:] or ["pr323-trunk","retain2-trunk","demand2-trunk","pr323-lazy","pr323-transient","pr323-both","retain2-lazy","retain2-transient","retain2-both","demand2-both"]
target=H/"target-wgpu"
out=H/"bin-wgpu"
out.mkdir(exist_ok=True)
for name in names:
    folder=H/"downstream/bench"/name
    clean=["cargo","clean","--target-dir",str(target)]
    for package in ["gpu-allocator","wgpu-hal","wgpu-core","wgpu","wgpu-mem-bench"]:
        clean.extend(["-p",package])
    p=subprocess.run(clean,cwd=folder,capture_output=True,text=True)
    (H/"logs"/f"clean-wgpu-{name}.log").write_text(p.stdout+p.stderr)
    if p.returncode: raise SystemExit(p.stderr)
    cmd=["cargo","build","--release","--locked","--target-dir",str(target)]
    p=subprocess.run(cmd,cwd=folder,capture_output=True,text=True)
    (H/"logs"/f"build-wgpu-{name}.log").write_text(p.stdout+p.stderr,encoding="utf-8")
    if p.returncode:
        print(p.stderr[-4500:],flush=True)
        raise SystemExit(p.returncode)
    exe=out/f"{name}.exe"
    shutil.copyfile(target/"release/wgpu-mem-bench.exe",exe)
    allocator,state=name.split("-",1)
    diffs={}
    for label,repo in [("wgpu",H/"downstream/trees"/state),("allocator",H/"work"/allocator/"gpu-allocator")]:
        diff=subprocess.check_output(["git","-C",str(repo),"diff","--binary"])
        diffs[label]=hashlib.sha256(diff).hexdigest()
    (out/f"{name}.json").write_text(json.dumps({"command":cmd,"clean":clean,"diffs":diffs,
        "exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
        "lock_sha256":hashlib.sha256((folder/"Cargo.lock").read_bytes()).hexdigest()},indent=2))
    print("built wgpu",name,flush=True)

