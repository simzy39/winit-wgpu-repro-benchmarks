# Focused integrated wgpu measurements

Each row is the median of five standalone processes. Process CPU totals were not sampled in this continuation. Full trial ranges and OS/GPU metrics are in downstream-summary.csv. Reservation is sampled at harness stages; resource-drop reservation includes wgpu's remaining live internal allocations.

## dx12

| Hints and workload | Variant | Initial MiB | Peak reserved MiB | After resource drop MiB | CPU operation p50 us | CPU operation p99 us | Process CPU ms | Peak private commit MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| manual-8-256 large_textures | cache2-both | 8.00 | 524.00 | 12.00 | 3983.00 | 38733.00 |  | 661.93 |
| memory_usage churn | cache2-both | 8.00 | 92.00 | 28.00 | 5.40 | 23.70 |  | 225.61 |
| performance idle | cache2-both | 128.00 | 128.00 | 128.00 |  |  |  | 227.79 |
| performance repeated_uploads | cache2-both | 128.00 | 144.00 | 144.00 | 429.40 | 737.30 |  | 246.37 |
| performance sustained_render | cache2-both | 128.00 | 208.00 | 208.00 | 4013.00 | 4638.50 |  | 309.91 |
| manual-8-256 large_textures | recovery-both | 8.00 | 524.00 | 12.00 | 3855.50 | 51155.30 |  | 662.14 |
| memory_usage churn | recovery-both | 8.00 | 92.00 | 28.00 | 7.10 | 9.50 |  | 225.57 |
| performance idle | recovery-both | 128.00 | 128.00 | 128.00 |  |  |  | 227.38 |
| performance repeated_uploads | recovery-both | 128.00 | 144.00 | 144.00 | 406.10 | 737.90 |  | 246.39 |
| performance sustained_render | recovery-both | 128.00 | 208.00 | 208.00 | 3983.70 | 4464.50 |  | 310.30 |
| manual-8-256 large_textures | recovery-candidate | 8.00 | 524.00 | 12.00 | 3952.40 | 57263.70 |  | 662.43 |
| memory_usage churn | recovery-candidate | 8.00 | 92.00 | 28.00 | 5.10 | 5.70 |  | 225.50 |
| performance idle | recovery-candidate | 128.00 | 128.00 | 128.00 |  |  |  | 227.96 |
| performance repeated_uploads | recovery-candidate | 128.00 | 144.00 | 144.00 | 391.90 | 620.90 |  | 246.45 |
| performance sustained_render | recovery-candidate | 128.00 | 208.00 | 208.00 | 3990.30 | 4473.70 |  | 310.34 |
| manual-8-256 large_textures | recovery-singlepool | 8.00 | 524.00 | 12.00 | 4323.50 | 35166.30 |  | 661.93 |
| memory_usage churn | recovery-singlepool | 8.00 | 92.00 | 28.00 | 8.10 | 10.00 |  | 225.55 |
| performance idle | recovery-singlepool | 128.00 | 128.00 | 128.00 |  |  |  | 227.80 |
| performance repeated_uploads | recovery-singlepool | 128.00 | 192.00 | 192.00 | 388.10 | 655.90 |  | 294.50 |
| performance sustained_render | recovery-singlepool | 128.00 | 256.00 | 256.00 | 4002.50 | 4321.60 |  | 358.16 |
## vulkan

| Hints and workload | Variant | Initial MiB | Peak reserved MiB | After resource drop MiB | CPU operation p50 us | CPU operation p99 us | Process CPU ms | Peak private commit MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|