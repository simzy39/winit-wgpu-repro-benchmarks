"""Preserve a process spanning system sleep and repeat the same cell after diagnostics."""
import pathlib, json, time, subprocess, hashlib, datetime, re
from process_metrics import run_process
H = pathlib.Path(__file__).resolve().parent
(H / "SUSPEND_RECHECK_REQUESTED").write_text("Repeat the process spanning system suspension")
while not (H / "DIAGNOSTIC_COMPLETE").exists(): time.sleep(2)
assert (H / "DOWNSTREAM_COMPLETE").exists()
stem = "cache2-both__dx12__manual-8-256__large_alloc__t5"
source = H / "results-downstream"
archived = H / "results-downstream-suspended"
archived.mkdir(exist_ok=True)
original = json.loads((source / (stem + ".receipt.json")).read_text())
assert original["wall_s"] > 600
paths = list(source.glob(stem + ".*"))
assert len(paths) == 4
for path in paths:
    assert path.resolve().parent == source.resolve()
    target = archived / path.name
    assert not target.exists()
    path.rename(target)
exe = H / "bin-wgpu/cache2-both.exe"
cmd = [str(exe), "--backend", "dx12", "--hints", "manual-8-256", "--workload", "large_alloc", "--json", str(source / (stem + ".json"))]
time.sleep(10)
p = run_process(cmd, timeout=600)
(source / (stem + ".stdout.txt")).write_text(p.stdout)
(source / (stem + ".stderr.txt")).write_text(p.stderr)
validation_error = bool(re.search(r"VUID-|Validation Error|panicked", p.stdout + p.stderr, re.I))
receipt = {"rc": p.returncode, "command": cmd, "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
    "validation_error": validation_error, "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "wall_s": p.wall_s, "cpu_times": p.cpu_times, "settle_after_s": 2,
    "replaces_suspended_run": str(archived / (stem + ".receipt.json"))}
(source / (stem + ".receipt.json")).write_text(json.dumps(receipt, indent=2))
assert p.returncode == 0 and not validation_error, p.stderr
assert p.wall_s < 600
(H / "measurement-exclusions.json").write_text(json.dumps({"excluded_runs": [{"stem": stem,
    "reason": "Process spans a long system suspension; preserve raw data and repeat identical binary/configuration",
    "original_receipt": original, "replacement_receipt": receipt}],
    "valid_downstream_processes": 520, "attempted_downstream_processes": 521}, indent=2))
subprocess.run(["python", "analyze_downstream.py"], cwd=H, check=True)
(H / "SUSPEND_RECHECK_COMPLETE").write_text("complete")
print("Repeated suspended cell:", receipt, flush=True)
