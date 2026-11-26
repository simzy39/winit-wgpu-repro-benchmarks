//! Standalone reproduction of Windows event-buffer stranding on `winit` master.
//!
//! Each scenario waits ~150ms after window creation for startup Win32 messages
//! (WM_SHOWWINDOW, WM_ACTIVATE, DWM, etc.) to completely settle so the Win32
//! message queue is genuinely empty before triggering the test.

use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use windows_sys::Win32::Foundation::HWND;
use windows_sys::Win32::UI::WindowsAndMessaging::{
    DispatchMessageW, MSG, PM_REMOVE, PeekMessageW, PostMessageW, RegisterWindowMessageA,
    TranslateMessage, WM_NULL, WM_PAINT,
};
use winit::application::ApplicationHandler;
use winit::dpi::{LogicalSize, PhysicalPosition};
use winit::event::{StartCause, WindowEvent};
use winit::event_loop::pump_events::EventLoopExtPumpEvents;
use winit::event_loop::run_on_demand::EventLoopExtRunOnDemand;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy};
use winit::platform::windows::EventLoopBuilderExtWindows;
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
use winit::window::{Window, WindowAttributes, WindowId};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Scenario {
    RedrawWindowEvent,
    RedrawPumpAll,
    RedrawPumpWakeupOnly,
    AboutToWaitWindowEvent,
    AboutToWaitPumpAll,
    PumpEventsRedraw,
    RedrawBurst,
    MultiWindowRedraw,
    WaitUntilRedraw,
    ExitDuringRedraw,
}

impl Scenario {
    fn from_arg(s: &str) -> Option<Self> {
        match s {
            "redraw_window_event" => Some(Self::RedrawWindowEvent),
            "redraw_pump_all" => Some(Self::RedrawPumpAll),
            "redraw_pump_wakeup_only" => Some(Self::RedrawPumpWakeupOnly),
            "about_to_wait_window_event" => Some(Self::AboutToWaitWindowEvent),
            "about_to_wait_pump_all" => Some(Self::AboutToWaitPumpAll),
            "pump_events_redraw" => Some(Self::PumpEventsRedraw),
            "redraw_burst" => Some(Self::RedrawBurst),
            "multi_window_redraw" => Some(Self::MultiWindowRedraw),
            "wait_until_redraw" => Some(Self::WaitUntilRedraw),
            "exit_during_redraw" => Some(Self::ExitDuringRedraw),
            _ => None,
        }
    }

    fn name(self) -> &'static str {
        match self {
            Self::RedrawWindowEvent => "redraw_window_event",
            Self::RedrawPumpAll => "redraw_pump_all",
            Self::RedrawPumpWakeupOnly => "redraw_pump_wakeup_only",
            Self::AboutToWaitWindowEvent => "about_to_wait_window_event",
            Self::AboutToWaitPumpAll => "about_to_wait_pump_all",
            Self::PumpEventsRedraw => "pump_events_redraw",
            Self::RedrawBurst => "redraw_burst",
            Self::MultiWindowRedraw => "multi_window_redraw",
            Self::WaitUntilRedraw => "wait_until_redraw",
            Self::ExitDuringRedraw => "exit_during_redraw",
        }
    }
}

fn hwnd_of(window: &dyn Window) -> HWND {
    match window.window_handle().unwrap().as_raw() {
        RawWindowHandle::Win32(h) => h.hwnd.get() as HWND,
        _ => panic!("not win32"),
    }
}

/// Simulates a nested Win32 message pump (COM STA / DXGI / modal dialog) while
/// avoiding re-pumping WM_PAINT for the window whose WM_PAINT is currently active
/// (Windows itself masks WM_PAINT for an already-painting HWND, or only pumps
/// non-reentrant messages; note winit's hidden `thread_msg_target` IS a separate HWND!).
fn pump_nested_messages(painting_hwnd: HWND) -> (usize, usize) {
    let mut total = 0usize;
    let mut target_paints = 0usize;
    unsafe {
        let mut msg: MSG = std::mem::zeroed();
        for _ in 0..64 {
            if PeekMessageW(&mut msg, std::ptr::null_mut(), 0, 0, PM_REMOVE) == 0 {
                break;
            }
            if msg.hwnd == painting_hwnd && msg.message == WM_PAINT {
                // Skip self-WM_PAINT so we don't spin on winit's RDW_INTERNALPAINT re-arm.
                break;
            }
            if msg.hwnd != painting_hwnd && msg.message == WM_PAINT {
                target_paints += 1;
            }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
            total += 1;
        }
    }
    (total, target_paints)
}

