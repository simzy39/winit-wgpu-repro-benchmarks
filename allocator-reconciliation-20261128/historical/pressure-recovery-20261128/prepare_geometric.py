"""Implement a typed-OOM backoff alternative, preserving the exact-size candidate."""
import pathlib,subprocess,shutil
H=pathlib.Path(__file__).resolve().parent;folder=H/'work/geometric';repo=folder/'gpu-allocator'
assert not repo.exists();folder.mkdir(parents=True)
subprocess.run(['git','-C',str(H.parent/'repo'),'worktree','add','--detach',str(repo),'179ea43f05332c2809addd7922cd056220efc36b'],check=True)
source=H/'work/recovery/gpu-allocator'
shutil.copytree(source/'src',repo/'src',dirs_exist_ok=True)
for name in ['README.md','Cargo.toml']:shutil.copyfile(source/name,repo/name)
(folder/'Cargo.toml').write_text('[workspace]\nmembers=["gpu-allocator"]\nresolver="2"\n')
shutil.copyfile(H/'work/recovery/Cargo.lock',folder/'Cargo.lock')
p=repo/'src/lib.rs';s=p.read_text();a=s.index('impl Default for AllocationSizes')
s=s[:a]+'''#[cfg(any(feature = "vulkan", all(windows, feature = "d3d12"), test))]
pub(crate) fn smaller_block_size(current: u64, required: u64, alignment: u64) -> Option<u64> {
    if current <= required { return None; }
    let next = (current / 2).max(required).checked_add(alignment - 1)? & !(alignment - 1);
    (next < current).then_some(next)
}

'''+s[a:]
s+='''
#[cfg(test)]
mod pressure_size_tests {
    #[test]
    fn aligned_backoff_terminates_at_the_resource_floor() {
        for alignment in [1, 4*1024*1024] {
            let floor = alignment;
            for mut current in [floor, floor+1, 3*floor, u64::MAX] {
                let mut count=0;
                while let Some(next)=super::smaller_block_size(current,floor,alignment) {
                    assert!(next<current && next>=floor);
                    assert_eq!(next%alignment,0);
                    current=next;count+=1;assert!(count<=64);
                }
                assert_eq!(current,floor);
            }
        }
    }
}
''';p.write_text(s)
p=repo/'src/vulkan/mod.rs';s=p.read_text();a=s.index('            if can_shrink\n');b=s.index('\n        Err(first_error.error)',a)
part=s[a:b].replace('            if can_shrink\n','            while can_shrink\n',1)
part=part.replace('                && size < attempted_size\n','')
part=part.replace('            {\n                match self.allocate_type(','''            {
                let Some(next) = crate::smaller_block_size(attempted_size, size, 1) else { break; };
                attempted_size = next;
                match self.allocate_type(''',1)
part=part.replace('                    Some(size),','                    Some(attempted_size),')
s=s[:a]+part+s[b:];p.write_text(s)
p=repo/'src/d3d12/mod.rs';s=p.read_text();a=s.index('        if can_shrink\n');b=s.index('\n        Err(first_error.error)',a)
part=s[a:b].replace('        if can_shrink\n','        while can_shrink\n',1).replace('            && minimum < attempted_size\n','')
part=part.replace('        {\n            match self.allocate_type(','''        {
            let Some(next) = crate::smaller_block_size(attempted_size, minimum,
                D3D12_DEFAULT_MSAA_RESOURCE_PLACEMENT_ALIGNMENT as u64) else { break; };
            attempted_size = next;
            match self.allocate_type(''',1).replace('                Some(minimum),','                Some(attempted_size),')
part=part.replace('                    if error.is_allocation_limit() {\n                        return Err(error.error);\n                    }','''                    if error.is_allocation_limit() { return Err(error.error); }
                    can_shrink = error.may_shrink();''')
s=s[:a]+part+s[b:];p.write_text(s)
p=repo/'src/vulkan/capacity_tests.rs';s=p.read_text()
s=s.replace('    map_errors: VecDeque<vk::Result>,','    map_errors: VecDeque<vk::Result>,\n    map_fail: Option<vk::Result>,')
s=s.replace('state.map_errors.pop_front()','state.map_errors.pop_front().or(state.map_fail)')
s=s.replace('vec![(1, 64 * MIB), (1, 16 * MIB)]','vec![(1,64*MIB),(1,32*MIB),(1,16*MIB)]')
s=s.replace('vec![(1, 64 * MIB), (1, MIB), (0, 8 * MIB), (0, MIB)]','vec![(1,64*MIB),(1,32*MIB),(1,16*MIB),(1,8*MIB),(1,4*MIB),(1,2*MIB),(1,MIB),(0,8*MIB),(0,4*MIB),(0,2*MIB),(0,MIB)]')
s=s.replace('vec![(0, 8 * MIB), (0, MIB)]','vec![(0,8*MIB),(0,4*MIB)]')
old='''        d.borrow_mut().map_errors.extend([
            vk::Result::ERROR_MEMORY_MAP_FAILED,
            vk::Result::ERROR_OUT_OF_DEVICE_MEMORY,
        ])'''
if old in s:s=s.replace(old,'''        let mut d=d.borrow_mut();
        d.map_errors.push_back(vk::Result::ERROR_MEMORY_MAP_FAILED);
        d.map_fail=Some(vk::Result::ERROR_OUT_OF_DEVICE_MEMORY);''')
else:
    a=s.index('fn native_host_oom_recovers_and_failed_mapping_preserves_first_cause()');start=s.index('    DRIVER.with(',s.index('allocator.memory_types[0].mappable = true;',a));end=s.index('\n    assert!',start)
    s=s[:start]+'''    DRIVER.with(|d| {let mut d=d.borrow_mut();d.map_errors.push_back(vk::Result::ERROR_MEMORY_MAP_FAILED);d.map_fail=Some(vk::Result::ERROR_OUT_OF_DEVICE_MEMORY);});'''+s[end:]
a=s.index('fn native_host_oom_recovers_and_failed_mapping_preserves_first_cause()');b=s.index('\n#[test]',a)
part=s[a:b].replace('assert_eq!(DRIVER.with(|d| d.borrow().freed), 2);','assert_eq!(DRIVER.with(|d| d.borrow().freed), DRIVER.with(|d|d.borrow().calls.len()));')
s=s[:a]+part+s[b:];p.write_text(s)
subprocess.run(['cargo','fmt','--manifest-path',str(folder/'Cargo.toml'),'-p','gpu-allocator'],check=True)
print('Prepared geometric Vulkan/D3D12 reduction; Metal keeps bounded exact fallback for unclassified nil')
