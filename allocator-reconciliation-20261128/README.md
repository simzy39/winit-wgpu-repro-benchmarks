# Allocator and wgpu reconciliation — 28 November 2026

This bundle preserves the completed architectural investigation and adds publication-source validation. Historical reports retain the review-only boundary and proposals that applied at the time. The current upstream contributions supersede those proposals without rewriting their evidence.

- [Allocator sizing, cache and recovery](https://github.com/Traverse-Research/gpu-allocator/pull/323), with independent [D3D12 rollback](https://github.com/Traverse-Research/gpu-allocator/pull/327) and [Vulkan allocation contracts](https://github.com/Traverse-Research/gpu-allocator/pull/328).
- [wgpu lazy external-texture parameters](https://github.com/gfx-rs/wgpu/pull/11129) and [DX12 transient pool](https://github.com/gfx-rs/wgpu/pull/11130).
- Independent [wgpu DX12 creation rollback](https://github.com/gfx-rs/wgpu/pull/11152) and [surface reconfiguration test correction](https://github.com/gfx-rs/wgpu/pull/11153).
- [wgpu cross-pool recovery dependency blocker](https://github.com/gfx-rs/wgpu/issues/11145); no invented allocator release or production dependency override.

## Results and provenance

The [publication report](REPORT.md) maps every confirmed finding to an issue, lists exact public PR heads and validation, and separates remaining API-release, native-failure and Apple-runtime blockers. [Prepared source patches](final-source/patches/README.md) document the merge dependencies and narrow recovery follow-up.

Read the historical [architectural reassessment](historical/reassessment-20261128/REPORT.md), [pressure/recovery report](historical/pressure-recovery-20261128/REPORT.md), [downstream comparison](historical/pressure-recovery-20261128/DOWNSTREAM_RESULTS.md), [failure ledger](historical/pressure-recovery-20261128/VALIDATION_FAILURES.md), and [matched GPUAV/layer controls](historical/pressure-recovery-20261128/GPUAV_CONTROL.md).

The seven-policy Windows comparison covers 210 independent processes, followed by a 60-process policy comparison and 100 focused wgpu processes. One bounded largest eligible empty cache per type remained the best practical default across these workloads. Vulkan also caps aggregate empty retention across types sharing a heap to its physical size. More aggressive aggregate limits, alternative cache selection and packing did not give a universal improvement. The synthetic 48 MiB/two-block experiment serves 48 one-MiB allocations with geometric fallback and two with exact-resource fallback; this is an allocation-plan/count limit experiment, not an OS-budget measurement.

The single-pool wgpu alternative raises retained reservation from 144 to 192 MiB for repeated uploads and from 208 to 256 MiB for sustained rendering (Performance hints, medians of five processes). Those historical measurements justify retaining #11130 even with the improved allocator. Timing ranges and raw OS/GPU metrics are preserved in the linked CSV/JSON, without claiming fresh final-source latency results.

The final allocator source has 54 passing std and 10 no_std library tests, strict Clippy/rustdoc/formatting checks, actual Rust 1.71 std / 1.81 no_std consumers, minimum Windows 0.53 binding checks, and Apple ARM/Intel cross-compilation. Six new native harness processes match all 60 historical normal allocation-plan cells. Their source hashes, raw records and receipt are under `final-source/checks/final-plans*`. Source patches and Git commit pins are under `final-source/patches` and the publication index.

The full native wgpu suite is **not green**. The historical integrated run has 2,184 passes and 23 failures/aborts among 2,207 executed tests, plus 18 profile exclusions. Twenty-two reproduce on pristine upstream with registry gpu-allocator and no proposed wgpu patches. DX12 multiview behavior depends on executable basename; its native cause remains unresolved. New publication-source runs are recorded separately as they complete. Apple runtime validation remains outstanding. Disabling GPUAV/validation in a diagnostic is not a conformance pass and does not identify the faulting component.

## Reproduction

`python reproduce_allocator.py --source <clean committed allocator checkout> --output <fresh directory> --trials 5` builds the supplied Windows native harness from a Git archive and the preserved lock. Each source variant gets its own target and executable receipt. The default one trial is a plan check; use isolated, interleaved trials and controlled system load before making latency claims. The harness reports logical allocator capacity; OS reclamation can lag native reference release.

The historical reproduction guides specify exact source revisions, diagnostic harness patches and commands. Historical generation scripts are provenance records and can contain sanitized placeholders; use the new runner for allocator measurements. wgpu diagnostics require the pinned upstream checkout, a matching SDK/driver and the explicit test-initialization controls described in GPUAV_CONTROL.md. Production manifests are not changed for those experiments.

For compiler consumers, `python reproduce_msrv.py --source <allocator checkout> --fixture final-std-vulkan --output <fresh directory>` reuses the exact preserved manifest, lock and minimal source after substituting the checkout path. Choose a `nostd` fixture for Rust 1.81; std fixtures use Rust 1.71. D3D12 fixtures require Windows. The original sanitized manifests retain their historical paths for provenance. The public runner has also been exercised successfully against the final allocator head; see `final-source/checks/reproduction-runner-smoke.json`.

Raw logs, JUnit and JSONL are gzip-compressed. Copied Markdown references use the published gzip filenames where available; decompress before processing the raw text. Local workspace, home, user and drive prefixes are sanitized, and private author email is removed. Numeric measurement fields are preserved. `provenance.json` records original, sanitized and stored SHA-256 values, including link normalization. Historical `EVIDENCE.sha256` files describe the original sealed bundles, including excluded binaries; use the root `SHA256SUMS` to verify this public derivative. Rejected shared-target pilots remain rejected: consult each report's accepted-run receipts rather than treating every archived run as accepted. Build caches, executables, SDK libraries and unrelated project files are excluded.

Source changes, reports and this bundle were prepared with an OpenAI coding agent at the contributor's direction. Upstream licenses accompany the copied source; existing unrelated benchmark-repository content is unchanged.
