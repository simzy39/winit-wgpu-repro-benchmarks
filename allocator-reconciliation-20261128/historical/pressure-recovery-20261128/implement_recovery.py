"""Build the isolated pressure-recovery candidate from the frozen prior candidate."""
import pathlib,shutil
from string import Template
H=pathlib.Path(__file__).resolve().parent
R=H/"work/recovery/gpu-allocator"
shutil.copytree(H/"work/cache2/gpu-allocator/src",R/"src",dirs_exist_ok=True)

for backend in ["vulkan","d3d12","metal"]:
    p=R/"src"/backend/"mod.rs";s=p.read_text()
    vk=backend=="vulkan";metal=backend=="metal"
    device="ash::Device" if vk else "ProtocolObject<dyn MTLDevice>" if metal else "ID3D12DeviceVersion"
    size="desc.requirements.size" if vk else "desc.size"
    align="desc.requirements.alignment" if vk else "desc.alignment"
    force='desc.allocation_scheme != AllocationScheme::GpuAllocatorManaged' if vk else 'false'
    args='''                self.memory_type_index, self.mappable, self.buffer_device_address,
                desc.allocation_scheme, dedicated,'''
    if not vk:args='''                &self.heap_properties, dedicated, self.memory_location,''' if metal else '''                &self.heap_properties, self.heap_category, dedicated,'''
    existing_fields='''                    device_memory: block.device_memory,
                    mapped_ptr,
                    memory_properties: self.memory_properties,
                    dedicated_allocation: false,'''
    new_fields=existing_fields.replace('dedicated_allocation: false','dedicated_allocation')
    if not vk:existing_fields=new_fields='''                    heap: block.heap.clone(),'''
    mapped='''                        let mapped_ptr = block.mapped_ptr.and_then(|SendSyncPtr(ptr)| {
                            core::ptr::NonNull::new(unsafe { ptr.as_ptr().add(offset as usize) }).map(SendSyncPtr)
                        });''' if vk else ''
    new_mapped=mapped.replace('                        ','        ')
    destroy='block.destroy(device);' if vk else 'drop(block);'
    release='block.destroy(device);' if vk else '''if let Some(rs) = &self.global_residency_set { rs.removeAllocation(block.heap.as_ref()); }
                drop(block);''' if metal else 'drop(block);'
    release_param=', device: &ash::Device' if vk else ''
    release_call='(&self.device)' if vk else '()'
    cap='''        if size > self.heap_size { return Err(AllocationError::OutOfMemory); }''' if vk else ''
    residency='''        if let Some(rs) = &self.global_residency_set { rs.addAllocation(block.heap.as_ref()); }''' if metal else ''
    code=Template('''    fn block_size(&self, desc: &AllocationCreateDesc<'_>) -> u64 {
        let size = $size;
        if $force || size > self.block_sizes.dedicated_threshold() { return size; }
        let occupied = self.active_general_blocks - usize::from(self.empty_block_index.is_some());
        self.block_sizes.shared_block_size(occupied, size)
    }

    fn cached_size(&self) -> u64 {
        self.empty_block_index.and_then(|i| self.memory_blocks.get(i))
            .and_then(Option::as_ref).filter(|block| block.sub_allocator.is_empty())
            .map_or(0, |block| block.size)
    }

    fn release_cached(&mut self$release_param) -> u64 {
        let Some(index) = self.empty_block_index.take() else { return 0; };
        let Some(slot) = self.memory_blocks.get_mut(index) else { return 0; };
        if !slot.as_ref().is_some_and(|block| block.sub_allocator.is_empty()
            && block.sub_allocator.supports_general_allocations()) { return 0; }
        if let Some(block) = slot.take() {
            let bytes = block.size;
            self.active_general_blocks -= 1;
            $release
            bytes
        } else { 0 }
    }

    fn allocate(
        &mut self, device: &$device, desc: &AllocationCreateDesc<'_>,
        $granularity_arg
        #[cfg(feature = "std")] backtrace: Arc<Backtrace>,
        new_block_size: Option<u64>,
    ) -> Result<Allocation> {
        let size = $size;
        let alignment = $align;
        $cap
        let allocation_type = $allocation_type;
        let dedicated_allocation = $force;
        let dedicated = dedicated_allocation || size > self.block_sizes.dedicated_threshold();
        let mut vacant = None;
        if !dedicated {
            for (index, slot) in self.memory_blocks.iter_mut().enumerate().rev() {
                let Some(block) = slot else { if vacant.is_none() { vacant = Some(index); } continue; };
                match block.sub_allocator.allocate(size, alignment, allocation_type, $granularity,
                    desc.name, #[cfg(feature = "std")] backtrace.clone()) {
                    Ok((offset, chunk_id)) => {
                        if self.empty_block_index == Some(index) { self.empty_block_index = None; }
                        $mapped
                        return Ok(Allocation {
                            chunk_id: Some(chunk_id), size, offset,
                            memory_block_index: index, memory_type_index: self.memory_type_index,
                            name: Some(desc.name.into()),
                            $existing_fields
                        });
                    }
                    Err(AllocationError::OutOfMemory) => {},
                    Err(error) => return Err(error),
                }
            }
        }
        let Some(block_size) = new_block_size else { return Err(AllocationError::OutOfMemory); };
        let mut block = MemoryBlock::new(device, if dedicated { size } else { block_size },
            $args
        )?;
        let (offset, chunk_id) = match block.sub_allocator.allocate(
            size, alignment, allocation_type, $granularity, desc.name,
            #[cfg(feature = "std")] backtrace,
        ) {
            Ok(value) => value,
            Err(error) => { $destroy return Err(error); }
        };
        $residency
        let index = if dedicated {
            self.memory_blocks.iter().position(Option::is_none)
        } else { vacant };
        let index = match index {
            Some(index) => { self.memory_blocks[index] = Some(block); index },
            None => { self.memory_blocks.push(Some(block)); self.memory_blocks.len() - 1 },
        };
        if !dedicated { self.active_general_blocks += 1; }
        let block = self.memory_blocks[index].as_ref()
            .ok_or_else(|| AllocationError::Internal("Published memory block is missing".into()))?;
        $new_mapped
        Ok(Allocation {
            chunk_id: Some(chunk_id), size, offset,
            memory_block_index: index, memory_type_index: self.memory_type_index,
            name: Some(desc.name.into()),
            $new_fields
        })
    }

''').substitute(size=size,force=force,release_param=release_param,release=release,device=device,
        granularity_arg='granularity: u64,' if vk else '',cap=cap,align=align,
        allocation_type='if desc.linear { AllocationType::Linear } else { AllocationType::NonLinear }' if vk else 'AllocationType::Linear',
        granularity='granularity' if vk else '1',mapped=mapped,existing_fields=existing_fields,args=args,destroy=destroy,
        residency=residency,new_mapped=new_mapped,new_fields=new_fields)
    start=s.index('    fn allocate(',s.index('impl MemoryType {'))
    end=s.index('    fn free(',start) if metal else s.index('    #[allow(clippy::needless_pass_by_value)]',start)
    s=s[:start]+code+s[end:]
    # Public cache operations visit only the one recorded empty block per type.
    a=s.index('    /// Releases all empty memory blocks')
    b=s.index('    pub fn free(',a)
    trim=Template('''    /// Returns the allocator capacity held by cached empty blocks.
    pub fn cached_capacity(&self) -> u64 {
        self.memory_types.iter().map(MemoryType::cached_size).sum()
    }

    /// Releases cached empty blocks and returns bytes removed from allocator capacity.
    /// Live indices remain valid. This does not wait for GPU work or release external references.
    pub fn trim(&mut self) -> u64 {
        self.memory_types.iter_mut().map(|ty| ty.release_cached$release_call).sum()
    }

    /// Releases largest cached blocks until their total capacity is at most `bytes`.
    /// The target applies to empty cached capacity, not live allocations or an OS memory budget.
    pub fn trim_to(&mut self, bytes: u64) -> u64 {
        let mut cached = self.cached_capacity();
        let before = cached;
        while cached > bytes {
            let Some((index, size)) = self.memory_types.iter().enumerate()
                .map(|(index, ty)| (index, ty.cached_size())).max_by_key(|(_, size)| *size)
                .filter(|(_, size)| *size != 0) else { break; };
            let released = self.memory_types[index].release_cached$release_call;
            debug_assert_eq!(released, size);
            if released == 0 { break; }
            cached -= released;
        }
        before - cached
    }

''').substitute(release_call=release_call)
    s=s[:a]+trim+s[b:]
    # Device allocation errors are recoverable only for memory/mapping exhaustion.
    if vk:
        s=s.replace('vk::Result::ERROR_OUT_OF_DEVICE_MEMORY => AllocationError::OutOfMemory,','vk::Result::ERROR_OUT_OF_DEVICE_MEMORY | vk::Result::ERROR_OUT_OF_HOST_MEMORY => AllocationError::OutOfMemory,')
        a=s.index('        let mapped_ptr = mapped\n')
        b=s.index('        let sub_allocator:',a)
        s=s[:a]+'''        let mapped_ptr = if mapped {
            let pointer = match unsafe { device.map_memory(device_memory, 0, vk::WHOLE_SIZE, vk::MemoryMapFlags::empty()) } {
                Ok(pointer) => pointer,
                Err(error) => {
                    unsafe { device.free_memory(device_memory, None) };
                    return Err(match error {
                        vk::Result::ERROR_OUT_OF_HOST_MEMORY | vk::Result::ERROR_OUT_OF_DEVICE_MEMORY => AllocationError::OutOfMemory,
                        vk::Result::ERROR_MEMORY_MAP_FAILED => AllocationError::FailedToMap(error.to_string()),
                        other => AllocationError::Internal(format!("Unexpected error in vkMapMemory: {other:?}")),
                    });
                }
            };
            match core::ptr::NonNull::new(pointer) {
                Some(pointer) => Some(SendSyncPtr(pointer)),
                None => {
                    unsafe { device.unmap_memory(device_memory); device.free_memory(device_memory, None); }
                    return Err(AllocationError::Internal("vkMapMemory returned a null pointer".into()));
                }
            }
        } else { None };

'''+s[b:]
    if metal:s=s.replace('AllocationError::Internal("No MTLHeap was returned".to_string())','AllocationError::OutOfMemory')
    # A small helper keeps backtrace cloning and backend parameters in one place.
    helper=Template('''    fn allocate_type(&mut self, index: usize, desc: &AllocationCreateDesc<'_>,
        #[cfg(feature = "std")] backtrace: &Arc<Backtrace>, block_size: Option<u64>) -> Result<Allocation> {
        self.memory_types[index].allocate(&self.device, desc, $granularity
            #[cfg(feature = "std")] backtrace.clone(), block_size)
    }

''').substitute(granularity='self.buffer_image_granularity,' if vk else '')
    at=s.index('    pub fn allocate(',s.index('impl Allocator {'))
    s=s[:at]+helper+s[at:]
    start=s.index('        let mem_loc_preferred_bits',at) if vk else s.index('        // Find memory type',at)
    end=s.index('    /// Returns the allocator capacity',start)
    if vk:
        outer='''        let required = match desc.location {
            MemoryLocation::GpuOnly => vk::MemoryPropertyFlags::DEVICE_LOCAL,
            MemoryLocation::CpuToGpu | MemoryLocation::GpuToCpu => vk::MemoryPropertyFlags::HOST_VISIBLE | vk::MemoryPropertyFlags::HOST_COHERENT,
            MemoryLocation::Unknown => vk::MemoryPropertyFlags::empty(),
        };
        let preferred = required | match desc.location {
            MemoryLocation::CpuToGpu => vk::MemoryPropertyFlags::DEVICE_LOCAL,
            MemoryLocation::GpuToCpu => vk::MemoryPropertyFlags::HOST_CACHED,
            _ => vk::MemoryPropertyFlags::empty(),
        };
        let mut indices = [0usize; vk::MAX_MEMORY_TYPES];
        let mut count = 0;
        let mut compatible = false;
        for prefer in [true, false] {
            for (index, ty) in self.memory_types.iter().enumerate() {
                if desc.requirements.memory_type_bits & (1 << index) == 0 || !ty.memory_properties.contains(required) { continue; }
                compatible = true;
                if ty.heap_size < size || ty.memory_properties.contains(preferred) != prefer { continue; }
                indices[count] = index; count += 1;
            }
        }
        if count == 0 { return Err(if compatible { AllocationError::OutOfMemory } else { AllocationError::NoCompatibleMemoryTypeFound }); }
        let first = indices[0];
        let mut attempted_size = self.memory_types[first].block_size(desc);
        let first_error = match self.allocate_type(first, desc, #[cfg(feature="std")] &backtrace, Some(attempted_size)) {
            Ok(allocation) => return Ok(allocation),
            Err(error) if error.is_memory_pressure() => error,
            Err(error) => return Err(error),
        };
        // Preserve usable blocks in another compatible type before reclaiming caches.
        for &index in &indices[1..count] {
            match self.allocate_type(index, desc, #[cfg(feature="std")] &backtrace, None) {
                Ok(allocation) => return Ok(allocation),
                Err(AllocationError::OutOfMemory) => {},
                Err(error) => return Err(error),
            }
        }
        let released = self.trim();
        for (position, &index) in indices[..count].iter().enumerate() {
            if position != 0 || released != 0 {
                attempted_size = self.memory_types[index].block_size(desc);
                match self.allocate_type(index, desc, #[cfg(feature="std")] &backtrace, Some(attempted_size)) {
                    Ok(allocation) => return Ok(allocation),
                    Err(error) if error.is_memory_pressure() => {},
                    Err(error) => return Err(error),
                }
            }
            if desc.allocation_scheme == AllocationScheme::GpuAllocatorManaged && size < attempted_size {
                match self.allocate_type(index, desc, #[cfg(feature="std")] &backtrace, Some(size)) {
                    Ok(allocation) => return Ok(allocation),
                    Err(error) if error.is_memory_pressure() => {},
                    Err(error) => return Err(error),
                }
            }
        }
        Err(first_error)
    }

'''
    else:
        predicate='''let location = desc.location == MemoryLocation::Unknown || desc.location == ty.memory_location;
                let category = ty.heap_category == HeapCategory::All || ty.heap_category == desc.resource_category.into();
                location && category''' if not metal else '''desc.location == MemoryLocation::Unknown || desc.location == ty.memory_location'''
        minimum='''size.checked_add(D3D12_DEFAULT_MSAA_RESOURCE_PLACEMENT_ALIGNMENT as u64 - 1)
            .map(|size| size & !(D3D12_DEFAULT_MSAA_RESOURCE_PLACEMENT_ALIGNMENT as u64 - 1))
            .unwrap_or(size)''' if not metal else 'size'
        outer=Template('''        let index = self.memory_types.iter().position(|ty| { $predicate })
            .ok_or(AllocationError::NoCompatibleMemoryTypeFound)?;
        let mut attempted_size = self.memory_types[index].block_size(desc);
        let first_error = match self.allocate_type(index, desc, #[cfg(feature="std")] &backtrace, Some(attempted_size)) {
            Ok(allocation) => return Ok(allocation),
            Err(error) if error.is_memory_pressure() => error,
            Err(error) => return Err(error),
        };
        if self.trim() != 0 {
            attempted_size = self.memory_types[index].block_size(desc);
            match self.allocate_type(index, desc, #[cfg(feature="std")] &backtrace, Some(attempted_size)) {
                Ok(allocation) => return Ok(allocation),
                Err(error) if error.is_memory_pressure() => {},
                Err(error) => return Err(error),
            }
        }
        let minimum = $minimum;
        if size <= self.memory_types[index].block_sizes.max && minimum < attempted_size {
            match self.allocate_type(index, desc, #[cfg(feature="std")] &backtrace, Some(minimum)) {
                Ok(allocation) => return Ok(allocation),
                Err(error) if error.is_memory_pressure() => {},
                Err(error) => return Err(error),
            }
        }
        Err(first_error)
    }

''').substitute(predicate=predicate,minimum=minimum)
    s=s[:start]+outer+s[end:]
    if vk:
        a=s.index('    fn find_memorytype_index(');b=s.index('    pub fn generate_report(',a);s=s[:a]+s[b:]
    p.write_text(s)

p=R/"src/result.rs";s=p.read_text();s+='''
impl AllocationError {
    pub(crate) fn is_memory_pressure(&self) -> bool {
        matches!(self, Self::OutOfMemory | Self::FailedToMap(_))
    }
}
''';p.write_text(s)
print("Implemented pressure recovery, indexed trimming, minimal-block fallback and atomic block publication")
