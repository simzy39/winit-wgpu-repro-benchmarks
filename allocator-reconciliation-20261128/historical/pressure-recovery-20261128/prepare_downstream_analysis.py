from pathlib import Path
H=Path(__file__).resolve().parent
s=(H.parent/'reassessment-20261128/analyze_downstream.py').read_text()
s=s.replace('H/"results-downstream"','H/"results/downstream-isolated"')
s=s.replace('receipt["cpu_times"]["total_cpu_ms"]','None')
s=s.replace('the allocator-by-wgpu-patch factorial','the focused four-way DX12 comparison')
s=s.replace('Integrated wgpu measurements','Focused integrated wgpu measurements')
s=s.replace('Full trial ranges and OS/GPU metrics','Process CPU totals were not sampled in this continuation. Full trial ranges and OS/GPU metrics')
(H/'analyze_downstream.py').write_text(s)
