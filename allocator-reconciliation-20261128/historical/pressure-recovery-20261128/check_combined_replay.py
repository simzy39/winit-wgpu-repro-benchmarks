"""Replay the combined wgpu export against its full clean source archive."""
from pathlib import Path
import subprocess,tarfile,io,json,shutil,os
H=Path(__file__).resolve().parent;W=H/'wgpu/candidate'
replay=H/'replay-combined-final';replay.mkdir(exist_ok=True)
def git(root,*args,input=None):
    p=subprocess.run(['git','-C',str(root),*args],input=input,capture_output=True)
    assert p.returncode==0,p.stderr.decode(errors='replace')
    return p.stdout
base='60cef2be828e03ba54e2e1598001b4625c0c2163'
with tarfile.open(fileobj=io.BytesIO(git(W,'archive',base))) as archive:
    # tarfile's directory-metadata pass retains POSIX separators, which Windows
    # rejects inside an extended path. Extract trusted git archive entries using
    # native paths throughout, without deleting the initial partial extraction.
    for member in archive:
        relative=Path(*member.name.split('/'))
        assert not relative.is_absolute() and '..' not in relative.parts
        dest=replay/relative
        native=lambda p:'\\\\?\\'+str(p.resolve())
        os.makedirs(native(dest if member.isdir() else dest.parent),exist_ok=True)
        if member.isdir():continue
        assert member.isfile(),member.name
        with archive.extractfile(member) as source, open(native(dest),'wb') as output:
            shutil.copyfileobj(source,output)
git(replay,'init','--quiet');git(replay,'config','core.longpaths','true')
patch=H/'patches/wgpu-combined-on-base-60cef2b.patch'
git(replay,'apply','--check',str(patch));git(replay,'apply',str(patch))
excluded={'.cargo/config.toml','Cargo.toml','Cargo.lock'}
files=[p for p in git(W,'ls-files').decode().splitlines() if p not in excluded]
def blobs(root):
    values=git(root,'hash-object','--stdin-paths',input=('\n'.join(files)+'\n').encode()).decode().splitlines()
    assert len(values)==len(files)
    return dict(zip(files,values))
expected=blobs(W);actual=blobs(replay);assert expected==actual
manifest=H/'patches/manifest.json';j=json.loads(manifest.read_text())
j[patch.name].update(apply_check=True,replay_equal_git_canonical_blobs=True,files_compared=len(files),excluded_local_testing_files=sorted(excluded))
manifest.write_text(json.dumps(j,indent=2))
changed=[p for p in git(W,'diff','--name-only',base,'--','.',':(exclude).cargo/config.toml',':(exclude)Cargo.toml',':(exclude)Cargo.lock').decode().splitlines()]
for name in changed:
    dest=H/'wgpu-source-changes'/name;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(W/name,dest)
(H/'wgpu-source-changes/README-review.txt').write_text('Complete changed files from wgpu combined patch on '+base+'; workspace dependency override, config and lock excluded. Final HAL-only followup is separately exported on PR11130.\n')
(H/'patches/wgpu-combined-source-blobs.json').write_text(json.dumps({p:expected[p] for p in changed},indent=2))
print({'combined_wgpu_apply':True,'files_compared':len(files),'changed_files':changed},flush=True)
