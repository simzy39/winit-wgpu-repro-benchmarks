"""Relevant checks against the final candidate, with persistent individual logs."""
import pathlib,subprocess,os,json,time
H=pathlib.Path(__file__).resolve().parent;P=H.parent/'reassessment-20261128'
old=json.loads((P/'validation.json').read_text())
checks=[]
for row in old:
    command=[x.replace(str(P/'target-validation'),str(H/'target-allocator')) for x in row['command']]
    checks.append((row['name'],command))
command=next(c for n,c in checks if n=='unit-std')
checks.insert(2,('unit-nostd',[x.replace('std,vulkan,d3d12','hashbrown,vulkan,d3d12') for x in command]))
env=os.environ.copy();env['RUSTDOCFLAGS']='-D warnings';env['CARGO_BUILD_JOBS']='2'
rows=[]
for name,command in checks:
    start=time.perf_counter()
    with (H/'logs'/('validation-'+name+'.log')).open('w') as log:
        p=subprocess.run(command,cwd=H/'work/recovery/gpu-allocator',env=env,stdout=log,stderr=subprocess.STDOUT)
    rows.append({'name':name,'command':command,'rc':p.returncode,'wall_s':time.perf_counter()-start})
    (H/'validation.json').write_text(json.dumps(rows,indent=2));print(name,p.returncode,flush=True)
(H/'VALIDATION_COMPLETE').write_text('complete')
