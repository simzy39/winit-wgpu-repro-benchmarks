"""Propagate the local allocator override into trybuild's generated workspace."""
from pathlib import Path
H=Path(__file__).resolve().parent;R=H/'wgpu/candidate'
p=R/'.cargo/config.toml';s=p.read_text();marker='\n[patch.crates-io.gpu-allocator]\n';assert marker in s
s=s[:s.index(marker)];p.write_text(s)
p=R/'Cargo.toml';s=p.read_text();marker='[patch.crates-io]\n';assert marker in s
line='gpu-allocator = { path = "'+str(H/'work/recovery/gpu-allocator').replace('\\','/')+'" }\n'
s=s.replace(marker,marker+line,1);p.write_text(s)
print('Moved test-only override to workspace manifest so trybuild inherits it')
