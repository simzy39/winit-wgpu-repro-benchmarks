import pathlib
H=pathlib.Path(__file__).resolve().parent
bad='''        if size > self.heap_size {
            return Err(AllocationError::OutOfMemory);
        }
'''
for name in ["retain2","demand2","request","vma-policy"]:
    p=H/"work"/name/"gpu-allocator/src/vulkan/mod.rs"
    s=p.read_text()
    positions=[i for i in range(len(s)) if s.startswith(bad,i)]
    assert len(positions)==2,(name,positions)
    at=positions[1]
    s=s[:at]+s[at+len(bad):]
    p.write_text(s)
p=H/"prepare.py"
s=p.read_text()
s=s.replace('s=replace(s,"        let alignment = desc.requirements.alignment;",','s=s.replace("        let alignment = desc.requirements.alignment;",')
s=s.replace('return Err(AllocationError::OutOfMemory);\\n        }")','return Err(AllocationError::OutOfMemory);\\n        }",1)')
s=s.replace('    if not repo.exists():','    if repo.exists():\n        print(f"Preserving existing {name}")\n        continue\n    if not repo.exists():')
p.write_text(s)
p=H/"build.py"
s=p.read_text().replace('HERE/"bin"','HERE/"bin-verified"').replace('HERE/"target"','HERE/("target-"+name)')
s=s.replace('f"build-{name}.log"','f"build-verified-{name}.log"')
s=s.replace('HERE/"target/release/gpua-policy-bench.exe"','HERE/("target-"+name)/"release/gpua-policy-bench.exe"')
p.write_text(s)
p=H/"run_direct.py"
s=p.read_text().replace('"results-direct"','"results-direct-verified"').replace('H/"bin"','H/"bin-verified"').replace('"STOP_DIRECT"','"STOP_VERIFIED"')
p.write_text(s)
(H/"results-direct"/"INVALID.txt").write_text("INVALID PILOT: Cargo reused a shared target artifact across allocator worktrees. Do not use these measurements. Replaced with isolated target directories and results-direct-verified.")
print("Fixed candidate source guard and enabled unique Cargo target directories")