fn pump_only_wakeup_message() -> usize {
    let wakeup_id = unsafe { RegisterWindowMessageA(c"Winit::WakeupMsg".as_ptr() as *const u8) };
    let mut count = 0;
    unsafe {
        let mut msg: MSG = std::mem::zeroed();
        for _ in 0..64 {
            if PeekMessageW(&mut msg, std::ptr::null_mut(), wakeup_id, wakeup_id, PM_REMOVE) == 0 {
                break;
            }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
            count += 1;
        }
    }
    count
}

struct TraceEntry {
    at_us: u128,
    label: String,
}

struct ReproApp {
    scenario: Scenario,
    proxy: EventLoopProxy,
    windows: Vec<Box<dyn Window>>,
    start: Instant,
    settled: bool,
    arm_redraw_sent: bool,
    trigger_time: Option<Instant>,
    triggered: bool,
    target_delivered: Arc<AtomicBool>,
    watchdog_fired: Arc<AtomicBool>,
    delivered_count: Arc<AtomicUsize>,
    expected_count: usize,
    trace: Vec<TraceEntry>,
    about_to_wait_after_trigger: usize,
    window_hwnd_for_watchdog: Arc<AtomicUsize>,
    settle_deadline: Instant,
}

impl ReproApp {
    fn log(&mut self, msg: impl Into<String>) {
        self.trace.push(TraceEntry {
            at_us: self.start.elapsed().as_micros(),
            label: msg.into(),
        });
    }

    fn arm_watchdog(&self, timeout_ms: u64) {
        let delivered = self.target_delivered.clone();
        let fired = self.watchdog_fired.clone();
        let hwnd_raw = self.window_hwnd_for_watchdog.clone();
        let name = self.scenario.name();
        std::thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_millis(timeout_ms);
            while Instant::now() < deadline {
                if delivered.load(Ordering::Acquire) {
                    return;
                }
                std::thread::sleep(Duration::from_millis(10));
            }
            if !delivered.load(Ordering::Acquire) {
                fired.store(true, Ordering::Release);
                // Post an unrelated WM_NULL to wake MsgWaitForMultipleObjectsEx WITHOUT
                // generating any winit event. If the event now arrives, it was STRANDED
                // in winit's event_buffer rather than permanently lost!
                let hwnd = hwnd_raw.load(Ordering::Acquire) as HWND;
                if !hwnd.is_null() {
                    unsafe {
                        PostMessageW(hwnd, WM_NULL, 0, 0);
                    }
                }
                // Hard safety timeout if permanently lost
                std::thread::sleep(Duration::from_millis(800));
                if !delivered.load(Ordering::Acquire) {
                    eprintln!("SCENARIO {name:<28} | HARD TIMEOUT (PERMANENTLY LOST!)");
                    std::process::exit(3);
                }
            }
        });
    }

    fn mark_delivered(&mut self, el: &dyn ActiveEventLoop, what: &str) {
        let n = self.delivered_count.fetch_add(1, Ordering::AcqRel) + 1;
        let latency_ms = self
            .trigger_time
            .map(|t| t.elapsed().as_secs_f64() * 1000.0)
            .unwrap_or(-1.0);
        let stranded = self.watchdog_fired.load(Ordering::Acquire);
        self.log(format!(
            "DELIVERED({what}) #{n}/{} latency={latency_ms:.3}ms stranded_until_watchdog={stranded}",
            self.expected_count
        ));
        if n >= self.expected_count {
            self.target_delivered.store(true, Ordering::Release);
            el.exit();
        }
    }

    fn trigger_from_redraw(&mut self, el: &dyn ActiveEventLoop) {
        self.triggered = true;
        self.trigger_time = Some(Instant::now());
        let hwnd0 = hwnd_of(self.windows[0].as_ref());
        match self.scenario {
            Scenario::RedrawWindowEvent | Scenario::WaitUntilRedraw | Scenario::MultiWindowRedraw => {
                self.log("TRIGGER: set_outer_position(321, 234) inside RedrawRequested");
                self.arm_watchdog(600);
                self.windows[0].set_outer_position(PhysicalPosition::new(321, 234).into());
            }
            Scenario::RedrawPumpAll => {
                self.log("TRIGGER: bg proxy.wake_up() + nested pump (incl thread_msg_target WM_PAINT) inside RedrawRequested");
                let proxy = self.proxy.clone();
                std::thread::spawn(move || proxy.wake_up()).join().unwrap();
                let (total, target_paints) = pump_nested_messages(hwnd0);
                self.log(format!(
                    "TRIGGER: nested pump dispatched {total} msgs (thread_msg_target WM_PAINT={target_paints})"
                ));
                self.arm_watchdog(600);
            }
            Scenario::RedrawPumpWakeupOnly => {
                self.log("TRIGGER: bg proxy.wake_up() + pump_only_wakeup inside RedrawRequested");
                let proxy = self.proxy.clone();
                std::thread::spawn(move || proxy.wake_up()).join().unwrap();
                let pumped = pump_only_wakeup_message();
                self.log(format!("TRIGGER: pump_only_wakeup dispatched {pumped} msgs"));
                self.arm_watchdog(600);
            }
            Scenario::RedrawBurst => {
                self.log("TRIGGER: 50x set_outer_position inside RedrawRequested");
                self.arm_watchdog(600);
                for i in 0..50 {
                    self.windows[0]
                        .set_outer_position(PhysicalPosition::new(200 + i, 200 + i).into());
                }
            }
            Scenario::ExitDuringRedraw => {
                self.log("TRIGGER: set_outer_position + el.exit() inside RedrawRequested");
                self.windows[0].set_outer_position(PhysicalPosition::new(321, 234).into());
                el.exit();
                self.target_delivered.store(true, Ordering::Release);
            }
            Scenario::PumpEventsRedraw => {
                self.log("TRIGGER: set_outer_position inside RedrawRequested (pump_app_events)");
                self.windows[0].set_outer_position(PhysicalPosition::new(321, 234).into());
            }
            Scenario::AboutToWaitWindowEvent | Scenario::AboutToWaitPumpAll => unreachable!(),
        }
    }
}

