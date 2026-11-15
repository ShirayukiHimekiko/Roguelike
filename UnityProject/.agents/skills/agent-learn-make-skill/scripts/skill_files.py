"""Inspect actual Skill files or compare two payloads; never certify skill quality."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError:
    print(json.dumps(dict(files_passed=False, error='Missing dependency: PyYAML>=6. python -m pip install PyYAML')))
    raise SystemExit(2)


IGNORED_DIRS = {'.git', '.venv', '__pycache__', '.pytest_cache'}
IGNORED_SUFFIXES = {'.pyc', '.pyo'}
NONCLAIMS = ['File inspection does not certify knowledge, behavior, host discovery or permission.',
             'Only ordinary inline local Markdown links are checked; anchors, reference-style links and runtime dependencies require review.']


def payload(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Expected a Skill directory: ' + str(root))
    files = {}

    def walk_error(error):
        raise error  # Unreadable directories must not appear unchanged.

    for current, directories, names in os.walk(root, followlinks=False, onerror=walk_error):
        directories[:] = sorted(name for name in directories if name not in IGNORED_DIRS)
        for name in [*directories, *names]:
            path = Path(current) / name
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise ValueError('Skill payload escapes its root: ' + str(path))
            # Directory links/junctions are not enumerated by this inspector.
            if path.is_dir() and (path.is_symlink() or getattr(path, 'is_junction', lambda: False)()):
                raise ValueError('Linked payload directories are unsupported: ' + str(path))
        for name in sorted(names):
            path = Path(current) / name
            if path.suffix in IGNORED_SUFFIXES:
                continue
            if not path.is_file():
                raise ValueError('Expected a readable payload file: ' + str(path))
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            files[path.relative_to(root).as_posix()] = digest.hexdigest()
    return root, files


def frontmatter(root):
    text = (root / 'SKILL.md').read_text(encoding='utf-8-sig')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)', text, re.S)
    if not match:
        raise ValueError('SKILL.md needs YAML frontmatter with name and description')
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError('SKILL.md frontmatter must be a mapping')
    name, description = data.get('name'), data.get('description')
    if not isinstance(name, str) or len(name) >= 64 or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
        raise ValueError('Skill name must be lowercase hyphen-case and shorter than 64 characters')
    if not isinstance(description, str) or not description.strip():
        raise ValueError('Skill description must be a nonempty string')
    body = text[match.end():]
    if not body.strip():
        raise ValueError('SKILL.md body must contain actual instructions')
    return data, body


def prose_lines(text):
    """Exclude fenced examples; this is intentionally not a full Markdown parser."""
    marker, length = None, 0
    for line in text.splitlines():
        fence = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if fence:
            run, tail = fence.groups()
            if marker is None:
                marker, length = run[0], len(run)
            elif run[0] == marker and len(run) >= length and not tail.strip():
                marker = None
            continue
        if marker is None:
            # Inline code can contain illustrative links too.
            yield re.sub(r'(`+).*?\1', '', line)


def local_links(root, files):
    checked, issues = [], []
    for relative in files:
        if Path(relative).suffix.lower() != '.md':
            continue
        path = root / relative
        for line in prose_lines(path.read_text(encoding='utf-8-sig')):
            for match in re.finditer(
                    r'!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)'
                    r'(?:[ \t]+(?:"[^"\n]*"|\'[^\'\n]*\'|\([^\n)]*\)))?[ \t]*\)', line):
                raw = match.group(1).strip('<>')
                url = urlsplit(raw)
                if (re.match(r'^[A-Za-z]:', raw) or raw.startswith(('\\\\', '//'))
                        or url.scheme.lower() == 'file'):
                    issues.append(f'{relative}: {raw}: Absolute local links are not portable Skill payload references')
                    continue
                if url.scheme or url.netloc or not url.path:
                    continue
                try:
                    if '\\' in raw:
                        raise ValueError('Use / in links; backslashes only resolve on Windows')
                    target = (path.parent / unquote(url.path)).resolve(strict=True)
                    if not target.is_relative_to(root):
                        raise ValueError('Link escapes Skill root')
                    # 必须与载荷里实际路径逐字一致：Windows 上大小写不同也能打开，换到区分大小写的宿主就断；
                    # 指向被忽略目录（__pycache__ 等）的文件也不在载荷里
                    # Windows 的 resolve() 保留链接里写的大小写，所以按链接原文拼出相对路径再逐字比对
                    key = os.path.normpath(os.path.join(os.path.dirname(relative), unquote(url.path))).replace(os.sep, '/')
                    if key not in ('.', '') and key not in files and not any(f.startswith(key.rstrip('/') + '/') for f in files):
                        raise ValueError('Link target is not in the Skill payload with this exact path/case')
                    if target.is_file():
                        with target.open('rb') as stream:
                            stream.read(1)
                    elif not target.is_dir():
                        raise ValueError('Link does not identify a file or directory')
                    checked.append(dict(source=relative, target=raw))
                except (OSError, ValueError) as error:
                    issues.append(f'{relative}: {raw}: {error}')
    return checked, issues


def inspect(root):
    root, files = payload(root)
    metadata, _ = frontmatter(root)
    links, issues = local_links(root, files)
    if metadata['name'] != root.name:
        issues.append('Directory name must match frontmatter name: ' + metadata['name'])
    return dict(files_passed=not issues, name=metadata['name'], files=files,
                checked_local_links=links, issues=issues, nonclaims=NONCLAIMS)


def compare(old_root, new_root):
    old_root, old = payload(old_root)
    new_root, new = payload(new_root)
    old_meta, _ = frontmatter(old_root)
    new_meta, _ = frontmatter(new_root)
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    changed = sorted(name for name in old.keys() & new.keys() if old[name] != new[name])
    def version(metadata):
        value = metadata.get('metadata')
        value = value.get('version') if isinstance(value, dict) else None
        return str(value) if value is not None else None
    old_version, new_version = version(old_meta), version(new_meta)
    return dict(review_required=bool(added or removed or changed), added=added, removed=removed, changed=changed,
                old_name=old_meta['name'], new_name=new_meta['name'], old_version=old_version, new_version=new_version,
                applied=False, nonclaims=[*NONCLAIMS, 'Differences require human/agent review; no automatic version, compatibility or adoption decision.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inspect').add_argument('skill')
    diff = commands.add_parser('compare')
    diff.add_argument('old'); diff.add_argument('new')
    args = parser.parse_args()
    try:
        if args.command == 'inspect':
            report = inspect(args.skill)
            code = 0 if report['files_passed'] else 2
        else:
            report = compare(args.old, args.new)
            code = 3 if report['review_required'] else 0
    except (OSError, ValueError, UnicodeError, yaml.YAMLError, RecursionError) as error:
        report, code = dict(files_passed=False, error=str(error) or type(error).__name__, nonclaims=NONCLAIMS), 2
        if args.command == 'compare':
            report['review_required'] = True
    # stdout 用 ASCII 转义：任何控制台编码下都能按 UTF-8/GBK 解析出同一份 JSON（json.loads 结果不变）
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
