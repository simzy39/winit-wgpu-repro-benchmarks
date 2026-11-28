"""The same faulting Vulkan driver and request stream against old and new sources."""
import pathlib,shutil,subprocess,json,os
H=pathlib.Path(__file__).resolve().parent
source=(H/'work/recovery/gpu-allocator/src/vulkan/capacity_tests.rs').read_text()
fixture=source[:source.index('\n#[test]')]
grow=source[source.index('fn growable('):source.index('\n#[test]',source.index('fn growable('))]
test=r'''
#[test]
fn comparative_pressure_stream() {
    for scenario in ["cross_type_cache","minimum_fallback","fatal_error"] {
        let flags=vk::MemoryPropertyFlags::DEVICE_LOCAL;
        let host=vk::MemoryPropertyFlags::HOST_VISIBLE|vk::MemoryPropertyFlags::HOST_COHERENT;
        let mut allocator=fixture(&[(256*MIB,flags),(256*MIB,host)],false);
        growable(&mut allocator,8*MIB,64*MIB);
        let anchor=if scenario=="cross_type_cache" {
            let anchor=allocator.allocate(&request(MIB,MemoryLocation::GpuOnly)).unwrap();
            let cached=allocator.allocate(&request(MIB,MemoryLocation::CpuToGpu)).unwrap();
            allocator.free(cached).unwrap();Some(anchor)
        } else {None};
        DRIVER.with(|d| {
            let mut d=d.borrow_mut();d.limit=Some(if scenario=="cross_type_cache" {24*MIB} else {12*MIB});
            if scenario=="fatal_error" {d.errors.push_back(vk::Result::ERROR_DEVICE_LOST);}
        });
        let size=if scenario=="cross_type_cache" {8*MIB} else {9*MIB};
        let result=allocator.allocate(&request(size,MemoryLocation::GpuOnly));
        let (calls,freed,live) = DRIVER.with(|d| {let d=d.borrow();(d.calls.clone(),d.freed,d.live.values().sum::<u64>())});
        println!("PRESSURE_JSON {{\"scenario\":\"{}\",\"success\":{},\"calls\":{:?},\"freed\":{},\"native_live_bytes\":{}}}",scenario,result.is_ok(),calls,freed,live);
        if let Ok(allocation)=result {allocator.free(allocation).unwrap();}
        if let Some(anchor)=anchor {allocator.free(anchor).unwrap();}
        drop(allocator);
        assert!(DRIVER.with(|d|d.borrow().live.is_empty()));
    }
}
'''
env=os.environ.copy();env['CARGO_BUILD_JOBS']='2'
rows=[]
for name in ['cache2','recovery']:
    folder=H/'pressure-controls'/name
    shutil.copytree(H/'work'/name/'gpu-allocator',folder,ignore=shutil.ignore_patterns('.git','target'),dirs_exist_ok=True)
    (folder/'Cargo.toml').write_text((folder/'Cargo.toml').read_text()+'\n[workspace]\n')
    shutil.copyfile(H/'work/recovery/Cargo.lock',folder/'Cargo.lock')
    body=fixture+grow+test
    if name=='cache2':body=body.replace('            active_blocks: 0,\n','').replace('        max_memory_allocation_count: 4096,\n','')
    (folder/'src/vulkan/comparative_pressure.rs').write_text(body)
    with (folder/'src/vulkan/mod.rs').open('a') as f:f.write('\n#[cfg(all(test,feature="std"))]\nmod comparative_pressure;\n')
    command=['cargo','test','--offline','--manifest-path',str(folder/'Cargo.toml'),'--no-default-features','--features','std,vulkan','--lib','comparative_pressure_stream','--target-dir',str(H/'target-pressure-controls'),'--','--nocapture']
    p=subprocess.run(command,env=env,capture_output=True,text=True)
    (H/'logs'/('pressure-control-'+name+'.log')).write_text(p.stdout+p.stderr)
    assert not p.returncode,p.stderr
    for line in p.stdout.splitlines():
        if line.startswith('PRESSURE_JSON '):
            row=json.loads(line[len('PRESSURE_JSON '):].replace('(','[').replace(')',']'));row['variant']=name;rows.append(row)
    (H/'pressure-comparison.json').write_text(json.dumps(rows,indent=2));print(name,rows[-3:],flush=True)
print('Compared identical request streams with a bounded fake driver')
