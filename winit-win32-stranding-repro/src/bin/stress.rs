use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use winit::application::ApplicationHandler;
use winit::dpi::{LogicalSize, PhysicalPosition};
use winit::event::{StartCause, WindowEvent};
use winit::event_loop::run_on_demand::EventLoopExtRunOnDemand;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::platform::windows::EventLoopBuilderExtWindows;
use winit::window::{Window, WindowAttributes, WindowId};

use windows_sys::Win32::Foundation::FILETIME;
use windows_sys::Win32::System::Threading::{GetCurrentProcess, GetProcessTimes};

fn process_cpu_ms() -> f64 {
    let mut create = FILETIME { dwLowDateTime: 0, dwHighDateTime: 0 };
    let mut exit = FILETIME { dwLowDateTime: 0, dwHighDateTime: 0 };
    let mut kernel = FILETIME { dwLowDateTime: 0, dwHighDateTime: 0 };
    let mut user = FILETIME { dwLowDateTime: 0, dwHighDateTime: 0 };
    unsafe {
        GetProcessTimes(GetCurrentProcess(), &mut create, &mut exit, &mut kernel, &mut user);
    }
    let k = ((kernel.dwHighDateTime as u64) << 32) | (kernel.dwLowDateTime as u64);
    let u = ((user.dwHighDateTime as u64) << 32) | (user.dwLowDateTime as u64);
    // 100ns ticks -> ms
    (k + u) as f64 / 10_000.0
}

fn main() {
    let mode = std::env::args().nth(1).unwrap_or_else(|| "stress".to_string());
    match mode.as_str() {
        "stress" => run_stress_100(),
        "idle_cpu" => run_idle_cpu(),
        "exit_in_about_to_wait" => run_exit_in_about_to_wait(),
        "destroy_in_redraw" => run_destroy_in_redraw(),
        "redraw_in_buffered" => run_redraw_in_buffered(),
        other => panic!("unknown mode: {other}"),
    }
}

