#!/usr/bin/env python3
"""Check current Markdown navigation and machine-readable examples."""
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def prose(text, errors, name):
    lines, block, language, marker = [], [], None, None
    for line in text.splitlines():
        fence = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if fence and marker is None:
            marker, language = fence[1], fence[2].strip()
            block = []
        elif fence and fence[1][0] == marker[0] and len(fence[1]) >= len(marker):
            try:
                if language == 'json':
                    json.loads('\n'.join(block))
                elif language == 'toml':
                    tomllib.loads('\n'.join(block))
            except ValueError as error:
                errors.append(f'{name}: invalid {language} example: {error}')
            marker = None
        elif marker is None:
            lines.append(line)
        else:
            block.append(line)
    if marker:
        errors.append(f'{name}: unclosed code fence')
    return '\n'.join(lines)


def anchors(text):
    result = set(re.findall(r'<a\s+id=[\"\']([^\"\']+)[\"\']', text))
    seen = {}
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, re.M):
        heading = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', heading)
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug + (f'-{count}' if count else ''))
    return result


def check(root):
    root = root.resolve()
    paths = set(root.glob('*.md'))
    for pattern in ('docs/**/*.md', 'shared/**/*.md', 'skills/**/SKILL.md', 'tests/fixtures/README.md'):
        paths.update(root.glob(pattern))
    paths = {path for path in paths if path.relative_to(root).parts[:2] != ('docs', 'spec')}
    errors, texts = [], {}
    for path in sorted(paths):
        name = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        if '\ufffd' in text:
            errors.append(f'{name}: replacement character')
        markers = re.findall(r'<!-- (/?)source-only -->', text)
        if markers != ['', '/'] * (len(markers) // 2):
            errors.append(f'{name}: unbalanced source-only markers')
        texts[path.resolve()] = prose(text, errors, name)
    links = 0
    for path, text in texts.items():
        for link in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', text):
            link = link.strip().strip('<>')
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                continue
            links += 1
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            label = f'{path.relative_to(root)}: {link}'
            if not target.is_relative_to(root) or not target.exists():
                errors.append(label + ': missing or outside project')
            elif parsed.fragment and target in texts and unquote(parsed.fragment) not in anchors(texts[target]):
                errors.append(label + ': missing anchor')
    return {'documents': len(paths), 'local_links': links, 'errors': errors}


if __name__ == '__main__':
    result = check(ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['errors']))
