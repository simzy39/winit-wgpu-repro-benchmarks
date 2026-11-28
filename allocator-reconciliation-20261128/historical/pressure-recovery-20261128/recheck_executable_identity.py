"""After the full suite, separate basename from directory effects using the same bytes.

Only the two IO-free multiview/error-message cases run. Nextest's package graph and
working directories are remapped to H2; reports and metadata remain in H2.
"""
import pathlib,json,shutil,os,subprocess,hashlib,time,xml.etree.ElementTree as ET
H=pathlib.Path(__file__).resolve().parent;P=H.parent/'reassessment-20261128';R=H/'wgpu/upstream'
while not (H/'CANDIDATE_WG_COMPLETE').exists():time.sleep(10)
assert any(r['name']=='candidate-full' for r in json.loads((H/'candidate-wgpu-tests.json').read_text()))
out=H/'identity-controls';out.mkdir(exist_ok=True);folder=out/'bin';folder.mkdir(exist_ok=True)
meta=json.loads((P/'wgpu-failure-controls/candidate-frozen-binaries.json').read_text());key='wgpu-test::wgpu-gpu'
source=pathlib.Path(meta['rust-binaries'][key]['binary-path']);digest=hashlib.sha256(source.read_bytes()).hexdigest()
assert digest=='36c6ff16d27f6190242f914c16097e5809600362d104d9a22b5824f09fbc7a16'
for name in [source.name,'gpu-test.exe']:shutil.copyfile(source,folder/name)
shutil.copyfile(R/'target/debug/deps/d3d10warp.dll',folder/'d3d10warp.dll')
old=P/'downstream/validation';raw=json.dumps(meta)
for before,after in [(json.dumps(str(old))[1:-1],json.dumps(str(R))[1:-1]),(old.as_posix(),R.as_posix()),(old.as_uri(),R.as_uri())]:raw=raw.replace(before,after)
meta=json.loads(raw)
cases=[r for r in json.loads((H/'control-comparison.json').read_text())['rows'] if 'draw_multiview_single' in r['name'] or ('Microsoft Basic' in r['name'] and 'request_device_error_message' in r['name'])]
escape=lambda s:s.replace('\\','\\\\').replace(')','\\)').replace(',','\\,').replace('/','\\/')
expression=' | '.join('(binary_id(='+escape(r['binary'])+') & test(='+escape(r['name'])+'))' for r in cases)
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+str(R/'target/debug/deps')+';'+env['PATH']
env.update(WGPU_BACKEND='dx12,vulkan',NEXTEST_TEST_THREADS='1',CARGO_NET_OFFLINE='true',WGPU_DX12_AGILITY_SDK_PATH=str(next((R/'target/agility-sdk').rglob('D3D12Core.dll')).parent),WGPU_DX12_AGILITY_SDK_VERSION='619',WGPU_DX12_AGILITY_SDK_REQUIRE='1')
rows=[]
for trial in range(1,4):
    modes=[('original-path',source),('new-dir-original-name',folder/source.name),('new-dir-short-name',folder/'gpu-test.exe')]
    if trial%2==0:modes.reverse()
    for label,exe in modes:
        assert hashlib.sha256(exe.read_bytes()).hexdigest()==digest
        meta['rust-binaries'][key]['binary-path']=str(exe)
        metadata=out/(label+'.json');metadata.write_text(json.dumps(meta));stem=label+'-'+str(trial)
        log=out/(stem+'.log');assert not log.exists()
        command=['cargo','nextest','run','--binaries-metadata',str(metadata),'-E',expression,'--success-output','immediate']
        with log.open('w') as stream:p=subprocess.run(command,cwd=R,env=env,stdout=stream,stderr=subprocess.STDOUT)
        junit=R/'target/nextest/default/junit.xml';shutil.copyfile(junit,out/(stem+'.xml'));root=ET.parse(junit).getroot();assert root.attrib['tests']=='2'
        outcomes=[{'name':c.attrib['name'],'failed':c.find('failure') is not None or c.find('error') is not None} for c in root.iter('testcase')]
        rows.append({'trial':trial,'mode':label,'binary':str(exe),'exe_sha256':digest,'rc':p.returncode,'outcomes':outcomes})
        (H/'identity-controls.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
(H/'IDENTITY_CONTROLS_COMPLETE').write_text('complete')
