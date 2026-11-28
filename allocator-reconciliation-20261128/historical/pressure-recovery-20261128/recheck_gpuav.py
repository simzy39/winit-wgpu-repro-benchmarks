"""Focused clean-upstream control: GPU-assisted versus core-only validation."""
import pathlib,json,subprocess,os,time,hashlib,shutil,xml.etree.ElementTree as ET
H=pathlib.Path(__file__).resolve().parent;R=H/'wgpu/upstream'
while not (H/'IDENTITY_CONTROLS_COMPLETE').exists():time.sleep(10)
out=H/'gpuav-controls';out.mkdir(exist_ok=True)
meta=H/'sources/upstream-frozen-binaries.json';data=json.loads(meta.read_text())
exe=pathlib.Path(data['rust-binaries']['wgpu-test::wgpu-gpu']['binary-path']);digest=hashlib.sha256(exe.read_bytes()).hexdigest()
cases=[r for r in json.loads((H/'control-comparison.json').read_text())['rows'] if '[Vulkan/' in r['name'] and ('wgpu_gpu::mesh_shader::mesh_draw'==r['name'].split('] ')[-1] or r['name'].endswith('binding_array::tlas::binding_array_tlas'))]
assert len(cases)==2
escape=lambda s:s.replace('\\','\\\\').replace(')','\\)').replace(',','\\,').replace('/','\\/')
expression=' | '.join('(binary_id(='+escape(r['binary'])+') & test(='+escape(r['name'])+'))' for r in cases)
base=os.environ.copy();base['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+base['PATH']
base.update(WGPU_BACKEND='vulkan',NEXTEST_TEST_THREADS='1',CARGO_NET_OFFLINE='true',VK_LAYER_VALIDATE_CORE='1')
rows=[]
for trial in range(1,4):
    modes=['default','gpuav-off'] if trial%2 else ['gpuav-off','default']
    for mode in modes:
        env=base.copy()
        if mode=='gpuav-off':env['VK_LAYER_GPUAV_ENABLE']='0'
        stem=mode+'-'+str(trial);log=out/(stem+'.log');assert not log.exists()
        command=['cargo','nextest','run','--binaries-metadata',str(meta),'-E',expression,'--success-output','immediate']
        with log.open('w') as stream:p=subprocess.run(command,cwd=R,env=env,stdout=stream,stderr=subprocess.STDOUT)
        junit=R/'target/nextest/default/junit.xml';shutil.copyfile(junit,out/(stem+'.xml'));root=ET.parse(junit).getroot();assert root.attrib['tests']=='2'
        outcomes=[{'name':c.attrib['name'],'failed':c.find('failure') is not None or c.find('error') is not None} for c in root.iter('testcase')]
        rows.append({'mode':mode,'trial':trial,'rc':p.returncode,'exe_sha256':digest,'VK_LAYER_VALIDATE_CORE':env['VK_LAYER_VALIDATE_CORE'],'VK_LAYER_GPUAV_ENABLE':env.get('VK_LAYER_GPUAV_ENABLE'),'outcomes':outcomes})
        (H/'gpuav-controls.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
(H/'GPUAV_CONTROLS_COMPLETE').write_text('complete')
