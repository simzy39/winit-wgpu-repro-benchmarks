"""Fill the report from complete recorded results; no benchmark result is edited."""
import pathlib, json, statistics, collections, re
H = pathlib.Path(__file__).resolve().parent
load = lambda name: json.loads((H / name).read_text())
direct = load("direct-summary.json")
focused = load("cache-limit-summary.json")
down = load("downstream-summary.json")
assert direct["processes"] == 405 and not direct["proposal_mismatches"]
assert focused["processes"] == 80
assert down["processes"] == 520 and not down["failures"]
assert all(r["trials"] == 5 for r in down["cells"])
dc = {(r["variant"], r["backend"], r["config"], r["workload"]): r for r in direct["cells"]}
fc = {(r["variant"], r["backend"], r["config"], r["workload"]): r for r in focused["cells"]}
wc = {(r["variant"], r["backend"], r["hints"], r["workload"]): r for r in down["cells"]}
def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"] +
        ["| " + " | ".join(str(v) for v in row) + " |" for row in rows])
def num(x):
    return "—" if x is None else f"{x:.2f}".rstrip("0").rstrip(".")
def timed(r):
    return f"{r['alloc_us_sum_ms_median']:.2f} ({r['alloc_us_sum_ms_min']:.2f}–{r['alloc_us_sum_ms_max']:.2f})"
replacements = {}
rows = []
for workload in ["textures", "burst_release", "mixed_frames", "sporadic_long_lived"]:
    for name in ["pr323", "cache2", "demand2", "request"]:
        r = dc[name, "vulkan", "memory_usage", workload]
        rows.append([workload, name, num(r["blocks_created"]), num(r["peak_capacity_mib"]), num(r["retained_after_release_mib"])])
replacements["GROWTH_TABLE"] = table(["Vulkan MemoryUsage workload", "Policy", "Heaps created", "Peak MiB", "Retained MiB"], rows)
rows = []
for backend in ["vulkan", "d3d12"]:
    for config in ["memory_usage", "manual"]:
        for workload in ["burst_release", "mixed_frames", "textures"]:
            for name in ["cache2", "cachemax"]:
                r = fc[name, backend, config, workload]
                rows.append([backend, config, workload, name, num(r["blocks_created"]), num(r["peak_capacity_mib"]), num(r["retained_after_release_mib"]),
                    f"{r['alloc_total_ms']:.2f} ({r['alloc_total_min_ms']:.2f}–{r['alloc_total_max_ms']:.2f})"])
replacements["CACHE_LIMIT_TABLE"] = table(["Backend", "Config", "Workload", "Cache", "Heaps", "Peak MiB", "Retained MiB", "Alloc ms median (range)"], rows)
replacements["CACHE_LIMIT_TABLE"] += "\n\nThe Manual burst saves three heap creations with the larger cache, while retention rises from 8 to 128 MiB. Mixed frames retain 76 rather than 28 MiB with identical heap counts. The selected bound favors memory efficiency in that trade-off. Performance permits caching a whole 256 MiB GPU block or 128 MiB CPU-visible block; its single texture burst retains 256 MiB versus zero on PR 323, without reducing creations for that first burst. This is a per-type limit, not an allocator-wide budget. Multiple types and separate allocator instances multiply it. Applications needing immediate release must call trim."
replacements["DIRECT_COUNTS"] = (
    f"The suite completed {direct['processes']} processes and {direct['workload_measurements']:,} workload measurements, with no harness failures. "
    f"All {direct['proposal_equivalence_comparisons']} paired PR/proposal decision comparisons match; all block-decision cells are stable across five trials. "
    "This verifies successful allocation behavior, not the absence of untraced driver-level failed attempts.")
rows = []
for backend, config, workload in [("vulkan", "performance", "burst_release"), ("d3d12", "performance", "burst_release"),
        ("vulkan", "memory_usage", "mixed_frames"), ("d3d12", "memory_usage", "mixed_frames")]:
    for name in ["main", "pr323", "cache2"]:
        r = dc[name, backend, config, workload]
        rows.append([backend, config + " " + workload, name, num(r["blocks_created"]), num(r["peak_capacity_mib"]), num(r["retained_after_release_mib"]), timed(r), num(r["alloc_us_p99_median"]), num(r["free_us_sum_ms_median"])])
