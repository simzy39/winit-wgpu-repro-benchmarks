import pathlib,shutil,subprocess
H=pathlib.Path(__file__).resolve().parent
folder=H/"work/vma"
(folder/"src").mkdir(parents=True,exist_ok=True)
m=(H/"work/proposal/bench/Cargo.toml").read_text()
m=m.replace('../gpu-allocator','../proposal/gpu-allocator')
m+='\nvk-mem = "=0.5.0"\n\n[workspace]\n'
(folder/"Cargo.toml").write_text(m)
(folder/"src/main.rs").write_text("fn main() {}\n")
subprocess.run(["cargo","fetch","--manifest-path",str(folder/"Cargo.toml")],check=True)

