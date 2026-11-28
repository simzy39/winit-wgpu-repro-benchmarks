"""Read-only audit of historical evidence and repositories; writes only this directory."""
import hashlib, json, pathlib, subprocess, datetime
HERE = pathlib.Path(__file__).resolve().parent
OLD = HERE.parent
def git(path, *args):
    p = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
manifest = []
for line in (OLD / "EVIDENCE.sha256").read_text().splitlines():
    expected, relative = line.split(maxsplit=1)
    relative = relative.lstrip("*")
    path = OLD / relative
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    manifest.append({"path":relative,"expected":expected,"actual":actual,"ok":expected==actual})
repos = [OLD / "repo"]
repos += sorted((OLD / "ws").glob("*/gpu-allocator"))
wgpu = OLD.parent / "winit-wgpu"
repos += sorted((wgpu / "repos").glob("*"))
repos += sorted((wgpu / "ws").glob("*"))
states = {}
for path in repos:
    if (path / ".git").exists():
        states[str(path)] = {key:git(path,*args) for key,args in {
            "status":("status","--short","--branch"),"head":("rev-parse","HEAD"),
            "refs":("show-ref",),"diff":("diff","--stat"),"remotes":("remote","-v"),
            "worktrees":("worktree","list","--porcelain")}.items()}
latest = []
for path in OLD.rglob("*"):
    if not path.is_file() or any(part in {".git","target",HERE.name} for part in path.relative_to(OLD).parts):
        continue
    latest.append({"path":str(path.relative_to(OLD)),"mtime_ns":path.stat().st_mtime_ns,"size":path.stat().st_size})
report = {"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"manifest_count":len(manifest),
          "manifest_failures":[r for r in manifest if not r["ok"]],"manifest":manifest,
          "repositories":states,"latest_files":sorted(latest,key=lambda x:x["mtime_ns"],reverse=True)[:30]}
(HERE/"recovery-audit.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"manifest_count":len(manifest),"failures":report["manifest_failures"],
                 "repositories":{k:{"status":v["status"],"head":v["head"]} for k,v in states.items()},
                 "latest_files":report["latest_files"][:8]},indent=2))

