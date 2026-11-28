import pathlib,subprocess,os,json,time
H=pathlib.Path(__file__).resolve().parent
old=json.loads((H/'validation.json').read_text())
checks=[r for r in old if r['rc'] or r['name'] in ['fmt','unit-std','unit-nostd','rustdoc','metal-intel']]
env=os.environ.copy();env['RUSTDOCFLAGS']='-D warnings';env['CARGO_BUILD_JOBS']='2'
rows=[]
for row in checks:
    name=row['name'];command=row['command'];start=time.perf_counter()
    with (H/'logs'/('validation-recheck-'+name+'.log')).open('w') as log:p=subprocess.run(command,cwd=H/'work/recovery/gpu-allocator',env=env,stdout=log,stderr=subprocess.STDOUT)
    rows.append({'name':name,'command':command,'rc':p.returncode,'wall_s':time.perf_counter()-start})
    (H/'validation-recheck.json').write_text(json.dumps(rows,indent=2));print(name,p.returncode,flush=True)
(H/'REVALIDATION_COMPLETE').write_text('complete')
