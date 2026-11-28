"""Read-only hash verification of both earlier research bundles."""
import pathlib,json,hashlib,datetime
H=pathlib.Path(__file__).resolve().parent
rows=[]
for root in [H.parent,H.parent/"reassessment-20261128"]:
    entries=[]
    for line in (root/"EVIDENCE.sha256").read_text().splitlines():
        expected,name=line.split(maxsplit=1);name=name.lstrip("*")
        sha=hashlib.sha256()
        with (root/name).open("rb") as stream:
            for chunk in iter(lambda:stream.read(8*1024*1024),b""):sha.update(chunk)
        if sha.hexdigest()!=expected:entries.append(name)
    rows.append({"root":str(root),"files":len((root/"EVIDENCE.sha256").read_text().splitlines()),"failures":entries})
(H/"prior-integrity.json").write_text(json.dumps({"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"bundles":rows},indent=2))
assert not any(r["failures"] for r in rows)
print(rows,flush=True)