fn run_stress_100() {
    struct App {
        window: Option<Box<dyn Window>>,
        cycle: usize,
        target_cycles: usize,
        waiting_pos: Option<PhysicalPosition<i32>>,
        trigger_at: Option<Instant>,
        latencies_us: Vec<f64>,
        spurious_atw: usize,
        settled: bool,
        settle_deadline: Instant,
    }
    impl ApplicationHandler for App {
        fn can_create_surfaces(&mut self, el: &dyn ActiveEventLoop) {
            self.settle_deadline = Instant::now() + Duration::from_millis(400);
            el.set_control_flow(ControlFlow::WaitUntil(self.settle_deadline));
            let w = el
                .create_window(
                    WindowAttributes::default()
                        .with_title("stress-100")
                        .with_surface_size(LogicalSize::new(160.0, 120.0))
                        .with_position(PhysicalPosition::new(100, 100)),
                )
                .unwrap();
            self.window = Some(w);
        }
        fn window_event(&mut self, el: &dyn ActiveEventLoop, _: WindowId, event: WindowEvent) {
            match event {
                WindowEvent::RedrawRequested if self.settled && self.waiting_pos.is_none() => {
                    let pos = PhysicalPosition::new(120 + (self.cycle as i32 % 50) * 2, 120 + (self.cycle as i32 % 50));
                    self.waiting_pos = Some(pos);
                    self.trigger_at = Some(Instant::now());
                    self.window.as_ref().unwrap().set_outer_position(pos.into());
                }
                WindowEvent::Moved(pos) if self.waiting_pos == Some(pos) => {
                    let us = self.trigger_at.unwrap().elapsed().as_secs_f64() * 1e6;
                    self.latencies_us.push(us);
                    self.waiting_pos = None;
                    self.cycle += 1;
                    if self.cycle >= self.target_cycles {
                        el.exit();
                    } else {
                        self.window.as_ref().unwrap().request_redraw();
                    }
                }
                _ => {}
            }
        }
        fn about_to_wait(&mut self, el: &dyn ActiveEventLoop) {
            if !self.settled {
                if Instant::now() >= self.settle_deadline {
                    self.settled = true;
                    el.set_control_flow(ControlFlow::Wait);
                    self.window.as_ref().unwrap().request_redraw();
                }
                return;
            }
            if self.waiting_pos.is_some() {
                self.spurious_atw += 1;
            }
        }
    }

    let done = Arc::new(AtomicBool::new(false));
    let done_wd = done.clone();
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_secs(3));
        if !done_wd.load(Ordering::Acquire) {
            println!("STRESS_100 | HUNG=true (watchdog 3000ms exceeded)");
            std::process::exit(2);
        }
    });

    let mut el = EventLoop::builder().with_any_thread(true).build().unwrap();
    let mut app = App {
        window: None,
        cycle: 0,
        target_cycles: 100,
        waiting_pos: None,
        trigger_at: None,
        latencies_us: Vec::new(),
        spurious_atw: 0,
        settled: false,
        settle_deadline: Instant::now() + Duration::from_millis(400),
    };
    el.run_app_on_demand(&mut app).unwrap();
    done.store(true, Ordering::Release);
    app.latencies_us.sort_by(|a, b| a.total_cmp(b));
    let min = *app.latencies_us.first().unwrap();
    let p50 = app.latencies_us[app.latencies_us.len() / 2];
    let p90 = app.latencies_us[(app.latencies_us.len() * 90) / 100];
    let p99 = app.latencies_us[(app.latencies_us.len() * 99) / 100];
    let max = *app.latencies_us.last().unwrap();
    let mean = app.latencies_us.iter().sum::<f64>() / app.latencies_us.len() as f64;
    println!(
        "STRESS_100 | cycles={}/100 | spurious_about_to_wait={} | min={:.1}us | p50={:.1}us | p90={:.1}us | p99={:.1}us | max={:.1}us | mean={:.1}us",
        app.cycle, app.spurious_atw, min, p50, p90, p99, max, mean
    );
    assert_eq!(app.cycle, 100);
    assert_eq!(app.spurious_atw, 0);
}

fn run_idle_cpu() {
    struct App {
        window: Option<Box<dyn Window>>,
        settled: bool,
        settle_deadline: Instant,
        cpu_start_ms: f64,
        wall_start: Instant,
        idle_wakeups: usize,
        done: Arc<AtomicBool>,
    }
    impl ApplicationHandler for App {
        fn new_events(&mut self, _: &dyn ActiveEventLoop, cause: StartCause) {
            if self.settled && !self.done.load(Ordering::Acquire) {
                if !matches!(cause, StartCause::ResumeTimeReached { .. }) {
                    self.idle_wakeups += 1;
                }
            }
        }
        fn can_create_surfaces(&mut self, el: &dyn ActiveEventLoop) {
            self.settle_deadline = Instant::now() + Duration::from_millis(500);
            el.set_control_flow(ControlFlow::WaitUntil(self.settle_deadline));
            let w = el
                .create_window(
                    WindowAttributes::default()
                        .with_title("idle-cpu")
                        .with_surface_size(LogicalSize::new(160.0, 120.0)),
                )
                .unwrap();
            self.window = Some(w);
        }
        fn window_event(&mut self, _: &dyn ActiveEventLoop, _: WindowId, _: WindowEvent) {}
        fn about_to_wait(&mut self, el: &dyn ActiveEventLoop) {
            if !self.settled {
                if Instant::now() >= self.settle_deadline {
                    self.settled = true;
                    self.cpu_start_ms = process_cpu_ms();
                    self.wall_start = Instant::now();
                    el.set_control_flow(ControlFlow::WaitUntil(
                        Instant::now() + Duration::from_secs(2),
                    ));
                }
                return;
            }
            if self.wall_start.elapsed() >= Duration::from_secs(2) {
                self.done.store(true, Ordering::Release);
                el.exit();
            }
        }
    }

    let mut el = EventLoop::builder().with_any_thread(true).build().unwrap();
    let mut app = App {
        window: None,
        settled: false,
        settle_deadline: Instant::now() + Duration::from_millis(500),
        cpu_start_ms: 0.0,
        wall_start: Instant::now(),
        idle_wakeups: 0,
        done: Arc::new(AtomicBool::new(false)),
    };
    el.run_app_on_demand(&mut app).unwrap();
    let cpu_delta_ms = process_cpu_ms() - app.cpu_start_ms;
    let wall_ms = app.wall_start.elapsed().as_secs_f64() * 1000.0;
    let cpu_pct = 100.0 * cpu_delta_ms / wall_ms;
    println!(
        "IDLE_CPU | wall={:.1}ms | cpu={:.2}ms ({:.3}%) | non_timer_wakeups={}",
        wall_ms, cpu_delta_ms, cpu_pct, app.idle_wakeups
    );
    assert!(cpu_pct < 2.0, "idle CPU too high: {cpu_pct}%");
}

