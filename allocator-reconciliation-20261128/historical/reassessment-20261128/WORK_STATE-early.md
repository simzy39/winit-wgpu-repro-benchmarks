# Active task state

User request is in <user-home>/.codex/attachments/044edff7-ada2-4713-91cc-ab464fd49431/Pasted text.txt. Complete the comprehensive gpu-allocator PR 323 architectural reassessment, isolated candidates, hardware benchmarks, downstream wgpu combinations, final report and reviewable patch. No commits, pushes, upstream writes, actual PR branch edits, vendor or application edits. No subagents authorized. Continue autonomously to completion.

## Preserved state

Historical research is the parent directory. All 438 manifest entries matched; independently reanalyzed all historical matrix data with exact summary equality and zero proposal mismatches in 1500 cross-trial comparisons. Historical normalized allocation API streams matched over 3910 calls. Eleven published GPU tables have been downloaded afresh into sources/gpuinfo, all match recovered tables. Original raw HTML had not been retained there; new gzip snapshots preserve it. Local hardware probe refreshed.

Current upstream fc22df05140b15ed6d764beabd12a1b807011bc5, PR 179ea43f05332c2809addd7922cd056220efc36b, verified via GitHub connector and ls-remote. wgpu base 60cef2be828e03ba54e2e1598001b4625c0c2163; lazy PR 793698d89332250d5abe92e61769625233be9ac9; transient PR 22827ee25285b56c4056fe6bb1de27917caf45a9. All three PRs draft. Discussion includes user's newer expansion comment. Snapshots in sources/github-*.json.

All new files are inside this reassessment directory. Existing historical worktrees (proposal/proto dirty) untouched; actual PR branches clean. RustyGUI root has no .git. Detached worktrees registered in existing research clones only.

## Candidate

work/cache2/gpu-allocator is the current strongest candidate; production code frozen pending comparative results:
- resolved immutable min/max per memory type using CPU accessibility only to interpret legacy configuration
- Vulkan uses its canonical mappable bool, exact heap cap (no 4 MiB flooring), resource-capacity guard inside MemoryType also covers fallback
- explicit supported D3D12 types/properties, named GPU_UPLOAD constant available in windows 0.62
- Metal recognizes Shared placement heaps; Managed resource mode is not a supported heap
- existing PR max dedicated threshold and geometric growth preserved
- one empty shared block cached per memory type, even alongside live blocks; keep largest <= min(2*min,max), clear cache on reuse, replace cached block when larger eligible block becomes empty
- trim() -> u64 on all 3 backends removes empty blocks while preserving live indices and Metal residency bookkeeping
- 16 std unit tests, 9 no_std unit tests (verify actual stdout if uncertain), 7 doctests passed (5 doctests ignored).
- Strict repository-config Clippy std, no_std, visualizer, Metal ARM; Metal Intel and Linux no_std compile; fmt, rustdoc, actual Vulkan/D3D examples all pass after rechecks.
- Original strict lint failures (doc markup + test pointer casts) fixed; logs retained. Upstream removed Clippy lint emits a pre-existing non-fatal warning.
- Hardware trim: both Vulkan/D3D release 8 MiB while live anchor remains in 4 MiB; free anchor and trim -> zero; Vulkan mapped A7 byte preserved.
- Metadata instrumentation (separate binaries; timings explicitly excluded) covers main/pr323/cache2, both backends, memory_usage, all 10 workloads. All tracked Rust allocation bytes reach zero after allocator drop. Fragmentation peak PR vs cache2 +120 B VK / +96 B D3 (3 types). results-metadata.

Exported complete patches in patches/ against PR and main. Both git apply --check pass read-only against historical clean worktrees. Patch 5 files +787/-208 including 290-line new mocked Vulkan tests. Git intent-to-add only in isolated cache2 worktree includes new file; no commit. May re-export if any source edits, but avoid unnecessary behavioral changes until results.

## Experiments and build incident

