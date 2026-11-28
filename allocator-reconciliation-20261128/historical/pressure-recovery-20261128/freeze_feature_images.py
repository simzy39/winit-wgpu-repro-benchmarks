"""Copy generated feature screenshot evidence out of the mutable test worktree."""
from pathlib import Path
import shutil,json,hashlib
H=Path(__file__).resolve().parent;R=H/'wgpu/candidate/examples/features/src'
parents={p.parent for p in R.rglob('screenshot-*.png')}
rows=[]
for folder in sorted(parents):
    for source in sorted(folder.glob('screenshot*.png')):
        relative=source.relative_to(R);dest=H/'sources/final-feature-images'/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        rows.append({'path':relative.as_posix(),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'source_mtime_ns':source.stat().st_mtime_ns})
(H/'sources/final-feature-images.json').write_text(json.dumps({'scope':'Latest generated feature actual/difference screenshots plus colocated screenshot reference images, archived after geometric full suite; includes passing cases. Original logs record which cases failed.','files':rows},indent=2))
print('Archived feature screenshot files:',len(rows))
