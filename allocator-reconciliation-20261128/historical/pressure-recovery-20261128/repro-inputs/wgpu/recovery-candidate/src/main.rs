//! Standalone `wgpu` DX12 & Vulkan memory allocation and workload benchmark.
//! Completely independent of RustyGUI.
//!
//! Usage:
//!   wgpu-mem-bench --backend dx12|vulkan --hints performance|memory_usage|manual-4-256|manual-16-256|manual-32-256|manual-4-64 --workload <name> [--json <path>]

use std::sync::Arc;
use std::time::{Duration, Instant};

use serde::Serialize;
use windows::core::Interface;
use windows::Win32::Graphics::Dxgi::{
    CreateDXGIFactory1, IDXGIAdapter3, IDXGIFactory4, DXGI_MEMORY_SEGMENT_GROUP_LOCAL,
    DXGI_MEMORY_SEGMENT_GROUP_NON_LOCAL, DXGI_QUERY_VIDEO_MEMORY_INFO,
};
use windows::Win32::System::Memory::{
    VirtualQuery, MEMORY_BASIC_INFORMATION, MEM_COMMIT, MEM_RESERVE,
};
use windows::Win32::System::ProcessStatus::{
    GetProcessMemoryInfo, PROCESS_MEMORY_COUNTERS_EX2,
};
use windows::Win32::System::Threading::GetCurrentProcess;
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, EventLoop};
use winit::platform::windows::EventLoopBuilderExtWindows;
use winit::window::{Window, WindowId};

#[derive(Clone, Debug, Serialize)]
struct MemSnapshot {
    stage: String,
    working_set_bytes: u64,
    private_working_set_bytes: u64,
    private_commit_bytes: u64,
    peak_working_set_bytes: u64,
    reserved_va_bytes: u64,
    dxgi_local_usage_bytes: u64,
    dxgi_local_budget_bytes: u64,
    dxgi_non_local_usage_bytes: u64,
    dxgi_non_local_budget_bytes: u64,
    allocator_blocks: usize,
    allocator_block_sizes: Vec<u64>,
    allocator_allocations: usize,
    allocator_allocated_bytes: u64,
    allocator_reserved_bytes: u64,
    allocator_unused_bytes: u64,
    allocator_utilization_pct: f64,
    allocation_names: Vec<(String, u64)>,
}

#[derive(Clone, Debug, Serialize)]
struct TimingSummary {
    samples: usize,
    p50_us: f64,
    p90_us: f64,
    p99_us: f64,
    mean_us: f64,
    total_ms: f64,
}

#[derive(Clone, Debug, Serialize)]
struct BenchReport {
    backend: String,
    hints: String,
    workload: String,
    adapter_name: String,
    adapter_backend: String,
    adapter_device_type: String,
    adapter_driver: String,
    adapter_driver_info: String,
    stages: Vec<MemSnapshot>,
    cpu_op_timing: Option<TimingSummary>,
    gpu_pass_timing: Option<TimingSummary>,
    device_create_us: f64,
    peak_working_set_bytes: u64,
    peak_private_commit_bytes: u64,
    peak_allocator_reserved_bytes: u64,
}

fn query_reserved_va_bytes() -> u64 {
    let mut total_reserved = 0u64;
    let mut addr: usize = 0;
    let mut mbi = MEMORY_BASIC_INFORMATION::default();
    let mbi_size = std::mem::size_of::<MEMORY_BASIC_INFORMATION>();
    loop {
        let ret = unsafe { VirtualQuery(Some(addr as *const _), &mut mbi, mbi_size) };
        if ret == 0 {
            break;
        }
        if mbi.State == MEM_RESERVE || mbi.State == MEM_COMMIT {
            total_reserved = total_reserved.saturating_add(mbi.RegionSize as u64);
        }
        let next = (mbi.BaseAddress as usize).saturating_add(mbi.RegionSize);
        if next <= addr {
            break;
        }
        addr = next;
    }
    total_reserved
}

fn find_dxgi_adapter(name_hint: Option<&str>) -> Option<IDXGIAdapter3> {
    let factory: IDXGIFactory4 = unsafe { CreateDXGIFactory1().ok()? };
    let mut fallback = None;
    for i in 0..16 {
        let Ok(a1) = (unsafe { factory.EnumAdapters1(i) }) else {
            break;
        };
        let Ok(desc) = (unsafe { a1.GetDesc1() }) else {
            continue;
        };
        let len = desc.Description.iter().position(|&c| c == 0).unwrap_or(desc.Description.len());
        let name = String::from_utf16_lossy(&desc.Description[..len]);
        let Ok(a3) = a1.cast::<IDXGIAdapter3>() else {
            continue;
        };
        if let Some(hint) = name_hint {
            if name.contains(hint) || hint.contains(&name) {
                return Some(a3);
            }
        }
        if fallback.is_none() && (desc.Flags & 2) == 0 {
            fallback = Some(a3);
        }
    }
    fallback
}

