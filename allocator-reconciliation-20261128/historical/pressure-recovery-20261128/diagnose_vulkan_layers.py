"""Check the loaded layer and the SDK's documented long-name setting override."""
import pathlib,json,subprocess,os,shutil,xml.etree.ElementTree as ET
H=pathlib.Path(__file__).resolve().parent;R=H/'wgpu/upstream';out=H/'layer-diagnostics';out.mkdir(exist_ok=True)
cases=[r for r in json.loads((H/'control-comparison.json').read_text())['rows'] if '[Vulkan/' in r['name'] and (r['name'].endswith('wgpu_gpu::mesh_shader::mesh_draw') or r['name'].endswith('binding_array::tlas::binding_array_tlas'))]
escape=lambda s:s.replace('\\','\\\\').replace(')','\\)').replace(',','\\,').replace('/','\\/')
expression=' | '.join('(binary_id(='+escape(r['binary'])+') & test(='+escape(r['name'])+'))' for r in cases)
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+env['PATH'];env.update(WGPU_BACKEND='vulkan',NEXTEST_TEST_THREADS='1',CARGO_NET_OFFLINE='true',VK_LOADER_DEBUG='layer',VK_KHRONOS_VALIDATION_VALIDATE_CORE='true')
rows=[]
for mode in ['default','long-name-gpuav-off']:
    settings=env.copy()
    if mode!='default':settings['VK_KHRONOS_VALIDATION_GPUAV_ENABLE']='false'
    command=['cargo','nextest','run','--binaries-metadata',str(H/'sources/upstream-frozen-binaries.json'),'-E',expression,'--success-output','immediate']
    log=out/(mode+'.log');assert not log.exists()
    with log.open('w') as stream:p=subprocess.run(command,cwd=R,env=settings,stdout=stream,stderr=subprocess.STDOUT)
    junit=R/'target/nextest/default/junit.xml';shutil.copyfile(junit,out/(mode+'.xml'));root=ET.parse(junit).getroot();assert root.attrib['tests']=='2'
    text=log.read_text();outcomes=[{'name':c.attrib['name'],'failed':c.find('failure') is not None or c.find('error') is not None} for c in root.iter('testcase')]
    rows.append({'mode':mode,'rc':p.returncode,'gpuav_enabled_warning':'Both GPU Assisted Validation and Normal Core Check Validation are enabled' in text,'outcomes':outcomes,'layer_lines':[line.strip() for line in text.splitlines() if ('khronos_validation' in line.lower() and ('dll' in line.lower() or 'json' in line.lower()))]})
    (H/'layer-diagnostics.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
