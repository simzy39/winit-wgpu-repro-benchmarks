"""Freeze source inputs for a fresh reproduction without changing any worktree."""
import pathlib, subprocess, json, hashlib, shutil
H = pathlib.Path(__file__).resolve().parent
out = H / "repro-inputs"
out.mkdir(exist_ok=True)
records = {}
for name in ["main", "pr323", "proposal", "retain2", "demand2", "request", "vma-policy", "cache2", "cachemax"]:
    folder = H / "work" / name
    repo = folder / "gpu-allocator"
    base = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    diff = subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", base])
    untracked = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard", "--", "src"], text=True).splitlines()
    for relative in untracked:
        lines = (repo / relative).read_text().splitlines()
        header = f"diff --git a/{relative} b/{relative}\nnew file mode 100644\n--- /dev/null\n+++ b/{relative}\n@@ -0,0 +1,{len(lines)} @@\n"
        diff += (header + "\n".join("+" + line for line in lines) + "\n").encode()
    (out / (name + ".patch")).write_bytes(diff)
    shutil.copyfile(folder / "Cargo.lock", out / (name + ".Cargo.lock"))
    records[name] = {"base": base, "patch_sha256": hashlib.sha256(diff).hexdigest(), "source_hash_normalization": "CRLF to LF",
        "source_files": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in (repo / "src").rglob("*.rs")}}
    shutil.copyfile(folder / "bench/Cargo.toml", out / (name + ".bench.toml"))
shutil.copyfile(H / "work/vma/Cargo.toml", out / "vma.Cargo.toml")
shutil.copyfile(H / "work/vma/Cargo.lock", out / "vma.Cargo.lock")
shutil.copyfile(H / "work/vma/src/main.rs", out / "vma.rs")
shutil.copyfile(H / "bench.rs", out / "bench.rs")
shutil.copyfile(H / "downstream/bench/pr323-trunk/src/main.rs", out / "wgpu-bench.rs")
shutil.copyfile(H / "downstream/bench/pr323-trunk/Cargo.toml", out / "wgpu-bench.toml")
shutil.copyfile(H / "downstream/bench/pr323-trunk/Cargo.lock", out / "wgpu.Cargo.lock")
(out / "manifest.json").write_text(json.dumps(records, indent=2))
print("Archived", len(records), "allocator variants and both harnesses")
