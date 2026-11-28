"""Temporarily inhibit idle system sleep while this experiment's checks are running."""
import ctypes, pathlib, time, json
H = pathlib.Path(__file__).resolve().parent
kernel = ctypes.windll.kernel32
previous = kernel.SetThreadExecutionState(0x80000001)
assert previous
(H / "sleep-inhibition.json").write_text(json.dumps({"scope": "This helper thread until FINAL_CHECKS_COMPLETE; no power plan or display setting changed", "previous_state": previous}, indent=2))
try:
    while not (H / "FINAL_CHECKS_COMPLETE").exists(): time.sleep(3)
finally:
    kernel.SetThreadExecutionState(0x80000000)
