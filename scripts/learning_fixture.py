"""Fixed local learning-cycle inputs shared by controlled and native acceptance."""
BROKEN = 'def total(values):\n    return len(values)\n'
CORRECT = 'def total(values):\n    return sum(values)\n'
ITERATOR_BUG = 'def total(values):\n    return sum(values) if isinstance(values, list) else 0\n'
BASE = '# 项目审查\n\n审查约定：尚无。\n'
RULE = '核对整数求和时使用独立字面量样例，注明观察范围。'
FINAL = BASE.replace('尚无。', RULE)
UNIT = ('import unittest\nfrom total import total\nclass Totals(unittest.TestCase):\n'
        '    def test_literals(self):\n        self.assertEqual(total([2,3]),5)\n'
        '        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n')
IMPROVED = UNIT + '\n    def test_generator(self):\n        self.assertEqual(total(iter([5,-2])),3)\n'
GUARD = '''import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ORIGINAL = __ORIGINAL__
VARIANTS = __VARIANTS__

def literals(tree):
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Totals')
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'test_literals')

def main():
    root = Path(__file__).resolve().parent
    candidate = (root / 'test_total.py').read_text()
    preserved = ast.dump(literals(ast.parse(candidate))) == ast.dump(literals(ast.parse(ORIGINAL)))
    if not preserved:
        print(json.dumps({'passed': False, 'original_literals_preserved': False}))
        return 1
    directory = root / '.evolve-local' / 'guard-labs'
    directory.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, source in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix=name+'-', dir=directory) as place:
            target = Path(place)
            (target / 'total.py').write_text(source)
            (target / 'test_total.py').write_text(candidate)
            observed = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_total', '-v'],
                cwd=target, capture_output=True, text=True, timeout=10)
            results[name] = {'returncode': observed.returncode, 'stdout': observed.stdout, 'stderr': observed.stderr}
    passed = results['correct']['returncode'] == 0 and all(results[k]['returncode'] != 0 for k in ('count', 'iterator_zero'))
    print(json.dumps({'passed': passed, 'original_literals_preserved': True, 'variants': results}))
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
'''.replace('__ORIGINAL__', repr(UNIT)).replace('__VARIANTS__', repr({
    'correct': CORRECT, 'count': BROKEN, 'iterator_zero': ITERATOR_BUG}))
FILES = {'total.py': BROKEN, 'test_total.py': UNIT, 'guide.md': BASE, 'guard.py': GUARD}
CHECKS = [{'id': 'unit', 'argv': ['python3', '-B', '-m', 'unittest', 'test_total', '-v'], 'cwd': '.', 'timeout': 15},
          {'id': 'guard', 'argv': ['python3', '-B', 'guard.py'], 'cwd': '.', 'timeout': 40}]
