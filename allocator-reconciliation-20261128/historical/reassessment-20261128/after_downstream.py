"""Start final correctness validation only after every latency process has finished."""
import pathlib, subprocess, time, sys
H = pathlib.Path(__file__).resolve().parent
while not (H / "TIMING_PHASE_COMPLETE").exists():
    time.sleep(3)
for script in ["analyze_downstream.py", "analyze_interactions.py", "run_wgpu_validation.py", "verify_historical_wgpu.py"]:
    print("Starting", script, flush=True)
    subprocess.run([sys.executable, script], cwd=H, check=True)
    print("Completed", script, flush=True)
(H / "FINAL_CHECKS_COMPLETE").write_text("complete")