fn run_exit_in_about_to_wait() {
    struct App {
        exited: bool,
        start: Instant,
    }
    impl ApplicationHandler for App {
        fn can_create_surfaces(&mut self, el: &dyn ActiveEventLoop) {
            el.set_control_flow(ControlFlow::Wait);
            self.start = Instant::now();
        }
        fn window_event(&mut self, _: &dyn ActiveEventLoop, _: WindowId, _: WindowEvent) {}
        fn about_to_wait(&mut self, el: &dyn ActiveEventLoop) {
            if !self.exited {
                self.exited = true;
                el.exit();
            }
        }
    }
    // Safety watchdog in case of hang
    std::thread::spawn(|| {
        std::thread::sleep(Duration::from_secs(2));
        eprintln!("FAIL: exit_in_about_to_wait hung!");
        std::process::exit(2);
    });
    let mut el = EventLoop::builder().with_any_thread(true).build().unwrap();
    let mut app = App { exited: false, start: Instant::now() };
    el.run_app_on_demand(&mut app).unwrap();
    let ms = app.start.elapsed().as_secs_f64() * 1000.0;
    println!("EXIT_IN_ABOUT_TO_WAIT | exited={} | elapsed={:.3}ms", app.exited, ms);
    assert!(app.exited && ms < 200.0);
}

fn run_destroy_in_redraw() {
    struct App {
        window: Option<Box<dyn Window>>,
        settled: bool,
        settle_deadline: Instant,
        destroyed_seen: bool,
        trigger_at: Option<Instant>,
    }
    impl ApplicationHandler for App {
        fn can_create_surfaces(&mut self, el: &dyn ActiveEventLoop) {
            self.settle_deadline = Instant::now() + Duration::from_millis(500);
            el.set_control_flow(ControlFlow::WaitUntil(self.settle_deadline));
            let w = el
                .create_window(
                    WindowAttributes::default()
                        .with_title("destroy-in-redraw")
                        .with_surface_size(LogicalSize::new(160.0, 120.0)),
                )
                .unwrap();
            self.window = Some(w);
        }
        fn window_event(&mut self, el: &dyn ActiveEventLoop, _: WindowId, event: WindowEvent) {
            match event {
                WindowEvent::RedrawRequested if self.settled && self.window.is_some() => {
                    self.trigger_at = Some(Instant::now());
                    self.window = None; // drops Window -> DestroyWindow synchronously -> buffers Destroyed
                }
                WindowEvent::Destroyed => {
                    self.destroyed_seen = true;
                    let ms = self.trigger_at.unwrap().elapsed().as_secs_f64() * 1000.0;
                    println!("DESTROY_IN_REDRAW | destroyed_seen=true | latency={:.3}ms", ms);
                    assert!(ms < 100.0);
                    el.exit();
                }
                _ => {}
            }
        }
        fn about_to_wait(&mut self, el: &dyn ActiveEventLoop) {
            if !self.settled && Instant::now() >= self.settle_deadline {
                self.settled = true;
                el.set_control_flow(ControlFlow::Wait);
                self.window.as_ref().unwrap().request_redraw();
            }
        }
    }
    std::thread::spawn(|| {
        std::thread::sleep(Duration::from_secs(3));
        eprintln!("FAIL: destroy_in_redraw hung!");
        std::process::exit(2);
    });
    let mut el = EventLoop::builder().with_any_thread(true).build().unwrap();
    let mut app = App {
        window: None,
        settled: false,
        settle_deadline: Instant::now() + Duration::from_millis(500),
        destroyed_seen: false,
        trigger_at: None,
    };
    el.run_app_on_demand(&mut app).unwrap();
    assert!(app.destroyed_seen);
}