replacements["DIRECT_TABLE"] = table(["Backend", "Case", "Policy", "Heaps", "Peak MiB", "Retained MiB", "Alloc ms median (range)", "Alloc p99 µs", "Free total ms"], rows)
counts = collections.defaultdict(lambda: collections.Counter())
for key, row in dc.items():
    if key[0] != "cache2": continue
    baseline = dc["pr323", *key[1:]]
    for field in ["peak_capacity_mib", "blocks_created", "retained_after_release_mib"]:
        delta = row[field] - baseline[field]
        counts[field]["lower" if delta < 0 else "higher" if delta > 0 else "equal"] += 1
replacements["DIRECT_TABLE"] += "\n\nAcross all 100 direct configuration/backend/workload cells, cache2 lowers peak reservation in four, matches it in 96 and raises it in none. It reduces heap creations in 28 and matches them in 72. Retention is higher in 38 and equal in 62. These cell counts are descriptive, not a weighted application score. The integrated churn regression below shows why these direct workloads alone are insufficient."
cpu = collections.defaultdict(list)
for r in focused["process_cpu"]:
    cpu[r["variant"], r["backend"], r["config"]].append(r["total_cpu_ms"])
rows = []
for backend in ["vulkan", "d3d12"]:
    for config in ["memory_usage", "performance"]:
        for variant in ["pr323", "cache2"]:
            values = cpu[variant, backend, config]
            rows.append([backend, config, variant, f"{statistics.median(values):.2f} ({min(values):.2f}–{max(values):.2f})"])
replacements["DIRECT_TABLE"] += "\n\n" + table(["Backend", "Ten-workload process config", "Policy", "Whole-process CPU ms median (range)"], rows)
replacements["DIRECT_TABLE"] += "\n\nCPU time includes setup, reporting, driver threads and all ten workloads. Observed values are quantized in 15.625 ms steps. It does not establish an overall CPU improvement: Vulkan MemoryUsage is higher for cache2 in this sample and ranges overlap. The elapsed-call reductions in a specific mixed workload must not be presented as equivalent whole-process CPU savings."
outliers = []
for path in sorted((H / "results-direct-verified").glob("cache2__vulkan__memory_usage__t[1-5].json")):
    w = json.loads(path.read_text())["result"]["workloads"]["mixed_frames"]
    outliers.append({"file": path.name, "alloc": w["alloc_us"], "heap_creation": w["heap_creation_us"], "reuse": w["reuse_us"]})
(H / "outlier-review.json").write_text(json.dumps(outliers, indent=2))
replacements["OUTLIER_NOTE"] = "One cache2 Vulkan MemoryUsage mixed trial takes 25.84 ms versus a 3.93 ms median. Its longest allocation, 14.34 ms, is also the heap-creation p99; reuse p99 stays at 2 µs and all seven block decisions match other trials. This localizes the outlier to a heap-creating call, but does not identify whether the driver, OS scheduling or page commitment caused it. The outlier remains in every summary. Identical fixed-policy texture decisions also show large timing variation across variants. [Outlier review](outlier-review.json)."
diagnostic = load("texture-diagnostic-summary.json")
replay = load("texture-original-replay-summary.json")
rows = []
for r in diagnostic["summary"]:
    rows.append(["Filtered diagnostic " + r["mode"], r["variant"], f"{r['median_ms']:.2f} ({r['min_ms']:.2f}–{r['max_ms']:.2f})"])
for r in replay["summary"]:
    rows.append(["Exact archived binary replay", r["variant"], f"{r['median_ms']:.2f} ({r['min_ms']:.2f}–{r['max_ms']:.2f})"])
replacements["OUTLIER_NOTE"] += "\n\nThe main fixed-size Vulkan texture cell has a consistent unfavorable gap: PR 1.49 ms versus cache2 27.70 ms despite the same two heaps. A separate 20-process diagnostic compares textures alone and in the original workload sequence. Ten further processes replay the exact original executables after correctness checks, with compiler activity excluded. Those follow-ups are retained separately and do not replace any main-suite value.\n\n" + table(["Fixed texture follow-up", "Policy", "Alloc ms median (range)"], rows)
replacements["OUTLIER_NOTE"] += "\n\nAPI traces confirm identical texture allocation inputs: two 256 MiB requests on memory type zero, with null pNext. Cache retention intentionally reverses which empty handle is freed first. Follow-up timing rankings vary, so the original gap cannot be treated as a stable intrinsic algorithm cost or silently discarded as noise. Driver history and environmental state are plausible influences; the exact cause remains unresolved. The filtered follow-up also changes the harness binary, while the replay retains the original executable hashes. Both occur after wake and the recorded power-source event. [Diagnostic results](texture-diagnostic-summary.json), [original executable replay](texture-original-replay-summary.json), [API inputs and free order](texture-api-comparison.json)."
rows = []
for workload in ["burst_release", "mixed_frames", "textures"]:
    for name in ["pr323", "cache2", "vma"]:
        r = dc[name, "vulkan", "default", workload]
        rows.append([workload, name, num(r["blocks_created"]), num(r["shared_blocks_created"]), num(r["dedicated_blocks_created"]), num(r["peak_capacity_mib"]), num(r["retained_after_release_mib"]), timed(r)])
