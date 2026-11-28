import pathlib,subprocess,os,json,shutil
H=pathlib.Path(__file__).resolve().parent
rows=[];env=os.environ.copy();env['CARGO_BUILD_JOBS']='2'
for name,features,target in [('metal','std,metal','aarch64-apple-darwin'),('visualizer','std,vulkan,visualizer',None)]:
    folder=H/'msrv-extra'/name;(folder/'src').mkdir(parents=True,exist_ok=True)
    path=str(H/'work/recovery/gpu-allocator').replace('\\','/')
    manifest='[package]\nname="msrv-extra"\nversion="0.0.0"\nedition="2021"\nrust-version="1.71"\n[workspace]\n[dependencies]\n'
    manifest+='gpu-allocator={path="'+path+'",default-features=false,features=['+','.join('"'+x+'"' for x in features.split(','))+']}\nthiserror={version="=2.0.20",default-features=false}\n'
    (folder/'Cargo.toml').write_text(manifest);(folder/'src/lib.rs').write_text('pub fn sizes()->gpu_allocator::AllocationSizes {gpu_allocator::AllocationSizes::default()}\n')
    command=['cargo','+stable','generate-lockfile','--offline','--manifest-path',str(folder/'Cargo.toml')]
    p=subprocess.run(command,env=env,capture_output=True,text=True);output=p.stdout+p.stderr
    assert not p.returncode,output
    lock=folder/'Cargo.lock';lock.write_text(lock.read_text().replace('version = 4\n','version = 3\n',1))
    command=['cargo','+1.71.0','check','--offline','--locked','--lib','--manifest-path',str(folder/'Cargo.toml')]
    if target:command.extend(['--target',target])
    p=subprocess.run(command,env=env,capture_output=True,text=True);output+=p.stdout+p.stderr
    (H/'logs'/('msrv-extra-'+name+'.log')).write_text(output)
    rows.append({'name':name,'command':command,'rc':p.returncode});(H/'msrv-extra-results.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
(H/'MSRV_EXTRA_COMPLETE').write_text('complete')