fn snapshot(
    stage: &str,
    dxgi: Option<&IDXGIAdapter3>,
    device: Option<&wgpu::Device>,
    include_names: bool,
) -> MemSnapshot {
    let mut pmc = PROCESS_MEMORY_COUNTERS_EX2 {
        cb: std::mem::size_of::<PROCESS_MEMORY_COUNTERS_EX2>() as u32,
        ..Default::default()
    };
    unsafe {
        let _ = GetProcessMemoryInfo(
            GetCurrentProcess(),
            &mut pmc as *mut _ as *mut _,
            pmc.cb,
        );
    }
    let (local_u, local_b, non_local_u, non_local_b) = if let Some(a) = dxgi {
        let mut l = DXGI_QUERY_VIDEO_MEMORY_INFO::default();
        let mut nl = DXGI_QUERY_VIDEO_MEMORY_INFO::default();
        unsafe {
            let _ = a.QueryVideoMemoryInfo(0, DXGI_MEMORY_SEGMENT_GROUP_LOCAL, &mut l);
            let _ = a.QueryVideoMemoryInfo(0, DXGI_MEMORY_SEGMENT_GROUP_NON_LOCAL, &mut nl);
        }
        (l.CurrentUsage, l.Budget, nl.CurrentUsage, nl.Budget)
    } else {
        (0, 0, 0, 0)
    };

    let (blocks, block_sizes, allocs, alloc_bytes, res_bytes, names) =
        if let Some(dev) = device.and_then(|d| d.generate_allocator_report()) {
            let sizes: Vec<u64> = dev.blocks.iter().map(|b| b.size).collect();
            let names = if include_names {
                dev.allocations
                    .iter()
                    .take(64)
                    .map(|a| (a.name.clone(), a.size))
                    .collect()
            } else {
                Vec::new()
            };
            (
                dev.blocks.len(),
                sizes,
                dev.allocations.len(),
                dev.total_allocated_bytes,
                dev.total_reserved_bytes,
                names,
            )
        } else {
            (0, Vec::new(), 0, 0, 0, Vec::new())
        };

    let unused = res_bytes.saturating_sub(alloc_bytes);
    let util = if res_bytes > 0 {
        (alloc_bytes as f64 / res_bytes as f64) * 100.0
    } else {
        0.0
    };

    MemSnapshot {
        stage: stage.to_string(),
        working_set_bytes: pmc.WorkingSetSize as u64,
        private_working_set_bytes: pmc.PrivateWorkingSetSize as u64,
        private_commit_bytes: pmc.PrivateUsage as u64,
        peak_working_set_bytes: pmc.PeakWorkingSetSize as u64,
        reserved_va_bytes: query_reserved_va_bytes(),
        dxgi_local_usage_bytes: local_u,
        dxgi_local_budget_bytes: local_b,
        dxgi_non_local_usage_bytes: non_local_u,
        dxgi_non_local_budget_bytes: non_local_b,
        allocator_blocks: blocks,
        allocator_block_sizes: block_sizes,
        allocator_allocations: allocs,
        allocator_allocated_bytes: alloc_bytes,
        allocator_reserved_bytes: res_bytes,
        allocator_unused_bytes: unused,
        allocator_utilization_pct: util,
        allocation_names: names,
    }
}

fn summarize_us(samples: &[f64]) -> Option<TimingSummary> {
    if samples.is_empty() {
        return None;
    }
    let mut s = samples.to_vec();
    s.sort_by(|a, b| a.total_cmp(b));
    let pct = |p: f64| -> f64 {
        let idx = ((s.len() - 1) as f64 * p).round() as usize;
        s[idx]
    };
    let sum: f64 = s.iter().sum();
    Some(TimingSummary {
        samples: s.len(),
        p50_us: pct(0.50),
        p90_us: pct(0.90),
        p99_us: pct(0.99),
        mean_us: sum / s.len() as f64,
        total_ms: sum / 1000.0,
    })
}

fn parse_hints(name: &str) -> wgpu::MemoryHints {
    const MB: u64 = 1024 * 1024;
    match name {
        "performance" | "default" => wgpu::MemoryHints::Performance,
        "memory_usage" => wgpu::MemoryHints::MemoryUsage,
        "manual-4-256" => wgpu::MemoryHints::Manual {
            suballocated_device_memory_block_size: (4 * MB)..(256 * MB),
        },
        "manual-8-256" => wgpu::MemoryHints::Manual {
            suballocated_device_memory_block_size: (8 * MB)..(256 * MB),
        },
        "manual-16-256" => wgpu::MemoryHints::Manual {
            suballocated_device_memory_block_size: (16 * MB)..(256 * MB),
        },
        "manual-32-256" => wgpu::MemoryHints::Manual {
            suballocated_device_memory_block_size: (32 * MB)..(256 * MB),
        },
        "manual-4-64" => wgpu::MemoryHints::Manual {
            suballocated_device_memory_block_size: (4 * MB)..(64 * MB),
        },
        other => panic!("Unknown hints: {other}"),
    }
}

fn mib(b: u64) -> f64 {
    b as f64 / (1024.0 * 1024.0)
}

