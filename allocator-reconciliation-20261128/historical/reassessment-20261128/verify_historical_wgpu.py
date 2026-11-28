"""Read-only verification of published historical wgpu benchmark artifacts."""
import pathlib,subprocess,json,hashlib
H=pathlib.Path(__file__).resolve().parent
OLD=H.parent.parent/"winit-wgpu"
R=OLD/"public-repro"
suites=["gpu-allocator-323","wgpu-11129","wgpu-11130"]
raw=subprocess.check_output(["git","-C",str(R),"ls-files","--stage","-z","--",*[f"results/{s}" for s in suites]])
entries=[]
for entry in raw.split(b"\0"):
    if not entry:continue
    metadata,path=entry.split(b"\t",1)
    mode,oid,stage=metadata.decode().split()
    assert stage=="0"
    entries.append((path.decode(),oid))
assert entries
p=subprocess.run(["git","-C",str(R),"hash-object","--stdin-paths"],input="".join(path+"\n" for path,_ in entries),
    capture_output=True,text=True,check=True)
actual=p.stdout.splitlines()
assert len(actual)==len(entries)
failures=[path for (path,expected),got in zip(entries,actual) if expected!=got]
compared=equal=0
for relative,_ in entries:
    path=R/relative
    if path.suffix!=".json":continue
    suite=path.parts[path.parts.index("results")+1]
    local=OLD/"logs-isolated"/suite/path.name
    if local.exists():
        compared+=1;equal+=json.loads(local.read_text())==json.loads(path.read_text())
out={"published_head":subprocess.check_output(["git","-C",str(R),"rev-parse","HEAD"],text=True).strip(),
     "tracked_files_checked":len(entries),"git_blob_mismatches":failures,
     "local_raw_json_comparisons":compared,"local_raw_json_equal":equal,
     "status":subprocess.check_output(["git","-C",str(R),"status","--short","--branch"],text=True)}
(H/"historical-wgpu-integrity.json").write_text(json.dumps(out,indent=2))
print(out)
assert not failures

