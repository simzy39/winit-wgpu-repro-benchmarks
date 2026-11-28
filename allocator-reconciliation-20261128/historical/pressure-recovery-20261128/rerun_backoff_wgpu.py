"""Required full suite after final pressure policy change, with corrected local patch."""
import pathlib,subprocess,os,json,time,shutil,ctypes
H=pathlib.Path(__file__).resolve().parent;R=H/'wgpu/candidate'
while not (H/'BACKOFF_PLANS_COMPLETE').exists():time.sleep(10)
assert (H/'compile-fail-final-fixed-rc.txt').read_text().strip()=='0'
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+env['PATH'];env['LIB']=str(H/'tools/atl')+';'+env.get('LIB','')
env.update(CARGO_TARGET_DIR=str(H/'wgpu/upstream/target'),CARGO_NET_OFFLINE='true',CARGO_BUILD_JOBS='2',NEXTEST_TEST_THREADS='2',WGPU_BACKEND='dx12,vulkan')
kernel=ctypes.windll.kernel32;kernel.SetThreadExecutionState(0x80000001)
start=time.perf_counter();command=['cargo','xtask','test']
try:
    with (H/'logs/backoff-full-wgpu.log').open('w') as log:p=subprocess.run(command,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
    shutil.copyfile(R/'target/nextest/default/junit.xml',H/'sources/backoff-full-junit.xml')
    result={'command':command,'rc':p.returncode,'wall_s':time.perf_counter()-start,'junit_source':str(R/'target/nextest/default/junit.xml'),'test_override':'workspace Cargo.toml, inherited by trybuild'}
    (H/'backoff-full-wgpu.json').write_text(json.dumps(result,indent=2));print(result,flush=True)
finally:kernel.SetThreadExecutionState(0x80000000)
(H/'BACKOFF_WGPU_COMPLETE').write_text('complete')
