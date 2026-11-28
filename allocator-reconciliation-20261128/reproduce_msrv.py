"""Re-run a preserved compiler consumer with a local allocator checkout."""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parent
    fixtures = root / 'final-source/checks/msrv'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--fixture', required=True,
                        choices=sorted(p.name for p in fixtures.iterdir() if p.is_dir()))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    assert not subprocess.check_output(
        ['git', 'status', '--porcelain', '--untracked-files=no'], cwd=source
    ), 'Use a clean committed allocator checkout'
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    fixture = fixtures / args.fixture
    manifest = (fixture / 'Cargo.toml').read_text()
    manifest, count = re.subn(r'path="[^"]+"',
                             'path=' + json.dumps(source.as_posix()), manifest)
    assert count == 1, 'Expected exactly one allocator path'
    (destination / 'Cargo.toml').write_text(manifest)
    shutil.copyfile(fixture / 'Cargo.lock', destination / 'Cargo.lock')
    shutil.copytree(fixture / 'src', destination / 'src')
    toolchain = '1.81.0' if 'nostd' in args.fixture else '1.71.0'
    environment = os.environ.copy()
    environment['CARGO_TARGET_DIR'] = str(destination / 'target')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    command = ['cargo', '+' + toolchain, 'check', '--locked', '--lib']
    result = subprocess.run(command, cwd=destination, env=environment)
    (destination / 'receipt.json').write_text(json.dumps(
        {'fixture': args.fixture, 'source_head': head, 'command': command,
         'return_code': result.returncode}, indent=2))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
