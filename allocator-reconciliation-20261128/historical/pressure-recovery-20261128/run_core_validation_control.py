"""Actual GPUAV-off experiment: test-harness-only flag change on pristine upstream.

This diagnostic configuration does not satisfy tests' GPUAV requirements and is not
a replacement conformance run. All intended PR/allocator changes are absent.
"""
from pathlib import Path
import subprocess,shutil,os,json,time,hashlib,xml.etree.ElementTree as ET
H=Path(__file__).resolve().parent;R=H/'wgpu/core-validation';target=H/'target-core-validation'
assert not R.exists() and not target.exists()
base='60cef2be828e03ba54e2e1598001b4625c0c2163'
subprocess.run(['git','-C',str(H/'wgpu/upstream'),'worktree','add','--detach',str(R),base],check=True,capture_output=True)
p=R/'tests/src/init.rs';s=p.read_text()
needle='        .difference(params.forbidden_instance_flags);'
assert s.count(needle)==1
s=s.replace(needle,needle+'''
    // Diagnostic control only: override the tests' explicit GPUAV request.
    let flags = flags - wgpu::InstanceFlags::GPU_BASED_VALIDATION;
    assert!(flags.contains(wgpu::InstanceFlags::VALIDATION));
    assert!(!flags.contains(wgpu::InstanceFlags::GPU_BASED_VALIDATION));
    eprintln!("CORE_ONLY_CONTROL: core=true gpuav=false flags={flags:?}");
''')
p.write_text(s)
(H/'sources/core-validation-harness.patch').write_bytes(subprocess.check_output(['git','-C',str(R),'diff','--','tests/src/init.rs']))
shutil.copyfile(p,H/'sources/core-validation-init.rs')
shutil.copyfile(H/'wgpu/upstream/.gpuconfig',R/'.gpuconfig')
exclude=['wgpu','naga','gpu_allocator','gpu-allocator']
ignore=lambda directory,names:[name for name in names if any(part in name.lower() for part in exclude)]
native=lambda p:'\\\\?\\'+str(p.resolve())
shutil.copytree(native(H/'wgpu/upstream/target'),native(target),ignore=ignore)
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+r'<drive>/VulkanSDK\1.4.363.0\Bin'+';'+env['PATH'];env['LIB']=str(H/'tools/atl')+';'+env.get('LIB','')
env.update(CARGO_TARGET_DIR=str(target),CARGO_NET_OFFLINE='true',CARGO_BUILD_JOBS='2',NEXTEST_TEST_THREADS='1',WGPU_BACKEND='vulkan',WGPU_VALIDATION='1')
build=['cargo','nextest','list','--locked','--all-features','-p','wgpu-test','--test','wgpu-gpu','--message-format','json','--list-type','binaries-only']
meta=H/'sources/core-validation-binaries.json'
with meta.open('w') as out,(H/'logs/core-validation-build.log').open('w') as log:
    process=subprocess.run(build,cwd=R,env=env,stdout=out,stderr=log)
assert process.returncode==0,(H/'logs/core-validation-build.log').read_text()[-3000:]
build_output=(H/'logs/core-validation-build.log').read_text()
for name in ['wgpu-hal','wgpu-core','wgpu','wgpu-test','gpu-allocator']:
    assert 'Compiling '+name+' ' in build_output,name
data=json.loads(meta.read_text());binary=Path(data['rust-binaries']['wgpu-test::wgpu-gpu']['binary-path'])
frozen=H/'core-validation-bin'/binary.name;frozen.parent.mkdir();shutil.copyfile(binary,frozen)
cases=[r for r in json.loads((H/'control-comparison.json').read_text())['rows'] if r['binary']=='wgpu-test::wgpu-gpu' and '[Vulkan/' in r['name'] and any(x in r['name'] for x in ['::mesh_shader::','binding_array::tlas::binding_array_tlas','prevent_invalid_ray_query_calls'])]
assert len(cases)==10,len(cases)
escape=lambda s:s.replace('\\','\\\\').replace(')','\\)').replace(',','\\,').replace('/','\\/')
expression=' | '.join('(binary_id(='+escape(r['binary'])+') & test(='+escape(r['name'])+'))' for r in cases)
out=H/'core-validation-controls';out.mkdir();rows=[]
for trial in range(1,4):
    command=['cargo','nextest','run','--binaries-metadata',str(meta),'-E',expression,'--success-output','immediate']
    log=out/f'trial{trial}.log'
    with log.open('w') as stream:process=subprocess.run(command,cwd=R,env=env,stdout=stream,stderr=subprocess.STDOUT)
    junit=R/'target/nextest/default/junit.xml';shutil.copyfile(junit,out/f'trial{trial}.xml')
    root=ET.parse(junit).getroot();assert root.attrib['tests']=='10'
    text=log.read_text();assert text.count('CORE_ONLY_CONTROL: core=true gpuav=false')==10
    outcomes=[]
    for c in root.iter('testcase'):
        failure=c.find('failure')
        if failure is None:failure=c.find('error')
        outcomes.append({'name':c.attrib['name'],'failed':failure is not None,'type':None if failure is None else failure.attrib.get('type'),'details':None if failure is None else failure.text})
    rows.append({'trial':trial,'rc':process.returncode,'verified_core_true_gpuav_false_markers':10,'gpuav_enabled_layer_warning_present':'GPU-Assisted Validation (GPU-AV) is enabled' in text,'outcomes':outcomes})
    print('trial',trial,'failed',sum(r['failed'] for r in outcomes),flush=True)
record={'base':base,'control_change':'tests/src/init.rs clears GPU_BASED_VALIDATION after required test flags; core validation asserted enabled. Not a conformance configuration.','source_status':subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True),'lock_unchanged':(R/'Cargo.lock').read_bytes()==(H/'wgpu/upstream/Cargo.lock').read_bytes(),'allocator':'unmodified registry dependency, no override','our_wgpu_pr_patches':[],'build_command':build,'isolated_target':str(target),'excluded_seed_patterns':exclude,'verified_recompiled_local_crates':True,'binary_sha256':hashlib.sha256(frozen.read_bytes()).hexdigest(),'rows':rows}
assert record['lock_unchanged'] and record['source_status'].strip()=='M tests/src/init.rs',record['source_status']
(H/'core-validation-control.json').write_text(json.dumps(record,indent=2))
(H/'CORE_VALIDATION_COMPLETE').write_text('complete')
print('Complete verified core-only diagnostic control',flush=True)
