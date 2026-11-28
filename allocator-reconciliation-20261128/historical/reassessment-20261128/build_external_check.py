"""Build the existing external-texture correctness fixture against the combined candidate."""
import pathlib,shutil,subprocess,json,hashlib
H=pathlib.Path(__file__).resolve().parent
folder=H/"downstream/bench/cache2-both"
source=H.parent.parent/"winit-wgpu/wgpu/mem-bench/src/bin/ext_tex_verify.rs"
dest=folder/"src/bin/ext_tex_verify.rs"
dest.parent.mkdir(exist_ok=True)
shutil.copyfile(source,dest)
p=subprocess.run(["cargo","build","--release","--locked","--bin","ext_tex_verify","--target-dir",str(H/"target-wgpu")],cwd=folder,capture_output=True,text=True)
(H/"logs/build-external-texture-check.log").write_text(p.stdout+p.stderr,encoding="utf-8")
if p.returncode:raise SystemExit(p.stderr)
out=H/"bin-checks";out.mkdir(exist_ok=True)
exe=out/"external-texture-cache2-both.exe"
shutil.copyfile(H/"target-wgpu/release/ext_tex_verify.exe",exe)
(out/"external-texture-cache2-both.json").write_text(json.dumps({"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
    "fixture_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"fixture_unmodified":True},indent=2))
print("Built unmodified external texture fixture")

