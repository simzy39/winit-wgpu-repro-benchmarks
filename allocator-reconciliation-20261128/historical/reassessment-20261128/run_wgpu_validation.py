"""Run the required full wgpu check after latency measurements have ended."""
import pathlib,os,subprocess,json,time,datetime
H=pathlib.Path(__file__).resolve().parent
assert (H/"DIRECT_COMPLETE").exists() and (H/"DOWNSTREAM_COMPLETE").exists(),"Complete latency suites first"
while (H/"DIAGNOSTIC_REQUESTED").exists() and not (H/"DIAGNOSTIC_COMPLETE").exists():
    time.sleep(2)
while (H/"SUSPEND_RECHECK_REQUESTED").exists() and not (H/"SUSPEND_RECHECK_COMPLETE").exists():
    time.sleep(2)
repo=H/"downstream/validation"
env=os.environ.copy()
env["PATH"]=str(H/"tools")+";"+r"<drive>/VulkanSDK\1.4.363.0\Bin"+";"+env["PATH"]
env["VULKAN_SDK"]=r"<drive>/VulkanSDK\1.4.363.0"
env["WGPU_BACKEND"]="dx12,vulkan"
env["NEXTEST_TEST_THREADS"]="2"
if (H/"tools/atl/atls.lib").exists():
    env["LIB"]=str(H/"tools/atl")+";"+env.get("LIB","")
env["CARGO_BUILD_JOBS"]="3"
cmd=["cargo","xtask","test"]
start=time.perf_counter()
print("Starting full wgpu test suite",flush=True)
with (H/"logs/wgpu-full-tests.log").open("w",encoding="utf-8") as log:
    p=subprocess.run(cmd,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
(H/"wgpu-full-tests.json").write_text(json.dumps({"command":cmd,"rc":p.returncode,
    "utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"wall_s":time.perf_counter()-start,
    "environment":{"WGPU_BACKEND":env["WGPU_BACKEND"],"NEXTEST_TEST_THREADS":env["NEXTEST_TEST_THREADS"],
        "CARGO_BUILD_JOBS":env["CARGO_BUILD_JOBS"],"local_atl":str(H/"tools/atl") if (H/"tools/atl/atls.lib").exists() else None}},indent=2))
print("Full wgpu test exit",p.returncode,flush=True)
raise SystemExit(p.returncode)

