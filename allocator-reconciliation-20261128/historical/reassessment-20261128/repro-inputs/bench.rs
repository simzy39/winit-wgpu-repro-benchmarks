//! Block-size policy A/B harness for gpu-allocator variants.
//!
//! One source, built once per variant (see `build_variants.sh`). Each process creates one real
//! device (Vulkan or D3D12, adapter 0), then runs every workload with a fresh `Allocator`
//! configured with one `AllocationSizes` configuration, and prints a JSON record.
//!
//! Only `Allocator::allocate` / `Allocator::free` are timed. Block creation/destruction is derived
//! from `Allocator::capacity()` deltas sampled outside the timed region: an allocation creates at
//! most one block and a free destroys at most one. A created block is classed as *dedicated* when
//! its size equals the allocation size and is not one of the configuration's shared block step
//! sizes (all workload sizes are chosen to be non-multiples of 4 MiB, so this is unambiguous).
//!
//! Usage: gpua-policy-bench <vulkan|d3d12> <config> [trial] [variant-label]

use std::collections::{BTreeMap, HashMap};
use std::time::Instant;

use gpu_allocator::{AllocationSizes, MemoryLocation};
use serde_json::{json, Value};

const KIB: u64 = 1024;
const MIB: u64 = 1024 * 1024;

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug, PartialOrd, Ord)]
enum Loc {
    GpuOnly,
    CpuToGpu,
    GpuToCpu,
}

