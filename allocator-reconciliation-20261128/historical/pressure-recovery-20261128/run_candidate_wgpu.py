import pathlib,subprocess,os,json,shutil,time,ctypes,hashlib
H=pathlib.Path(__file__).resolve().parent;R=H/'wgpu/candidate';target=H/'wgpu/upstream/target'
while not all((H/marker).exists() for marker in ['UPSTREAM_CONTROL_COMPLETE','DIRECT_COMPLETE','DOWNSTREAM_COMPLETE']):time.sleep(10)
assert json.loads((H/'upstream-failure-control.json').read_text())['source_status']==''
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+env['PATH']
env['LIB']=str(H/'tools/atl')+';'+env.get('LIB','')
env.update(CARGO_TARGET_DIR=str(target),WGPU_BACKEND='dx12,vulkan',NEXTEST_TEST_THREADS='2',CARGO_BUILD_JOBS='2',CARGO_NET_OFFLINE='true')
rows=[];kernel=ctypes.windll.kernel32;kernel.SetThreadExecutionState(0x80000001)
try:
    for name,command in [('candidate-hal-unit',['cargo','test','-p','wgpu-hal','--lib','--features','dx12','suballocation::tests']),('candidate-full',['cargo','xtask','test'])]:
        start=time.perf_counter()
        with (H/'logs'/(name+'.log')).open('w') as log:p=subprocess.run(command,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
        rows.append({'name':name,'command':command,'rc':p.returncode,'wall_s':time.perf_counter()-start})
        (H/'candidate-wgpu-tests.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
        if name=='candidate-hal-unit' and p.returncode:break
    junit=R/'target/nextest/default/junit.xml'
    if junit.exists():shutil.copyfile(junit,H/'sources/candidate-full-junit.xml')
    gpuconfig=R/'.gpuconfig'
    if gpuconfig.exists():shutil.copyfile(gpuconfig,H/'sources/candidate-gpuconfig.json')
finally:kernel.SetThreadExecutionState(0x80000000)
(H/'CANDIDATE_WG_COMPLETE').write_text('complete')
