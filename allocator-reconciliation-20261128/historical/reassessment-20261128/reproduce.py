"""Prepare a new detached reproduction from frozen source inputs. Never overwrites an output."""
import pathlib, subprocess, shutil, json, hashlib, argparse
H = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=pathlib.Path)
args = parser.parse_args()
dest = args.output.resolve()
assert not dest.exists(), "Choose a new output directory; existing evidence is immutable"
assert dest != H and H not in dest.parents, "Use a sibling destination outside this evidence tree"
inputs = H / "repro-inputs"
manifest = json.loads((inputs / "manifest.json").read_text())
dest.mkdir(parents=True)
(dest / "logs").mkdir()
for name, meta in manifest.items():
    folder = dest / "work" / name
    repo = folder / "gpu-allocator"
    folder.mkdir(parents=True)
    subprocess.run(["git", "-C", str(H.parent / "repo"), "worktree", "add", "--detach", str(repo), meta["base"]], check=True)
    patch = inputs / (name + ".patch")
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == meta["patch_sha256"]
    if patch.stat().st_size:
        subprocess.run(["git", "-C", str(repo), "apply", str(patch)], check=True)
    for path, expected in meta["source_files"].items():
        assert hashlib.sha256((repo / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected, (name, path)
    (folder / "Cargo.toml").write_text('[workspace]\nmembers=["gpu-allocator","bench"]\nresolver="2"\n')
    (folder / "bench/src").mkdir(parents=True)
    shutil.copyfile(inputs / (name + ".bench.toml"), folder / "bench/Cargo.toml")
    shutil.copyfile(inputs / (name + ".Cargo.lock"), folder / "Cargo.lock")
    shutil.copyfile(inputs / "bench.rs", folder / "bench/src/main.rs")
vma = dest / "work/vma"
(vma / "src").mkdir(parents=True)
for source, target in [("vma.Cargo.toml", "Cargo.toml"), ("vma.Cargo.lock", "Cargo.lock"), ("vma.rs", "src/main.rs")]:
    shutil.copyfile(inputs / source, vma / target)
wgpu_repo = H.parent.parent / "winit-wgpu/repos/wgpu"
for state in ["trunk", "lazy", "transient", "both", "validation"]:
    repo = dest / "downstream/validation" if state == "validation" else dest / "downstream/trees" / state
    repo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(wgpu_repo), "worktree", "add", "--detach", str(repo), "60cef2be828e03ba54e2e1598001b4625c0c2163"], check=True)
    for change in (["lazy", "transient"] if state in {"both", "validation"} else [state] if state != "trunk" else []):
        subprocess.run(["git", "-C", str(repo), "apply", str(H / "sources" / ("wgpu-" + change + ".patch"))], check=True)
    if state == "validation":
        config = repo / ".cargo/config.toml"
        config.write_text(config.read_text() + '\n[patch.crates-io]\ngpu-allocator = { path = "' + str(dest / "work/cache2/gpu-allocator").replace("\\", "/") + '" }\n')
for allocator in ["pr323", "cache2", "retain2", "demand2"]:
    for state in ["trunk", "lazy", "transient", "both"]:
        folder = dest / "downstream/bench" / (allocator + "-" + state)
        (folder / "src").mkdir(parents=True)
        text = (inputs / "wgpu-bench.toml").read_text()
        text = text.replace(str(H / "downstream/trees/trunk/wgpu").replace("\\", "/"), str(dest / "downstream/trees" / state / "wgpu").replace("\\", "/"))
        text = text.replace(str(H / "work/pr323/gpu-allocator").replace("\\", "/"), str(dest / "work" / allocator / "gpu-allocator").replace("\\", "/"))
        assert str(H).replace("\\", "/") not in text
        (folder / "Cargo.toml").write_text(text)
        shutil.copyfile(inputs / "wgpu-bench.rs", folder / "src/main.rs")
        shutil.copyfile(inputs / "wgpu.Cargo.lock", folder / "Cargo.lock")
for script in ["build.py", "build_vma.py", "build_downstream.py", "validate.py", "run_direct.py", "run_cache_limits.py", "run_downstream.py", "process_metrics.py", "analyze_direct.py", "analyze_cache_limits.py", "analyze_downstream.py", "analyze_interactions.py", "validate_vma_counts.py", "run_wgpu_validation.py"]:
    shutil.copyfile(H / script, dest / script)
for relative in ["tools/cargo-nextest.exe", "tools/atl/atls.lib"]:
    source = H / relative
    if source.exists():
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
(dest / "REPRODUCTION_SOURCE.json").write_text(json.dumps({"source": str(H), "allocator_variants": manifest}, indent=2))
print("Prepared and source-verified:", dest)
print("Build and measurement commands are in", H / "REPRODUCE.md")
