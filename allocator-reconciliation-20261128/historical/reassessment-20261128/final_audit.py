"""Verify preserved historical evidence, original repository states and current remote heads."""
import pathlib, subprocess, json, hashlib, datetime
H = pathlib.Path(__file__).resolve().parent
old = json.loads((H / "recovery-audit.json").read_text())
def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
evidence = []
for record in old["manifest"]:
    path = H.parent / record["path"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    evidence.append({"path": record["path"], "expected": record["expected"], "actual": actual, "ok": actual == record["expected"]})
repos = {}
changes = []
for path, original in old["repositories"].items():
    state = {key: git(path, *args) for key, args in {
        "status": ("status", "--short", "--branch"), "head": ("rev-parse", "HEAD"),
        "refs": ("show-ref",), "diff": ("diff", "--stat")}.items()}
    repos[path] = state
    for field in state:
        if state[field]["stdout"] != original[field]["stdout"]:
            changes.append({"path": path, "field": field, "before": original[field], "after": state[field]})
remotes = {}
for name, url, refs in [
    ("allocator-upstream", "https://github.com/Traverse-Research/gpu-allocator.git", ["refs/heads/main", "refs/pull/323/head"]),
    ("allocator-fork", "https://github.com/simzy39/gpu-allocator.git", ["refs/heads/fix/growable-memblock-dedicated-threshold"]),
    ("wgpu", "https://github.com/gfx-rs/wgpu.git", ["refs/pull/11129/head", "refs/pull/11130/head"])]:
    p = subprocess.run(["git", "ls-remote", url, *refs], capture_output=True, text=True)
    remotes[name] = {"url": url, "refs": refs, "rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
patches = json.loads((H / "patches/manifest.json").read_text())
for filename, meta in patches.items():
    path = H / "patches" / filename
    assert hashlib.sha256(path.read_bytes()).hexdigest() == meta["sha256"]
    control = H.parent / "ws" / ("pr323" if "pr323" in filename else "main") / "gpu-allocator"
    meta["final_apply_check"] = git(control, "apply", "--check", str(path))
    assert meta["final_apply_check"]["exit"] == 0
result = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "historical_files_checked": len(evidence),
    "historical_hash_failures": [r for r in evidence if not r["ok"]], "repository_changes": changes,
    "repositories": repos, "remote_heads": remotes, "patches": patches}
(H / "final-recovery-audit.json").write_text(json.dumps(result, indent=2))
print({"historical_files_checked": len(evidence), "historical_failures": len(result["historical_hash_failures"]), "repository_changes": changes, "remote_heads": remotes})
assert not result["historical_hash_failures"]
assert not changes, "Review repository-state changes explicitly before finalizing"
assert all(r["rc"] == 0 for r in remotes.values())
