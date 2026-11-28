"""Compare all full-suite failures with the unchanged allocator PR in the same wgpu sources."""
import pathlib,json,subprocess,shutil,os,hashlib,time,ctypes,xml.etree.ElementTree as ET
H=pathlib.Path(__file__).resolve().parent
R=H/"downstream/validation"
O=H/"wgpu-failure-controls"
env=os.environ.copy()
env["PATH"]=str(H/"tools")+";"+r"<drive>/VulkanSDK\1.4.363.0\Bin"+";"+str(R/"target/debug/deps")+";"+env["PATH"]
env["LIB"]=str(H/"tools/atl")+";"+env.get("LIB","")
env.update(WGPU_BACKEND="dx12,vulkan",NEXTEST_TEST_THREADS="2",CARGO_BUILD_JOBS="3")
sdk=next((R/"target/agility-sdk").rglob("D3D12Core.dll")).parent
env.update(WGPU_DX12_AGILITY_SDK_PATH=str(sdk),WGPU_DX12_AGILITY_SDK_VERSION="619",WGPU_DX12_AGILITY_SDK_REQUIRE="1")
meta=json.loads((O/"candidate-binaries.json").read_text())
failures=json.loads((O/"failures.json").read_text())
expression=failures["filter"]
ids={r["binary_id"] for r in failures["failures"]}
def freeze(metadata,label):
    folder=O/(label+"-bin");folder.mkdir(exist_ok=True)
    records={}
    for key,record in metadata["rust-binaries"].items():
        if key not in ids:continue
        source=pathlib.Path(record["binary-path"])
        target=folder/source.name
        assert not target.exists()
        shutil.copyfile(source,target)
        records[key]={"path":str(target),"sha256":hashlib.sha256(target.read_bytes()).hexdigest()}
        record["binary-path"]=str(target)
    assert len(records)==len(ids)
    shutil.copyfile(R/"target/debug/deps/d3d10warp.dll",folder/"d3d10warp.dll")
    (O/(label+"-frozen-binaries.json")).write_text(json.dumps(metadata,indent=2))
    (O/(label+"-executable-hashes.json")).write_text(json.dumps(records,indent=2))
    return O/(label+"-frozen-binaries.json")
candidate=freeze(meta,"candidate")
check=["cargo","nextest","list","--binaries-metadata",str(candidate),"-E",expression,"--message-format","json"]
p=subprocess.run(check,cwd=R,env=env,capture_output=True,text=True)
(O/"filter-check.stderr.txt").write_text(p.stderr)
assert p.returncode==0,p.stderr
listing=json.loads(p.stdout)
(O/"filtered-tests.json").write_text(p.stdout)
selected=sum(1 for suite in listing["rust-suites"].values() for test in suite["testcases"].values() if test["filter-match"]["status"]=="matches")
assert selected==26,selected
config=R/".cargo/config.toml"
original=config.read_text()
assert str(H/"work/cache2/gpu-allocator").replace("\\","/") in original
baseline=original.replace(str(H/"work/cache2/gpu-allocator").replace("\\","/"),str(H/"work/pr323/gpu-allocator").replace("\\","/"))
kernel=ctypes.windll.kernel32
assert kernel.SetThreadExecutionState(0x80000001)
results=[]
try:
    config.write_text(baseline)
    clean=["cargo","clean"]
    for name in ["gpu-allocator","wgpu-hal","wgpu-core","wgpu","wgpu-test","wgpu-examples","wgpu-benchmark"]:clean += ["-p",name]
    p=subprocess.run(clean,cwd=R,env=env,capture_output=True,text=True)
    (O/"baseline-clean.log").write_text(p.stdout+p.stderr)
    assert p.returncode==0,p.stderr
    command=["cargo","nextest","list","--benches","--tests","--all-features","--list-type","binaries-only","--message-format","json"]
    print("Building unchanged allocator PR control with both wgpu patches",flush=True)
    with (O/"baseline-binaries.json").open("w") as stdout,(O/"baseline-build.log").open("w") as stderr:
        p=subprocess.run(command,cwd=R,env=env,stdout=stdout,stderr=stderr)
    assert p.returncode==0,"Inspect baseline-build.log"
    baseline_bins=freeze(json.loads((O/"baseline-binaries.json").read_text()),"pr323")
    for label,bins in [("pr323",baseline_bins),("candidate",candidate)]:
        print("Running 26-case control:",label,flush=True)
        command=["cargo","nextest","run","--binaries-metadata",str(bins),"-E",expression,"--no-fail-fast"]
        start=time.perf_counter()
        with (O/(label+"-filtered.log")).open("w") as log:
            p=subprocess.run(command,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
        shutil.copyfile(R/"target/nextest/default/junit.xml",O/(label+"-filtered-junit.xml"))
        results.append({"label":label,"rc":p.returncode,"command":command,"wall_s":time.perf_counter()-start})
        (O/"control-runs.json").write_text(json.dumps(results,indent=2))
finally:
    config.write_text(original)
    kernel.SetThreadExecutionState(0x80000000)
print("Failure controls completed:",results,flush=True)
