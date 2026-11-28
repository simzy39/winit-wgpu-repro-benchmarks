"""Finish targeted correctness and cache-limit experiments, then downstream timings."""
import pathlib,subprocess,time,sys,shutil,json
H=pathlib.Path(__file__).resolve().parent
while not (H/"DIRECT_COMPLETE").exists():
    time.sleep(2)
def run(name,cmd,cwd=H):
    print("Starting",name,flush=True)
    with (H/"logs"/f"{name}.log").open("w",encoding="utf-8") as output:
        p=subprocess.run(cmd,cwd=cwd,stdout=output,stderr=subprocess.STDOUT)
    if p.returncode:
        print((H/"logs"/f"{name}.log").read_text()[-5000:],flush=True)
        raise SystemExit(p.returncode)
    print("Completed",name,flush=True)
run("add-growth-regression",[sys.executable,"add_growth_regression.py"])
run("format-growth-regression",["cargo","fmt","--manifest-path","work/cache2/Cargo.toml","-p","gpu-allocator"])
run("unit-growth-regression",["cargo","test","--offline","--manifest-path","work/cache2/Cargo.toml","-p","gpu-allocator","--no-default-features","--features","std,vulkan,d3d12","--lib","--target-dir",str(H/"target-cache-tests")])
run("clippy-growth-regression",["cargo","clippy","--offline","-p","gpu-allocator","--no-default-features","--features","std,vulkan,d3d12","--all-targets","--target-dir",str(H/"target-validation"),"--","-D","warnings"],cwd=H/"work/cache2/gpu-allocator")
run("metal-nostd-check",["cargo","check","--offline","-p","gpu-allocator","--target","aarch64-apple-darwin","--no-default-features","--features","hashbrown,metal","--lib","--target-dir",str(H/"target-validation")],cwd=H/"work/cache2/gpu-allocator")
if not (H/"patches/manifest-before-growth-test.json").exists():
    shutil.copyfile(H/"patches/manifest.json",H/"patches/manifest-before-growth-test.json")
run("export-complete-patch",[sys.executable,"export_patch.py"])
run("prepare-cachemax",[sys.executable,"prepare_cachemax.py"])
target=(H/"target-cachemax").resolve()
assert target.parent==H.resolve()
shutil.copytree(H/"target-cache-tests/debug",target/"debug",dirs_exist_ok=True)
run("clean-cachemax-test-artifact",["cargo","clean","--manifest-path","work/cachemax/Cargo.toml","--target-dir",str(target),"-p","gpu-allocator"])
run("unit-cachemax",["cargo","test","--offline","--manifest-path","work/cachemax/Cargo.toml","-p","gpu-allocator","--no-default-features","--features","std,vulkan,d3d12","--lib","--target-dir",str(target)])
run("build-cachemax",[sys.executable,"build.py","cachemax"])
run("validate-vma-counters",[sys.executable,"validate_vma_counts.py"])
run("capacity-matrix-final",[sys.executable,"capacity_matrix.py"])
from process_metrics import run_process
probe=run_process([sys.executable,"-c","pass"],timeout=30)
assert probe.returncode==0
(H/"process-cpu-probe.json").write_text(json.dumps(probe.cpu_times,indent=2))
run("cache-limit-and-cpu-suite",[sys.executable,"run_cache_limits.py"])
run("analyze-direct",[sys.executable,"analyze_direct.py"])
run("downstream-timing-suite",[sys.executable,"run_downstream.py"])
(H/"TIMING_PHASE_COMPLETE").write_text("complete")

