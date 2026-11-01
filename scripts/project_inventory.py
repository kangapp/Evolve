#!/usr/bin/env python3
"""Generate the actual maintained source tree and complete runtime-package tree."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / 'docs/project-layout.md'
INDEX = ROOT / 'engineering-file-manifest.json'
EXCLUDED_PARTS = {'.git', '__pycache__', '.pytest_cache', '.venv', 'venv', 'node_modules', 'dist', '.evolve-local'}


def source_paths():
    return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
        if p.is_file() and not p.is_symlink() and not (set(p.relative_to(ROOT).parts) & EXCLUDED_PARTS)
        and p.relative_to(ROOT).parts[:2] != ('docs', 'spec')
        and p != INDEX and p.name != '.DS_Store' and p.suffix not in ('.pyc', '.pyo'))


def tree(names):
    branches = {}
    for name in names:
        node = branches
        for part in Path(name).parts:
            node = node.setdefault(part, {})
    lines = ['evolve/']
    def visit(node, prefix='', parent=''):
        items = sorted(node.items(), key=lambda pair: (not bool(pair[1]), pair[0]))
        for i, (name, children) in enumerate(items):
            last = i == len(items) - 1
            relative = parent + name
            directory = bool(children) or (ROOT / relative).is_dir()
            lines.append(prefix + ('└── ' if last else '├── ') + name + ('/' if directory else ''))
            if children:
                visit(children, prefix + ('    ' if last else '│   '), relative + '/')
    visit(branches)
    return '\n'.join(lines)


def document(paths, package):
    source_names = paths
    runtime = sorted(package['files']) + ['evolve-package.json']
    return ('# 实际工程目录\n\n版本 ' + package['package_version'] + '，protocol ' + str(package['protocol_version'])
        + '／schema ' + str(package['schema_version']) + '。本页由当前源码和运行包清单生成。\n\n'
        '<!-- source-only -->\n## 源码工程\n\n维护文件共 ' + str(len(paths)) + ' 份；完整路径、字节数和摘要见[工程文件清单](../engineering-file-manifest.json)。'
        '源码、当前文档、测试及开发工具纳入维护清单；缓存、临时项目和构建输出不计入。\n\n```text\n'
        + tree(source_names) + '\n```\n<!-- /source-only -->\n\n## 独立运行包\n\n'
        '完整运行包含 ' + str(len(package['files'])) + ' 份运行资源及 evolve-package.json 自身。实际资源摘要以'
        '[包清单](../evolve-package.json)为准；目录可整体安装、移动并离线定位资源。以下各路径在工程中有真实文件，构建时只复制这些资源。\n\n```text\n'
        + tree(runtime) + '\n```\n\n'
        '运行包保留八 Skill、单份 shared／runtime、模板、宿主与市场清单、许可／来源说明及本版本离线指南。'
        '源码 tests、开发控制器、用户数据不进入运行包。目标项目的 evolve/／.evolve-local/ 是工作资料，不放进插件目录。\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    package = json.loads((ROOT / 'evolve-package.json').read_text())
    paths = source_paths()
    expected = document(paths, package)
    if args.write:
        LAYOUT.write_text(expected)
        # Refresh after generating the layout; the index deliberately excludes itself.
        rows = [{'path': name, 'bytes': (ROOT / name).stat().st_size,
                 'sha256': hashlib.sha256((ROOT / name).read_bytes()).hexdigest()} for name in paths]
        INDEX.write_text(json.dumps({'package_version': package['package_version'], 'purpose': 'actual-maintained-engineering-files-not-runtime-package',
            'excluded': ['itself', 'local caches and temporary/build outputs'], 'files': rows}, ensure_ascii=False, indent=2) + '\n')
    else:
        if LAYOUT.read_text() != expected:
            parser.error('Actual layout is stale; regenerate from the current files')
        value = json.loads(INDEX.read_text())
        if value['package_version'] != package['package_version'] or [r['path'] for r in value['files']] != paths:
            parser.error('Engineering file collection changed')
        for row in value['files']:
            path = ROOT / row['path']
            if row['bytes'] != path.stat().st_size or row['sha256'] != hashlib.sha256(path.read_bytes()).hexdigest():
                parser.error('Engineering file digest changed: ' + row['path'])
    print(json.dumps({'source_files': len(paths), 'runtime_resources': len(package['files']), 'mode': 'write' if args.write else 'check'}))

if __name__ == '__main__':
    main()
