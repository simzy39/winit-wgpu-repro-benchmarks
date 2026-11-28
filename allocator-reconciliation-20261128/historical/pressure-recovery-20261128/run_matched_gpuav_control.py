"""Same executable bytes/path, interleaved GPUAV on/off diagnostic configurations."""
from pathlib import Path
import os,subprocess,json,shutil,time,hashlib,xml.etree.ElementTree as ET
H=Path(__file__).resolve().parent;R=H/'wgpu/core-validation';target=H/'target-core-validation'
while not (H/'CORE_VALIDATION_COMPLETE').exists():time.sleep(10)
p=R/'tests/src/init.rs';s=p.read_text()
start=s.index('    // Diagnostic control only:')
end=s.index('\n\n    Instance::new',start)
s=s[:start]+'''    // Diagnostic control only: retain one executable/path for both modes.
    let core_only = std::env::var_os("GPUA_DIAGNOSTIC_CORE_ONLY").is_some();
    let flags = if core_only {
        flags - wgpu::InstanceFlags::GPU_BASED_VALIDATION
    } else {
        flags
    };
    assert!(flags.contains(wgpu::InstanceFlags::VALIDATION));
    assert_eq!(flags.contains(wgpu::InstanceFlags::GPU_BASED_VALIDATION), !core_only);
    eprintln!("GPUAV_FLAG_CONTROL: core=true gpuav={} flags={flags:?}", !core_only);
'''+s[end:]
p.write_text(s)
(H/'sources/gpuav-flag-control-harness.patch').write_bytes(subprocess.check_output(['git','-C',str(R),'diff','--','tests/src/init.rs']))
shutil.copyfile(p,H/'sources/gpuav-flag-control-init.rs')
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+env['PATH'];env['LIB']=str(H/'tools/atl')+';'+env.get('LIB','')
env.update(CARGO_TARGET_DIR=str(target),CARGO_NET_OFFLINE='true',CARGO_BUILD_JOBS='2',NEXTEST_TEST_THREADS='1',WGPU_BACKEND='vulkan',WGPU_VALIDATION='1')
env.pop('GPUA_DIAGNOSTIC_CORE_ONLY',None)
build=['cargo','nextest','list','--locked','--all-features','-p','wgpu-test','--test','wgpu-gpu','--message-format','json','--list-type','binaries-only']
meta=H/'sources/gpuav-flag-control-binaries.json'
with meta.open('w') as out,(H/'logs/gpuav-flag-control-build.log').open('w') as log:
    process=subprocess.run(build,cwd=R,env=env,stdout=out,stderr=log)
assert process.returncode==0
assert 'Compiling wgpu-test ' in (H/'logs/gpuav-flag-control-build.log').read_text()
data=json.loads(meta.read_text());binary=Path(data['rust-binaries']['wgpu-test::wgpu-gpu']['binary-path'])
frozen=H/'gpuav-flag-control-bin'/binary.name;frozen.parent.mkdir();shutil.copyfile(binary,frozen)
data['rust-binaries']['wgpu-test::wgpu-gpu']['binary-path']=str(frozen)
meta.write_text(json.dumps(data,indent=2));digest=hashlib.sha256(frozen.read_bytes()).hexdigest()
cases=[r for r in json.loads((H/'control-comparison.json').read_text())['rows'] if r['binary']=='wgpu-test::wgpu-gpu' and '[Vulkan/' in r['name'] and any(x in r['name'] for x in ['::mesh_shader::','binding_array::tlas::binding_array_tlas','prevent_invalid_ray_query_calls'])]
assert len(cases)==10
escape=lambda s:s.replace('\\','\\\\').replace(')','\\)').replace(',','\\,').replace('/','\\/')
expression=' | '.join('(binary_id(='+escape(r['binary'])+') & test(='+escape(r['name'])+'))' for r in cases)
folder=H/'gpuav-flag-controls';folder.mkdir();rows=[]
for trial in range(1,4):
    for mode in (['on','off'] if trial%2 else ['off','on']):
        current=env.copy()
        if mode=='off':current['GPUA_DIAGNOSTIC_CORE_ONLY']='1'
        log=folder/f'{mode}-{trial}.log'
        command=['cargo','nextest','run','--binaries-metadata',str(meta),'-E',expression,'--success-output','immediate']
        with log.open('w') as stream:process=subprocess.run(command,cwd=R,env=current,stdout=stream,stderr=subprocess.STDOUT)
        junit=R/'target/nextest/default/junit.xml';shutil.copyfile(junit,folder/f'{mode}-{trial}.xml')
        root=ET.parse(junit).getroot();assert root.attrib['tests']=='10'
        text=log.read_text();marker='GPUAV_FLAG_CONTROL: core=true gpuav='+('true' if mode=='on' else 'false')
        assert text.count(marker)==10,(mode,text.count(marker))
        outcomes=[]
        for c in root.iter('testcase'):
            failure=c.find('failure')
            if failure is None:failure=c.find('error')
            outcomes.append({'name':c.attrib['name'],'failed':failure is not None,'type':None if failure is None else failure.attrib.get('type'),'details':None if failure is None else failure.text})
        rows.append({'trial':trial,'mode':mode,'rc':process.returncode,'verified_flag_markers':10,'gpuav_enabled_warning_present':'Both GPU Assisted Validation and Normal Core Check Validation are enabled' in text,'outcomes':outcomes})
        (H/'gpuav-flag-control-progress.json').write_text(json.dumps(rows,indent=2))
        print(mode,trial,'failed',sum(r['failed'] for r in outcomes),flush=True)
record={'base':'60cef2be828e03ba54e2e1598001b4625c0c2163','source_change':'Test initialization only; one binary, process-local diagnostic variable clears GPUAV after required flags in off mode. Core validation asserted enabled in both.','configuration_limit':'Off mode intentionally changes tests required GPUAV configuration; diagnostic, not conformance success.','allocator':'Registry dependency; no path override','our_wgpu_patches':[],'lock_unchanged':(R/'Cargo.lock').read_bytes()==(H/'wgpu/upstream/Cargo.lock').read_bytes(),'source_status':subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True),'same_binary_and_path_for_both_modes':str(frozen),'exe_sha256':digest,'build_command':build,'initial_isolated_build':'core-validation-control.json','native_test_executions':60,'rows':rows}
assert record['lock_unchanged'] and record['source_status'].strip()=='M tests/src/init.rs'
assert hashlib.sha256(frozen.read_bytes()).hexdigest()==digest
(H/'gpuav-flag-control.json').write_text(json.dumps(record,indent=2))
(H/'GPUAV_FLAG_CONTROL_COMPLETE').write_text('complete')
print('Complete same-binary GPUAV control',flush=True)