Direct variants: main, pr323, proposal, retain2 (last block only bounded to 2min), demand2 (geometry constrained by 2x current request rounded 4MiB), request (request-sized rounded shared blocks), vma-policy (simplified VMA-inspired policy; NOT actual VMA), cache2. Separate actual VMA reference uses vk-mem 0.5.0 bundled VMA 3.3.0; native defaults, forced same type, externally synchronized, mapped CPU allocations. Current upstream VMA 3.5 source researched separately.

Initial shared Cargo target INCORRECTLY reused the first allocator artifact across worktrees. Invalid pilot stopped and preserved in results-direct/INVALID.txt and bin/ (old invalid binaries except original actual VMA adapter valid). Never use pilot numbers. Fixed using separate target-NAME directories and bin-verified. All 8 direct variants rebuilt correctly; actual VMA copied to bin-verified. Old build/log evidence retained. build.py default list excludes cache2; pass cache2 explicitly.

Common direct bench.rs has 10 workloads and precomputes actual resource requirements outside timing (old harness included Vulkan misses and every D3D requirements query). Added fragmentation, sporadic burst + long-lived anchor, small bursts, large mixed buffers. Growth alternatives have rounded sizes to retain classification inference. Direct raw includes every block event, heap/reuse latency, fragmentation marks, peak unused and driver snapshots. Do not claim free bytes are all fragmentation. VMA uses native stats for fragmentation and capacity.

run_direct.py 5 is READY but VERIFIED SUITE HAS NOT BEEN STARTED. It will run 8 variants * 2 backends * 5 configs * 5 trials = 400 processes, plus actual VMA 5 = 405, each 10 workloads. Interleaves/rotates variant order. Checks competing cargo/rustc/r1bench-final before timing. Original unrelated R1 benchmark finished; it was not stopped. All compilation should finish before timing. Output results-direct-verified; refuses to overwrite previous receipt with different binary. analyze_direct.py produces full CSV/JSON/Markdown and paired comparisons. It has not been run on verified data yet.

## Live work and immediate next steps

At state save, tool exec session 49990 runs:
python build_downstream.py cache2-trunk cache2-lazy cache2-transient cache2-both
First three built; cache2-both currently compiling. Wait for completion. This uses shared target-wgpu WITH explicit cargo clean of every changed crate before each build to prevent the Cargo cache incident. All 10 other combinations already built in bin-wgpu:
pr323 x trunk/lazy/transient/both;
retain2 x trunk/lazy/transient/both;
demand2 x trunk/both.
Sources in downstream/trees/{trunk,lazy,transient,both}. Actual wgpu PR branches untouched.

