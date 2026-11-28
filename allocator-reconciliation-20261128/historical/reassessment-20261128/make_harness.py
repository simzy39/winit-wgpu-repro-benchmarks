import pathlib
HERE=pathlib.Path(__file__).resolve().parent
s=(HERE.parent/"bench/src/main.rs").read_text()
s=s.replace('        "default" => (256, 256, 64, 64),','        "default" => (256, 256, 64, 64),\n        "manual" => (8, 256, 4, 128),\n        "tiny_fixed" => (8, 8, 4, 4),')
s=s.replace('    w\n}\n\ntrait Backend', '''    let mut ops = vec![];
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

trait Backend''')
s=s.replace('    fn alloc(&mut self, loc: Loc, res: Res) -> Self::A;', '''    fn prepare(&mut self, loc: Loc, res: Res);
    fn report(&self) -> gpu_allocator::AllocatorReport;
    fn alloc(&mut self, loc: Loc, res: Res) -> Self::A;''')
s=s.replace('    let baseline_usage = b.driver_usage();', '''    for op in ops {
        if let Op::Alloc(_, loc, res) = *op { b.prepare(loc, res); }
    }
    let baseline_usage = b.driver_usage();''')
s=s.replace('    let mut marks = vec![];', '''    let mut marks = vec![];
    let mut block_events = vec![];
    let mut creating_ns = vec![];
    let mut reuse_ns = vec![];
    let mut peak_unused = 0u64;''')
s=s.replace('                alloc_ns.push(t.elapsed().as_nanos() as u64);','                let ns = t.elapsed().as_nanos() as u64;\n                alloc_ns.push(ns);')
s=s.replace('                    created_total += 1;', '''                    created_total += 1;
                    creating_ns.push(ns);
                    block_events.push(json!({"block_bytes":delta,"request_bytes":size,"location":format!("{loc:?}")}));''')
s=s.replace('                cap = c;\n                live_bytes += size;', '''                if c == cap { reuse_ns.push(ns); }
                cap = c;
                live_bytes += size;
                peak_unused = peak_unused.max(cap.saturating_sub(live_bytes));''')
s=s.replace('                "blocks_created_so_far": created_total,','                "blocks_created_so_far": created_total,\n                "fragmentation": fragmentation(&b.report()),')
s=s.replace('        "per_location": locs,','''        "per_location": locs,
        "heap_creation_us": {"p50":pct(&mut creating_ns.clone(),0.5),"p99":pct(&mut creating_ns.clone(),0.99)},
        "reuse_us": {"p50":pct(&mut reuse_ns.clone(),0.5),"p99":pct(&mut reuse_ns.clone(),0.99)},
        "peak_unused_mib": peak_unused as f64 / MIB as f64,
        "block_events": block_events,''')
s=s.replace('        fn alloc(&mut self, loc: Loc, res: Res) -> Allocation {\n            let requirements = self.requirements(res);', '''        fn prepare(&mut self, _loc: Loc, res: Res) { self.requirements(res); }
        fn report(&self) -> gpu_allocator::AllocatorReport { self.alloc.as_ref().unwrap().generate_report() }
        fn alloc(&mut self, loc: Loc, res: Res) -> Allocation {
            let requirements = self.reqs[&res];''')
# D3D12 caches resource requirements before timing, as Vulkan does.
s=s.replace('        alloc: Option<Allocator>,\n    }\n\n    impl Dx', '        alloc: Option<Allocator>,\n        reqs: HashMap<(Loc, Res), AllocationCreateDesc<\'static>>,\n    }\n\n    impl Dx')
s=s.replace('adapter: adapter.cast().unwrap(), name, alloc: None }','adapter: adapter.cast().unwrap(), name, alloc: None, reqs: HashMap::new() }')
s=s.replace('        fn alloc(&mut self, loc: Loc, res: Res) -> Allocation {\n            let desc = match res {','        fn prepare(&mut self, loc: Loc, res: Res) {\n            if self.reqs.contains_key(&(loc,res)) { return; }\n            let desc = match res {')
s=s.replace('            self.alloc.as_mut().unwrap().allocate(&ad).unwrap()\n        }','''            self.reqs.insert((loc,res),ad);
        }
        fn report(&self) -> gpu_allocator::AllocatorReport { self.alloc.as_ref().unwrap().generate_report() }
        fn alloc(&mut self, loc: Loc, res: Res) -> Allocation {
            self.alloc.as_mut().unwrap().allocate(&self.reqs[&(loc,res)]).unwrap()
        }''')
s=s.replace('fn quiet_debug_settings()', '''fn fragmentation(report: &gpu_allocator::AllocatorReport) -> Value {
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

fn quiet_debug_settings()''')
(HERE/"bench.rs").write_text(s)
print("Wrote common harness with 10 workloads and precomputed resource requirements")

