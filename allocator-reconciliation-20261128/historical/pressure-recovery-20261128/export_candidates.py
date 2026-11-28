"""Export complete review patches and replay them without committing anything."""
import pathlib,subprocess,json,hashlib,tarfile,io,difflib,os
H=pathlib.Path(__file__).resolve().parent;R=H/'work/recovery/gpu-allocator';W=H/'wgpu/candidate'
replay_root=H/os.environ.get('GPUA_REPLAY_SUBDIR','replay')
out=H/'patches';out.mkdir(exist_ok=True)
def git(repo,*args,input=None):
    p=subprocess.run(['git','-C',str(repo),*args],input=input,capture_output=True)
    assert not p.returncode,p.stderr.decode(errors='replace')
    return p.stdout
git(R,'add','--intent-to-add','--','src/vulkan/capacity_tests.rs','src/d3d12/pressure_tests.rs')
files=git(R,'ls-files').decode().splitlines()
def blobs(repo,files):
    values=git(repo,'hash-object','--stdin-paths',input=('\n'.join(files)+'\n').encode()).decode().splitlines()
    assert len(values)==len(files)
    return dict(zip(files,values))
expected=blobs(R,files);records={}
for base,label in [('179ea43f05332c2809addd7922cd056220efc36b','pr323-179ea43'),('fc22df05140b15ed6d764beabd12a1b807011bc5','main-fc22df0')]:
    patch=git(R,'diff','--binary',base);name='candidate-on-'+label+'.patch';path=out/name;path.write_bytes(patch)
    replay=replay_root/label;assert not replay.exists();replay.mkdir(parents=True)
    archive=git(R,'archive',base)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:source.extractall(replay,filter='data')
    git(replay,'init','--quiet')
    git(replay,'apply','--check',str(path));git(replay,'apply',str(path))
    actual=blobs(replay,files);assert actual==expected
    records[name]={'base':base,'sha256':hashlib.sha256(patch).hexdigest(),'apply_check':True,'replay_equal_git_canonical_blobs':True,'files_compared':len(files)}
# The two HAL files from the prior combined experiment exactly match PR11130's head.
base='22827ee25285b56c4056fe6bb1de27917caf45a9'
patch=git(W,'diff','--binary',base,'--','wgpu-hal/src/dx12/suballocation.rs')
name='wgpu-pressure-followup-on-pr11130-22827ee.patch';(out/name).write_bytes(patch)
before=git(W,'show',base+':wgpu-hal/src/dx12/suballocation.rs')
replay=replay_root/'wgpu-pr11130';(replay/'wgpu-hal/src/dx12').mkdir(parents=True)
(replay/'wgpu-hal/src/dx12/suballocation.rs').write_bytes(before);git(replay,'init','--quiet')
git(replay,'apply','--check',str(out/name));git(replay,'apply',str(out/name))
assert blobs(replay,['wgpu-hal/src/dx12/suballocation.rs'])==blobs(W,['wgpu-hal/src/dx12/suballocation.rs'])
records[name]={'base':base,'scope':'HAL followup only; requires new allocator APIs; no lazy-allocation prerequisite','sha256':hashlib.sha256(patch).hexdigest(),'apply_check':True,'replay_equal_git_canonical_blobs':True}
base='60cef2be828e03ba54e2e1598001b4625c0c2163'
patch=git(W,'diff','--binary',base,'--','.',':(exclude).cargo/config.toml',':(exclude)Cargo.toml',':(exclude)Cargo.lock')
name='wgpu-combined-on-base-60cef2b.patch';(out/name).write_bytes(patch)
records[name]={'base':base,'scope':'Both PRs, earlier regression checks and new HAL followup; test-only path override and lock excluded','sha256':hashlib.sha256(patch).hexdigest()}
for variant in ['smallcache','heapcap','packed']:
    repo=H/'work'/variant/'gpu-allocator'
    git(repo,'add','--intent-to-add','--','src/vulkan/capacity_tests.rs','src/d3d12/pressure_tests.rs')
    patch=git(repo,'diff','--binary','179ea43f05332c2809addd7922cd056220efc36b')
    name='experiment-'+variant+'-on-pr323.patch';(out/name).write_bytes(patch)
    records[name]={'base':'179ea43f05332c2809addd7922cd056220efc36b','scope':'Measured experimental implementation, not proposed default','sha256':hashlib.sha256(patch).hexdigest()}
(out/'manifest.json').write_text(json.dumps(records,indent=2))
(out/'candidate-source-blobs.json').write_text(json.dumps(expected,indent=2))
print(json.dumps(records,indent=2))
