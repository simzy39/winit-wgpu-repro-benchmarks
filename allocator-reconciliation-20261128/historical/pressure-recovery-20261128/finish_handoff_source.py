"""Adopt the proven convenience-API fix after the native suite stops using its source."""
from pathlib import Path
import time, shutil, subprocess, json, os, hashlib
H=Path(__file__).resolve().parent
while not (H/'BACKOFF_WGPU_COMPLETE').exists():time.sleep(10)
rows=json.loads((H/'lifetime-comparison.json').read_text())
assert len(rows)==3 and all(r['rc']==r['expected'] for r in rows)
R=H/'work/recovery/gpu-allocator'
shutil.copytree(H/'candidate-source',H/'measurement-sources/backoff-final')
shutil.copytree(H/'patches',H/'patches-backoff-stage')
def hashes():
    return {str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in R.rglob('*') if p.is_file() and '.git' not in p.parts}
before=hashes()
old=(R/'src/d3d12/mod.rs').read_text()
for name in ['src/d3d12/mod.rs','src/d3d12/pressure_tests.rs']:
    shutil.copyfile(H/'lifetime-review/gpu-allocator'/name,R/name)
after=hashes();new=(R/'src/d3d12/mod.rs').read_text()
assert old[:old.index('    pub fn create_resource(')]==new[:new.index('    pub fn create_resource(')]
assert old[old.index('    pub fn free_resource('):]==new[new.index('    pub fn free_resource('):]
receipt={'before':before,'after':after,'changed':[p for p in before if before[p]!=after[p]],
    'production_delta':'D3D12 create_resource only; allocate/free/recovery and all other backends identical',
    'full_wgpu_source':'measurement-sources/backoff-final',
    'reason_no_full_suite_repetition':'wgpu DX12 uses gpu_allocator allocate/free, not its convenience create_resource API; same production allocation path. Final convenience API has identical-driver controls and full allocator checks.'}
(H/'handoff-source-delta.json').write_text(json.dumps(receipt,indent=2))
assert set(receipt['changed'])=={'src\\d3d12\\mod.rs','src\\d3d12\\pressure_tests.rs'}
s=(H/'check_final_source.py').read_text().replace('final-source-','handoff-source-').replace('FINAL_SOURCE_CHECKS_COMPLETE','HANDOFF_SOURCE_CHECKS_COMPLETE')
exec(compile(s,str(H/'check_final_source.py'),'exec'))
env=os.environ.copy();env.update(CARGO_BUILD_JOBS='2')
command=['cargo','clippy','--offline','-p','gpu-allocator','--no-default-features','--features','std,vulkan,d3d12,visualizer','--all-targets','--target-dir',str(H/'target-allocator'),'--','-D','warnings']
with (H/'logs/handoff-visualizer-clippy.log').open('w') as log:
    p=subprocess.run(command,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
(H/'handoff-visualizer-clippy.json').write_text(json.dumps({'command':command,'rc':p.returncode},indent=2))
assert p.returncode==0
env['GPUA_REPLAY_SUBDIR']='replay-handoff'
subprocess.run(['python',str(H/'export_final_candidates.py')],env=env,check=True)
(H/'HANDOFF_SOURCE_COMPLETE').write_text('complete')
print('Final convenience-resource fix adopted, checked and exported',flush=True)
