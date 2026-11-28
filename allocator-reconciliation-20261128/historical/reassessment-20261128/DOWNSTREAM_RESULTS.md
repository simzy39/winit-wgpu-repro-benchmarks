# Integrated wgpu measurements

Each row is the median of five standalone processes. Full trial ranges and OS/GPU metrics are in downstream-summary.csv. Reservation is sampled at harness stages; resource-drop reservation includes wgpu's remaining live internal allocations.

## dx12

| Hints and workload | Variant | Initial MiB | Peak reserved MiB | After resource drop MiB | CPU operation p50 us | CPU operation p99 us | Process CPU ms | Peak private commit MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| manual-8-256 large_alloc | cache2-both | 8.00 | 792.00 | 12.00 | 29509.00 | 78909.50 | 421.88 | 900.34 |
| manual-8-256 large_textures | cache2-both | 8.00 | 524.00 | 12.00 | 6974.30 | 62563.70 | 421.88 | 662.01 |
| memory_usage churn | cache2-both | 8.00 | 92.00 | 28.00 | 13.50 | 118.40 | 281.25 | 226.10 |
| memory_usage large_textures | cache2-both | 8.00 | 460.00 | 12.00 | 10283.50 | 35513.40 | 359.38 | 597.62 |
| performance idle | cache2-both | 128.00 | 128.00 | 128.00 |  |  | 265.62 | 227.73 |
| performance repeated_uploads | cache2-both | 128.00 | 144.00 | 144.00 | 393.40 | 1658.10 | 359.38 | 246.41 |
| performance sustained_compute | cache2-both | 128.00 | 208.00 | 208.00 | 1008.00 | 2353.30 | 359.38 | 311.11 |
| performance sustained_render | cache2-both | 128.00 | 208.00 | 208.00 | 4927.90 | 5781.30 | 406.25 | 310.21 |
| manual-8-256 large_alloc | cache2-lazy | 8.00 | 792.00 | 12.00 | 22249.60 | 141131.90 | 390.62 | 900.37 |
| manual-8-256 large_textures | cache2-lazy | 8.00 | 524.00 | 12.00 | 6114.10 | 74932.70 | 437.50 | 662.01 |
| memory_usage churn | cache2-lazy | 8.00 | 92.00 | 28.00 | 13.70 | 75.80 | 296.88 | 225.70 |
| memory_usage large_textures | cache2-lazy | 8.00 | 460.00 | 12.00 | 7449.10 | 32675.10 | 406.25 | 597.48 |
| performance idle | cache2-lazy | 128.00 | 128.00 | 128.00 |  |  | 296.88 | 227.57 |
| performance repeated_uploads | cache2-lazy | 128.00 | 192.00 | 192.00 | 463.90 | 1733.10 | 421.88 | 294.81 |
| performance sustained_compute | cache2-lazy | 128.00 | 256.00 | 256.00 | 1043.20 | 2463.90 | 390.62 | 359.31 |
| performance sustained_render | cache2-lazy | 128.00 | 256.00 | 256.00 | 4879.20 | 7076.00 | 343.75 | 358.15 |
| manual-8-256 large_alloc | cache2-transient | 12.00 | 792.00 | 12.00 | 20622.10 | 80502.50 | 375.00 | 900.23 |
| manual-8-256 large_textures | cache2-transient | 12.00 | 524.00 | 12.00 | 6267.70 | 57565.80 | 406.25 | 662.30 |
| memory_usage churn | cache2-transient | 12.00 | 92.00 | 28.00 | 12.80 | 70.70 | 296.88 | 225.55 |
| memory_usage large_textures | cache2-transient | 12.00 | 460.00 | 12.00 | 8260.50 | 32745.20 | 375.00 | 597.58 |
| performance idle | cache2-transient | 144.00 | 144.00 | 144.00 |  |  | 265.62 | 244.01 |
| performance repeated_uploads | cache2-transient | 144.00 | 144.00 | 144.00 | 503.20 | 1907.90 | 437.50 | 246.54 |
| performance sustained_compute | cache2-transient | 144.00 | 208.00 | 208.00 | 1042.80 | 2067.90 | 375.00 | 311.18 |
| performance sustained_render | cache2-transient | 144.00 | 208.00 | 208.00 | 4944.10 | 6158.60 | 312.50 | 310.16 |
| manual-8-256 large_alloc | cache2-trunk | 12.00 | 792.00 | 12.00 | 16308.40 | 132742.10 | 406.25 | 900.47 |
| manual-8-256 large_textures | cache2-trunk | 12.00 | 524.00 | 12.00 | 5801.70 | 64584.20 | 375.00 | 662.21 |
| memory_usage churn | cache2-trunk | 12.00 | 92.00 | 28.00 | 14.60 | 130.20 | 312.50 | 225.74 |
| memory_usage large_textures | cache2-trunk | 12.00 | 460.00 | 12.00 | 6675.60 | 20571.50 | 375.00 | 597.76 |
| performance idle | cache2-trunk | 192.00 | 192.00 | 192.00 |  |  | 250.00 | 291.68 |
| performance repeated_uploads | cache2-trunk | 192.00 | 192.00 | 192.00 | 424.60 | 1685.10 | 390.62 | 294.29 |
| performance sustained_compute | cache2-trunk | 192.00 | 256.00 | 256.00 | 1070.90 | 2459.50 | 453.12 | 359.48 |
| performance sustained_render | cache2-trunk | 192.00 | 256.00 | 256.00 | 4908.00 | 5907.10 | 375.00 | 358.35 |
| manual-8-256 large_textures | demand2-both | 8.00 | 388.00 | 12.00 | 9880.90 | 39838.30 | 406.25 | 524.44 |
| manual-8-256 large_textures | demand2-trunk | 12.00 | 388.00 | 12.00 | 9602.60 | 29071.40 | 468.75 | 524.86 |
| manual-8-256 large_alloc | pr323-both | 8.00 | 792.00 | 12.00 | 24660.80 | 82499.60 | 421.88 | 900.09 |
| manual-8-256 large_textures | pr323-both | 8.00 | 524.00 | 12.00 | 6879.30 | 59502.90 | 406.25 | 662.09 |
| memory_usage churn | pr323-both | 8.00 | 76.00 | 12.00 | 11.50 | 106.70 | 281.25 | 225.85 |
| memory_usage large_textures | pr323-both | 8.00 | 460.00 | 12.00 | 8981.00 | 32334.20 | 390.62 | 597.45 |
| performance idle | pr323-both | 128.00 | 128.00 | 128.00 |  |  | 250.00 | 228.01 |
| performance repeated_uploads | pr323-both | 128.00 | 144.00 | 144.00 | 540.70 | 2606.70 | 343.75 | 246.50 |
| performance sustained_compute | pr323-both | 128.00 | 208.00 | 208.00 | 1017.20 | 2574.10 | 359.38 | 311.19 |
| performance sustained_render | pr323-both | 128.00 | 208.00 | 208.00 | 4935.70 | 6536.60 | 359.38 | 310.05 |
| manual-8-256 large_alloc | pr323-lazy | 8.00 | 792.00 | 12.00 | 24399.40 | 99497.70 | 468.75 | 900.12 |
| manual-8-256 large_textures | pr323-lazy | 8.00 | 524.00 | 12.00 | 6216.30 | 65344.20 | 359.38 | 662.11 |
| memory_usage churn | pr323-lazy | 8.00 | 76.00 | 12.00 | 10.20 | 55.70 | 234.38 | 225.57 |
| memory_usage large_textures | pr323-lazy | 8.00 | 460.00 | 12.00 | 6971.10 | 66165.20 | 421.88 | 597.49 |
| performance idle | pr323-lazy | 128.00 | 128.00 | 128.00 |  |  | 250.00 | 227.54 |
| performance repeated_uploads | pr323-lazy | 128.00 | 192.00 | 192.00 | 410.10 | 1544.80 | 406.25 | 294.33 |
| performance sustained_compute | pr323-lazy | 128.00 | 256.00 | 256.00 | 923.90 | 1344.30 | 359.38 | 359.19 |
| performance sustained_render | pr323-lazy | 128.00 | 256.00 | 256.00 | 4872.00 | 5664.70 | 375.00 | 358.38 |
| manual-8-256 large_alloc | pr323-transient | 12.00 | 792.00 | 12.00 | 22636.90 | 70367.00 | 406.25 | 900.31 |
| manual-8-256 large_textures | pr323-transient | 12.00 | 524.00 | 12.00 | 5718.60 | 53820.30 | 406.25 | 662.15 |
| memory_usage churn | pr323-transient | 12.00 | 76.00 | 12.00 | 11.10 | 52.40 | 296.88 | 225.66 |
| memory_usage large_textures | pr323-transient | 12.00 | 460.00 | 12.00 | 6713.20 | 33436.80 | 406.25 | 597.70 |
| performance idle | pr323-transient | 144.00 | 144.00 | 144.00 |  |  | 250.00 | 243.94 |
| performance repeated_uploads | pr323-transient | 144.00 | 144.00 | 144.00 | 413.10 | 1511.30 | 421.88 | 246.61 |
| performance sustained_compute | pr323-transient | 144.00 | 208.00 | 208.00 | 1014.40 | 1612.20 | 406.25 | 311.38 |
| performance sustained_render | pr323-transient | 144.00 | 208.00 | 208.00 | 4875.10 | 5700.40 | 390.62 | 310.33 |
| manual-8-256 large_alloc | pr323-trunk | 12.00 | 792.00 | 12.00 | 26713.60 | 98804.30 | 406.25 | 900.29 |
| manual-8-256 large_textures | pr323-trunk | 12.00 | 524.00 | 12.00 | 6041.40 | 54943.40 | 421.88 | 662.15 |
| memory_usage churn | pr323-trunk | 12.00 | 76.00 | 12.00 | 10.20 | 13.00 | 265.62 | 225.71 |
| memory_usage large_textures | pr323-trunk | 12.00 | 460.00 | 12.00 | 8631.90 | 34867.50 | 390.62 | 597.28 |
| performance idle | pr323-trunk | 192.00 | 192.00 | 192.00 |  |  | 281.25 | 291.97 |
| performance repeated_uploads | pr323-trunk | 192.00 | 192.00 | 192.00 | 375.60 | 1260.10 | 390.62 | 294.63 |
| performance sustained_compute | pr323-trunk | 192.00 | 256.00 | 256.00 | 982.30 | 1658.20 | 390.62 | 359.30 |
| performance sustained_render | pr323-trunk | 192.00 | 256.00 | 256.00 | 4921.30 | 5980.40 | 406.25 | 358.39 |
| manual-8-256 large_textures | retain2-both | 8.00 | 524.00 | 12.00 | 5956.60 | 78855.30 | 484.38 | 662.21 |
| manual-8-256 large_textures | retain2-trunk | 12.00 | 524.00 | 12.00 | 6822.60 | 76749.20 | 484.38 | 662.25 |
## vulkan