fn run_redraw_in_buffered() {
    struct App {
        window: Option<Box<dyn Window>>,
        settled: bool,
        settle_deadline: Instant,
        redraws_after_settle: usize,
        moved_seen: bool,
        trigger_at: Option<Instant>,
    }
    impl ApplicationHandler for App {
        fn can_create_surfaces(&mut self, el: &dyn ActiveEventLoop) {
            self.settle_deadline = Instant::now() + Duration::from_millis(500);
            el.set_control_flow(ControlFlow::WaitUntil(self.settle_deadline));
            let w = el
                .create_window(
                    WindowAttributes::default()
                        .with_title("redraw-in-buffered")
                        .with_surface_size(LogicalSize::new(160.0, 120.0))
                        .with_position(PhysicalPosition::new(100, 100)),
                )
                .unwrap();
            self.window = Some(w);
        }
        fn window_event(&mut self, el: &dyn ActiveEventLoop, _: WindowId, event: WindowEvent) {
            match event {
                WindowEvent::RedrawRequested if self.settled => {
                    self.redraws_after_settle += 1;
                    if self.redraws_after_settle == 1 {
                        self.trigger_at = Some(Instant::now());
                        // Buffers Moved(222, 222) during RedrawRequested
                        self.window
                            .as_ref()
                            .unwrap()
                            .set_outer_position(PhysicalPosition::new(222, 222).into());
                    } else if self.redraws_after_settle == 2 {
                        let ms = self.trigger_at.unwrap().elapsed().as_secs_f64() * 1000.0;
                        println!(
                            "REDRAW_IN_BUFFERED | moved_seen={} | redraws=2 | latency={:.3}ms",
                            self.moved_seen, ms
                        );
                        assert!(self.moved_seen && ms < 200.0);
                        el.exit();
                    }
                }
                WindowEvent::Moved(pos) if pos == PhysicalPosition::new(222, 222) => {
                    self.moved_seen = true;
                    // Request another redraw from INSIDE the buffered event drained during WM_PAINT!
                    self.window.as_ref().unwrap().request_redraw();
                }
                _ => {}
            }
        }
        fn about_to_wait(&mut self, el: &dyn ActiveEventLoop) {
            if !self.settled && Instant::now() >= self.settle_deadline {
                self.settled = true;
                el.set_control_flow(ControlFlow::Wait);
                self.window.as_ref().unwrap().request_redraw();
            }
        }
    }
    std::thread::spawn(|| {
        std::thread::sleep(Duration::from_secs(3));
        eprintln!("FAIL: redraw_in_buffered hung!");
        std::process::exit(2);
    });
    let mut el = EventLoop::builder().with_any_thread(true).build().unwrap();
    let mut app = App {
        window: None,
        settled: false,
        settle_deadline: Instant::now() + Duration::from_millis(500),
        redraws_after_settle: 0,
        moved_seen: false,
        trigger_at: None,
    };
    el.run_app_on_demand(&mut app).unwrap();
    assert_eq!(app.redraws_after_settle, 2);
}