replacements["NATIVE_REFERENCE_TABLE"] = table(["Vulkan default case", "Implementation", "Heaps", "Shared", "Personal/dedicated", "Peak MiB", "Retained MiB", "Alloc ms median (range)"], rows)
replacements["NATIVE_REFERENCE_TABLE"] += "\n\nNative VMA reduces texture reservation from 512 to 448 MiB here, but raises burst peak reservation from 256 to 480 MiB. It makes different packing and retention choices and supplies a broader budget/fallback system. These data justify learning from its combined policy, not claiming that gpu-allocator or VMA wins generally. The differing default block ranges prevent attributing every difference to one heuristic."
replacements["PRACTICAL_DECISION"] = "Compared with the current PR, the candidate adds resolved policy ownership, explicit classification, capacity checks, bounded caching and trim. Compared with Claude's proposal, it intentionally changes allocation/reclamation behavior; the original proposal remains the measured behavior-preserving control. The small additional dynamic state addresses the live-anchor churn that last-block-only retention cannot fix. The cost is retained memory and, in integrated churn, additional peak headroom. Keep that cost explicit in review."
rows = []
for backend in ["vulkan", "d3d12"]:
    for workload in ["burst_release", "mixed_frames", "fragmentation"]:
        for variant in ["pr323", "cache2"]:
            w = load(f"results-metadata/{variant}-{backend}.json")["result"]["workloads"][workload]
            assert w["metadata_after_allocator_drop_bytes"] == 0
            rows.append([backend, workload, variant, w["metadata_peak_rust_bytes"], w["metadata_retained_rust_bytes"], w["metadata_after_allocator_drop_bytes"]])
replacements["METADATA_TABLE"] = table(["Backend", "MemoryUsage case", "Policy", "Peak tracked Rust bytes", "After release bytes", "After allocator drop bytes"], rows)
replacements["DOWNSTREAM_COUNTS"] = f"All {down['processes']} integrated processes completed across {len(down['cells'])} five-trial cells, with no captured panic or validation-error output. The driver records OS/GPU metrics and whole-process CPU time for every run. The full table includes each independent patch state and unfavorable cells."
rows = []
selected = [("dx12", "performance", "idle", ["pr323-trunk", "pr323-lazy", "pr323-transient", "pr323-both", "cache2-trunk", "cache2-both"]),
    ("vulkan", "performance", "idle", ["pr323-trunk", "pr323-lazy", "cache2-trunk", "cache2-lazy"]),
    ("dx12", "performance", "repeated_uploads", ["pr323-trunk", "pr323-both", "cache2-trunk", "cache2-both"]),
    ("dx12", "memory_usage", "churn", ["pr323-trunk", "pr323-both", "cache2-trunk", "cache2-both"]),
    ("vulkan", "memory_usage", "churn", ["pr323-trunk", "pr323-lazy", "cache2-trunk", "cache2-lazy"]),
    ("dx12", "manual-8-256", "large_textures", ["pr323-trunk", "cache2-trunk", "demand2-trunk", "pr323-both", "cache2-both", "demand2-both"])]
for backend, hints, workload, variants in selected:
    for variant in variants:
        r = wc[variant, backend, hints, workload]
        rows.append([backend, hints + " " + workload, variant, num(r["initial_reserved_mib"]), num(r["sampled_peak_reserved_mib"]), num(r["reserved_after_resources_mib"]), num(r["creation_p50_us"]), num(r["creation_p99_us"]), num(r["process_cpu_ms"])])
