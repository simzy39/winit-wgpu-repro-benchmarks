import pathlib,subprocess,os,json,time
H=pathlib.Path(__file__).resolve().parent;R=H/'work/recovery/gpu-allocator';target=str(H/'target-allocator')
checks=[]
for name,verb,features,extra in [('unit-std','test','std,vulkan,d3d12',['--lib']),('unit-nostd','test','hashbrown,vulkan,d3d12',['--lib']),('clippy-std','clippy','std,vulkan,d3d12',['--all-targets']),('clippy-nostd','clippy','hashbrown,vulkan,d3d12',['--lib'])]:
    command=['cargo',verb,'--offline','-p','gpu-allocator','--no-default-features','--features',features,*extra,'--target-dir',target]
    if verb=='clippy':command+=['--','-D','warnings']
    checks.append((name,command,R))
for name,verb,triple in [('metal-arm','clippy','aarch64-apple-darwin'),('metal-intel','check','x86_64-apple-darwin')]:
    command=['cargo',verb,'--offline','-p','gpu-allocator','--no-default-features','--features','std,metal','--lib','--target',triple,'--target-dir',target]
    if verb=='clippy':command+=['--','-D','warnings']
    checks.append((name,command,R))
for mode in ['std-vulkan','std-d3d12','nostd-vulkan']:
    checks.append(('msrv-'+mode,['cargo','+1.71.0','check','--offline','--locked','--lib','--manifest-path',str(H/'msrv-final'/('recovery-'+mode)/'Cargo.toml')],H))
checks.append(('msrv-metal',['cargo','+1.71.0','check','--offline','--locked','--lib','--target','aarch64-apple-darwin','--manifest-path',str(H/'msrv-extra/metal/Cargo.toml')],H))
checks.append(('rustdoc',['cargo','doc','--offline','-p','gpu-allocator','--no-deps','--no-default-features','--features','std,vulkan,d3d12','--document-private-items','--target-dir',target],R))
checks.append(('fmt',['cargo','fmt','-p','gpu-allocator','--','--check'],R))
rows=[];env=os.environ.copy();env.update(CARGO_BUILD_JOBS='2',RUSTDOCFLAGS='-D warnings')
for name,command,cwd in checks:
    start=time.perf_counter();log=H/'logs'/('final-source-'+name+'.log')
    with log.open('w') as stream:p=subprocess.run(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
    rows.append({'name':name,'command':command,'rc':p.returncode,'wall_s':time.perf_counter()-start});(H/'final-source-checks.json').write_text(json.dumps(rows,indent=2));print(name,p.returncode,flush=True)
    if p.returncode:print(log.read_text()[-3500:],flush=True)
assert all(r['rc']==0 for r in rows)
(H/'FINAL_SOURCE_CHECKS_COMPLETE').write_text('complete')
