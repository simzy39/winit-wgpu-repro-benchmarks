"""Create and independently read back a scoped evidence manifest; no cache deletion."""
from pathlib import Path
import os,hashlib,json,datetime
H=Path(__file__).resolve().parent
def digest(p):
    sha=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):sha.update(chunk)
    return sha.hexdigest()
files=[]
for directory,dirs,names in os.walk(H):
    relative=Path(directory).relative_to(H)
    dirs[:]=[d for d in dirs if d not in {'.git','__pycache__','target'} and not d.startswith('target-')]
    if relative==Path('.'):
        dirs[:]=[d for d in dirs if d not in {'work','wgpu'} and not d.startswith('replay')]
    if relative.parts and relative.parts[0] in {'path-controls','identity-controls','gpuav-controls'}:
        dirs[:]=[d for d in dirs if d!='bin']
    for name in names:
        p=Path(directory)/name;rel=p.relative_to(H)
        if name in {'.git','EVIDENCE.sha256','evidence-integrity.json'} or p.suffix=='.pyc':continue
        if rel.parts[0] in {'bin','bin-wgpu'} and p.suffix.lower() in {'.exe','.dll','.pdb'}:continue
        files.append(p)
files.sort(key=lambda p:p.relative_to(H).as_posix())
rows=[(digest(p),p.relative_to(H).as_posix()) for p in files]
manifest=H/'EVIDENCE.sha256'
manifest.write_text(''.join(f'{sha}  {name}\n' for sha,name in rows),encoding='utf-8')
failures=[name for expected,name in rows if digest(H/name)!=expected]
assert not failures,failures
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest':'EVIDENCE.sha256','sha256':digest(manifest),'files':len(rows),'bytes':sum(p.stat().st_size for p in files),'read_back_failures':failures,'scope':'EVIDENCE_SCOPE.md','previous_manifests':'prior-integrity-final.json','repository_and_source_checks':'final-boundary-audit.json'}
(H/'evidence-integrity.json').write_text(json.dumps(receipt,indent=2))
print(receipt,flush=True)