replacements["DOWNSTREAM_TABLE"] = table(["Backend", "Case", "Variant", "Initial MiB", "Sampled peak MiB", "After resources MiB", "Create p50 µs", "Create p99 µs", "Process CPU ms"], rows)
rows = []
for backend in ["dx12", "vulkan"]:
    for workload in ["sustained_render", "sustained_compute"]:
        for variant in ["pr323-trunk", "cache2-trunk", "cache2-both" if backend == "dx12" else "cache2-lazy"]:
            r = wc[variant, backend, "performance", workload]
            rows.append([backend, workload, variant, num(r["gpu_pass_p50_us"]), num(r["gpu_pass_p99_us"]), num(r["sampled_peak_reserved_mib"])])
replacements["DOWNSTREAM_TABLE"] += "\n\n" + table(["Backend", "Performance workload", "Variant", "GPU pass p50 µs", "GPU pass p99 µs", "Sampled reserved MiB"], rows)
rows = []
for backend in ["dx12", "vulkan"]:
    for hints, workload in [("performance", "idle"), ("memory_usage", "churn")]:
        for variant in ["pr323-trunk", "cache2-trunk", "cache2-both" if backend == "dx12" else "cache2-lazy"]:
            r = wc[variant, backend, hints, workload]
            rows.append([backend, hints + " " + workload, variant, num(r["sampled_peak_dxgi_local_mib"]), num(r["sampled_peak_private_commit_mib"]), num(r["after_resources_private_ws_mib"])])
replacements["DOWNSTREAM_TABLE"] += "\n\n" + table(["Backend", "Case", "Variant", "Sampled DXGI local peak MiB", "Sampled private commit peak MiB", "Private working set after resources MiB"], rows)
replacements["DOWNSTREAM_INTERPRETATION"] = """The idle DX12 savings overlap. Lazy initialization removes the first CPU-visible block: 192 to 128 MiB with Performance settings. Transient separation alone changes 192 to 144 MiB. Together they reach 128 MiB, not the sum of both independent savings. Cache2 leaves these initial reservations unchanged. On Vulkan, lazy initialization changes 144 to 128 MiB; transient separation has no Vulkan implementation.

Once uploads actually occur, a staging pool is needed. The combined DX12 path peaks and remains at 144 MiB in the repeated-upload case versus 192 MiB without the patches. This supports smaller lifetime-specific sizing even with the revised cache. Lazy allocation avoids unused resources; it cannot eliminate resources a workload uses.

The cache has an unfavorable integrated churn cell: with MemoryUsage settings, sampled peak reservation rises from 76 to 92 MiB and resource-drop reservation from 12 to 28 MiB. Retaining a reusable empty block alongside live internal resources costs 16 MiB here. This direct counterexample limits the claim of memory improvement and is a reason to keep explicit trimming and application sizing.

Demand-limited growth reduces the Manual integrated texture peak from 524 to 388 MiB. That confirms the direct geometric-headroom concern using real resources. It does not outweigh demand2's much greater mixed and burst heap churn in the direct suite. A future opt-in texture/lifetime policy could use this result; a universal default change would trade away substantial amortization.

Rendering and compute pass timings, DXGI local usage, private commit, working set, CPU-call ranges and full factorial states are retained in downstream-summary.csv. Paired allocator deltas and patch interactions are in downstream-interactions.csv and downstream-interactions.json. The harness samples GPU timestamps when supported. Changes in process commit and DXGI accounting are not interchangeable with allocator capacity. Identical reservations with variable creation latency do not demonstrate a stable GPU performance gain. No throughput improvement is required for the two wgpu patches' resource-avoidance and lifetime-sizing rationale."""
validation = {}
for name in ["validation.json", "validation-recheck.json"]:
    for record in load(name): validation[record["name"]] = record
assert all(r["rc"] == 0 for r in validation.values())
full = load("wgpu-full-tests.json")
triage = load("failure-triage.json")
assert len(triage["rows"]) == 26
assert not triage["classifications"].get("candidate-only in focused control: investigate", 0), "Investigate candidate-only failures before finalizing"
reproduced = triage["classifications"].get("reproduces without candidate allocator", 0)
unreproduced = triage["classifications"].get("not reproduced in either focused control", 0)
path_sensitive = triage["classifications"].get("executable-path sensitive with identical candidate bytes", 0)
assert reproduced + unreproduced + path_sensitive == 26
replacements["FULL_VALIDATION_STATUS"] = (
    "Allocator-specific checks and the benchmark processes pass. The broader wgpu matrix is not clean: "
    f"2,179 of 2,205 tests pass, 23 fail and three time out. Matched controls reproduce {reproduced} of the 26 unsuccessful cases "
    f"with unchanged allocator PR 323; {unreproduced} case remains unreproduced in both focused controls, and {path_sensitive} case depends on executable path with identical candidate bytes. "
    "Both wgpu patches remain applied in these controls, so this comparison isolates the allocator candidate only. "
    "The recommendation is for review with these validation limits, not a claim of a fully passing wgpu matrix. [Every failure and control result](FAILURE_TRIAGE.md).")
