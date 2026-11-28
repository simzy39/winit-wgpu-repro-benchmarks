"""Byte-identical historical binaries at new paths; all output stays in this bundle."""
import pathlib,json,shutil,os,subprocess,hashlib,time,xml.etree.ElementTree as ET
H=pathlib.Path(__file__).resolve().parent;P=H.parent/'reassessment-20261128';R=H/'wgpu/upstream'
out=H/'path-controls';out.mkdir(exist_ok=True);common=out/'bin';common.mkdir(exist_ok=True)
shutil.copyfile(R/'target/debug/deps/d3d10warp.dll',common/'d3d10warp.dll')
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+str(R/'target/debug/deps')+';'+env['PATH']
env.update(WGPU_BACKEND='dx12,vulkan',NEXTEST_TEST_THREADS='1',CARGO_NET_OFFLINE='true',WGPU_DX12_AGILITY_SDK_PATH=str(next((R/'target/agility-sdk').rglob('D3D12Core.dll')).parent),WGPU_DX12_AGILITY_SDK_VERSION='619',WGPU_DX12_AGILITY_SDK_REQUIRE='1')
rows=json.loads((H/'control-comparison.json').read_text())['rows']
cases=[r for r in rows if ('draw_multiview_single' in r['name'] or ('Microsoft Basic' in r['name'] and 'request_device_error_message' in r['name']))]
escape=lambda s:s.replace('\\','\\\\').replace(')','\\)').replace(',','\\,').replace('/','\\/')
expression=' | '.join('(binary_id(='+escape(r['binary'])+') & test(='+escape(r['name'])+'))' for r in cases)
sources={'old-pr323':P/'wgpu-failure-controls/pr323-frozen-binaries.json','old-cache2':P/'wgpu-failure-controls/candidate-frozen-binaries.json','upstream':H/'sources/upstream-frozen-binaries.json'}
results=[]
for trial in range(1,4):
    labels=list(sources)
    if trial%2==0:labels.reverse()
    for label in labels:
        meta=json.loads(sources[label].read_text());key='wgpu-test::wgpu-gpu'
        source=pathlib.Path(meta['rust-binaries'][key]['binary-path']);exe=common/'gpu-test.exe';shutil.copyfile(source,exe)
        digest=hashlib.sha256(exe.read_bytes()).hexdigest();meta['rust-binaries'][key]['binary-path']=str(exe)
        if label!='upstream':
            raw=json.dumps(meta)
            old=P/'downstream/validation'
            for before,after in [(json.dumps(str(old))[1:-1],json.dumps(str(R))[1:-1]),(old.as_posix(),R.as_posix()),(old.as_uri(),R.as_uri())]:raw=raw.replace(before,after)
            meta=json.loads(raw)
        meta['rust-build-meta']['target-directory']=str(out/'target')
        metadata=out/(label+'.json');metadata.write_text(json.dumps(meta))
        stem=label+'-'+str(trial);log=out/(stem+'.log')
        if log.exists():log.rename(out/(stem+'-setup-'+str(time.time_ns())+'.log'))
        command=['cargo','nextest','run','--binaries-metadata',str(metadata),'-E',expression,'--success-output','immediate']
        with log.open('w') as f:p=subprocess.run(command,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
        junit=R/'target/nextest/default/junit.xml';assert junit.exists()
        shutil.copyfile(junit,out/(stem+'.xml'))
        root=ET.parse(junit).getroot();assert int(root.attrib['tests'])==2
        outcomes=[{'name':c.attrib['name'],'failed':c.find('failure') is not None or c.find('error') is not None} for c in root.iter('testcase')]
        results.append({'label':label,'trial':trial,'exe_sha256':digest,'rc':p.returncode,'outcomes':outcomes})
        (H/'path-controls.json').write_text(json.dumps(results,indent=2));print(results[-1],flush=True)
(H/'PATH_CONTROLS_COMPLETE').write_text('complete')
