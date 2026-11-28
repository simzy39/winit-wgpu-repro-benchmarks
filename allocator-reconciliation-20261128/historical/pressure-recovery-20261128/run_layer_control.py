"""Isolate the eight mesh aborts: same binary, core validation requested versus absent."""
from pathlib import Path
import os,subprocess,json,shutil,time,hashlib,xml.etree.ElementTree as ET,re
H=Path(__file__).resolve().parent;R=H/'wgpu/core-validation';target=H/'target-core-validation'
while not (H/'GPUAV_FLAG_CONTROL_COMPLETE').exists():time.sleep(5)
p=R/'tests/src/init.rs';s=p.read_text()
s=s.replace('    assert!(flags.contains(wgpu::InstanceFlags::VALIDATION));','''    let no_layer = std::env::var_os("GPUA_DIAGNOSTIC_NO_LAYER").is_some();
    let flags = if no_layer {
        flags - wgpu::InstanceFlags::VALIDATION
    } else {
        flags
    };
    assert_eq!(flags.contains(wgpu::InstanceFlags::VALIDATION), !no_layer);''')
s=s.replace('    eprintln!("GPUAV_FLAG_CONTROL: core=true gpuav={} flags={flags:?}", !core_only);','')
s=s.replace('    Instance::new(wgpu::InstanceDescriptor {','    let instance = Instance::new(wgpu::InstanceDescriptor {',1)
start=s.index('    let instance = Instance::new(');end=s.index('\n}\n',start)
assert s[end-2:end]=='})'
s=s[:end-2]+''' });
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetModuleHandleA(name: *const u8) -> *mut core::ffi::c_void;
    }
    let loaded = unsafe {
        !GetModuleHandleA(b"VkLayer_khronos_validation.dll\\0".as_ptr()).is_null()
    };
    eprintln!("LAYER_FLAG_CONTROL: core={} gpuav=false vvl_loaded={loaded}", !no_layer);
    instance'''+s[end:]
p.write_text(s)
(H/'sources/layer-control-harness.patch').write_bytes(subprocess.check_output(['git','-C',str(R),'diff','--','tests/src/init.rs']))
shutil.copyfile(p,H/'sources/layer-control-init.rs')
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+env['PATH'];env['LIB']=str(H/'tools/atl')+';'+env.get('LIB','')
env.update(CARGO_TARGET_DIR=str(target),CARGO_NET_OFFLINE='true',CARGO_BUILD_JOBS='2',NEXTEST_TEST_THREADS='1',WGPU_BACKEND='vulkan',WGPU_VALIDATION='1',GPUA_DIAGNOSTIC_CORE_ONLY='1',VK_LOADER_DEBUG='layer')
env.pop('GPUA_DIAGNOSTIC_NO_LAYER',None)
command=['cargo','nextest','list','--locked','--all-features','-p','wgpu-test','--test','wgpu-gpu','--message-format','json','--list-type','binaries-only']
meta=H/'sources/layer-control-binaries.json'
with meta.open('w') as out,(H/'logs/layer-control-build.log').open('w') as log:
    process=subprocess.run(command,cwd=R,env=env,stdout=out,stderr=log)
assert process.returncode==0,(H/'logs/layer-control-build.log').read_text()[-2500:]
assert 'Compiling wgpu-test ' in (H/'logs/layer-control-build.log').read_text()
data=json.loads(meta.read_text());binary=Path(data['rust-binaries']['wgpu-test::wgpu-gpu']['binary-path'])
frozen=H/'layer-control-bin'/binary.name;frozen.parent.mkdir();shutil.copyfile(binary,frozen)
data['rust-binaries']['wgpu-test::wgpu-gpu']['binary-path']=str(frozen);meta.write_text(json.dumps(data,indent=2))
digest=hashlib.sha256(frozen.read_bytes()).hexdigest()
cases=[r for r in json.loads((H/'control-comparison.json').read_text())['rows'] if r['binary']=='wgpu-test::wgpu-gpu' and '[Vulkan/' in r['name'] and '::mesh_shader::' in r['name']]
assert len(cases)==8
escape=lambda s:s.replace('\\','\\\\').replace(')','\\)').replace(',','\\,').replace('/','\\/')
expression=' | '.join('(binary_id(='+escape(r['binary'])+') & test(='+escape(r['name'])+'))' for r in cases)
out=H/'layer-controls';out.mkdir();rows=[]
for trial in range(1,4):
    for mode in (['core','none'] if trial%2 else ['none','core']):
        current=env.copy()
        if mode=='none':current['GPUA_DIAGNOSTIC_NO_LAYER']='1'
        log=out/f'{mode}-{trial}.log'
        run=['cargo','nextest','run','--binaries-metadata',str(meta),'-E',expression,'--success-output','immediate']
        with log.open('w') as stream:process=subprocess.run(run,cwd=R,env=current,stdout=stream,stderr=subprocess.STDOUT)
        junit=R/'target/nextest/default/junit.xml';shutil.copyfile(junit,out/f'{mode}-{trial}.xml')
        root=ET.parse(junit).getroot();assert root.attrib['tests']=='8'
        text=log.read_text();marker='LAYER_FLAG_CONTROL: core='+('true' if mode=='core' else 'false')+' gpuav=false'
        assert text.count(marker)==8,(mode,text.count(marker))
        loaded=re.findall(re.escape(marker)+r' vvl_loaded=(true|false)',text);assert len(loaded)==8
        outcomes=[]
        for c in root.iter('testcase'):
            failure=c.find('failure')
            if failure is None:failure=c.find('error')
            outcomes.append({'name':c.attrib['name'],'failed':failure is not None,'type':None if failure is None else failure.attrib.get('type'),'details':None if failure is None else failure.text})
        rows.append({'trial':trial,'mode':mode,'rc':process.returncode,'verified_flags':8,'validation_dll_loaded':loaded,'active_validation_layer_insert_lines':[line for line in text.splitlines() if re.search(r'insert.*VK_LAYER_KHRONOS_validation',line,re.I)],'outcomes':outcomes})
        (H/'layer-control-progress.json').write_text(json.dumps(rows,indent=2));print(mode,trial,'failed',sum(r['failed'] for r in outcomes),'vvl',set(loaded),flush=True)
record={'base':'60cef2be828e03ba54e2e1598001b4625c0c2163','source_change':'Test initialization only. Core mode retains backend validation; none mode removes it. GPUAV disabled in both. Same bytes/path per mode; module presence and loader messages captured.','conformance':False,'allocator':'unmodified registry dependency','our_wgpu_pr_patches':[],'lock_unchanged':(R/'Cargo.lock').read_bytes()==(H/'wgpu/upstream/Cargo.lock').read_bytes(),'source_status':subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True),'exe_sha256':digest,'binary':str(frozen),'executions':48,'rows':rows}
assert record['lock_unchanged'] and record['source_status'].strip()=='M tests/src/init.rs'
(H/'layer-control.json').write_text(json.dumps(record,indent=2));(H/'LAYER_CONTROL_COMPLETE').write_text('complete')
print('Complete native layer control',flush=True)