impl ApplicationHandler for ReproApp {
    fn new_events(&mut self, _el: &dyn ActiveEventLoop, cause: StartCause) {
        if self.triggered {
            self.log(format!("new_events({cause:?})"));
        }
    }

    fn can_create_surfaces(&mut self, el: &dyn ActiveEventLoop) {
        self.settle_deadline = Instant::now() + Duration::from_millis(600);
        el.set_control_flow(ControlFlow::WaitUntil(self.settle_deadline));

        let attrs1 = WindowAttributes::default()
            .with_title("winit-repro-1")
            .with_surface_size(LogicalSize::new(200.0, 150.0))
            .with_position(PhysicalPosition::new(100, 100))
            .with_visible(true);
        let w1 = el.create_window(attrs1).unwrap();
        self.window_hwnd_for_watchdog
            .store(hwnd_of(w1.as_ref()) as usize, Ordering::Release);
        self.windows.push(w1);

        if self.scenario == Scenario::MultiWindowRedraw {
            let attrs2 = WindowAttributes::default()
                .with_title("winit-repro-2")
                .with_surface_size(LogicalSize::new(200.0, 150.0))
                .with_position(PhysicalPosition::new(350, 100))
                .with_visible(true);
            let w2 = el.create_window(attrs2).unwrap();
            self.windows.push(w2);
        }
    }

    fn window_event(&mut self, el: &dyn ActiveEventLoop, window_id: WindowId, event: WindowEvent) {
        match event {
            WindowEvent::RedrawRequested => {
                if self.settled
                    && !self.triggered
                    && window_id == self.windows[0].id()
                    && !matches!(
                        self.scenario,
                        Scenario::AboutToWaitWindowEvent | Scenario::AboutToWaitPumpAll
                    )
                {
                    self.trigger_from_redraw(el);
                }
            }
            WindowEvent::Moved(pos) => {
                if self.triggered {
                    match self.scenario {
                        Scenario::RedrawWindowEvent
                        | Scenario::AboutToWaitWindowEvent
                        | Scenario::PumpEventsRedraw
                        | Scenario::MultiWindowRedraw
                        | Scenario::WaitUntilRedraw => {
                            if pos == PhysicalPosition::new(321, 234) {
                                self.mark_delivered(el, &format!("Moved({pos:?})"));
                            }
                        }
                        Scenario::RedrawBurst => {
                            if pos.x >= 200 && pos.x < 250 && pos.x == pos.y {
                                self.mark_delivered(el, &format!("Moved({pos:?})"));
                            }
                        }
                        _ => {}
                    }
                }
            }
            _ => {}
        }
    }

    fn proxy_wake_up(&mut self, el: &dyn ActiveEventLoop) {
        if self.triggered
            && matches!(
                self.scenario,
                Scenario::RedrawPumpAll
                    | Scenario::RedrawPumpWakeupOnly
                    | Scenario::AboutToWaitPumpAll
            )
        {
            self.mark_delivered(el, "proxy_wake_up");
        }
    }

