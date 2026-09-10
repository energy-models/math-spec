# SPDX-FileCopyrightText: math-spec Contributors
#
# SPDX-License-Identifier: MIT

"""Load every model in `models/` and every probe in `probes/` on all three branches.

Each proposal is a branch with its own `lookups:` schema, so each model is loaded
in a child interpreter whose `PYTHONPATH` points at that branch's `src/`. The
output is `evidence.json`: what loaded, the frame the loader reported for every
constraint, the math the typesetter printed, and the message behind every
refusal. `build.py` reads it, and nothing in the page is written by hand.

    python comparison/verify.py [--keep]

`--keep` leaves the worktrees in place. Run it from the repository root, with an
interpreter that has this package's runtime dependencies installed.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

#: A proposal, and the branch its pull request is open on.
BRANCHES = {
    'per': 'claude/lookup-per-keyword-vhvfjd',
    'keys': 'claude/lookup-keys-vhvfjd',
    'relations': 'claude/lookup-relations-vhvfjd',
}

HERE = Path(__file__).parent
ROOT = HERE.parent


def git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def load(worktree: Path, model: Path) -> dict:
    """Load *model* under *worktree*'s `src/`, and return what `_load.py` reported."""
    done = subprocess.run(
        [sys.executable, str(HERE / '_load.py'), str(model)],
        env={'PYTHONPATH': str(worktree / 'src'), 'PATH': '/usr/bin:/bin'},
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise RuntimeError(f'{model} on {worktree.name}: {done.stderr[-2000:]}')
    return json.loads(done.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--keep', action='store_true', help='leave the worktrees in place')
    keep = parser.parse_args().keep

    git('fetch', 'origin', *BRANCHES.values())
    root = Path(tempfile.mkdtemp(prefix='math-spec-proposals-'))
    evidence: dict = {'branches': {}, 'models': {}, 'probes': {}}
    try:
        trees = {}
        for proposal, branch in BRANCHES.items():
            tree = root / proposal
            git('worktree', 'add', '--detach', str(tree), f'origin/{branch}')
            trees[proposal] = tree
            evidence['branches'][proposal] = {
                'branch': branch,
                'sha': git('rev-parse', '--short', f'origin/{branch}'),
            }
        evidence['base'] = git('rev-parse', '--short', 'origin/main')

        for model in sorted(HERE.glob('models/*/*.yaml')):
            proposal = model.stem
            record = load(trees[proposal], model)
            record['yaml'] = model.read_text()
            evidence['models'][f'{model.parent.name}/{proposal}'] = record

        for probe in sorted(HERE.glob('probes/*.yaml')):
            evidence['probes'][probe.stem] = {
                'yaml': probe.read_text(),
                'by': {proposal: load(tree, probe) for proposal, tree in trees.items()},
            }
    finally:
        if not keep:
            for tree in root.glob('*'):
                git('worktree', 'remove', '--force', str(tree))
            shutil.rmtree(root, ignore_errors=True)

    (HERE / 'evidence.json').write_text(json.dumps(evidence, indent=1) + '\n')
    refused = [name for name, rec in evidence['models'].items() if not rec['ok']]
    print(f'{len(evidence["models"])} models loaded, {len(refused)} refused: {refused}')


if __name__ == '__main__':
    main()
