import glob
import json
import os
import sys

def mib(b):
    return b / (1024.0 * 1024.0)

def load_dir(d):
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["_file"] = os.path.basename(p)
            rows.append(data)
    return rows

def summarize_stage_alloc(s):
    if not s:
        return "n/a"
    blocks = s.get("allocator_blocks", 0)
    sizes = sorted([mib(x) for x in s.get("allocator_block_sizes", [])], reverse=True)
    allocs = s.get("allocator_allocations", 0)
    res = s.get("allocator_reserved_bytes", 0)
    used = s.get("allocator_allocated_bytes", 0)
    util = s.get("allocator_utilization_pct", 0.0)
    top = ",".join(f"{x:.1f}" for x in sizes[:6])
    if len(sizes) > 6:
        top += f",..(+{len(sizes)-6})"
    return f"blk={blocks} alloc={allocs} res={mib(res):.1f}M used={mib(used):.1f}M util={util:.1f}% [{top}]"

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    rows = load_dir(d)
    print(f"Loaded {len(rows)} JSON reports from {d}\n")
    seen = set()
    print("Adapters:")
    for r in rows:
        key = (r.get("backend"), r.get("adapter_name"), r.get("adapter_device_type"), r.get("adapter_driver"), r.get("adapter_driver_info"))
        if key not in seen:
            seen.add(key)
            print(f"  {key}")
    print()

    by_wl = {}
    for r in rows:
        by_wl.setdefault((r.get("workload"), r.get("backend")), []).append(r)

    for (wl, be), items in sorted(by_wl.items()):
        print(f"=== WORKLOAD: {wl} | BACKEND: {be} ===")
        hdr = f"{'hints':<18} {'dev_ms':>7} {'devPWS':>7} {'devCom':>7} {'pkPWS':>7} {'pkCom':>7} {'dxgiPk':>7} {'relCom':>7} {'dxgiRl':>7} {'cpu50':>8} {'cpu99':>8} {'gpu50':>7} | peak_allocator"
        print(hdr)
        print("-" * len(hdr))
        for r in sorted(items, key=lambda x: x.get("hints", "")):
            stages = r.get("stages", [])
            by_name = {s["stage"]: s for s in stages}
            dev = by_name.get("3_device_request", {})
            # find peak stage by allocator_reserved_bytes then dxgi_local_usage_bytes
            active_stages = [s for s in stages if not s["stage"].startswith(("0_", "1_", "2_", "11_"))]
            peak = max(active_stages, key=lambda s: (s.get("allocator_reserved_bytes", 0), s.get("allocator_allocated_bytes", 0), s.get("dxgi_local_usage_bytes", 0))) if active_stages else dev
            rel = by_name.get("10_extended_idle", by_name.get("9_after_release", peak))

            dev_ms = r.get("device_create_us", 0.0) / 1000.0
            cpu = r.get("cpu_op_timing") or {}
            gpu = r.get("gpu_pass_timing") or {}
            cpu50 = cpu.get("p50_us", 0.0)
            cpu99 = cpu.get("p99_us", 0.0)
            gpu50 = gpu.get("p50_us", 0.0)

            print(
                f"{r.get('hints',''):<18} {dev_ms:7.1f} "
                f"{mib(dev.get('private_working_set_bytes',0)):7.1f} "
                f"{mib(dev.get('private_commit_bytes',0)):7.1f} "
                f"{mib(peak.get('private_working_set_bytes',0)):7.1f} "
                f"{mib(r.get('peak_private_commit_bytes',0)):7.1f} "
                f"{mib(peak.get('dxgi_local_usage_bytes',0)):7.1f} "
                f"{mib(rel.get('private_commit_bytes',0)):7.1f} "
                f"{mib(rel.get('dxgi_local_usage_bytes',0)):7.1f} "
                f"{cpu50:8.1f} {cpu99:8.1f} {gpu50:7.1f} | {summarize_stage_alloc(peak)}"
            )
            if wl in ("idle", "small_gui", "large_alloc", "large_textures", "churn"):
                print(f"    @dev : {summarize_stage_alloc(dev)}  |  @idle: {summarize_stage_alloc(rel)}")
        print()

if __name__ == "__main__":
    main()