| Hints and workload | Variant | Initial MiB | Peak reserved MiB | After resource drop MiB | CPU operation p50 us | CPU operation p99 us | Process CPU ms | Peak private commit MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| manual-8-256 large_alloc | cache2-lazy | 8.00 | 792.00 | 12.00 | 5292.00 | 27777.20 | 296.88 | 844.86 |
| manual-8-256 large_textures | cache2-lazy | 8.00 | 524.00 | 12.00 | 4978.20 | 70130.90 | 328.12 | 641.48 |
| memory_usage churn | cache2-lazy | 8.00 | 92.00 | 28.00 | 5.20 | 65.40 | 171.88 | 175.61 |
| memory_usage large_textures | cache2-lazy | 8.00 | 460.00 | 12.00 | 7134.40 | 49635.20 | 296.88 | 577.39 |
| performance idle | cache2-lazy | 128.00 | 128.00 | 128.00 |  |  | 203.12 | 173.29 |
| performance repeated_uploads | cache2-lazy | 128.00 | 144.00 | 144.00 | 284.10 | 2143.10 | 265.62 | 196.66 |
| performance sustained_compute | cache2-lazy | 128.00 | 208.00 | 208.00 | 1146.60 | 2410.30 | 281.25 | 259.88 |
| performance sustained_render | cache2-lazy | 128.00 | 208.00 | 208.00 | 4248.00 | 7126.90 | 250.00 | 259.73 |
| manual-8-256 large_alloc | cache2-trunk | 12.00 | 792.00 | 12.00 | 3296.50 | 27093.70 | 343.75 | 844.95 |
| manual-8-256 large_textures | cache2-trunk | 12.00 | 524.00 | 12.00 | 5087.50 | 48722.10 | 375.00 | 641.48 |
| memory_usage churn | cache2-trunk | 12.00 | 92.00 | 28.00 | 4.30 | 30.70 | 203.12 | 175.67 |
| memory_usage large_textures | cache2-trunk | 12.00 | 460.00 | 12.00 | 6258.60 | 29013.50 | 265.62 | 577.35 |
| performance idle | cache2-trunk | 144.00 | 144.00 | 144.00 |  |  | 203.12 | 189.41 |
| performance repeated_uploads | cache2-trunk | 144.00 | 144.00 | 144.00 | 461.90 | 1587.70 | 250.00 | 196.60 |
| performance sustained_compute | cache2-trunk | 144.00 | 208.00 | 208.00 | 1095.00 | 2548.20 | 234.38 | 259.87 |
| performance sustained_render | cache2-trunk | 144.00 | 208.00 | 208.00 | 4206.30 | 4798.20 | 250.00 | 259.85 |
| manual-8-256 large_textures | demand2-both | 8.00 | 388.00 | 12.00 | 8077.00 | 31276.80 | 343.75 | 505.28 |
| manual-8-256 large_textures | demand2-trunk | 12.00 | 388.00 | 12.00 | 8288.00 | 28331.60 | 328.12 | 505.31 |
| manual-8-256 large_alloc | pr323-lazy | 8.00 | 792.00 | 12.00 | 3502.80 | 18032.10 | 281.25 | 844.92 |
| manual-8-256 large_textures | pr323-lazy | 8.00 | 524.00 | 12.00 | 5271.40 | 76528.40 | 328.12 | 641.42 |
| memory_usage churn | pr323-lazy | 8.00 | 76.00 | 12.00 | 3.70 | 30.30 | 218.75 | 175.58 |
| memory_usage large_textures | pr323-lazy | 8.00 | 460.00 | 12.00 | 6180.00 | 23258.10 | 281.25 | 577.37 |
| performance idle | pr323-lazy | 128.00 | 128.00 | 128.00 |  |  | 218.75 | 173.27 |
| performance repeated_uploads | pr323-lazy | 128.00 | 144.00 | 144.00 | 287.10 | 983.80 | 250.00 | 196.62 |
| performance sustained_compute | pr323-lazy | 128.00 | 208.00 | 208.00 | 1112.00 | 2326.20 | 234.38 | 259.77 |
| performance sustained_render | pr323-lazy | 128.00 | 208.00 | 208.00 | 4161.10 | 6478.50 | 250.00 | 259.75 |
| manual-8-256 large_alloc | pr323-trunk | 12.00 | 792.00 | 12.00 | 4395.90 | 26023.50 | 296.88 | 844.87 |
| manual-8-256 large_textures | pr323-trunk | 12.00 | 524.00 | 12.00 | 4631.10 | 72935.20 | 296.88 | 641.51 |
| memory_usage churn | pr323-trunk | 12.00 | 76.00 | 12.00 | 4.40 | 25.20 | 171.88 | 175.60 |
| memory_usage large_textures | pr323-trunk | 12.00 | 460.00 | 12.00 | 5546.20 | 26176.00 | 250.00 | 577.37 |
| performance idle | pr323-trunk | 144.00 | 144.00 | 144.00 |  |  | 187.50 | 189.35 |
| performance repeated_uploads | pr323-trunk | 144.00 | 144.00 | 144.00 | 289.50 | 1014.10 | 234.38 | 196.61 |
| performance sustained_compute | pr323-trunk | 144.00 | 208.00 | 208.00 | 1094.20 | 2618.80 | 218.75 | 259.87 |
| performance sustained_render | pr323-trunk | 144.00 | 208.00 | 208.00 | 4114.30 | 4765.20 | 265.62 | 259.81 |
| manual-8-256 large_textures | retain2-both | 8.00 | 524.00 | 12.00 | 5497.90 | 105976.50 | 375.00 | 641.51 |
| manual-8-256 large_textures | retain2-trunk | 12.00 | 524.00 | 12.00 | 5491.90 | 92921.50 | 375.00 | 641.46 |