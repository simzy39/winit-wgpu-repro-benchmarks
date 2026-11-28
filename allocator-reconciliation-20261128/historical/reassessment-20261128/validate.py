"""Relevant production checks for the cache candidate, with individual logs and exit codes."""
import pathlib,subprocess,json,os,time
H=pathlib.Path(__file__).resolve().parent
R=H/"work/cache2/gpu-allocator"
target=str(H/"target-validation")
checks=[
("fmt",["cargo","fmt","-p","gpu-allocator","--","--check"]),
("unit-std",["cargo","test","--offline","-p","gpu-allocator","--no-default-features","--features","std,vulkan,d3d12","--lib","--target-dir",target]),
("doc-tests",["cargo","test","--offline","-p","gpu-allocator","--no-default-features","--features","std,vulkan,d3d12","--doc","--target-dir",target]),
("clippy-std",["cargo","clippy","--offline","-p","gpu-allocator","--no-default-features","--features","std,vulkan,d3d12","--all-targets","--target-dir",target,"--","-D","warnings"]),
("clippy-nostd",["cargo","clippy","--offline","-p","gpu-allocator","--no-default-features","--features","hashbrown,vulkan,d3d12","--lib","--target-dir",target,"--","-D","warnings"]),
("clippy-visualizer",["cargo","clippy","--offline","-p","gpu-allocator","--no-default-features","--features","std,vulkan,d3d12,visualizer","--all-targets","--target-dir",target,"--","-D","warnings"]),
("rustdoc",["cargo","doc","--offline","-p","gpu-allocator","--no-deps","--no-default-features","--features","std,vulkan,d3d12","--document-private-items","--target-dir",target]),
("metal-arm",["cargo","clippy","--offline","-p","gpu-allocator","--target","aarch64-apple-darwin","--no-default-features","--features","std,metal","--lib","--target-dir",target,"--","-D","warnings"]),
("metal-intel",["cargo","check","--offline","-p","gpu-allocator","--target","x86_64-apple-darwin","--no-default-features","--features","std,metal","--lib","--target-dir",target]),
("linux-nostd",["cargo","check","--offline","-p","gpu-allocator","--target","x86_64-unknown-linux-gnu","--no-default-features","--features","hashbrown,vulkan","--lib","--target-dir",target]),
("example-vulkan",["cargo","run","--offline","-p","gpu-allocator","--example","vulkan-buffer","--no-default-features","--features","std,vulkan","--target-dir",target]),
("example-d3d12",["cargo","run","--offline","-p","gpu-allocator","--example","d3d12-buffer-winrs","--no-default-features","--features","std,d3d12","--target-dir",target])]
results=[]
env=os.environ.copy();env["RUSTDOCFLAGS"]="-D warnings"
for name,cmd in checks:
    start=time.perf_counter()
    p=subprocess.run(cmd,cwd=R,env=env,capture_output=True,text=True)
    (H/"logs"/f"validation-{name}.log").write_text(p.stdout+p.stderr,encoding="utf-8")
    results.append({"name":name,"command":cmd,"rc":p.returncode,"wall_s":time.perf_counter()-start})
    (H/"validation.json").write_text(json.dumps(results,indent=2))
    print(name,p.returncode,flush=True)
    if p.returncode:print(p.stderr[-4500:],flush=True)
(H/"VALIDATION_COMPLETE").write_text("complete")

