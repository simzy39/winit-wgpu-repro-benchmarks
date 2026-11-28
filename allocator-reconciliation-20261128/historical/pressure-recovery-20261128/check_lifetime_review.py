"""Run identical convenience-resource regressions against old and fixed source."""
from pathlib import Path
import shutil, subprocess, json, os, hashlib
H=Path(__file__).resolve().parent
fixed=H/'lifetime-review/gpu-allocator'
control=H/'lifetime-control/gpu-allocator'
assert not control.exists()
shutil.copytree(fixed.parent,control.parent)
shutil.copyfile(H/'candidate-source/src/d3d12/mod.rs',control/'src/d3d12/mod.rs')
rows=[];env=os.environ.copy();env['CARGO_BUILD_JOBS']='2'
for name,root,extra,expected in [
    ('lifetime-control',control,['test','--lib','creation'],101),
    ('lifetime-review',fixed,['test','--lib'],0),
    ('lifetime-clippy',fixed,['clippy','--all-targets'],0),
]:
    command=['cargo',extra[0],'--offline','-p','gpu-allocator','--no-default-features','--features','std,vulkan,d3d12',*extra[1:],'--target-dir',str(H/('target-'+name))]
    if extra[0]=='clippy':command+=['--','-D','warnings']
    with (H/'logs'/(name+'-comparison.log')).open('w') as log:
        p=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
    rows.append({'name':name,'command':command,'rc':p.returncode,'expected':expected,'source_sha256':hashlib.sha256((root/'src/d3d12/mod.rs').read_bytes()).hexdigest(),'tests_sha256':hashlib.sha256((root/'src/d3d12/pressure_tests.rs').read_bytes()).hexdigest()})
    (H/'lifetime-comparison.json').write_text(json.dumps(rows,indent=2))
    print(name,p.returncode,flush=True)
    assert p.returncode==expected
print('EXPECTED control fails; fixed source passes identical regressions',flush=True)
