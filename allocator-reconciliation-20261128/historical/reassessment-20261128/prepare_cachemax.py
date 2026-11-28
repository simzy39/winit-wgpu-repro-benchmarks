"""Focused experiment: one empty block up to max, compared with cache2's one-step limit."""
import pathlib,subprocess,shutil
H=pathlib.Path(__file__).resolve().parent
assert (H/"DIRECT_COMPLETE").exists(), "Complete the main latency suite before compiling the follow-up"
folder=H/"work/cachemax";repo=folder/"gpu-allocator"
if repo.exists():raise SystemExit("Preserving existing cachemax worktree")
folder.mkdir(parents=True)
subprocess.run(["git","-C",str(H.parent/"repo"),"worktree","add","--detach",str(repo),"179ea43"],check=True)
shutil.copytree(H/"work/cache2/gpu-allocator/src",repo/"src",dirs_exist_ok=True)
p=repo/"src/lib.rs"
s=p.read_text().replace("size <= self.min.saturating_mul(2).min(self.max)","size <= self.max")
s=s.replace("/// Keep the largest empty block within one growth step of the configured minimum.",
            "/// Experiment: keep the largest empty block through the configured maximum.")
s=s.replace("/// remain in use. Its size is limited to the smaller of twice the minimum and the\n/// maximum block size.",
            "/// remain in use. This experiment allows the cached block to reach the maximum block size.")
s=s.replace("assert!(!range.should_cache_empty_block(16 * MB + 1, None));",
            "assert!(!range.should_cache_empty_block(64 * MB + 1, None));")
p.write_text(s)
p=repo/"src/vulkan/capacity_tests.rs"
s=p.read_text().replace("assert!(size <= 16 * MIB);","assert!(size <= 64 * MIB);")
s=s.replace("allocator.free(allocation).unwrap();\n    assert_eq!(allocator.capacity(), 0);\n}",
            "allocator.free(allocation).unwrap();\n    assert_eq!(allocator.capacity(), 214 * MIB);\n}")
p.write_text(s)
(folder/"Cargo.toml").write_text('[workspace]\nmembers=["gpu-allocator","bench"]\nresolver="2"\n')
shutil.copytree(H/"work/cache2/bench",folder/"bench")
shutil.copyfile(H/"work/cache2/Cargo.lock",folder/"Cargo.lock")
target=(H/"target-cachemax").resolve()
assert target.parent==H.resolve()
shutil.copytree(H/"target-cache2",target)
p=subprocess.run(["cargo","clean","--target-dir",str(target),"-p","gpu-allocator","-p","gpua-policy-bench"],cwd=folder,capture_output=True,text=True,check=True)
(H/"logs/cachemax-seed-clean.log").write_text(p.stdout+p.stderr)
print("Prepared cachemax experiment; default and Performance policies are mathematically identical to cache2")

