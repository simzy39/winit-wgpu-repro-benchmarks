"""Preserve the prerequisite failure and rerun the full suite with a local ATL search path."""
import pathlib,shutil,time,subprocess,ctypes
H=pathlib.Path(__file__).resolve().parent
for source,target in [("wgpu-full-tests.json","wgpu-full-tests-missing-atl.json"),("logs/wgpu-full-tests.log","logs/wgpu-full-tests-missing-atl.log")]:
    assert not (H/target).exists()
    shutil.copyfile(H/source,H/target)
while not (H/"ORIGINAL_REPLAY_COMPLETE").exists():time.sleep(2)
kernel=ctypes.windll.kernel32
assert kernel.SetThreadExecutionState(0x80000001)
try:
    p=subprocess.run(["python","run_wgpu_validation.py"],cwd=H)
finally:
    kernel.SetThreadExecutionState(0x80000000)
if p.returncode:raise SystemExit(p.returncode)
(H/"WGPU_RECHECK_COMPLETE").write_text("complete")
