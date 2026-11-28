"""Align the pool rationale with the new bounded cache; no executable-code changes."""
from pathlib import Path
import hashlib,json,subprocess,os
H=Path(__file__).resolve().parent
p=H/'wgpu/candidate/wgpu-hal/src/dx12/suballocation.rs';old=p.read_bytes()
before='''/// `gpu-allocator` frees a block only after every allocation in it is freed (and
/// retains the last general block of each memory type), so short-lived resources
/// such as staging buffers use their own pool with smaller minimum block sizes.'''
after='''/// `gpu-allocator` releases a shared block only after every allocation in it is freed,
/// and may cache an empty block. Short-lived resources such as staging buffers use
/// their own pool with smaller minimum block sizes to avoid growing the general pool.'''
s=p.read_text();assert s.count(before)==1
(H/'sources/wgpu-full-suballocation.rs').write_bytes(old)
p.write_text(s.replace(before,after))
(H/'sources/wgpu-comment-delta.json').write_text(json.dumps({'before_sha256':hashlib.sha256(old).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scope':'Three documentation comment lines only; no executable code changes after the native suite.'},indent=2))
env=os.environ.copy();env['GPUA_REPLAY_SUBDIR']='replay-final'
subprocess.run(['python',str(H/'export_final_candidates.py')],env=env,check=True)
