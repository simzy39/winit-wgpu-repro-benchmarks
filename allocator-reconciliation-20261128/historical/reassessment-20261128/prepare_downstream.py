"""Prepare wgpu factorial sources without changing either PR branch."""
import pathlib,subprocess,shutil,json,sys,os,hashlib
H=pathlib.Path(__file__).resolve().parent
OLD=H.parent.parent/"winit-wgpu"
REPO=OLD/"repos/wgpu"
BASE="60cef2be828e03ba54e2e1598001b4625c0c2163"
PATCHES={}
for key,pr in [("lazy",11129),("transient",11130)]:
    meta=json.loads((H/"sources"/f"github-wgpu-pr{pr}.json").read_text())
    data=subprocess.check_output(["git","-C",str(REPO),"diff","--binary",BASE,meta["head_sha"]])
    PATCHES[key]=H/"sources"/f"wgpu-{key}.patch"
    PATCHES[key].write_bytes(data)
for state in ["trunk","lazy","transient","both"]:
    repo=H/"downstream/trees"/state
    if not repo.exists():
        subprocess.run(["git","-C",str(REPO),"worktree","add","--detach",str(repo),BASE],check=True)
        for key in (["lazy","transient"] if state=="both" else [state] if state!="trunk" else []):
            subprocess.run(["git","apply",str(PATCHES[key])],cwd=repo,check=True)
for allocator in ["pr323","retain2","demand2"]:
    for state in ["trunk","lazy","transient","both"]:
        folder=H/"downstream/bench"/f"{allocator}-{state}"
        (folder/"src").mkdir(parents=True,exist_ok=True)
        m=(OLD/"wgpu/mem-bench/Cargo.toml").read_text()
        m=m.replace("../../repos/wgpu/wgpu",str(H/"downstream/trees"/state/"wgpu").replace("\\","/"))
        m=m.replace("../../repos/gpu-allocator",str(H/"work"/allocator/"gpu-allocator").replace("\\","/"))
        (folder/"Cargo.toml").write_text(m)
        shutil.copyfile(OLD/"wgpu/mem-bench/src/main.rs",folder/"src/main.rs")
        shutil.copyfile(OLD/"wgpu/mem-bench/Cargo.lock",folder/"Cargo.lock")
print("Prepared 4 wgpu states x 3 allocator policies")

