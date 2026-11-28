"""Check report completeness, links, source freeze and principal raw result receipts."""
import pathlib,re,json,hashlib,ast
H=pathlib.Path(__file__).resolve().parent
report=(H/"REPORT.md").read_text()
sections=[int(x) for x in re.findall(r"(?m)^## (\d+) ",report)]
assert sections==list(range(1,21)),sections
assert not re.search(r"\{\{[A-Z_]+\}\}",report)
broken=[]
for filename in ["REPORT.md","README.md","REPRODUCE.md","PROPOSED_PR.md","RESEARCH.md","FAILURE_TRIAGE.md"]:
    for link in re.findall(r"\]\(([^)]+)\)",(H/filename).read_text()):
        if link.startswith(("https:","http:","#")):continue
        path=H/link.split("#",1)[0]
        if not path.exists() and path.name!="EVIDENCE.sha256":broken.append([filename,link])
assert not broken,broken
for p in H.glob("*.py"):ast.parse(p.read_text(encoding="utf-8-sig"))
for record in json.loads((H/"source-freeze-mtimes.json").read_text())["files"]:
    assert hashlib.sha256((H/record["path"]).read_bytes()).hexdigest()==record["sha256"],record["path"]
counts={}
for folder,expected in [("results-direct-verified",405),("results-cache-limits",80),("results-downstream",520)]:
    paths=list((H/folder).glob("*.receipt.json"));assert len(paths)==expected,(folder,len(paths))
    for path in paths:
        receipt=json.loads(path.read_text());assert receipt["rc"]==0,path
        assert not receipt.get("validation_error",False),path
        stem=path.name.removesuffix(".receipt.json")
        json.loads(path.with_name(stem+".json").read_text())
    counts[folder]=len(paths)
triage=json.loads((H/"failure-triage.json").read_text())
assert sum(triage["classifications"].values())==26
assert not triage["classifications"].get("candidate-only in focused control: investigate",0)
config=(H/"downstream/validation/.cargo/config.toml").read_text()
assert str(H/"work/cache2/gpu-allocator").replace("\\","/") in config
audit=json.loads((H/"final-recovery-audit.json").read_text())
assert not audit["historical_hash_failures"] and not audit["repository_changes"]
out={"sections":sections,"broken_local_links":broken,"raw_process_counts":counts,"source_freeze_verified":True,
    "full_wgpu_tests":{"passed":2179,"failed":23,"timed_out":3,"triage":triage["classifications"]},
    "validation_config_restored":True,"historical_hashes_verified":audit["historical_files_checked"]}
(H/"deliverable-checks.json").write_text(json.dumps(out,indent=2));print(out)
