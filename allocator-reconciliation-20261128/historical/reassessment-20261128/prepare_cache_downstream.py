import pathlib,shutil
H=pathlib.Path(__file__).resolve().parent
old=H.parent.parent/"winit-wgpu"
for state in ["trunk","lazy","transient","both"]:
    folder=H/"downstream/bench"/f"cache2-{state}"
    (folder/"src").mkdir(parents=True,exist_ok=True)
    m=(old/"wgpu/mem-bench/Cargo.toml").read_text()
    m=m.replace("../../repos/wgpu/wgpu",str(H/"downstream/trees"/state/"wgpu").replace("\\","/"))
    m=m.replace("../../repos/gpu-allocator",str(H/"work/cache2/gpu-allocator").replace("\\","/"))
    (folder/"Cargo.toml").write_text(m)
    shutil.copyfile(old/"wgpu/mem-bench/src/main.rs",folder/"src/main.rs")
    shutil.copyfile(old/"wgpu/mem-bench/Cargo.lock",folder/"Cargo.lock")
print("Prepared cache candidate for all four wgpu states")

