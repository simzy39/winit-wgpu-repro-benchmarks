import pathlib,json
H=pathlib.Path(__file__).resolve().parent
out=H/"historical-reanalysis"
(out/"results").mkdir(parents=True,exist_ok=True)
code=(H.parent/"analyze_matrix.py").read_text()
code=code.replace('RAW = os.path.join(HERE, "results", "raw")',f'RAW = {str(H.parent/"results/raw")!r}')
exec(compile(code,str(out/"analyze_matrix.py"),"exec"),{"__file__":str(out/"analyze_matrix.py"),"__name__":"__main__"})
new=json.loads((out/"results/summary.json").read_text())
old=json.loads((H.parent/"results/summary.json").read_text())
check={"historical_summary_identical":new==old,"pairwise_comparisons":new["pairwise_comparisons"],
       "nondeterministic":new["nondeterministic"],"mismatches":new["proto_vs_pr323_mismatches"]}
(H/"historical-reanalysis/verification.json").write_text(json.dumps(check,indent=2))
assert new==old
print(check)

