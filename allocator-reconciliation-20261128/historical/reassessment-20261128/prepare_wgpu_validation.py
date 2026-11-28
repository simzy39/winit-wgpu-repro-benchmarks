"""Prepare full wgpu checks in another detached tree; actual PR branches stay untouched."""
import pathlib,subprocess
H=pathlib.Path(__file__).resolve().parent
repo=H/"downstream/validation"
if not repo.exists():
    subprocess.run(["git","-C",str(H.parent.parent/"winit-wgpu/repos/wgpu"),"worktree","add","--detach",str(repo),"60cef2be828e03ba54e2e1598001b4625c0c2163"],check=True)
    for name in ["lazy","transient"]:
        subprocess.run(["git","apply",str(H/"sources"/f"wgpu-{name}.patch")],cwd=repo,check=True)
    config=repo/".cargo/config.toml"
    text=config.read_text()
    assert "[patch.crates-io]" not in text
    text+='\n[patch.crates-io]\ngpu-allocator = { path = "'+str(H/"work/cache2/gpu-allocator").replace("\\","/")+'" }\n'
    config.write_text(text)
print("Prepared isolated combined wgpu test tree")

