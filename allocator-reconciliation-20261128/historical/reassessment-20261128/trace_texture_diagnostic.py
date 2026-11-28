"""Capture API inputs for the texture diagnostic; trace-run timings are excluded."""
import pathlib, os, subprocess, time, json, hashlib
H = pathlib.Path(__file__).resolve().parent
while not (H / "DIAGNOSTIC_COMPLETE").exists(): time.sleep(2)
out = H / "texture-api-traces"
out.mkdir(exist_ok=True)
sdk = pathlib.Path(r"<drive>/VulkanSDK\1.4.363.0\Bin")
records = []
for mode in ["alone", "original_order"]:
    for variant in ["pr323", "cache2"]:
        env = os.environ.copy()
        env.update(VK_INSTANCE_LAYERS="VK_LAYER_LUNARG_api_dump", VK_LAYER_PATH=str(sdk),
            VK_APIDUMP_LOG_FILENAME=str(out / (variant + "-" + mode + ".txt")),
            VK_APIDUMP_OUTPUT_FORMAT="text", VK_APIDUMP_FILE="true", VK_APIDUMP_FLUSH="true")
        if mode == "alone": env["TEXTURES_ONLY"] = "1"
        else: env.pop("TEXTURES_ONLY", None)
        exe = H / "diagnostics" / variant / "bench.exe"
        p = subprocess.run([str(exe), "vulkan", "default", "0", variant + "-trace"], env=env, capture_output=True, text=True, timeout=300)
        (out / (variant + "-" + mode + ".stdout.txt")).write_text(p.stdout)
        (out / (variant + "-" + mode + ".stderr.txt")).write_text(p.stderr)
        records.append({"variant": variant, "mode": mode, "rc": p.returncode,
            "timings_excluded": True, "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()})
(out / "receipts.json").write_text(json.dumps(records, indent=2))
print("API trace receipts:", records, flush=True)
