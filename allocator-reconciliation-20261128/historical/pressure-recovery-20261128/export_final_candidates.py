"""Preserve earlier replay trees, then export the final backoff candidate."""
from pathlib import Path
import shutil,subprocess,json,hashlib,os
H=Path(__file__).resolve().parent
env=os.environ.copy();env.setdefault('GPUA_REPLAY_SUBDIR','replay-backoff')
subprocess.run(['python',str(H/'export_candidates.py')],check=True,env=env)
R=H/'work/recovery/gpu-allocator'
files=subprocess.check_output(['git','-C',str(R),'ls-files'],text=True).splitlines()
for relative in files:
    dest=H/'candidate-source'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(R/relative,dest)
out=H/'repro-inputs';out.mkdir(exist_ok=True)
for source,name in [(H/'work/recovery/bench/src/main.rs','bench.rs'),(H/'work/recovery/bench/Cargo.toml','bench.Cargo.toml'),(H/'work/recovery/Cargo.lock','bench.Cargo.lock')]:shutil.copyfile(source,out/name)
for name in ['cache2-both','recovery-both','recovery-candidate','recovery-singlepool']:
    folder=out/'wgpu'/name;(folder/'src').mkdir(parents=True,exist_ok=True)
    for file in ['Cargo.toml','Cargo.lock','src/main.rs']:shutil.copyfile(H/'downstream'/name/file,folder/file)
print('Exported final patches, complete standalone allocator source and reproduction inputs')
