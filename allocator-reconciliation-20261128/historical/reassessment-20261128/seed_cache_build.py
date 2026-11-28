import pathlib,shutil,subprocess,json
H=pathlib.Path(__file__).resolve().parent
target=(H/"target-cache2").resolve()
assert target.parent==H.resolve()
if not target.exists():
    shutil.copytree(H/"target-retain2",target)
    cmd=["cargo","clean","--target-dir",str(target),"-p","gpu-allocator","-p","gpua-policy-bench"]
    p=subprocess.run(cmd,cwd=H/"work/cache2",capture_output=True,text=True,check=True)
    (H/"logs/cache2-seed-clean.log").write_text(p.stdout+p.stderr)
shutil.copyfile(H/"bench.rs",H/"work/cache2/bench/src/main.rs")
shutil.copyfile(H/"bin/bench-vma.exe",H/"bin-verified/bench-vma.exe")
p=H/"run_direct.py"
s=p.read_text().replace('"request","vma-policy"]','"request","vma-policy","cache2"]')
p.write_text(s)
print("Seeded dependency cache; removed allocator and harness artifacts before rebuilding")

