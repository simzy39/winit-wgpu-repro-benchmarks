"""Run the known failure set on exact upstream wgpu, with none of our patches."""
import pathlib,subprocess,os,json,shutil,time,ctypes,hashlib
H=pathlib.Path(__file__).resolve().parent;P=H.parent/"reassessment-20261128";R=H/"wgpu/upstream"
assert (H/"BOOTSTRAP_COMPLETE").exists()
assert not subprocess.check_output(["git","-C",str(R),"status","--porcelain"],text=True).strip()
env=os.environ.copy();env["PATH"]=str(H/"tools")+";"+r"<drive>/VulkanSDK\1.4.363.0\Bin"+";"+env["PATH"]
env["LIB"]=str(H/"tools/atl")+";"+env.get("LIB","")
env.update(WGPU_BACKEND="dx12,vulkan",NEXTEST_TEST_THREADS="2",CARGO_BUILD_JOBS="2")
target=R/"target";(target/"debug/deps").mkdir(parents=True,exist_ok=True)
shutil.copytree(P/"downstream/validation/target/agility-sdk",target/"agility-sdk",dirs_exist_ok=True)
for parent in ["debug","debug/deps"]:
    shutil.copyfile(P/"downstream/validation/target/debug/deps/d3d10warp.dll",target/parent/"d3d10warp.dll")
shutil.copyfile(P/"downstream/validation/target/debug/warp.txt",target/"debug/warp.txt")
failure_filter=json.loads((P/"wgpu-failure-controls/failures.json").read_text())["filter"]
original_lock=hashlib.sha256((R/"Cargo.lock").read_bytes()).hexdigest()
kernel=ctypes.windll.kernel32;assert kernel.SetThreadExecutionState(0x80000001)
start=time.perf_counter()
try:
    fetch=["cargo","fetch","--locked"]
    with (H/"logs/upstream-fetch.log").open("w") as log:p=subprocess.run(fetch,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
    assert p.returncode==0,"Inspect upstream-fetch.log"
    env["CARGO_NET_OFFLINE"]="true"
    command=["cargo","xtask","test","-E",failure_filter]
    with (H/"logs/upstream-failure-control.log").open("w") as log:p=subprocess.run(command,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
    result={"command":command,"rc":p.returncode,"wall_s":time.perf_counter()-start,
        "head":subprocess.check_output(["git","-C",str(R),"rev-parse","HEAD"],text=True).strip(),
        "source_status":subprocess.check_output(["git","-C",str(R),"status","--porcelain"],text=True),
        "lock_sha256_before":original_lock,"lock_sha256_after":hashlib.sha256((R/"Cargo.lock").read_bytes()).hexdigest(),
        "allocator":"Unmodified registry dependency from upstream Cargo.lock; no path override", "wgpu_patches":[]}
    (H/"upstream-failure-control.json").write_text(json.dumps(result,indent=2))
    for source,name in [(target/"nextest/default/junit.xml","upstream-failure-junit.xml"),(R/".gpuconfig","upstream-gpuconfig.json")]:
        if source.exists():shutil.copyfile(source,H/"sources"/name)
    print(result,flush=True)
finally:kernel.SetThreadExecutionState(0x80000000)
(H/"UPSTREAM_CONTROL_COMPLETE").write_text("complete")
