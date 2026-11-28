"""Hash archived evidence without traversing build caches or mutable Git internals."""
import pathlib, os, hashlib, json, datetime
H = pathlib.Path(__file__).resolve().parent
excluded = {".git", "__pycache__", "work", "downstream"}
records = []
def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()
for root, dirs, files in os.walk(H):
    dirs[:] = [d for d in dirs if d not in excluded and not d.startswith("target")]
    for filename in sorted(files):
        path = pathlib.Path(root) / filename
        if filename in {"EVIDENCE.sha256", "manifest-receipt.json"}: continue
        if path.suffix in {".pyc"}: continue
        records.append((path.relative_to(H).as_posix(), digest(path), path.stat().st_size))
records.sort()
(H / "EVIDENCE.sha256").write_text("".join(f"{sha}  {path}\n" for path, sha, size in records), encoding="utf-8")
failures = []
for path, sha, size in records:
    if digest(H / path) != sha: failures.append(path)
assert not failures
(H / "manifest-receipt.json").write_text(json.dumps({"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "files": len(records), "bytes": sum(size for path, sha, size in records), "verify_failures": failures,
    "excluded": "Cargo targets, Git internals, generated worktrees (canonical source patches/harnesses are archived), Python caches, manifest itself and this receipt"}, indent=2))
print("Hashed and verified", len(records), "evidence files")