    fn about_to_wait(&mut self, el: &dyn ActiveEventLoop) {
        if !self.settled {
            if Instant::now() >= self.settle_deadline {
                self.settled = true;
                match self.scenario {
                    Scenario::WaitUntilRedraw => {
                        el.set_control_flow(ControlFlow::WaitUntil(
                            Instant::now() + Duration::from_secs(2),
                        ));
                    }
                    _ => el.set_control_flow(ControlFlow::Wait),
                }
                if matches!(
                    self.scenario,
                    Scenario::AboutToWaitWindowEvent | Scenario::AboutToWaitPumpAll
                ) {
                    self.triggered = true;
                    self.trigger_time = Some(Instant::now());
                    let hwnd0 = hwnd_of(self.windows[0].as_ref());
                    if self.scenario == Scenario::AboutToWaitWindowEvent {
                        self.log("TRIGGER: set_outer_position(321, 234) inside about_to_wait");
                        self.arm_watchdog(600);
                        self.windows[0].set_outer_position(PhysicalPosition::new(321, 234).into());
                    } else {
                        self.log("TRIGGER: bg proxy.wake_up() + nested pump inside about_to_wait");
                        let proxy = self.proxy.clone();
                        std::thread::spawn(move || proxy.wake_up()).join().unwrap();
                        let (total, target_paints) = pump_nested_messages(hwnd0);
                        self.log(format!(
                            "TRIGGER: nested pump dispatched {total} msgs (thread_msg_target WM_PAINT={target_paints})"
                        ));
                        self.arm_watchdog(600);
                    }
                } else if !self.arm_redraw_sent {
                    self.arm_redraw_sent = true;
                    self.windows[0].request_redraw();
                }
            }
            return;
        }

        if self.triggered {
            self.about_to_wait_after_trigger += 1;
            self.log(format!(
                "about_to_wait(#{}, delivered={})",
                self.about_to_wait_after_trigger,
                self.delivered_count.load(Ordering::Acquire)
            ));
        }
    }
}

fn run_scenario(scenario: Scenario) {
    let mut el = EventLoop::builder().with_any_thread(true).build().unwrap();
    let proxy = el.create_proxy();
    let expected = match scenario {
        Scenario::RedrawBurst => 50,
        Scenario::ExitDuringRedraw => 0,
        _ => 1,
    };

    let mut app = ReproApp {
        scenario,
        proxy,
        windows: Vec::new(),
        start: Instant::now(),
        settled: false,
        arm_redraw_sent: false,
        trigger_time: None,
        triggered: false,
        target_delivered: Arc::new(AtomicBool::new(false)),
        watchdog_fired: Arc::new(AtomicBool::new(false)),
        delivered_count: Arc::new(AtomicUsize::new(0)),
        expected_count: expected,
        trace: Vec::new(),
        about_to_wait_after_trigger: 0,
        window_hwnd_for_watchdog: Arc::new(AtomicUsize::new(0)),
        settle_deadline: Instant::now() + Duration::from_millis(600),
    };

    if scenario == Scenario::PumpEventsRedraw {
        let mut pumps_after_trigger = 0usize;
        for _ in 0..160 {
            let status = el.pump_app_events(Some(Duration::from_millis(10)), &mut app);
            if app.triggered {
                pumps_after_trigger += 1;
                let deliv = app.delivered_count.load(Ordering::Acquire);
                app.log(format!(
                    "pump_app_events returned ({status:?}) pumps_after_trigger={pumps_after_trigger} delivered={deliv}"
                ));
                if deliv >= 1 || pumps_after_trigger >= 3 {
                    break;
                }
            }
        }
        let deliv_on_first_pump = app
            .trace
            .iter()
            .any(|t| t.label.contains("pumps_after_trigger=1 delivered=1"));
        println!(
            "SCENARIO {:<26} | delivered={} | delivered_in_trigger_pump={} | pumps_after_trigger={}",
            scenario.name(),
            app.delivered_count.load(Ordering::Acquire),
            deliv_on_first_pump,
            pumps_after_trigger
        );
        for t in &app.trace {
            println!("  [{:>8}us] {}", t.at_us, t.label);
        }
        return;
    }

    el.run_app_on_demand(&mut app).unwrap();

    let delivered = app.delivered_count.load(Ordering::Acquire);
    let stranded = app.watchdog_fired.load(Ordering::Acquire);
    let latency_ms = app
        .trigger_time
        .map(|t| t.elapsed().as_secs_f64() * 1000.0)
        .unwrap_or(0.0);
    println!(
        "SCENARIO {:<26} | delivered={}/{} | STRANDED={:<5} | about_to_wait_after_trigger={} | total_ms={:.2}",
        scenario.name(),
        delivered,
        expected,
        stranded,
        app.about_to_wait_after_trigger,
        latency_ms
    );
    for t in &app.trace {
        println!("  [{:>8}us] {}", t.at_us, t.label);
    }
}

fn main() {
    let arg = std::env::args().nth(1).unwrap_or_else(|| "redraw_window_event".into());
    if let Some(s) = Scenario::from_arg(&arg) {
        run_scenario(s);
    } else {
        eprintln!("Unknown scenario: {arg}");
        std::process::exit(2);
    }
}
