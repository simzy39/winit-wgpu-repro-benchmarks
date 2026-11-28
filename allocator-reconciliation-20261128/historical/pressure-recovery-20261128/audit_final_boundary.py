"""Read-only original-repository/vendor inventory and final candidate checks."""
from pathlib import Path
import json,subprocess,hashlib,datetime
H=Path(__file__).resolve().parent
commands={'head':['rev-parse','HEAD'],'status':['status','--short','--branch'],'diff':['diff','--stat'],'refs':['show-ref']}
initial=json.loads((H/'initial-repositories.json').read_text());current={};changes=[]
for path,old in initial.items():
    current[path]={key:subprocess.check_output(['git','-C',path,*args],text=True) for key,args in commands.items()}
    changes.extend({'repository':path,'field':key} for key in old if old[key]!=current[path][key])
assert not changes,changes
start=datetime.datetime.fromisoformat((H/'BOOTSTRAP_COMPLETE').read_text()).timestamp()
vendor=H.parents[3]/'vendor'
assert vendor.is_dir(),vendor
inventory=[]
for p in sorted(vendor.rglob('*')):
    if not p.is_file():continue
    sha=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):sha.update(chunk)
    stat=p.stat()
    inventory.append({'path':str(p.relative_to(vendor)),'sha256':sha.hexdigest(),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns})
newer=[r['path'] for r in inventory if r['mtime_ns']/1e9>start]
(H/'sources/vendor-final-inventory.json').write_text(json.dumps({'root':str(vendor),'files':inventory,'modified_since_continuation_bootstrap':newer,'limit':'Final hashes/timestamps, not a retroactive pre-continuation hash baseline. No task tool writes targeted vendor.'},indent=2))
patches=json.loads((H/'patches/manifest.json').read_text())
for name,row in patches.items():assert hashlib.sha256((H/'patches'/name).read_bytes()).hexdigest()==row['sha256']
R=H/'work/recovery/gpu-allocator';files=subprocess.check_output(['git','-C',str(R),'ls-files'],text=True).splitlines()
assert len(files)==36
assert all((R/p).read_bytes()==(H/'candidate-source'/p).read_bytes() for p in files)
for p in (H/'patches').glob('*.patch'):
    assert b'<drive>/codex projects' not in p.read_bytes() and b'<drive>/codex projects' not in p.read_bytes(),p
assert b'diff --git a/Cargo.toml' not in (H/'patches/wgpu-combined-on-base-60cef2b.patch').read_bytes()
assert patches['wgpu-combined-on-base-60cef2b.patch']['files_compared']==2757
assert patches['wgpu-combined-on-base-60cef2b.patch']['replay_equal_git_canonical_blobs']
wgpu_blobs=json.loads((H/'patches/wgpu-combined-source-blobs.json').read_text())
assert len(wgpu_blobs)==7
assert all((H/'wgpu-source-changes'/p).read_bytes()==(H/'wgpu/candidate'/p).read_bytes() for p in wgpu_blobs)
assert '43 passed; 0 failed' in (H/'logs/handoff-source-unit-std.log').read_text()
assert '10 passed; 0 failed' in (H/'logs/handoff-source-unit-nostd.log').read_text()
assert all(r['rc']==0 for r in json.loads((H/'handoff-source-checks.json').read_text()))
assert json.loads((H/'handoff-visualizer-clippy.json').read_text())['rc']==0
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'repository_changes':changes,'repositories':current,'patches':patches,'exported_source_files':len(files),'exported_source_byte_equality':True,'wgpu_changed_files_byte_equal':len(wgpu_blobs),'vendor_files':len(inventory),'vendor_files_newer_than_bootstrap':newer,'vendor_inventory':'sources/vendor-final-inventory.json','candidate_worktree':'detached; modifications and intent-to-add test files only; no commits'}
(H/'final-boundary-audit.json').write_text(json.dumps(result,indent=2))
print({'original_repositories_unchanged':len(current),'source_files':len(files),'vendor_files':len(inventory),'vendor_files_newer_than_bootstrap':len(newer)},flush=True)