replacements["VALIDATION_SUMMARY"] = """The candidate passes formatting; 17 std unit tests; nine no_std tests; seven doctests (five intentionally ignored); strict Clippy for std, no_std and visualizer features; strict rustdoc; Apple ARM/Intel and Linux no_std checks; and physical Vulkan/D3D12 examples. The Apple ARM Metal no_std check also passes. The upstream Clippy configuration prints a pre-existing removed-lint warning; successful checks do not mean every tool emitted no warning.

Capacity/fallback, cache replacement, free-order invariants, trimming and regrowth are covered by behavioral tests. Hardware trimming and the unmodified downstream external-texture fixture pass. The complete combined wgpu cargo xtask test result is recorded in wgpu-full-tests.json and logs/wgpu-full-tests.log. Exact commands and exit codes accompany the validation logs. The declared Rust 1.71 minimum was not retested. Allocator checks use Rust 1.100.0; the full wgpu suite and its controls use the repository's Rust 1.97.1 pin.

The first full wgpu build stops before GPU tests because the optional Visual C++ ATL library is absent. Its failed result and log are preserved separately. A hash-verified Microsoft package supplies atls.lib inside this experiment, with a process-local LIB search path; the Visual Studio installation and global configuration are unchanged. Microsoft identifies ATL as an optional component. The recheck emits nonfatal missing-debug-PDB linker warnings for the supplied ATL objects. [Microsoft component list](https://learn.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-community?view=visualstudio), [package verification](local-atl.json).

The api_dump follow-up has one access violation at vkDestroyDevice with cache2. Repeating the same layered run on unchanged PR 323 reproduces that teardown access violation on its second attempt. All ordinary diagnostic processes pass. This validates that the failure also occurs without the candidate changes; its precise layer/driver cause is not established. Trace timings are excluded, and the captured allocation inputs remain available. See trace-teardown-recheck.json and texture-api-traces/receipts.json.

Both exported candidate patches pass git apply --check against their exact bases. A fresh reconstruction verifies all nine allocator source trees after line-ending normalization. The final audit verifies original evidence and branch state again; no commits, pushes, PR updates or upstream comments were made."""
replacements["VALIDATION_SUMMARY"] += (
    f"\n\nThe full wgpu run completes with 2,179 passes, 23 failures/aborts and three timeouts out of 2,205 tests, plus 18 profile exclusions. "
    f"The 26-case matched control reproduces {reproduced} with the unchanged allocator PR, leaves {unreproduced} unreproduced in both focused runs, and identifies {path_sensitive} executable-path-sensitive case. "
    "The original full-run results are preserved; focused results do not replace them. "
    "Controls retain both wgpu patches and therefore do not prove independence from those patches. "
    "The precise root causes remain unestablished and need further backend/driver investigation. "
    "[Failure table](FAILURE_TRIAGE.md), [full structured comparison](failure-triage.json).")
replacements["VALIDATION_SUMMARY"] += "\n\nThe asymmetric DX12 multiview result receives additional controls: five original-path PR passes versus five candidate failures; three passes per version at a common path; then eight candidate runs crossing path and logging. Identical candidate bytes fail four times at the original path and pass four times at the common path. Logging does not change that outcome, and staged WARP DLL hashes match. This establishes path sensitivity while leaving the underlying application-profile, cache, loader or driver cause unresolved. The full failure remains recorded; the experiment does not certify that every deployed executable path will work. [Path matrix](multiview-path-matrix.json)."
text = (H / "REPORT.template.md").read_text()
for key, value in replacements.items():
    assert "{{" + key + "}}" in text, key
    text = text.replace("{{" + key + "}}", value)
assert not re.search(r"\{\{[A-Z_]+\}\}", text)
(H / "REPORT.md").write_text(text, encoding="utf-8")
(H / "report-data.json").write_text(json.dumps({"direct_cell_comparisons": counts, "downstream_selected": selected,
    "validation": validation, "wgpu_full_tests": full}, indent=2))
print("Wrote complete 20-section report:", len(text.split()), "words")
