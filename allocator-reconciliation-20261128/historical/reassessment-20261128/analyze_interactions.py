"""Paired allocator effects and non-additivity of the independent wgpu patches."""
import pathlib, json, collections, statistics, csv
H = pathlib.Path(__file__).resolve().parent
assert (H / "DOWNSTREAM_COMPLETE").exists()
raw = {}
for path in (H / "results-downstream").glob("*.receipt.json"):
    stem = path.name.removesuffix(".receipt.json")
    variant, backend, hints, workload, trial = stem.split("__")
    receipt = json.loads(path.read_text())
    assert receipt["rc"] == 0 and not receipt["validation_error"]
    d = json.loads(path.with_name(stem + ".json").read_text())
    stages = {s["stage"]: s for s in d["stages"]}
    final = stages.get("9_resources_dropped", stages.get("10_extended_idle", stages["3_device_request"]))
    raw[variant, backend, hints, workload, trial] = {
        "initial_mib": stages["3_device_request"]["allocator_reserved_bytes"] / 1048576,
        "peak_mib": d["peak_allocator_reserved_bytes"] / 1048576,
        "after_resources_mib": final["allocator_reserved_bytes"] / 1048576,
        "cpu_op_p99_us": (d["cpu_op_timing"] or {}).get("p99_us"),
        "process_cpu_ms": receipt["cpu_times"]["total_cpu_ms"]}
groups = collections.defaultdict(list)
for (variant, backend, hints, workload, trial), values in raw.items():
    if variant.startswith("cache2-"):
        baseline = raw["pr323-" + variant.split("-", 1)[1], backend, hints, workload, trial]
        for metric, value in values.items():
            if value is not None:
                groups["cache2_minus_pr323", backend, hints, workload, variant.split("-", 1)[1], metric].append(value - baseline[metric])
    if backend == "dx12" and variant.endswith("-trunk") and variant.split("-", 1)[0] in {"pr323", "cache2"}:
        allocator = variant.split("-", 1)[0]
        states = {s: raw[allocator + "-" + s, backend, hints, workload, trial] for s in ["trunk", "lazy", "transient", "both"]}
        for metric, value in values.items():
            if value is not None:
                interaction = states["both"][metric] - states["lazy"][metric] - states["transient"][metric] + value
                groups["both_minus_lazy_minus_transient_plus_trunk", backend, hints, workload, allocator, metric].append(interaction)
rows = []
for key, values in sorted(groups.items()):
    row = dict(zip(["effect", "backend", "hints", "workload", "state_or_allocator", "metric"], key))
    row.update(trials=len(values), median=statistics.median(values), minimum=min(values), maximum=max(values), paired_values=values)
    rows.append(row)
(H / "downstream-interactions.json").write_text(json.dumps({"cells": rows, "interpretation": "Paired arithmetic differences, not a statistical significance test. Positive reservation interaction represents overlapping independent savings."}, indent=2))
with (H / "downstream-interactions.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
print("Paired interaction summaries:", len(rows))
