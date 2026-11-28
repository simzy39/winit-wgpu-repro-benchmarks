# Reproducing the reassessment

Use Windows with Vulkan and D3D12 drivers, Python 3, Git, Rust/Cargo and the Microsoft C++ build tools. The measured machine and exact tool versions are in sources/runtime-environment.json. The primary tests used physical Intel Arc integrated graphics. Use a different output directory for every run; do not run measurement commands in this evidence directory.

Direct/integrated benchmark builds and allocator checks use Rust 1.100.0. The full wgpu test tree pins Rust 1.97.1 in its tracked rust-toolchain.toml. Preserve that pin for the matched failure controls. sources/toolchains-by-workspace.json records the actual compiler selected in each directory.

The source inputs are frozen in repro-inputs. Each allocator variant has its base commit, patch, normalized source hashes, Cargo.lock and benchmark manifest. Both benchmark sources and the native VMA reference are included. Source identity checks normalize CRLF to LF; the evidence manifest hashes the actual archived bytes. Cached Cargo dependencies are sufficient for the offline build commands on this machine. On another machine, fetch the pinned dependencies with cargo fetch --locked first.

From this directory, prepare a fresh sibling experiment:

~~~powershell
python reproduce.py '..\reproduction-my-run'
Set-Location -LiteralPath '..\reproduction-my-run'
~~~

The preparation uses the existing full clones at ../repo and ../../winit-wgpu/repos/wgpu relative to the original report directory. It creates detached worktrees at the exact allocator and wgpu revisions, applies archived patches, verifies every allocator source file, copies the locked harnesses and rewrites only their local paths. It refuses to overwrite an existing destination. Fresh source reconstruction was checked in reproduction-source-check-20261128-v2. The first preparation attempt is preserved separately; its byte comparison needed CRLF normalization.

Build all direct variants and the native VMA reference before measuring. Each variant has a separate Cargo target directory:

~~~powershell
python build.py main pr323 proposal retain2 demand2 request vma-policy cache2 cachemax
python build_vma.py
python validate.py
~~~

validate.py checks the final cache2 source. Apple and Linux type checks require the installed Rust targets aarch64-apple-darwin, x86_64-apple-darwin and x86_64-unknown-linux-gnu. Those checks compile Rust code without claiming hardware execution. The full recorded validation and corrections are in validation.json, validation-recheck.json and logs. The final additional capacity regression was run through post_direct.py; the 17-test result is in logs/unit-growth-regression.log.

Build the integrated combinations before any measurements. build_downstream.py explicitly cleans every source-dependent crate in its shared target directory before rebuilding:

~~~powershell
python build_downstream.py pr323-trunk pr323-lazy pr323-transient pr323-both cache2-trunk cache2-lazy cache2-transient cache2-both retain2-trunk retain2-both demand2-trunk demand2-both
~~~

Stop compilation and other GPU benchmarks, then run the suites sequentially:

~~~powershell
python run_direct.py 5
python run_cache_limits.py
python run_downstream.py
~~~

The direct and downstream drivers wait when cargo, rustc or the unrelated R1 benchmark is active. They run one process at a time, rotate/reverse policy order across trials and wait two seconds after each process. The focused cache-limit suite must also be run without concurrent compilers or GPU benchmarks. Five direct trials contain 405 processes and 4,050 workload measurements. The cache-limit/CPU follow-up contains 80 processes. The integrated factorial contains 520 processes. Run order, executable hashes, exits, timestamps, stderr and process CPU accounting are retained alongside raw JSON.

Keep the same driver, power settings and workload dimensions when comparing policies. Requirements preparation is outside timed allocator calls. Old historical harness timings include requirements queries and are a different experiment. Integrated reservation peaks are sampled at stages, rather than driver-call high-water marks. Resource-drop reservation includes live wgpu internal allocations; device-drop is a separate stage.

After all timing suites finish, verify native VMA's dedicated/shared classification in a separately instrumented executable, then analyze:

~~~powershell
python validate_vma_counts.py
python analyze_direct.py
python analyze_cache_limits.py
python analyze_downstream.py
python analyze_interactions.py
~~~

The VMA counter run's timings are excluded. vk-mem 0.5.0 bundles VMA 3.3.0. Native VMA uses its defaults with the same selected memory type and requirements; it is a reference implementation comparison rather than matching gpu-allocator's configured ranges. vma-policy is only a simplified heuristic experiment. Its equal-request-sized shared blocks require threshold-based count reconstruction, which analyze_direct.py performs explicitly.

