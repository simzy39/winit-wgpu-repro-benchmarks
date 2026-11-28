"""Summarize every integrated wgpu run and the allocator-by-wgpu-patch factorial."""
import pathlib,json,collections,statistics,csv
H=pathlib.Path(__file__).resolve().parent
MIB=1024*1024
groups=collections.defaultdict(list)
failures=[]
for path in sorted((H/"results-downstream").glob("*.receipt.json")):
    receipt=json.loads(path.read_text())
    stem=path.name.removesuffix(".receipt.json")
    if receipt["rc"] or receipt["validation_error"]:failures.append({"run":stem,"receipt":receipt});continue
    d=json.loads(path.with_name(stem+".json").read_text())
    variant,backend,hints,workload,_=stem.split("__")
    assert d["adapter_name"]=="Intel(R) Arc(TM) Graphics"
    stages=d["stages"]
    by_name={s["stage"]:s for s in stages}
    initial=by_name["3_device_request"]
    released=by_name.get("9_resources_dropped",by_name.get("10_extended_idle",initial))
    timing=d["cpu_op_timing"] or {}
    gpu=d["gpu_pass_timing"] or {}
    row={"variant":variant,"backend":backend,"hints":hints,"workload":workload,
         "initial_reserved_mib":initial["allocator_reserved_bytes"]/MIB,
         "sampled_peak_reserved_mib":d["peak_allocator_reserved_bytes"]/MIB,
         "sampled_peak_live_mib":max(s["allocator_allocated_bytes"] for s in stages)/MIB,
         "sampled_peak_blocks":max(s["allocator_blocks"] for s in stages),
         "reserved_after_resources_mib":released["allocator_reserved_bytes"]/MIB,
         "live_after_resources_mib":released["allocator_allocated_bytes"]/MIB,
         "sampled_peak_dxgi_local_mib":max(s["dxgi_local_usage_bytes"] for s in stages)/MIB,
         "after_resources_dxgi_local_mib":released["dxgi_local_usage_bytes"]/MIB,
         "sampled_peak_private_commit_mib":d["peak_private_commit_bytes"]/MIB,
         "after_resources_private_commit_mib":released["private_commit_bytes"]/MIB,
         "after_resources_private_ws_mib":released["private_working_set_bytes"]/MIB,
         "device_create_us":d["device_create_us"],
         "creation_p50_us":timing.get("p50_us"),"creation_p99_us":timing.get("p99_us"),"creation_total_ms":timing.get("total_ms"),
         "gpu_pass_p50_us":gpu.get("p50_us"),"gpu_pass_p99_us":gpu.get("p99_us"),
         "process_cpu_ms":receipt["cpu_times"]["total_cpu_ms"],"wall_s":receipt["wall_s"]}
    groups[variant,backend,hints,workload].append(row)
rows=[]
for key,values in sorted(groups.items()):
    row=dict(zip(["variant","backend","hints","workload"],key));row["trials"]=len(values)
    for field in values[0]:
        if field in row:continue
        seq=[v[field] for v in values if v[field] is not None]
        row[field]=statistics.median(seq) if seq else None
        row[field+"_min"]=min(seq) if seq else None
        row[field+"_max"]=max(seq) if seq else None
    rows.append(row)
out={"processes":sum(len(v) for v in groups.values()),"failures":failures,"cells":rows,
     "stages":"Initial is 3_device_request. Resource-drop is 9_resources_dropped, or extended idle for idle runs. Peaks are stage samples."}
(H/"downstream-summary.json").write_text(json.dumps(out,indent=2))
with (H/"downstream-summary.csv").open("w",newline="") as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
lines=["# Integrated wgpu measurements","","Each row is the median of five standalone processes. Full trial ranges and OS/GPU metrics are in downstream-summary.csv. Reservation is sampled at harness stages; resource-drop reservation includes wgpu's remaining live internal allocations.",""]
for backend in ["dx12","vulkan"]:
    lines += [f"## {backend}","","| Hints and workload | Variant | Initial MiB | Peak reserved MiB | After resource drop MiB | CPU operation p50 us | CPU operation p99 us | Process CPU ms | Peak private commit MiB |","|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        if r["backend"]!=backend:continue
        num=lambda value:"" if value is None else f"{value:.2f}"
        lines.append(f"| {r['hints']} {r['workload']} | {r['variant']} | {num(r['initial_reserved_mib'])} | {num(r['sampled_peak_reserved_mib'])} | {num(r['reserved_after_resources_mib'])} | {num(r['creation_p50_us'])} | {num(r['creation_p99_us'])} | {num(r['process_cpu_ms'])} | {num(r['sampled_peak_private_commit_mib'])} |")
(H/"DOWNSTREAM_RESULTS.md").write_text("\n".join(lines),encoding="utf-8")
assert not failures,failures
print({"processes":out["processes"],"cells":len(rows),"failures":len(failures)})

