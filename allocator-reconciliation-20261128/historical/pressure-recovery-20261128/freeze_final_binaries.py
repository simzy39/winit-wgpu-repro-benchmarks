"""Preserve final plan-check and native GPU artifacts before any future rebuild."""
from pathlib import Path
import shutil,hashlib,json
H=Path(__file__).resolve().parent
plan=H/'target-backoff-final/release/gpua-policy-bench.exe'
expected=json.loads((H/'backoff-plan-verification.json').read_text())['exe_sha256']
assert hashlib.sha256(plan.read_bytes()).hexdigest()==expected
dest=H/'bin-final/backoff-plan-only.exe';assert not dest.exists();shutil.copyfile(plan,dest)
gpu=H/'wgpu/upstream/target/debug/deps/wgpu_gpu-4022cdc0eaa67d81.exe'
folder=H/'candidate-control-bin';folder.mkdir(exist_ok=True)
shutil.copyfile(gpu,folder/gpu.name)
(H/'sources/final-frozen-binaries.json').write_text(json.dumps({
    'backoff_plan':{'path':str(dest.relative_to(H)),'sha256':expected,'source':'measurement-sources/backoff-final; six verification processes, not five-trial timings'},
    'native_gpu':{'path':str((folder/gpu.name).relative_to(H)),'sha256':hashlib.sha256(gpu.read_bytes()).hexdigest(),'origin':str(gpu),'source_mtime_ns':gpu.stat().st_mtime_ns,'scope':'GPU binary compiled immediately before final geometric full suite. Clean upstream binary df9c6ae37ba8f6de remains separately frozen. No rebuild since final full run.'}
},indent=2))
print('Froze final plan/native GPU binaries')