impl Loc {
    fn ga(self) -> MemoryLocation {
        match self {
            Loc::GpuOnly => MemoryLocation::GpuOnly,
            Loc::CpuToGpu => MemoryLocation::CpuToGpu,
            Loc::GpuToCpu => MemoryLocation::GpuToCpu,
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
enum Res {
    Buffer(u64),
    Texture(u32, u32),
}

enum Op {
    Alloc(usize, Loc, Res),
    Free(usize),
    FreeAll,
    Mark(&'static str),
}

fn config(name: &str) -> (AllocationSizes, [(u64, u64); 2]) {
    // Returns the sizes and the (min,max) [device, host] ranges for step-set computation.
    let (dmin, dmax, hmin, hmax) = match name {
        // wgpu MemoryHints::MemoryUsage
        "memory_usage" => (8, 64, 4, 32),
        // wgpu MemoryHints::Performance
        "performance" => (128, 256, 64, 128),
        // Strongly asymmetric: large fixed device blocks, tiny fixed host blocks.
        "asym_dev_large" => (256, 256, 4, 4),
        // Reverse asymmetry: tiny growable device blocks, large growable host blocks.
        "asym_host_large" => (4, 16, 64, 256),
        // gpu-allocator default (256 MiB device / 64 MiB host, fixed).
        "default" => (256, 256, 64, 64),
        "manual" => (8, 256, 4, 128),
        "tiny_fixed" => (8, 8, 4, 4),
        _ => panic!("unknown config {name}"),
    };
    let sizes = AllocationSizes::new(dmin * MIB, hmin * MIB)
        .with_max_device_memblock_size(dmax * MIB)
        .with_max_host_memblock_size(hmax * MIB);
    (sizes, [(dmin * MIB, dmax * MIB), (hmin * MIB, hmax * MIB)])
}

fn step_set(ranges: &[(u64, u64); 2]) -> Vec<u64> {
    let mut v = vec![];
    for &(min, max) in ranges {
        for k in 0..8 {
            v.push((min << k).min(max));
        }
    }
    v.sort_unstable();
    v.dedup();
    v
}

/// Deterministic workloads. Sizes avoid multiples of 4 MiB (see module docs).
fn workloads() -> Vec<(&'static str, Vec<Op>)> {
    let mut w = vec![];

    // Staging ring: 4 uploads per frame, the last 6 frames stay alive.
    let mut ops = vec![];
    let sizes = [512 * KIB, 1280 * KIB, 2816 * KIB, 6400 * KIB];
    let ring = 6 * sizes.len();
    for f in 0..300 {
        for (i, &s) in sizes.iter().enumerate() {
            let slot = (f * sizes.len() + i) % ring;
            if f >= 6 {
                ops.push(Op::Free(slot));
            }
            ops.push(Op::Alloc(slot, Loc::CpuToGpu, Res::Buffer(s)));
        }
    }
    ops.push(Op::FreeAll);
    w.push(("upload_ring", ops));

    // Readback ring.
    let mut ops = vec![];
    for i in 0..200 {
        let slot = i % 4;
        if i >= 4 {
            ops.push(Op::Free(slot));
        }
        ops.push(Op::Alloc(slot, Loc::GpuToCpu, Res::Buffer(3328 * KIB)));
    }
    ops.push(Op::FreeAll);
    w.push(("readback_ring", ops));

    // GPU-only textures, ~16.06 MiB each (RGBA8 2048x2056).
    let mut ops = vec![];
    for i in 0..24 {
        ops.push(Op::Alloc(i, Loc::GpuOnly, Res::Texture(2048, 2056)));
    }
    ops.push(Op::FreeAll);
    w.push(("textures", ops));

    // Mixed frames: uploads, readbacks, GPU-only buffers and textures with different lifetimes.
    let mut ops = vec![];
    let mut next = 0usize;
    let mut live: Vec<(usize, usize)> = vec![]; // (slot, free_at_frame)
    for f in 0..300usize {
        live.retain(|&(slot, at)| {
            if at == f {
                ops.push(Op::Free(slot));
                false
            } else {
                true
            }
        });
        let mut add = |loc, res, life: usize, ops: &mut Vec<Op>| {
            ops.push(Op::Alloc(next, loc, res));
            live.push((next, f + life));
            next += 1;
        };
        add(Loc::CpuToGpu, Res::Buffer(1280 * KIB), 3, &mut ops);
        add(Loc::CpuToGpu, Res::Buffer(2816 * KIB), 3, &mut ops);
        add(Loc::GpuOnly, Res::Buffer(5376 * KIB), 16, &mut ops);
        add(Loc::GpuToCpu, Res::Buffer(768 * KIB), 3, &mut ops);
        if f % 10 == 0 {
            add(Loc::GpuOnly, Res::Texture(1024, 1040), 30, &mut ops);
        }
    }
    ops.push(Op::FreeAll);
    w.push(("mixed_frames", ops));

    // Burst then release, 4 rounds: retention / re-creation churn.
    let mut ops = vec![];
    for _ in 0..4 {
        for i in 0..40 {
            ops.push(Op::Alloc(i, Loc::CpuToGpu, Res::Buffer(6400 * KIB)));
        }
        ops.push(Op::FreeAll);
        ops.push(Op::Mark("round"));
    }
    w.push(("burst_release", ops));

    // Large uploads (40 MiB): exercises the host dedicated threshold.
    let mut ops = vec![];
    for i in 0..8 {
        ops.push(Op::Alloc(i, Loc::CpuToGpu, Res::Buffer(40 * MIB + 64 * KIB)));
    }
    ops.push(Op::FreeAll);
    w.push(("large_uploads", ops));

    let mut ops = vec![];
    for i in 0..1024 {
        ops.push(Op::Alloc(i, Loc::GpuOnly, Res::Buffer((i as u64 % 15 + 1) * 64 * KIB)));
    }
    for i in (0..1024).step_by(2) { ops.push(Op::Free(i)); }
    ops.push(Op::Mark("fragmented"));
    for i in 1024..1280 { ops.push(Op::Alloc(i, Loc::GpuOnly, Res::Buffer(1152 * KIB))); }
    ops.push(Op::Mark("refilled"));
    ops.push(Op::FreeAll);
    w.push(("fragmentation", ops));

    let mut ops = vec![Op::Alloc(10000, Loc::CpuToGpu, Res::Buffer(64 * KIB))];
    for round in 0..12 {
        for i in 0..(if round % 3 == 0 { 24 } else { 2 }) {
            ops.push(Op::Alloc(i, Loc::CpuToGpu, Res::Buffer(5376 * KIB)));
        }
        for i in 0..24 { ops.push(Op::Free(i)); }
        ops.push(Op::Mark("sporadic"));
    }
    ops.push(Op::FreeAll);
    w.push(("sporadic_long_lived", ops));

    let mut ops = vec![];
    for round in 0..40 {
        for i in 0..8 { ops.push(Op::Alloc(i, Loc::GpuOnly, Res::Buffer((round % 3 + 1) * 128 * KIB))); }
        ops.push(Op::FreeAll);
    }
    w.push(("small_bursts", ops));

    let mut ops=vec![];
    for (i, size) in [24, 48, 96, 192, 300].into_iter().enumerate() {
        ops.push(Op::Alloc(i, Loc::GpuOnly, Res::Buffer(size * MIB + 64 * KIB)));
    }
    ops.push(Op::FreeAll);
    w.push(("large_buffers", ops));
    w
}

trait Backend {
    type A;
    fn reset(&mut self, sizes: Option<AllocationSizes>);
    fn prepare(&mut self, loc: Loc, res: Res);
    fn report(&self) -> gpu_allocator::AllocatorReport;
    fn alloc(&mut self, loc: Loc, res: Res) -> Self::A;
    fn size_of(a: &Self::A) -> u64;
    fn memtype_of(&self, a: &Self::A) -> String;
    fn free(&mut self, a: Self::A);
    fn capacity(&self) -> u64;
    fn driver_usage(&self) -> u64;
    fn info(&self) -> Value;
}

#[derive(Default)]
struct LocStats {
    memtype: Option<String>,
    allocs: u32,
    shared_created: u32,
    dedicated_created: u32,
    shared_sizes: Vec<u64>,
}

fn pct(v: &mut [u64], p: f64) -> f64 {
    if v.is_empty() {
        return 0.0;
    }
    v.sort_unstable();
    let i = ((v.len() - 1) as f64 * p).round() as usize;
    v[i] as f64 / 1000.0
}

fn run_workload<B: Backend>(b: &mut B, sizes: AllocationSizes, steps: &[u64], ops: &[Op]) -> Value {
    b.reset(Some(sizes));
    for op in ops {
        if let Op::Alloc(_, loc, res) = *op { b.prepare(loc, res); }
    }
    let baseline_usage = b.driver_usage();
    let mut live: HashMap<usize, B::A> = HashMap::new();
    let mut per_loc: BTreeMap<Loc, LocStats> = BTreeMap::new();
    let (mut alloc_ns, mut free_ns) = (vec![], vec![]);
    let (mut destroyed, mut created_total) = (0u32, 0u32);
    let (mut peak_cap, mut peak_alloc, mut live_bytes, mut peak_usage) = (0u64, 0u64, 0u64, 0u64);
    let mut marks = vec![];
    let mut block_events = vec![];
    let mut creating_ns = vec![];
    let mut reuse_ns = vec![];
    let mut peak_unused = 0u64;
    let mut cap = b.capacity();

    let do_free = |b: &mut B, a: B::A, live_bytes: &mut u64, cap: &mut u64, destroyed: &mut u32, free_ns: &mut Vec<u64>| {
        *live_bytes -= B::size_of(&a);
        let t = Instant::now();
        b.free(a);
        free_ns.push(t.elapsed().as_nanos() as u64);
        let c = b.capacity();
        if c < *cap {
            *destroyed += 1;
        }
        *cap = c;
    };

    for op in ops {
        match *op {
            Op::Alloc(slot, loc, res) => {
                let t = Instant::now();
                let a = b.alloc(loc, res);
                let ns = t.elapsed().as_nanos() as u64;
                alloc_ns.push(ns);
                let size = B::size_of(&a);
                let st = per_loc.entry(loc).or_default();
                st.allocs += 1;
                if st.memtype.is_none() {
                    st.memtype = Some(b.memtype_of(&a));
                }
                let c = b.capacity();
                if c > cap {
                    let delta = c - cap;
                    created_total += 1;
                    creating_ns.push(ns);
                    block_events.push(json!({"block_bytes":delta,"request_bytes":size,"location":format!("{loc:?}")}));
                    if delta == size && !steps.contains(&delta) {
                        st.dedicated_created += 1;
                    } else {
                        st.shared_created += 1;
                        st.shared_sizes.push(delta);
                    }
                }
                if c == cap { reuse_ns.push(ns); }
                cap = c;
                live_bytes += size;
                peak_unused = peak_unused.max(cap.saturating_sub(live_bytes));
                peak_alloc = peak_alloc.max(live_bytes);
                if cap > peak_cap {
                    peak_cap = cap;
                    peak_usage = peak_usage.max(b.driver_usage());
                }
                if let Some(old) = live.insert(slot, a) {
                    do_free(b, old, &mut live_bytes, &mut cap, &mut destroyed, &mut free_ns);
                }
            }
            Op::Free(slot) => {
                if let Some(a) = live.remove(&slot) {
                    do_free(b, a, &mut live_bytes, &mut cap, &mut destroyed, &mut free_ns);
                }
            }
            Op::FreeAll => {
                let mut slots: Vec<usize> = live.keys().copied().collect();
                slots.sort_unstable();
                for s in slots {
                    let a = live.remove(&s).unwrap();
                    do_free(b, a, &mut live_bytes, &mut cap, &mut destroyed, &mut free_ns);
                }
            }
            Op::Mark(label) => marks.push(json!({
                "label": label,
                "capacity_mib": cap as f64 / MIB as f64,
                "blocks_created_so_far": created_total,
                "fragmentation": fragmentation(&b.report()),
            })),
        }
    }
    let retained = b.capacity();
    let usage_after = b.driver_usage();
    let locs: BTreeMap<String, Value> = per_loc
        .iter()
        .map(|(l, s)| {
            (
                format!("{l:?}"),
                json!({
                    "memory_type": s.memtype,
                    "allocs": s.allocs,
                    "shared_blocks_created": s.shared_created,
                    "dedicated_blocks_created": s.dedicated_created,
                    "first_shared_block_mib": s.shared_sizes.first().map(|v| *v as f64 / MIB as f64),
                    "max_shared_block_mib": s.shared_sizes.iter().max().map(|v| *v as f64 / MIB as f64),
                    "shared_block_sizes_mib": s.shared_sizes.iter().map(|v| v / MIB).collect::<Vec<_>>(),
                }),
            )
        })
        .collect();
    let n_allocs = alloc_ns.len();
    let out = json!({
        "per_location": locs,
        "heap_creation_us": {"p50":pct(&mut creating_ns.clone(),0.5),"p99":pct(&mut creating_ns.clone(),0.99)},
        "reuse_us": {"p50":pct(&mut reuse_ns.clone(),0.5),"p99":pct(&mut reuse_ns.clone(),0.99)},
        "peak_unused_mib": peak_unused as f64 / MIB as f64,
        "block_events": block_events,
        "allocations": n_allocs,
        "blocks_created": created_total,
        "blocks_destroyed": destroyed,
        "peak_capacity_mib": peak_cap as f64 / MIB as f64,
        "peak_allocated_mib": peak_alloc as f64 / MIB as f64,
        "retained_after_release_mib": retained as f64 / MIB as f64,
        "driver_usage_baseline_mib": baseline_usage as f64 / MIB as f64,
        "driver_usage_peak_mib": peak_usage as f64 / MIB as f64,
        "driver_usage_after_release_mib": usage_after as f64 / MIB as f64,
        "alloc_us": { "p50": pct(&mut alloc_ns.clone(), 0.5), "p99": pct(&mut alloc_ns.clone(), 0.99), "max": pct(&mut alloc_ns.clone(), 1.0), "sum_ms": alloc_ns.iter().sum::<u64>() as f64 / 1e6 },
        "free_us": { "p50": pct(&mut free_ns.clone(), 0.5), "p99": pct(&mut free_ns.clone(), 0.99), "max": pct(&mut free_ns.clone(), 1.0), "sum_ms": free_ns.iter().sum::<u64>() as f64 / 1e6 },
        "marks": marks,
    });
    b.reset(None);
    out
}

// ---------------------------------------------------------------------------------------------
// Vulkan
// ---------------------------------------------------------------------------------------------
mod vkb {
    use super::*;
    use ash::vk;
    use gpu_allocator::vulkan::*;

    pub struct Vk {
        _entry: ash::Entry,
        instance: ash::Instance,
        pd: vk::PhysicalDevice,
        device: ash::Device,
        has_budget: bool,
        name: String,
        alloc: Option<Allocator>,
        reqs: HashMap<Res, vk::MemoryRequirements>,
    }

    impl Vk {
        pub fn new() -> Self {
            let entry = unsafe { ash::Entry::load() }.expect("load vulkan");
            let app = vk::ApplicationInfo::default().api_version(vk::API_VERSION_1_2);
            let instance = unsafe {
                entry.create_instance(&vk::InstanceCreateInfo::default().application_info(&app), None)
            }
            .unwrap();
            let pd = unsafe { instance.enumerate_physical_devices() }.unwrap()[0];
            let props = unsafe { instance.get_physical_device_properties(pd) };
            let name = props.device_name_as_c_str().unwrap().to_string_lossy().into_owned();
            let exts = unsafe { instance.enumerate_device_extension_properties(pd) }.unwrap();
            let has_budget = exts
                .iter()
                .any(|e| e.extension_name_as_c_str().unwrap() == ash::ext::memory_budget::NAME);
            let ext_names: Vec<*const i8> =
                if has_budget { vec![ash::ext::memory_budget::NAME.as_ptr()] } else { vec![] };
            let prio = [1.0f32];
            let qci = [vk::DeviceQueueCreateInfo::default().queue_family_index(0).queue_priorities(&prio)];
            let device = unsafe {
                instance.create_device(
                    pd,
                    &vk::DeviceCreateInfo::default().queue_create_infos(&qci).enabled_extension_names(&ext_names),
                    None,
                )
            }
            .unwrap();
            Self { _entry: entry, instance, pd, device, has_budget, name, alloc: None, reqs: HashMap::new() }
        }

        fn requirements(&mut self, res: Res) -> vk::MemoryRequirements {
            if let Some(r) = self.reqs.get(&res) {
                return *r;
            }
            let r = unsafe {
                match res {
                    Res::Buffer(size) => {
                        let b = self
                            .device
                            .create_buffer(
                                &vk::BufferCreateInfo::default().size(size).usage(
                                    vk::BufferUsageFlags::TRANSFER_SRC
                                        | vk::BufferUsageFlags::TRANSFER_DST
                                        | vk::BufferUsageFlags::UNIFORM_BUFFER
                                        | vk::BufferUsageFlags::STORAGE_BUFFER
                                        | vk::BufferUsageFlags::VERTEX_BUFFER,
                                ),
                                None,
                            )
                            .unwrap();
                        let r = self.device.get_buffer_memory_requirements(b);
                        self.device.destroy_buffer(b, None);
                        r
                    }
                    Res::Texture(w, h) => {
                        let i = self
                            .device
                            .create_image(
                                &vk::ImageCreateInfo::default()
                                    .image_type(vk::ImageType::TYPE_2D)
                                    .format(vk::Format::R8G8B8A8_UNORM)
                                    .extent(vk::Extent3D { width: w, height: h, depth: 1 })
                                    .mip_levels(1)
                                    .array_layers(1)
                                    .samples(vk::SampleCountFlags::TYPE_1)
                                    .tiling(vk::ImageTiling::OPTIMAL)
                                    .usage(vk::ImageUsageFlags::SAMPLED | vk::ImageUsageFlags::TRANSFER_DST),
                                None,
                            )
                            .unwrap();
                        let r = self.device.get_image_memory_requirements(i);
                        self.device.destroy_image(i, None);
                        r
                    }
                }
            };
            self.reqs.insert(res, r);
            r
        }
    }

    impl Backend for Vk {
        type A = Allocation;
        fn reset(&mut self, sizes: Option<AllocationSizes>) {
            self.alloc = None;
            if let Some(sizes) = sizes {
                self.alloc = Some(
                    Allocator::new(&AllocatorCreateDesc {
                        instance: self.instance.clone(),
                        device: self.device.clone(),
                        physical_device: self.pd,
                        debug_settings: quiet_debug_settings(),
                        buffer_device_address: false,
                        allocation_sizes: sizes,
                    })
                    .unwrap(),
                );
            }
        }
        fn prepare(&mut self, _loc: Loc, res: Res) { self.requirements(res); }
        fn report(&self) -> gpu_allocator::AllocatorReport { self.alloc.as_ref().unwrap().generate_report() }
        fn alloc(&mut self, loc: Loc, res: Res) -> Allocation {
            let requirements = self.reqs[&res];
            self.alloc
                .as_mut()
                .unwrap()
                .allocate(&AllocationCreateDesc {
                    name: "bench",
                    requirements,
                    location: loc.ga(),
                    linear: matches!(res, Res::Buffer(_)),
                    allocation_scheme: AllocationScheme::GpuAllocatorManaged,
                })
                .unwrap()
        }
        fn size_of(a: &Allocation) -> u64 {
            a.size()
        }
        fn memtype_of(&self, a: &Allocation) -> String {
            format!("{:?}", a.memory_properties())
        }
        fn free(&mut self, a: Allocation) {
            self.alloc.as_mut().unwrap().free(a).unwrap()
        }
        fn capacity(&self) -> u64 {
            self.alloc.as_ref().unwrap().capacity()
        }
        fn driver_usage(&self) -> u64 {
            if !self.has_budget {
                return 0;
            }
            let mut budget = vk::PhysicalDeviceMemoryBudgetPropertiesEXT::default();
            let mut mp2 = vk::PhysicalDeviceMemoryProperties2::default().push_next(&mut budget);
            unsafe { self.instance.get_physical_device_memory_properties2(self.pd, &mut mp2) };
            let n = mp2.memory_properties.memory_heap_count as usize;
            budget.heap_usage[..n].iter().sum()
        }
        fn info(&self) -> Value {
            json!({ "adapter": self.name, "memory_budget_ext": self.has_budget })
        }
    }

    impl Drop for Vk {
        fn drop(&mut self) {
            self.alloc = None;
            unsafe {
                self.device.destroy_device(None);
                self.instance.destroy_instance(None);
            }
        }
    }
}

// ---------------------------------------------------------------------------------------------
// D3D12
// ---------------------------------------------------------------------------------------------
mod dxb {
    use super::*;
    use gpu_allocator::d3d12::*;
    use windows::core::Interface;
    use windows::Win32::Graphics::{Direct3D::*, Direct3D12::*, Dxgi::Common::*, Dxgi::*};

    pub struct Dx {
        device: ID3D12Device,
        adapter: IDXGIAdapter3,
        name: String,
        alloc: Option<Allocator>,
        reqs: HashMap<(Loc, Res), AllocationCreateDesc<'static>>,
    }

    impl Dx {
        pub fn new() -> Self {
            let factory: IDXGIFactory4 = unsafe { CreateDXGIFactory2(DXGI_CREATE_FACTORY_FLAGS(0)) }.unwrap();
            let adapter: IDXGIAdapter1 = unsafe { factory.EnumAdapters1(0) }.unwrap();
            let desc = unsafe { adapter.GetDesc1() }.unwrap();
            let name = String::from_utf16_lossy(&desc.Description).trim_end_matches('\0').to_string();
            let mut device: Option<ID3D12Device> = None;
            unsafe { D3D12CreateDevice(&adapter, D3D_FEATURE_LEVEL_11_0, &mut device) }.unwrap();
            Self { device: device.unwrap(), adapter: adapter.cast().unwrap(), name, alloc: None, reqs: HashMap::new() }
        }
    }

    impl Backend for Dx {
        type A = Allocation;
        fn reset(&mut self, sizes: Option<AllocationSizes>) {
            self.alloc = None;
            if let Some(sizes) = sizes {
                self.alloc = Some(
                    Allocator::new(&AllocatorCreateDesc {
                        device: ID3D12DeviceVersion::Device(self.device.clone()),
                        debug_settings: quiet_debug_settings(),
                        allocation_sizes: sizes,
                    })
                    .unwrap(),
                );
            }
        }
        fn prepare(&mut self, loc: Loc, res: Res) {
            if self.reqs.contains_key(&(loc,res)) { return; }
            let desc = match res {
                Res::Buffer(size) => D3D12_RESOURCE_DESC {
                    Dimension: D3D12_RESOURCE_DIMENSION_BUFFER,
                    Width: size,
                    Height: 1,
                    DepthOrArraySize: 1,
                    MipLevels: 1,
                    Format: DXGI_FORMAT_UNKNOWN,
                    SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
                    Layout: D3D12_TEXTURE_LAYOUT_ROW_MAJOR,
                    ..Default::default()
                },
                Res::Texture(w, h) => D3D12_RESOURCE_DESC {
                    Dimension: D3D12_RESOURCE_DIMENSION_TEXTURE2D,
                    Width: w as u64,
                    Height: h,
                    DepthOrArraySize: 1,
                    MipLevels: 1,
                    Format: DXGI_FORMAT_R8G8B8A8_UNORM,
                    SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
                    Layout: D3D12_TEXTURE_LAYOUT_UNKNOWN,
                    ..Default::default()
                },
            };
            let ad = AllocationCreateDesc::from_d3d12_resource_desc(&self.device, &desc, "bench", loc.ga());
            self.reqs.insert((loc,res),ad);
        }
        fn report(&self) -> gpu_allocator::AllocatorReport { self.alloc.as_ref().unwrap().generate_report() }
        fn alloc(&mut self, loc: Loc, res: Res) -> Allocation {
            self.alloc.as_mut().unwrap().allocate(&self.reqs[&(loc,res)]).unwrap()
        }
        fn size_of(a: &Allocation) -> u64 {
            a.size()
        }
        fn memtype_of(&self, a: &Allocation) -> String {
            let p = unsafe { a.heap().GetDesc() }.Properties;
            let p = if p.Type == D3D12_HEAP_TYPE_CUSTOM {
                p
            } else {
                unsafe { self.device.GetCustomHeapProperties(0, p.Type) }
            };
            let page = match p.CPUPageProperty {
                D3D12_CPU_PAGE_PROPERTY_NOT_AVAILABLE => "NOT_AVAILABLE",
                D3D12_CPU_PAGE_PROPERTY_WRITE_COMBINE => "WRITE_COMBINE",
                D3D12_CPU_PAGE_PROPERTY_WRITE_BACK => "WRITE_BACK",
                _ => "?",
            };
            let pool = if p.MemoryPoolPreference == D3D12_MEMORY_POOL_L1 { "L1" } else { "L0" };
            let ty = unsafe { a.heap().GetDesc() }.Properties.Type.0;
            format!("type={ty} page={page} pool={pool}")
        }
        fn free(&mut self, a: Allocation) {
            self.alloc.as_mut().unwrap().free(a).unwrap()
        }
        fn capacity(&self) -> u64 {
            self.alloc.as_ref().unwrap().capacity()
        }
        fn driver_usage(&self) -> u64 {
            let mut info = DXGI_QUERY_VIDEO_MEMORY_INFO::default();
            unsafe { self.adapter.QueryVideoMemoryInfo(0, DXGI_MEMORY_SEGMENT_GROUP_LOCAL, &mut info) }.unwrap();
            let mut nl = DXGI_QUERY_VIDEO_MEMORY_INFO::default();
            let _ = unsafe { self.adapter.QueryVideoMemoryInfo(0, DXGI_MEMORY_SEGMENT_GROUP_NON_LOCAL, &mut nl) };
            info.CurrentUsage + nl.CurrentUsage
        }
        fn info(&self) -> Value {
            json!({ "adapter": self.name })
        }
    }
}

fn fragmentation(report: &gpu_allocator::AllocatorReport) -> Value {
    let mut largest=0;
    let mut unused=0;
    for block in &report.blocks {
        let mut allocations: Vec<_> = report.allocations[block.allocations.clone()].iter().collect();
        allocations.sort_by_key(|a| a.offset);
        let mut end=0;
        for a in allocations {
            let gap=a.offset.saturating_sub(end);
            largest=largest.max(gap);
            unused+=gap;
            end=a.offset+a.size;
        }
        let gap=block.size.saturating_sub(end);
        largest=largest.max(gap);
        unused+=gap;
    }
    json!({"unused_bytes":unused,"largest_gap_bytes":largest,
           "external_fragmentation":if unused>0 {1.0-largest as f64/unused as f64} else {0.0}})
}

fn quiet_debug_settings() -> gpu_allocator::AllocatorDebugSettings {
    let mut s = gpu_allocator::AllocatorDebugSettings::default();
    s.log_leaks_on_shutdown = false;
    s
}

fn run_all<B: Backend>(mut b: B, cfg: &str) -> Value {
    let (sizes, ranges) = config(cfg);
    let steps = step_set(&ranges);
    let mut out = serde_json::Map::new();
    for (name, ops) in workloads() {
        out.insert(name.into(), run_workload(&mut b, sizes, &steps, &ops));
    }
    json!({ "device": b.info(), "workloads": out })
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let backend = args.get(1).map(String::as_str).unwrap_or("vulkan");
    let cfg = args.get(2).map(String::as_str).unwrap_or("memory_usage");
    let trial: u32 = args.get(3).and_then(|t| t.parse().ok()).unwrap_or(0);
    let variant = args.get(4).cloned().unwrap_or_else(|| env!("BENCH_VARIANT").to_string());
    let t0 = Instant::now();
    let result = match backend {
        "vulkan" => run_all(vkb::Vk::new(), cfg),
        "d3d12" => run_all(dxb::Dx::new(), cfg),
        _ => panic!("backend must be vulkan or d3d12"),
    };
    let out = json!({
        "variant": variant,
        "backend": backend,
        "config": cfg,
        "trial": trial,
        "wall_s": t0.elapsed().as_secs_f64(),
        "result": result,
    });
    println!("{}", serde_json::to_string(&out).unwrap());
}
