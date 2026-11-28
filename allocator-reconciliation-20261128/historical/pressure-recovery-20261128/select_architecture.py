import pathlib,json,hashlib,datetime
H=pathlib.Path(__file__).resolve().parent
assert (H/'FINAL_PAIR_COMPLETE').exists() and (H/'FINAL_SOURCE_CHECKS_COMPLETE').exists()
data=json.loads((H/'direct-summary.json').read_text());assert data['processes']==210 and not data['nondeterministic']
pair=json.loads((H/'final-pair-summary.json').read_text());assert pair['processes']==60 and not pair['nondeterministic']
assert all(r['rc']==0 for r in json.loads((H/'final-source-checks.json').read_text()))
record={'selected':'recovery','cache_selection':'largest eligible empty block, at most one per type and min(2*min,max)','aggregate_bound':'Vulkan: empty caches per physical heap <= declared heap size; explicit application scalar budget through trim_to','placement_order':'existing reverse slot order retained','growth':'occupied shared blocks, excluding empty cache','recovery':'cause-sensitive, existing compatible Vulkan reuse, cache reclamation/retry, one minimum-size fallback per type; Metal commits pending residency removals','alternatives':data['comparisons'],'reason':'Smallest-cache reduces retention but increases churn; aggressive derived aggregate cap can increase peak and creation count; packed placement showed no plan benefit. Preserve simple bounded default and explicit application control.','final_source_checks':'final-source-checks.json','final_pair':'final-pair-summary.json','utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(H/'ARCHITECTURE_SELECTED.json').write_text(json.dumps(record,indent=2))
print('Selected final recovery architecture; downstream isolated builds may proceed')