For one direct smoke run, invoke bin-verified/bench-cache2.exe vulkan memory_usage 1 cache2. It prints JSON and executes all ten direct workloads. A downstream smoke run accepts --backend dx12 --hints memory_usage --workload churn --json a-new-path.json. The backend spelling differs between the two harnesses: d3d12 for direct and dx12 for wgpu.

The complete candidate patch applies to either PR 323 at 179ea43 or upstream main at fc22df0; patch hashes and read-only git apply --check results are in patches/manifest.json. For a new correctness-only worktree, apply the corresponding patch to that base and run the commands recorded in validate.py. The Vulkan capacity fixture substitutes allocation/free callbacks; hardware trimming is checked separately by build_trim_check.py and the receipts in hardware-trim-check.json.

The unchanged external-texture fixture is built by build_external_check.py against cache2 and both wgpu patches. Its log and return code are in logs/external-texture-cache2-both.log and external-texture-check-rc.txt. The full wgpu correctness run uses a separate detached validation worktree, both wgpu patches, a Cargo path override for cache2, and cargo xtask test. Fresh preparation also creates that worktree and copies local nextest/ATL support when available. Run python run_wgpu_validation.py after the timing suites. The runner, local PATH/LIB additions and result are recorded in run_wgpu_validation.py and wgpu-full-tests.json. It does not run CTS. The first full build failed because atls.lib was absent. prepare_local_atl.py used the installed Visual Studio catalog to download a hash-verified Microsoft x64 ATL package and extracted its library inside tools/atl. local-atl.json records the package, official URL and hashes. No Visual Studio installation or global environment was changed.

One measurement process spanned lid-triggered Modern Standby. Its original files remain in results-downstream-suspended; measurement-exclusions.json links the identical-binary repeat. The final downstream summary uses 520 valid processes from 521 attempts. The power-source event after wake and system timestamps are preserved in sources/kernel-power-recent.json. If a reproduction is interrupted by sleep, preserve and label that attempt before repeating it. A temporary per-thread sleep inhibition was used for the remaining checks; the power plan and display policy were unchanged.

The fixed-texture timing follow-ups are separate experiments. texture_diagnostic.py builds a filtered harness and compares textures alone with the original ten-workload order over twenty processes. replay_original_textures.py repeats the exact archived executables over ten further processes after compilation ends. texture-diagnostic-summary.json and texture-original-replay-summary.json retain every range. API traces are captured by trace_texture_diagnostic.py and interpreted by analyze_texture_traces.py. Trace timings are excluded. The api_dump device-teardown access violation also reproduces on unchanged PR 323; trace-teardown-recheck.json preserves that control.

The full wgpu suite remains unsuccessful: 2,179 passes, 23 failures/aborts and three timeouts out of 2,205 tests, plus 18 profile exclusions. prepare_failure_controls.py freezes the JUnit failure set and binary metadata. run_failure_controls.py preserves the candidate executables, substitutes only the allocator path with PR 323 in the isolated validation configuration, cleans the affected crates, builds the same feature set and runs the exact 26-case filter against both versions. Its finally block restores the candidate path. Both wgpu patches stay applied, so this isolates the allocator change only. FAILURE_TRIAGE.md records 24 baseline reproductions, one case unreproduced in either focused run and one executable-path-sensitive case.

The path-sensitive multiview case has five PR passes versus five candidate failures at the original executable paths. recheck_multiview_common_path.py runs the same binary bytes at a shared staging path and records static DXC selection: three passes per version. multiview_path_matrix.py then crosses candidate executable path with warn/debug logging over two rounds. Original-path runs fail four times and common-path runs pass four times, with identical executable and WARP DLL hashes. Preserve these path names when reproducing the observation. The finding does not establish its underlying driver/cache/profile/loader cause or erase the original failure.

Metadata instrumentation is separate from timing: build_metadata.py generates tracked Rust allocator calls, and results-metadata records requested bytes with timing fields marked incomparable. It excludes inline memory and driver/C++ metadata. The trim and external-texture checks also serve correctness rather than comparative timing.

The initial stale-artifact pilot under results-direct and its original bin directory is invalid and excluded. Do not use fix_build_isolation.py or the early procedural preparation scripts to overwrite the completed experiment. The frozen repro-inputs and reproduce.py are the canonical fresh source reconstruction. All measured outputs are hashed in EVIDENCE.sha256. The original 438-file manifest remains in the parent directory and is checked again by final_audit.py.