Once 49990 completes:
1. Run python build_external_check.py (uses target-wgpu, so do not run concurrently with downstream builds). Copies existing unmodified ext_tex_verify fixture into cache2-both standalone bench as extra bin.
2. Run bin-checks/external-texture-cache2-both.exe, capture stdout/stderr/rc/hash in new evidence. It tests concurrent lazy external texture initialization, pixel readback, queue-drop safety, fresh 64MiB transient release on Vulkan/D3D. Some retention assertions may need principled reassessment if new cache changes expected counts; do not blindly change.
3. Then begin python run_direct.py 5, no compilation during timing. Keep user updated at <=60s.
4. Write downstream runner/analyzer (not yet created), run sequentially after direct timing. Planned full factorial original PR and cache2 x four wgpu patch states, N=5, plus meaningful retain2/demand2 comparison cells if useful. Wgpu harness existing unchanged, supports --backend dx12/vulkan --hints performance/memory_usage/manual-8-256 --workload idle/small_gui/repeated_uploads/large_textures/large_alloc/churn/sustained_render/sustained_compute/multi_surface --json PATH. Wgpu B3 changes only DX12 so Vulkan duplicate transient states may be omitted with source explanation. Measure source-equivalent builds and OS/DXGI/process stats (harness already implements them). Need create DOWNSTREAM_COMPLETE marker afterward.
5. After both latency suites complete, run python run_wgpu_validation.py. Guard requires DIRECT_COMPLETE and DOWNSTREAM_COMPLETE. This invokes full cargo xtask test in downstream/validation (new detached tree, both wgpu patches + .cargo patch pointing at cache2), with only-local PATH/Vulkan SDK settings and NEXTEST_TEST_THREADS=2, WGPU_BACKEND=dx12,vulkan. This satisfies relevant wgpu AGENTS full-test guidance. Local verified cargo-nextest 0.9.152 installed under tools only (official release asset SHA checked); no global install. Full suite can compile/run while writing final report, but not during latency measurements. AGENTS read: actual PRs fully agentic forbidden (not being published); no CTS unless asked; no commits; targeted tests supported. Existing docs/testing read.
6. Analyze all data honestly, select practical candidate based on evidence. Tentative recommendation: cache2 + cap + trim + refactor, preserve geometric growth for practical PR; demand-based alternatives may lower reservation but create more heaps. CPU visibility is not ideal primary policy, only legacy configuration selector. Ideal future architecture separates per-type pools and per-heap/segment dynamic budgets and application lifetime hints. Avoid eliminating wgpu transient pool without evidence; lazy resource elimination remains orthogonal.
7. Write comprehensive REPORT.md covering all 20 required deliverables, concise proposed GPU allocator PR draft, reproduction instructions, evidence manifests, final safety/integrity audit. RESEARCH.md already contains primary-source modern allocator research and policy table; can link as appendix. Sources snapshots VMA/D3D12MA/Dawn/ANGLE/Mesa with blob identities present.
8. Complete reproducibility scripts: prepare.py currently needs attaching capacity_tests.rs to retain2 and cfg module before prepare_cache.py in a fresh run (was done inline originally); finish_cache.py handles core RefCell and updated docs, but original root capacity_tests.rs now pointer .cast fixes. fix_build_isolation.py is an incident-only script; do not rerun on current prepared worktrees. Add build_vma.py and run_metadata/trim wrappers if useful; currently some steps were shell calls.
9. Update audit.py to preserve initial recovery-audit.json if final audit rerun (write final filename), compare historical states/438 manifest again. Do not overwrite initial evidence. Export patch again only if source changed, verify apply-check. Verify remote heads once more, no upstream mutations.
10. Final concise user response with decisive recommendation, key measured trade-off, links to comprehensive report and patch, test coverage/limits, branches untouched. No approval question needed; user explicitly requested final review boundary.

## Known interpretation limits and findings to explain

- VMA reference 3.3 differs from current researched 3.5 and does not mirror separate host/device config. Compare native strategy, not exact configuration.
- Main historical 1500 proposal comparisons are all cross-trial products (not 1500 independent runs). New paired comparisons would be 500.
- Original texture workload is 24 x 2048x2056 RGBA8; actual Intel requirement ~17.06 MiB each, 409.5 MiB live, old PR reserved 544 MiB. Payload ~16.06MiB each is distinct.
- Old Performance burst is 40 x 6.25MiB upload buffers, 4 rounds. Historical main 16ms VK vs PR130; D3 105 vs253, but old timings included requirements so do not compare old vs new absolute values.
- Capacity_matrix.json: 11 published tables, 928 static checks, old4 violations/new0. Exact cap preserves tiny/sub4MiB heaps and final non-4MiB bytes (improvement over old floor sketch). Mock tests prove fallback guard too.
- Full budget cannot be capped once at construction; budget is dynamic and shared by types in one heap. Current candidate has explicit trim but no dynamic budget/pressure retry integration. Wgpu budget check estimates minimum blocks, underestimates actual growth and ignores reuse; Manual range clamp vs 4MiB rounding also diverges. Treat as downstream future work, not fixed.
- Independent Metal Shared-texture helper chooses Private via Unknown, Shared heap unsupported on Intel Macs, Vulkan same-type fallback retry/error masking remain separate. Backend placement unchanged.
- Metal typechecked, no Apple hardware; other discrete/mobile devices table simulation only; one Intel Arc physical GPU plus WARP probe.
- One-cache policy changes retention for fixed configs too while other blocks remain live; sizes unchanged but do not claim identical retention.
- Metadata raw is scoped Rust allocator-call allocation traffic (including temporaries, excluding inline storage, driver/C++ heaps); final tracked zero in all cells.
- Pilot invalid data clearly marked; final report must disclose build-cache incident and exclusion.

