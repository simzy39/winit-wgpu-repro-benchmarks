"""Build the pinned native VMA reference into the verified binary directory."""
import pathlib, subprocess, os, shutil, hashlib, json
H = pathlib.Path(__file__).resolve().parent
env = os.environ.copy()
env["BENCH_VARIANT"] = "vma"
cmd = ["cargo", "build", "--release", "--locked", "--offline", "--target-dir", str(H / "target-vma")]
p = subprocess.run(cmd, cwd=H / "work/vma", env=env, capture_output=True, text=True)
(H / "logs/build-verified-vma.log").write_text(p.stdout + p.stderr)
assert p.returncode == 0, p.stderr
out = H / "bin-verified"
out.mkdir(exist_ok=True)
exe = out / "bench-vma.exe"
shutil.copyfile(H / "target-vma/release/gpua-policy-bench.exe", exe)
(out / "vma.json").write_text(json.dumps({"command": cmd, "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
    "lock_sha256": hashlib.sha256((H / "work/vma/Cargo.lock").read_bytes()).hexdigest()}, indent=2))
print("Built native VMA reference")
