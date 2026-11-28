"""Resolve a stable fixed-texture timing gap without changing the primary benchmark."""
import pathlib, subprocess, shutil, os, json, time, statistics, hashlib
H = pathlib.Path(__file__).resolve().parent
(H / "DIAGNOSTIC_REQUESTED").write_text("Investigate stable fixed-texture allocation timing gap before final validation")
while not (H / "TIMING_PHASE_COMPLETE").exists(): time.sleep(2)
out = H / "results-texture-diagnostic"
out.mkdir(exist_ok=True)
for variant in ["pr323", "cache2"]:
    folder = H / "diagnostics" / variant
    (folder / "src").mkdir(parents=True, exist_ok=True)
    manifest = (H / "work" / variant / "bench/Cargo.toml").read_text()
    manifest = manifest.replace('name = "gpua-policy-bench"', 'name = "gpua-texture-diagnostic"')
    manifest = manifest.replace('../gpu-allocator', str(H / "work" / variant / "gpu-allocator").replace("\\", "/"))
    (folder / "Cargo.toml").write_text(manifest + "\n[workspace]\n")
    source = (H / "bench.rs").read_text()
    needle = "    for (name, ops) in workloads() {"
    assert needle in source
    source = source.replace(needle, needle + '\n        if std::env::var("TEXTURES_ONLY").is_ok() && name != "textures" { continue; }')
    (folder / "src/main.rs").write_text(source)
    shutil.copyfile(H / "work" / variant / "Cargo.lock", folder / "Cargo.lock")
    env = os.environ.copy(); env["BENCH_VARIANT"] = variant + "-diagnostic"
    cmd = ["cargo", "build", "--release", "--offline", "--target-dir", str(H / ("target-" + variant))]
    p = subprocess.run(cmd, cwd=folder, env=env, capture_output=True, text=True)
    (H / "logs" / ("build-texture-diagnostic-" + variant + ".log")).write_text(p.stdout + p.stderr)
    assert p.returncode == 0, p.stderr
    shutil.copyfile(H / ("target-" + variant) / "release/gpua-texture-diagnostic.exe", folder / "bench.exe")
print("Diagnostic binaries built", flush=True)
time.sleep(10)
rows = []
for trial in range(1, 6):
    variants = ["pr323", "cache2"] if trial % 2 else ["cache2", "pr323"]
    for mode in ["alone", "original_order"]:
        for variant in variants:
            exe = H / "diagnostics" / variant / "bench.exe"
            env = os.environ.copy()
            if mode == "alone": env["TEXTURES_ONLY"] = "1"
            else: env.pop("TEXTURES_ONLY", None)
            cmd = [str(exe), "vulkan", "default", str(trial), variant + "-diagnostic"]
            p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
            stem = f"{variant}__{mode}__t{trial}"
            assert not (out / (stem + ".json")).exists()
            (out / (stem + ".json")).write_text(p.stdout)
            (out / (stem + ".receipt.json")).write_text(json.dumps({"rc": p.returncode, "stderr": p.stderr,
                "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(), "command": cmd, "mode": mode}, indent=2))
            assert p.returncode == 0, p.stderr
            w = json.loads(p.stdout)["result"]["workloads"]["textures"]
            rows.append({"variant": variant, "mode": mode, "trial": trial,
                "allocation_ms": w["alloc_us"]["sum_ms"], "heap_p99_us": w["heap_creation_us"]["p99"],
                "reuse_p99_us": w["reuse_us"]["p99"], "blocks_created": w["blocks_created"],
                "peak_mib": w["peak_capacity_mib"], "retained_mib": w["retained_after_release_mib"]})
            time.sleep(2)
    print("Diagnostic trial", trial, "complete", flush=True)
summary = []
for variant in ["pr323", "cache2"]:
    for mode in ["alone", "original_order"]:
        values = [r["allocation_ms"] for r in rows if r["variant"] == variant and r["mode"] == mode]
        summary.append({"variant": variant, "mode": mode, "median_ms": statistics.median(values), "min_ms": min(values), "max_ms": max(values)})
(H / "texture-diagnostic-summary.json").write_text(json.dumps({"summary": summary, "trials": rows}, indent=2))
(H / "DIAGNOSTIC_COMPLETE").write_text("complete")
print(summary, flush=True)
