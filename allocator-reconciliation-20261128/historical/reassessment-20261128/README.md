# gpu-allocator PR 323 reassessment

Start with [the 20-section report](REPORT.md). It contains the architectural decision, measured trade-offs, downstream factorial, validation results and limitations.

| Artifact | Purpose |
|---|---|
| [Candidate against PR 323](patches/candidate-on-pr323-179ea43.patch) | Review the proposed expansion from the existing PR head |
| [Candidate against main](patches/candidate-on-main-fc22df0.patch) | Review the complete change from its upstream base |
| [Proposed PR text](PROPOSED_PR.md) | Local draft only |
| [Reproduction](REPRODUCE.md) | Fresh detached source reconstruction, builds and measurements |
| [Research appendix](RESEARCH.md) | Specifications, current allocators and research applicability |
| [Direct results](DIRECT_RESULTS.md) | All primary allocation-policy cells |
| [Integrated results](DOWNSTREAM_RESULTS.md) | All wgpu patch combinations and sampled resource/OS metrics |
| [Full-suite failure controls](FAILURE_TRIAGE.md) | Every unsuccessful wgpu test and its allocator controls |
| [Final integrity audit](final-recovery-audit.json) | Historical hashes, preserved repository state and remote heads |
| [Evidence manifest](EVIDENCE.sha256) | Archived inputs, outputs, scripts, binaries and reports |

The primary suites contain 405 direct processes, 80 cache-limit/CPU processes and 520 valid integrated processes. A suspended integrated attempt is preserved separately. Focused texture diagnostics and exact-binary replays are additional experiments. Raw results and receipts are adjacent to each suite; source patches and locked harnesses are frozen under repro-inputs.

All changes are isolated research artifacts. Existing PR branches, application code and vendored dependencies remain untouched. Nothing has been committed, pushed or published.
