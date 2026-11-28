"""Identical driver/request streams against actual exact and geometric allocators."""
import pathlib,subprocess,shutil,json,os
H=pathlib.Path(__file__).resolve().parent
body=r'''
#[test]
fn comparative_reduction_stream() {
    for scenario in ["count_limited","no_memory","large_resource"] {
        let mut allocator=fixture(&[(256*MIB,vk::MemoryPropertyFlags::DEVICE_LOCAL)],false);
        growable(&mut allocator,64*MIB,64*MIB);
        allocator.max_memory_allocation_count=if scenario=="count_limited" {2} else {4096};
        let budget=if scenario=="count_limited" {48*MIB} else if scenario=="no_memory" {0} else {12*MIB};
        DRIVER.with(|d|d.borrow_mut().limit=Some(budget));
        let count=if scenario=="count_limited" {48} else {1};
        let size=if scenario=="large_resource" {9*MIB} else {MIB};
        let mut live=Vec::new();
        for _ in 0..count {
            match allocator.allocate(&request(size,MemoryLocation::GpuOnly)) {
                Ok(allocation)=>live.push(allocation), Err(_)=>break,
            }
        }
        let calls=DRIVER.with(|d|d.borrow().calls.iter().map(|(_,size)|size/MIB).collect::<Vec<_>>());
        println!("REDUCTION_JSON {{\"scenario\":\"{}\",\"successes\":{},\"calls_mib\":{:?},\"capacity_mib\":{}}}",scenario,live.len(),calls,allocator.capacity()/MIB);
        for allocation in live {allocator.free(allocation).unwrap();}
        allocator.trim();
        assert!(DRIVER.with(|d|d.borrow().live.is_empty()));
    }
}
'''
rows=[];env=os.environ.copy();env['CARGO_BUILD_JOBS']='2'
for name,variant in [('exact','recovery'),('geometric','geometric')]:
    source=H/'work'/variant/'gpu-allocator';folder=H/'reduction-controls'/name
    shutil.copytree(source,folder,ignore=shutil.ignore_patterns('.git','target'),dirs_exist_ok=True)
    (folder/'Cargo.toml').write_text((folder/'Cargo.toml').read_text()+'\n[workspace]\n')
    shutil.copyfile(H/'work/recovery/Cargo.lock',folder/'Cargo.lock')
    s=(source/'src/vulkan/capacity_tests.rs').read_text()
    fixture=s[:s.index('\n#[test]')];a=s.index('fn growable(');grow=s[a:s.index('\n#[test]',a)]
    (folder/'src/vulkan/reduction_stream.rs').write_text(fixture+grow+body)
    with (folder/'src/vulkan/mod.rs').open('a') as f:f.write('\n#[cfg(all(test,feature="std"))]\nmod reduction_stream;\n')
    command=['cargo','test','--offline','--manifest-path',str(folder/'Cargo.toml'),'--no-default-features','--features','std,vulkan','--lib','comparative_reduction_stream','--target-dir',str(H/('target-reduction-'+name)),'--','--nocapture']
    with (H/'logs'/('reduction-'+name+'.log')).open('w') as log:p=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
    assert not p.returncode,(H/'logs'/('reduction-'+name+'.log')).read_text()[-5000:]
    for line in (H/'logs'/('reduction-'+name+'.log')).read_text().splitlines():
        if line.startswith('REDUCTION_JSON '):rows.append({'variant':name,**json.loads(line[len('REDUCTION_JSON '):])})
    (H/'reduction-actual.json').write_text(json.dumps(rows,indent=2));print(name,rows[-3:],flush=True)
assert rows[0]['successes']==2 and rows[3]['successes']==48
print('Actual allocators reproduce the count-limit and failure-cost tradeoff')