fn print_stage(s: &MemSnapshot) {
    println!(
        "{:<26} WS={:>7.2} PrivWS={:>7.2} PrivCom={:>7.2} VA={:>8.1} | DXGI L={:>6.2} NL={:>6.2} | Alloc blks={} res={:>6.2} alloc={:>6.2} unused={:>6.2} ({:>5.1}%)",
        s.stage,
        mib(s.working_set_bytes),
        mib(s.private_working_set_bytes),
        mib(s.private_commit_bytes),
        mib(s.reserved_va_bytes),
        mib(s.dxgi_local_usage_bytes),
        mib(s.dxgi_non_local_usage_bytes),
        s.allocator_blocks,
        mib(s.allocator_reserved_bytes),
        mib(s.allocator_allocated_bytes),
        mib(s.allocator_unused_bytes),
        s.allocator_utilization_pct,
    );
}

const RENDER_WGSL: &str = r#"
@vertex fn vs(@builtin(vertex_index) i: u32) -> @builtin(position) vec4<f32> {
    let x = f32((i << 1u) & 2u) * 2.0 - 1.0;
    let y = f32(i & 2u) * 2.0 - 1.0;
    return vec4<f32>(x, y, 0.0, 1.0);
}
@fragment fn fs() -> @location(0) vec4<f32> {
    return vec4<f32>(0.2, 0.4, 0.8, 1.0);
}
"#;

const COMPUTE_WGSL: &str = r#"
@group(0) @binding(0) var<storage, read_write> data: array<u32>;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let idx = id.x;
    if idx < arrayLength(&data) {
        data[idx] = data[idx] * 1664525u + 1013904223u;
    }
}
"#;

struct MultiSurfaceApp {
    backends: wgpu::Backends,
    hints: wgpu::MemoryHints,
    dxgi: Option<IDXGIAdapter3>,
    stages: Vec<MemSnapshot>,
    adapter_info: Option<wgpu::AdapterInfo>,
    device_create_us: f64,
    cpu_samples: Vec<f64>,
}

