"""Isolated final audit of the allocator's convenience resource API.

Does not modify the source being used by the running full wgpu suite.
"""
from pathlib import Path
import shutil

H = Path(__file__).resolve().parent
R = H / 'lifetime-review/gpu-allocator'
assert not R.exists()
shutil.copytree(H / 'candidate-source', R)
for name in ['Cargo.toml', 'Cargo.lock']:
    shutil.copyfile(H / 'work/recovery' / name, R.parent / name)
shutil.copytree(H / 'work/recovery/bench', R.parent / 'bench')

p = R / 'src/d3d12/mod.rs'
s = p.read_text()
start = s.index('                let mut result: Option<ID3D12Resource> = None;', s.index('            ResourceType::Placed =>'))
end = s.index('                let size = allocation.size();', start)
old = s[start:end]
body = old[:old.index('                let resource = result.expect(')]
body = '\n'.join('    ' + line if line else line for line in body.splitlines())
replacement = '''                // Keep native output local so a partially returned resource is dropped
                // before its backing allocation is returned to the pool on every error.
                let created = (|| {
''' + body + '''
                    result.ok_or_else(|| {
                        AllocationError::Internal(
                            "CreatePlacedResource succeeded without returning a resource".into(),
                        )
                    })
                })();
                let resource = match created {
                    Ok(resource) => resource,
                    Err(error) => {
                        self.free(allocation)?;
                        return Err(error);
                    }
                };
'''
s = s[:start] + replacement + s[end:]
s = s.replace('let resource = result.expect("Allocation succeeded but no resource was returned?");', '''let resource = result.ok_or_else(|| {
                    AllocationError::Internal(
                        "CreateCommittedResource succeeded without returning a resource".into(),
                    )
                })?;''')
p.write_text(s)
print(R)
