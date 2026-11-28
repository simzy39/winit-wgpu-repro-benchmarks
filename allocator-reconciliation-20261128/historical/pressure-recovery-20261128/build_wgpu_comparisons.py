import pathlib,subprocess,shutil,os,json,hashlib
H=pathlib.Path(__file__).resolve().parent
env=os.environ.copy();env['CARGO_BUILD_JOBS']='2'
out=H/'bin-wgpu';out.mkdir(exist_ok=True)
target=H/'target-wgpu-bench'
for name in ['cache2-both','recovery-both','recovery-candidate','recovery-singlepool']:
    folder=H/'downstream'/name
    clean=['cargo','clean','--target-dir',str(target)]
    for package in ['gpu-allocator','wgpu-hal','wgpu-core','wgpu','wgpu-mem-bench']:clean.extend(['-p',package])
    commands=[clean,['cargo','build','--release','--locked','--offline','--target-dir',str(target)]]
    for phase,command in enumerate(commands):
        with (H/'logs'/('wgpu-build-'+name+'-'+str(phase)+'.log')).open('w') as log:p=subprocess.run(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT)
        assert not p.returncode,name
    exe=out/(name+'.exe');shutil.copyfile(target/'release/wgpu-mem-bench.exe',exe)
    meta={'name':name,'commands':commands,'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'lock_sha256':hashlib.sha256((folder/'Cargo.lock').read_bytes()).hexdigest()}
    (out/(name+'.json')).write_text(json.dumps(meta,indent=2));print('Built '+name,flush=True)
(H/'WG_BUILDS_COMPLETE').write_text('complete')