impl ApplicationHandler for MultiSurfaceApp {
    fn resumed(&mut self, el: &ActiveEventLoop) {
        let mut windows = Vec::new();
        for i in 0..3 {
            let w = Arc::new(
                el.create_window(
                    Window::default_attributes()
                        .with_title(format!("wgpu-multi-{i}"))
                        .with_inner_size(LogicalSize::new(640.0, 480.0))
                        .with_visible(false),
                )
                .unwrap(),
            );
            windows.push(w);
        }
        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
            backends: self.backends,
            ..wgpu::InstanceDescriptor::new_without_display_handle()
        });
        let s = snapshot("1_instance_new", self.dxgi.as_ref(), None, false);
        print_stage(&s);
        self.stages.push(s);

        let surfaces: Vec<_> = windows
            .iter()
            .map(|w| instance.create_surface(w.clone()).unwrap())
            .collect();
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            compatible_surface: Some(&surfaces[0]),
            power_preference: wgpu::PowerPreference::HighPerformance,
            ..Default::default()
        }))
        .unwrap();
        let info = adapter.get_info();
        self.dxgi = find_dxgi_adapter(Some(&info.name));
        self.adapter_info = Some(info);
        let s = snapshot("2_adapter_request", self.dxgi.as_ref(), None, false);
        print_stage(&s);
        self.stages.push(s);

        let t0 = Instant::now();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            memory_hints: self.hints.clone(),
            ..Default::default()
        }))
        .unwrap();
        self.device_create_us = t0.elapsed().as_secs_f64() * 1e6;
        let s = snapshot("3_device_request", self.dxgi.as_ref(), Some(&device), true);
        print_stage(&s);
        self.stages.push(s);

        for (i, surf) in surfaces.iter().enumerate() {
            let sz = windows[i].inner_size();
            let mut cfg = surf
                .get_default_config(&adapter, sz.width.max(1), sz.height.max(1))
                .unwrap();
            cfg.present_mode = wgpu::PresentMode::Fifo;
            surf.configure(&device, &cfg);
        }
        let s = snapshot("4_3_surfaces_configured", self.dxgi.as_ref(), Some(&device), true);
        print_stage(&s);
        self.stages.push(s);

        for _ in 0..30 {
            let ft = Instant::now();
            for surf in &surfaces {
                if let wgpu::CurrentSurfaceTexture::Success(frame)
                | wgpu::CurrentSurfaceTexture::Suboptimal(frame) = surf.get_current_texture()
                {
                    let view = frame.texture.create_view(&Default::default());
                    let mut enc = device.create_command_encoder(&Default::default());
                    {
                        let _rp = enc.begin_render_pass(&wgpu::RenderPassDescriptor {
                            label: None,
                            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                                view: &view,
                                depth_slice: None,
                                resolve_target: None,
                                ops: wgpu::Operations {
                                    load: wgpu::LoadOp::Clear(wgpu::Color::GREEN),
                                    store: wgpu::StoreOp::Store,
                                },
                            })],
                            depth_stencil_attachment: None,
                            timestamp_writes: None,
                            occlusion_query_set: None,
                            multiview_mask: None,
                        });
                    }
                    queue.submit([enc.finish()]);
                    queue.present(frame);
                }
            }
            self.cpu_samples.push(ft.elapsed().as_secs_f64() * 1e6);
        }
        let _ = device.poll(wgpu::PollType::wait_indefinitely());
        let s = snapshot("8_workload_complete", self.dxgi.as_ref(), Some(&device), false);
        print_stage(&s);
        self.stages.push(s);

        drop(surfaces);
        let _ = device.poll(wgpu::PollType::wait_indefinitely());
        let s = snapshot("9_resources_dropped", self.dxgi.as_ref(), Some(&device), false);
        print_stage(&s);
        self.stages.push(s);

        drop(queue);
        drop(device);
        let s = snapshot("11_device_dropped", self.dxgi.as_ref(), None, false);
        print_stage(&s);
        self.stages.push(s);

        drop(windows);
        el.exit();
    }

    fn window_event(&mut self, _: &ActiveEventLoop, _: WindowId, _: WindowEvent) {}
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let get_arg = |flag: &str, default: &str| -> String {
        args.windows(2)
            .find(|w| w[0] == flag)
            .map(|w| w[1].clone())
            .unwrap_or_else(|| default.to_string())
    };
    let backend_name = get_arg("--backend", "dx12");
    let hints_name = get_arg("--hints", "performance");
    let workload = get_arg("--workload", "idle");
    let json_path = args
        .windows(2)
        .find(|w| w[0] == "--json")
        .map(|w| w[1].clone());

    let backends = match backend_name.as_str() {
        "dx12" => wgpu::Backends::DX12,
        "vulkan" => wgpu::Backends::VULKAN,
        other => panic!("Unknown backend: {other}"),
    };
    let hints = parse_hints(&hints_name);

    let mut dxgi = find_dxgi_adapter(None);
    let mut stages = Vec::new();
    let s0 = snapshot("0_process_start", dxgi.as_ref(), None, false);
    println!("=== wgpu-mem-bench backend={backend_name} hints={hints_name} workload={workload} ===");
    print_stage(&s0);
    stages.push(s0);

    if workload == "multi_surface" {
        let el = EventLoop::builder().with_any_thread(true).build().unwrap();
        let mut app = MultiSurfaceApp {
            backends,
            hints,
            dxgi,
            stages,
            adapter_info: None,
            device_create_us: 0.0,
            cpu_samples: Vec::new(),
        };
        el.run_app(&mut app).unwrap();
        let info = app.adapter_info.unwrap();
        let report = build_report(
            backend_name,
            hints_name,
            workload,
            info,
            app.stages,
            summarize_us(&app.cpu_samples),
            None,
            app.device_create_us,
        );
        if let Some(p) = json_path {
            std::fs::write(p, serde_json::to_string_pretty(&report).unwrap()).unwrap();
        }
        return;
    }

    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends,
        ..wgpu::InstanceDescriptor::new_without_display_handle()
    });
    let s1 = snapshot("1_instance_new", dxgi.as_ref(), None, false);
    print_stage(&s1);
    stages.push(s1);

    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        ..Default::default()
    }))
    .unwrap();
    let info = adapter.get_info();
    dxgi = find_dxgi_adapter(Some(&info.name));
    println!(
        "  adapter: {} ({:?}, {:?}, driver={} {})",
        info.name, info.backend, info.device_type, info.driver, info.driver_info
    );
    let s2 = snapshot("2_adapter_request", dxgi.as_ref(), None, false);
    print_stage(&s2);
    stages.push(s2);

    let has_ts = adapter.features().contains(wgpu::Features::TIMESTAMP_QUERY);
    let req_features = if has_ts {
        wgpu::Features::TIMESTAMP_QUERY
    } else {
        wgpu::Features::empty()
    };

    let t_dev = Instant::now();
    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
        required_features: req_features,
        required_limits: adapter.limits(),
        memory_hints: hints,
        ..Default::default()
    }))
    .unwrap();
    let device_create_us = t_dev.elapsed().as_secs_f64() * 1e6;
    let s3 = snapshot("3_device_request", dxgi.as_ref(), Some(&device), true);
    print_stage(&s3);
    println!("  device_request blocks={:?} allocs={:?}", s3.allocator_block_sizes, s3.allocation_names);
    stages.push(s3);

    let mut cpu_samples: Vec<f64> = Vec::new();
    let mut gpu_samples: Vec<f64> = Vec::new();

    if workload == "idle" {
        std::thread::sleep(Duration::from_millis(500));
        let _ = device.poll(wgpu::PollType::wait_indefinitely());
        let s10 = snapshot("10_extended_idle", dxgi.as_ref(), Some(&device), true);
        print_stage(&s10);
        stages.push(s10);
    } else {
        // Common stage 4..7 setup
        let first_buf = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("first_buf_64k"),
            size: 64 * 1024,
            usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        let first_tex = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("first_tex_512"),
            size: wgpu::Extent3d { width: 512, height: 512, depth_or_array_layers: 1 },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm,
            usage: wgpu::TextureUsages::TEXTURE_BINDING
                | wgpu::TextureUsages::COPY_DST
                | wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
            texture_binding_view_dimension: None,
        });
        let s4 = snapshot("4_first_buf_and_tex", dxgi.as_ref(), Some(&device), true);
        print_stage(&s4);
        stages.push(s4);

        let upload_data = vec![0xABu8; 64 * 1024];
        queue.write_buffer(&first_buf, 0, &upload_data);
        let tex_data = vec![0x7Fu8; 512 * 512 * 4];
        queue.write_texture(
            first_tex.as_image_copy(),
            &tex_data,
            wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(512 * 4),
                rows_per_image: Some(512),
            },
            wgpu::Extent3d { width: 512, height: 512, depth_or_array_layers: 1 },
        );
        let s5 = snapshot("5_first_upload", dxgi.as_ref(), Some(&device), false);
        print_stage(&s5);
        stages.push(s5);

        let render_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("render_shader"),
            source: wgpu::ShaderSource::Wgsl(RENDER_WGSL.into()),
        });
        let render_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("render_pipeline"),
            layout: None,
            vertex: wgpu::VertexState {
                module: &render_shader,
                entry_point: Some("vs"),
                compilation_options: Default::default(),
                buffers: &[],
            },
            fragment: Some(wgpu::FragmentState {
                module: &render_shader,
                entry_point: Some("fs"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::TextureFormat::Rgba8Unorm.into())],
            }),
            primitive: Default::default(),
            depth_stencil: None,
            multisample: Default::default(),
            multiview_mask: None,
            cache: None,
        });
        let s6 = snapshot("6_pipeline_creation", dxgi.as_ref(), Some(&device), false);
        print_stage(&s6);
        stages.push(s6);

        let first_view = first_tex.create_view(&Default::default());
        {
            let mut enc = device.create_command_encoder(&Default::default());
            {
                let mut rp = enc.begin_render_pass(&wgpu::RenderPassDescriptor {
                    label: None,
                    color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                        view: &first_view,
                        depth_slice: None,
                        resolve_target: None,
                        ops: wgpu::Operations {
                            load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                            store: wgpu::StoreOp::Store,
                        },
                    })],
                    depth_stencil_attachment: None,
                    timestamp_writes: None,
                    occlusion_query_set: None,
                    multiview_mask: None,
                });
                rp.set_pipeline(&render_pipeline);
                rp.draw(0..3, 0..1);
            }
            queue.submit([enc.finish()]);
            let _ = device.poll(wgpu::PollType::wait_indefinitely());
        }
        let s7 = snapshot("7_first_submit_and_poll", dxgi.as_ref(), Some(&device), false);
        print_stage(&s7);
        stages.push(s7);

        // Run selected workload
        match workload.as_str() {
            "small_gui" => {
                // Retained GUI: 2048x2048 R8 glyph atlas (4 MiB) + 1200x800 RT (3.84 MiB) + 256 KiB vertex/instance
                let atlas = device.create_texture(&wgpu::TextureDescriptor {
                    label: Some("glyph_atlas"),
                    size: wgpu::Extent3d { width: 2048, height: 2048, depth_or_array_layers: 1 },
                    mip_level_count: 1,
                    sample_count: 1,
                    dimension: wgpu::TextureDimension::D2,
                    format: wgpu::TextureFormat::R8Unorm,
                    usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
                    view_formats: &[],
            texture_binding_view_dimension: None,
                });
                let rt = device.create_texture(&wgpu::TextureDescriptor {
                    label: Some("gui_rt"),
                    size: wgpu::Extent3d { width: 1200, height: 800, depth_or_array_layers: 1 },
                    mip_level_count: 1,
                    sample_count: 1,
                    dimension: wgpu::TextureDimension::D2,
                    format: wgpu::TextureFormat::Rgba8Unorm,
                    usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
                    view_formats: &[],
            texture_binding_view_dimension: None,
                });
                let rt_view = rt.create_view(&Default::default());
                let inst_buf = device.create_buffer(&wgpu::BufferDescriptor {
                    label: Some("gui_instances"),
                    size: 256 * 1024,
                    usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
                    mapped_at_creation: false,
                });
                let chunk = vec![42u8; 16 * 1024];
                for i in 0..200 {
                    let t0 = Instant::now();
                    queue.write_buffer(&inst_buf, ((i % 16) * 16 * 1024) as u64, &chunk);
                    let mut enc = device.create_command_encoder(&Default::default());
                    {
                        let mut rp = enc.begin_render_pass(&wgpu::RenderPassDescriptor {
                            label: None,
                            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                                view: &rt_view,
                                depth_slice: None,
                                resolve_target: None,
                                ops: wgpu::Operations {
                                    load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                                    store: wgpu::StoreOp::Store,
                                },
                            })],
                            depth_stencil_attachment: None,
                            timestamp_writes: None,
                            occlusion_query_set: None,
                            multiview_mask: None,
                        });
                        rp.set_pipeline(&render_pipeline);
                        rp.draw(0..3, 0..1);
                    }
                    queue.submit([enc.finish()]);
                    let _ = device.poll(wgpu::PollType::wait_indefinitely());
                    if i >= 20 {
                        cpu_samples.push(t0.elapsed().as_secs_f64() * 1e6);
                    }
                }
                let s8 = snapshot("8_workload_complete", dxgi.as_ref(), Some(&device), false);
                print_stage(&s8);
                stages.push(s8);
                drop((atlas, rt_view, rt, inst_buf));
            }
            "repeated_uploads" => {
                let target = device.create_buffer(&wgpu::BufferDescriptor {
                    label: Some("upload_target_4m"),
                    size: 4 * 1024 * 1024,
                    usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_DST,
                    mapped_at_creation: false,
                });
                let payload = vec![1u8; 256 * 1024];
                for i in 0..400 {
                    let t0 = Instant::now();
                    queue.write_buffer(&target, ((i % 16) * 256 * 1024) as u64, &payload);
                    queue.submit([]);
                    let _ = device.poll(wgpu::PollType::wait_indefinitely());
                    if i >= 40 {
                        cpu_samples.push(t0.elapsed().as_secs_f64() * 1e6);
                    }
                }
                let s8 = snapshot("8_workload_complete", dxgi.as_ref(), Some(&device), false);
                print_stage(&s8);
                stages.push(s8);
                drop(target);
            }
            "large_textures" => {
                // 20 x 2048x2048 RGBA8 = 320 MiB
                let mut textures = Vec::new();
                let row_data = vec![0x55u8; 2048 * 2048 * 4];
                for i in 0..20 {
                    let t0 = Instant::now();
                    let tex = device.create_texture(&wgpu::TextureDescriptor {
                        label: Some("large_tex_16m"),
                        size: wgpu::Extent3d { width: 2048, height: 2048, depth_or_array_layers: 1 },
                        mip_level_count: 1,
                        sample_count: 1,
                        dimension: wgpu::TextureDimension::D2,
                        format: wgpu::TextureFormat::Rgba8Unorm,
                        usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
                        view_formats: &[],
            texture_binding_view_dimension: None,
                    });
                    queue.write_texture(
                        tex.as_image_copy(),
                        &row_data,
                        wgpu::TexelCopyBufferLayout {
                            offset: 0,
                            bytes_per_row: Some(2048 * 4),
                            rows_per_image: Some(2048),
                        },
                        wgpu::Extent3d { width: 2048, height: 2048, depth_or_array_layers: 1 },
                    );
                    queue.submit([]);
                    let _ = device.poll(wgpu::PollType::wait_indefinitely());
                    cpu_samples.push(t0.elapsed().as_secs_f64() * 1e6);
                    textures.push(tex);
                    let _ = i;
                }
                let s8 = snapshot("8_workload_complete", dxgi.as_ref(), Some(&device), false);
                print_stage(&s8);
                stages.push(s8);
                drop(textures);
            }
            "churn" => {
                // Repeated mixed-size allocation + destruction churn (64 KiB .. 16 MiB)
                let sizes = [64 * 1024u64, 512 * 1024, 2 * 1024 * 1024, 8 * 1024 * 1024, 16 * 1024 * 1024];
                let mut live = Vec::new();
                for i in 0..250 {
                    let t0 = Instant::now();
                    let sz = sizes[i % sizes.len()];
                    let b = device.create_buffer(&wgpu::BufferDescriptor {
                        label: Some("churn_buf"),
                        size: sz,
                        usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_DST,
                        mapped_at_creation: false,
                    });
                    live.push(b);
                    if live.len() > 8 {
                        live.remove(0);
                    }
                    if i % 4 == 0 {
                        let _ = device.poll(wgpu::PollType::wait_indefinitely());
                    }
                    if i >= 25 {
                        cpu_samples.push(t0.elapsed().as_secs_f64() * 1e6);
                    }
                }
                let _ = device.poll(wgpu::PollType::wait_indefinitely());
                let s8 = snapshot("8_workload_complete", dxgi.as_ref(), Some(&device), false);
                print_stage(&s8);
                stages.push(s8);
                drop(live);
            }
            "sustained_render" => {
                let rt = device.create_texture(&wgpu::TextureDescriptor {
                    label: Some("sustained_rt"),
                    size: wgpu::Extent3d { width: 1920, height: 1080, depth_or_array_layers: 1 },
                    mip_level_count: 1,
                    sample_count: 1,
                    dimension: wgpu::TextureDimension::D2,
                    format: wgpu::TextureFormat::Rgba8Unorm,
                    usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
                    view_formats: &[],
            texture_binding_view_dimension: None,
                });
                let rt_view = rt.create_view(&Default::default());
                let qs = has_ts.then(|| {
                    device.create_query_set(&wgpu::QuerySetDescriptor {
                        label: Some("ts"),
                        ty: wgpu::QueryType::Timestamp,
                        count: 2,
                    })
                });
                let ts_resolve = has_ts.then(|| {
                    device.create_buffer(&wgpu::BufferDescriptor {
                        label: Some("ts_resolve"),
                        size: 16,
                        usage: wgpu::BufferUsages::QUERY_RESOLVE | wgpu::BufferUsages::COPY_SRC,
                        mapped_at_creation: false,
                    })
                });
                let ts_read = has_ts.then(|| {
                    device.create_buffer(&wgpu::BufferDescriptor {
                        label: Some("ts_read"),
                        size: 16,
                        usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
                        mapped_at_creation: false,
                    })
                });
                let period_ns = queue.get_timestamp_period() as f64;
                for i in 0..250 {
                    let t0 = Instant::now();
                    let mut enc = device.create_command_encoder(&Default::default());
                    {
                        let mut rp = enc.begin_render_pass(&wgpu::RenderPassDescriptor {
                            label: None,
                            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                                view: &rt_view,
                                depth_slice: None,
                                resolve_target: None,
                                ops: wgpu::Operations {
                                    load: wgpu::LoadOp::Clear(wgpu::Color::BLUE),
                                    store: wgpu::StoreOp::Store,
                                },
                            })],
                            depth_stencil_attachment: None,
                            timestamp_writes: qs.as_ref().map(|q| wgpu::RenderPassTimestampWrites {
                                query_set: q,
                                beginning_of_pass_write_index: Some(0),
                                end_of_pass_write_index: Some(1),
                            }),
                            occlusion_query_set: None,
                            multiview_mask: None,
                        });
                        rp.set_pipeline(&render_pipeline);
                        for _ in 0..100 {
                            rp.draw(0..3, 0..1);
                        }
                    }
                    if let (Some(q), Some(res), Some(rd)) = (&qs, &ts_resolve, &ts_read) {
                        enc.resolve_query_set(q, 0..2, res, 0);
                        enc.copy_buffer_to_buffer(res, 0, rd, 0, 16);
                    }
                    queue.submit([enc.finish()]);
                    if let Some(rd) = &ts_read {
                        let slice = rd.slice(..);
                        let (tx, rx) = std::sync::mpsc::channel();
                        slice.map_async(wgpu::MapMode::Read, move |r| {
                            let _ = tx.send(r);
                        });
                        let _ = device.poll(wgpu::PollType::wait_indefinitely());
                        rx.recv().unwrap().unwrap();
                        let data = slice.get_mapped_range().unwrap();
                        let t_start = u64::from_le_bytes(data[0..8].try_into().unwrap());
                        let t_end = u64::from_le_bytes(data[8..16].try_into().unwrap());
                        drop(data);
                        rd.unmap();
                        if i >= 25 && t_end >= t_start {
                            gpu_samples.push((t_end - t_start) as f64 * period_ns / 1000.0);
                        }
                    } else {
                        let _ = device.poll(wgpu::PollType::wait_indefinitely());
                    }
                    if i >= 25 {
                        cpu_samples.push(t0.elapsed().as_secs_f64() * 1e6);
                    }
                }
                let s8 = snapshot("8_workload_complete", dxgi.as_ref(), Some(&device), false);
                print_stage(&s8);
                stages.push(s8);
                drop((qs, ts_resolve, ts_read, rt_view, rt));
            }
            "sustained_compute" => {
                let cs_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
                    label: Some("compute_shader"),
                    source: wgpu::ShaderSource::Wgsl(COMPUTE_WGSL.into()),
                });
                let cs_pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
                    label: Some("cs_pipe"),
                    layout: None,
                    module: &cs_shader,
                    entry_point: Some("main"),
                    compilation_options: Default::default(),
                    cache: None,
                });
                let buf = device.create_buffer(&wgpu::BufferDescriptor {
                    label: Some("compute_64m"),
                    size: 64 * 1024 * 1024,
                    usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_DST,
                    mapped_at_creation: false,
                });
                let bg = device.create_bind_group(&wgpu::BindGroupDescriptor {
                    label: Some("cs_bg"),
                    layout: &cs_pipeline.get_bind_group_layout(0),
                    entries: &[wgpu::BindGroupEntry {
                        binding: 0,
                        resource: buf.as_entire_binding(),
                    }],
                });
                let qs = has_ts.then(|| {
                    device.create_query_set(&wgpu::QuerySetDescriptor {
                        label: Some("ts"),
                        ty: wgpu::QueryType::Timestamp,
                        count: 2,
                    })
                });
                let ts_resolve = has_ts.then(|| {
                    device.create_buffer(&wgpu::BufferDescriptor {
                        label: Some("ts_resolve"),
                        size: 16,
                        usage: wgpu::BufferUsages::QUERY_RESOLVE | wgpu::BufferUsages::COPY_SRC,
                        mapped_at_creation: false,
                    })
                });
                let ts_read = has_ts.then(|| {
                    device.create_buffer(&wgpu::BufferDescriptor {
                        label: Some("ts_read"),
                        size: 16,
                        usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
                        mapped_at_creation: false,
                    })
                });
                let period_ns = queue.get_timestamp_period() as f64;
                let workgroups = (64 * 1024 * 1024 / 4) / 64;
                for i in 0..120 {
                    let t0 = Instant::now();
                    let mut enc = device.create_command_encoder(&Default::default());
                    {
                        let mut cp = enc.begin_compute_pass(&wgpu::ComputePassDescriptor {
                            label: None,
                            timestamp_writes: qs.as_ref().map(|q| wgpu::ComputePassTimestampWrites {
                                query_set: q,
                                beginning_of_pass_write_index: Some(0),
                                end_of_pass_write_index: Some(1),
                            }),
                        });
                        cp.set_pipeline(&cs_pipeline);
                        cp.set_bind_group(0, &bg, &[]);
                        cp.dispatch_workgroups(workgroups.min(65535) as u32, 1, 1);
                    }
                    if let (Some(q), Some(res), Some(rd)) = (&qs, &ts_resolve, &ts_read) {
                        enc.resolve_query_set(q, 0..2, res, 0);
                        enc.copy_buffer_to_buffer(res, 0, rd, 0, 16);
                    }
                    queue.submit([enc.finish()]);
                    if let Some(rd) = &ts_read {
                        let slice = rd.slice(..);
                        let (tx, rx) = std::sync::mpsc::channel();
                        slice.map_async(wgpu::MapMode::Read, move |r| {
                            let _ = tx.send(r);
                        });
                        let _ = device.poll(wgpu::PollType::wait_indefinitely());
                        rx.recv().unwrap().unwrap();
                        let data = slice.get_mapped_range().unwrap();
                        let t_start = u64::from_le_bytes(data[0..8].try_into().unwrap());
                        let t_end = u64::from_le_bytes(data[8..16].try_into().unwrap());
                        drop(data);
                        rd.unmap();
                        if i >= 15 && t_end >= t_start {
                            gpu_samples.push((t_end - t_start) as f64 * period_ns / 1000.0);
                        }
                    } else {
                        let _ = device.poll(wgpu::PollType::wait_indefinitely());
                    }
                    if i >= 15 {
                        cpu_samples.push(t0.elapsed().as_secs_f64() * 1e6);
                    }
                }
                let s8 = snapshot("8_workload_complete", dxgi.as_ref(), Some(&device), false);
                print_stage(&s8);
                stages.push(s8);
                drop((qs, ts_resolve, ts_read, bg, buf, cs_pipeline, cs_shader));
            }
            "large_alloc" => {
                // Sequence of large buffers: 24 MiB, 48 MiB, 96 MiB, 192 MiB, 300 MiB
                // Tests dedicated vs general block growth!
                let mut bufs = Vec::new();
                for mb in [24u64, 48, 96, 192, 300] {
                    let t0 = Instant::now();
                    let b = device.create_buffer(&wgpu::BufferDescriptor {
                        label: Some("large_buf"),
                        size: mb * 1024 * 1024,
                        usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_DST,
                        mapped_at_creation: false,
                    });
                    cpu_samples.push(t0.elapsed().as_secs_f64() * 1e6);
                    bufs.push(b);
                }
                let s8 = snapshot("8_workload_complete", dxgi.as_ref(), Some(&device), true);
                print_stage(&s8);
                println!("  large_alloc blocks={:?}", s8.allocator_block_sizes);
                stages.push(s8);
                drop(bufs);
            }
            other => panic!("Unknown workload: {other}"),
        }

        drop((first_view, render_pipeline, render_shader, first_tex, first_buf));
        let _ = device.poll(wgpu::PollType::wait_indefinitely());
        let s9 = snapshot("9_resources_dropped", dxgi.as_ref(), Some(&device), true);
        print_stage(&s9);
        println!("  after_drop blocks={:?} allocs={:?}", s9.allocator_block_sizes, s9.allocation_names);
        stages.push(s9);

        std::thread::sleep(Duration::from_millis(500));
        let _ = device.poll(wgpu::PollType::wait_indefinitely());
        let s10 = snapshot("10_extended_idle", dxgi.as_ref(), Some(&device), false);
        print_stage(&s10);
        stages.push(s10);
    }

    drop(queue);
    drop(device);
    let s11 = snapshot("11_device_dropped", dxgi.as_ref(), None, false);
    print_stage(&s11);
    stages.push(s11);

    let report = build_report(
        backend_name,
        hints_name,
        workload,
        info,
        stages,
        summarize_us(&cpu_samples),
        summarize_us(&gpu_samples),
        device_create_us,
    );
    if let Some(ref c) = report.cpu_op_timing {
        println!(
            "  CPU timing: n={} p50={:.1}us p90={:.1}us p99={:.1}us mean={:.1}us",
            c.samples, c.p50_us, c.p90_us, c.p99_us, c.mean_us
        );
    }
    if let Some(ref g) = report.gpu_pass_timing {
        println!(
            "  GPU timing: n={} p50={:.1}us p90={:.1}us p99={:.1}us mean={:.1}us",
            g.samples, g.p50_us, g.p90_us, g.p99_us, g.mean_us
        );
    }
    if let Some(p) = json_path {
        std::fs::write(p, serde_json::to_string_pretty(&report).unwrap()).unwrap();
    }
}

#[allow(clippy::too_many_arguments)]
fn build_report(
    backend: String,
    hints: String,
    workload: String,
    info: wgpu::AdapterInfo,
    stages: Vec<MemSnapshot>,
    cpu_op_timing: Option<TimingSummary>,
    gpu_pass_timing: Option<TimingSummary>,
    device_create_us: f64,
) -> BenchReport {
    let peak_ws = stages.iter().map(|s| s.peak_working_set_bytes).max().unwrap_or(0);
    let peak_priv = stages.iter().map(|s| s.private_commit_bytes).max().unwrap_or(0);
    let peak_res = stages.iter().map(|s| s.allocator_reserved_bytes).max().unwrap_or(0);
    BenchReport {
        backend,
        hints,
        workload,
        adapter_name: info.name,
        adapter_backend: format!("{:?}", info.backend),
        adapter_device_type: format!("{:?}", info.device_type),
        adapter_driver: info.driver,
        adapter_driver_info: info.driver_info,
        stages,
        cpu_op_timing,
        gpu_pass_timing,
        device_create_us,
        peak_working_set_bytes: peak_ws,
        peak_private_commit_bytes: peak_priv,
        peak_allocator_reserved_bytes: peak_res,
    }
}
