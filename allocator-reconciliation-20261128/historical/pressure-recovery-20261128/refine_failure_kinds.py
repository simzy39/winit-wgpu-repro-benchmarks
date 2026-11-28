"""Keep backend recovery causes private while preserving public error variants."""
import pathlib
H=pathlib.Path(__file__).resolve().parent;R=H/"work/recovery/gpu-allocator"
p=R/"src/result.rs";s=p.read_text();s=s[:s.index('\nimpl AllocationError {')]+'''
#[derive(Clone, Copy, PartialEq, Eq)]
#[allow(dead_code)] // Allocation-count limits are reported by Vulkan only.
enum FailureKind { Memory, AllocationCount, Other }

pub(crate) struct AllocationFailure {
    pub(crate) error: AllocationError,
    kind: FailureKind,
}

#[allow(dead_code)]
impl AllocationFailure {
    pub(crate) fn fatal(error: AllocationError) -> Self { Self { error, kind: FailureKind::Other } }
    pub(crate) fn allocation_limit(error: AllocationError) -> Self { Self { error, kind: FailureKind::AllocationCount } }
    pub(crate) fn is_memory_pressure(&self) -> bool { self.kind != FailureKind::Other }
    pub(crate) fn may_shrink(&self) -> bool { self.kind == FailureKind::Memory }
    pub(crate) fn is_allocation_limit(&self) -> bool { self.kind == FailureKind::AllocationCount }
}

impl From<AllocationError> for AllocationFailure {
    fn from(error: AllocationError) -> Self {
        let kind = if matches!(&error, AllocationError::OutOfMemory | AllocationError::FailedToMap(_)) {
            FailureKind::Memory
        } else { FailureKind::Other };
        Self { error, kind }
    }
}

pub(crate) type AllocationResult<T> = core::result::Result<T, AllocationFailure>;
''';p.write_text(s)
for backend in ["vulkan","d3d12","metal"]:
    p=R/"src"/backend/"mod.rs";s=p.read_text().replace('use crate::{','use crate::{AllocationFailure, AllocationResult,',1)
    start=s.index('impl MemoryBlock {');a=s.index(') -> Result<Self> {',start);s=s[:a]+s[a:].replace(') -> Result<Self> {',') -> AllocationResult<Self> {',1)
    if backend=="vulkan":
        s=s.replace('borrow::ToOwned, ','')
        a=s.index('.map_err(|e| match e {',start);b=s.index('\n            })?',a)+len('\n            })?')
        s=s[:a]+'.map_err(Self::allocation_error)?'+s[b:]
        a=s.index('                    return Err(match error {');b=s.index('                    });',a)
        s=s[:b]+s[b:].replace('                    });','                    }.into());',1)
        s=s.replace('"vkMapMemory returned a null pointer".into(),\n                    ));','"vkMapMemory returned a null pointer".into(),\n                    ).into());')
        s=s.replace('impl MemoryBlock {','''impl MemoryBlock {
    fn allocation_error(error: vk::Result) -> AllocationFailure {
        let public = match error {
            vk::Result::ERROR_OUT_OF_HOST_MEMORY | vk::Result::ERROR_OUT_OF_DEVICE_MEMORY => AllocationError::OutOfMemory,
            other => AllocationError::Internal(format!("Unexpected error in vkAllocateMemory: {other:?}")),
        };
        if error == vk::Result::ERROR_TOO_MANY_OBJECTS { AllocationFailure::allocation_limit(public) }
        else { public.into() }
    }
''',1)
        s=s.replace('ty.heap_size < size ||','self.memory_heaps[ty.heap_index].size < size ||')
    # All first-suballocation failures roll back the block and are not interpreted as driver OOM.
    a=s.index('    fn allocate(',s.index('impl MemoryType {'));b=s.index('    fn free(',a)
    part=s[a:b].replace(') -> Result<Allocation> {',') -> AllocationResult<Allocation> {',1)
    part=part.replace('return Err(AllocationError::OutOfMemory);','return Err(AllocationError::OutOfMemory.into());')
    part=part.replace('Err(error) => return Err(error),','Err(error) => return Err(error.into()),')
    part=part.replace('return Err(error);','return Err(AllocationFailure::fatal(error));')
    s=s[:a]+part+s[b:]
    a=s.index('    fn allocate_type(',s.index('impl Allocator {'));b=s.index('    pub fn allocate(',a)
    part=s[a:b].replace(') -> Result<Allocation> {',') -> AllocationResult<Allocation> {')
    s=s[:a]+part+s[b:]
    a=s.index('    pub fn allocate(',s.index('impl Allocator {'));b=s.index('    /// Returns the allocator capacity',a)
    part=s[a:b]
    # Only errors returned by allocate_type carry the private cause.
    pivot=part.index('        let required') if backend=="vulkan" else part.index('        let index =')
    prefix,body=part[:pivot],part[pivot:]
    body=body.replace('Err(error) => return Err(error),','Err(error) => return Err(error.error),')
    body=body.replace('Err(first_error)','Err(first_error.error)')
    body=body.replace('Err(AllocationError::OutOfMemory) => {}','Err(error) if matches!(&error.error, AllocationError::OutOfMemory) => {}')
    close=body.index('        };',body.index('let first_error'))+len('        };')
    body=body[:close]+'\n        let mut can_shrink = first_error.may_shrink();'+body[close:]
    body=body.replace('Err(error) if error.is_memory_pressure() => {}','''Err(error) if error.is_memory_pressure() => {
                        if error.is_allocation_limit() { return Err(error.error); }
                        can_shrink = error.may_shrink();
                    }''')
    if backend=="vulkan":
        body=body.replace('        let released = self.trim();','''        let released = self.trim();
        if released == 0 && first_error.is_allocation_limit() { return Err(first_error.error); }''')
        body=body.replace('            if desc.allocation_scheme == AllocationScheme::GpuAllocatorManaged','            if can_shrink && desc.allocation_scheme == AllocationScheme::GpuAllocatorManaged')
    else:body=body.replace('        if size <= self.memory_types[index].block_sizes.max','        if can_shrink && size <= self.memory_types[index].block_sizes.max')
    s=s[:a]+prefix+body+s[b:]
    p.write_text(s)
print("Separated allocation-count limits, memory exhaustion and fatal errors")
