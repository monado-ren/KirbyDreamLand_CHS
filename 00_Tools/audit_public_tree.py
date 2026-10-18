# SPDX-License-Identifier: MIT
"""Read-only audit of files proposed for the public patch/source repository.

With Git available, inspect tracked plus unignored untracked files. --tracked
restricts the audit to the actual index, including mistakenly tracked ignored
files. This is a release check, not a general-purpose secret detector.
"""
from __future__ import annotations

import argparse
import ast
import base64
import fnmatch
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {
    '.gb', '.gbc', '.gba', '.sna', '.sav', '.state', '.dem',
    '.exe', '.dll', '.so', '.dylib', '.pyc', '.pyd',
    '.psd', '.7z', '.rar', '.zip', '.xlsx', '.xls', '.ttf', '.otf', '.bdf',
}
FORBIDDEN_PARTS = {'.vendor', '.venv', 'venv', 'node_modules', '__pycache__',
                   'roms', 'reports', 'exports', 'references'}
PRIVATE_PATH = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/(?:Users|home)/[^/\s]+/')
EMAIL = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I)
SECRETS = (
    re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{50,}'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{32,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
)
# Public Game Boy boot-logo signature: used only to detect a complete cartridge
# header in disguised binaries or encoded JSON, not to construct a game ROM.
GB_LOGO = bytes.fromhex(
    'ce ed 66 66 cc 0d 00 0b 03 73 00 83 00 0c 00 0d '
    '00 08 11 1f 88 89 00 0e dc cc 6e e6 dd dd d9 99 '
    'bb bb 67 63 6e 0e ec cc dd dc 99 9f bb b9 33 3e')
PRIVATE_IMPORT = re.compile(r'^(?:localize_jp|probe_jp|capture_runtime|bgb_state|rom_project|make_bgb|migrate_jp)')


def read_ignore(root: Path) -> list[str]:
    path = root / '.gitignore'
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def is_ignored(name: str, patterns: list[str]) -> bool:
    """Fallback for a non-Git source export; Git itself is used when available."""
    ignored = False
    for item in patterns:
        negate = item.startswith('!')
        pattern = item[1:] if negate else item
        pattern = pattern.lstrip('/')
        if pattern.endswith('/'):
            prefix = pattern.rstrip('/')
            match = name == prefix or name.startswith(prefix + '/') or prefix in name.split('/')[:-1]
        elif '/' in pattern:
            match = fnmatch.fnmatchcase(name, pattern)
        else:
            match = any(fnmatch.fnmatchcase(part, pattern) for part in name.split('/'))
        if match:
            ignored = not negate
    return ignored


def public_paths(root: Path, tracked: bool = False) -> tuple[list[Path], str]:
    try:
        # Git for MSYS can spell the root differently from native Windows Python.
        # At a worktree root the prefix is empty; this avoids comparing absolute
        # path strings from two different path namespaces.
        probe = subprocess.run(['git', '-C', str(root), 'rev-parse',
                                '--is-inside-work-tree', '--show-prefix'],
                               capture_output=True, text=True, check=False)
        own_repo = probe.returncode == 0 and probe.stdout.strip() == 'true'
        if own_repo:
            args = ['git', '-C', str(root), 'ls-files', '-z', '--cached']
            if not tracked:
                args.extend(['--others', '--exclude-standard'])
            result = subprocess.run(args, capture_output=True, check=True)
            names = sorted(set(result.stdout.decode('utf-8').split('\0')) - {''})
            return [root / name for name in names], 'git-index' if tracked else 'git-public-candidates'
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    if tracked:
        raise ValueError('--tracked requires a Git repository at the specified root')
    patterns = read_ignore(root)
    paths = [path for path in root.rglob('*') if path.is_file()
             and '.git' not in path.relative_to(root).parts
             and not is_ignored(path.relative_to(root).as_posix(), patterns)]
    return sorted(paths), 'source-export'


def contains_rom(data: bytes) -> bool:
    """Detect a cartridge header even when prepended/appended to another file."""
    at = data.find(GB_LOGO)
    while at >= 0:
        start = at - 0x104
        if start >= 0 and len(data) >= start + 0x150:
            title = data[start + 0x134:start + 0x144]
            if all(value == 0 or 32 <= value <= 126 for value in title):
                return True
        at = data.find(GB_LOGO, at + 1)
    return False


def encoded_rom(value: object) -> bool:
    if isinstance(value, dict):
        return any(encoded_rom(v) for v in value.values())
    if isinstance(value, list):
        if len(value) >= 0x150 and all(type(v) is int and 0 <= v <= 255 for v in value):
            return contains_rom(bytes(value))
        return any(encoded_rom(v) for v in value)
    if not isinstance(value, str) or not 448 <= len(value) <= 16 * 1024 * 1024:
        return False
    compact = ''.join(value.split())
    if len(compact) % 2 == 0 and re.fullmatch('[0-9a-fA-F]+', compact):
        if contains_rom(bytes.fromhex(compact)):
            return True
    try:
        return contains_rom(base64.b64decode(compact, validate=True))
    except (ValueError, base64.binascii.Error):
        return False


def is_runtime(data: bytes) -> bool:
    if data.startswith(b'\x7fELF'):
        return True
    if data.startswith(b'MZ') and len(data) >= 64:
        offset = struct.unpack_from('<I', data, 60)[0]
        return data[offset:offset + 4] == b'PE\0\0'
    return data.startswith((b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf'))


def audit_tree(root: Path, paths: list[Path] | None = None, tracked: bool = False) -> dict:
    root = root.resolve()
    selected, selection = public_paths(root, tracked) if paths is None else (paths, 'explicit')
    findings: list[dict[str, str]] = []
    def issue(name: str, rule: str) -> None:
        findings.append({'path': name, 'rule': rule})
    for path in selected:
        try:
            name = path.relative_to(root).as_posix()
        except ValueError:
            issue('<outside-root>', 'PATH_OUTSIDE_ROOT')
            continue
        if path.is_symlink():
            issue(name, 'SYMLINK_NOT_ALLOWED')
            continue
        if not path.is_file():
            issue(name, 'MISSING_TRACKED_FILE')
            continue
        parts = {part.lower() for part in Path(name).parts}
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            issue(name, 'FORBIDDEN_FILE_TYPE')
        if parts & FORBIDDEN_PARTS:
            issue(name, 'PRIVATE_OR_RUNTIME_DIRECTORY')
        data = path.read_bytes()
        if contains_rom(data):
            issue(name, 'CARTRIDGE_HEADER_IN_CONTENT')
        if is_runtime(data):
            issue(name, 'EXECUTABLE_RUNTIME_IN_CONTENT')
        try:
            text = data.decode('utf-8-sig')
        except UnicodeError:
            continue
        if PRIVATE_PATH.search(text):
            issue(name, 'ABSOLUTE_PRIVATE_PATH')
        if any(pattern.search(text) for pattern in SECRETS):
            issue(name, 'SECRET_PATTERN')
        # Keep upstream author/contact notices verbatim under licenses/.
        if not name.lower().startswith('licenses/') and EMAIL.search(text):
            issue(name, 'EMAIL_OUTSIDE_LICENSE_NOTICE')
        if path.suffix.lower() == '.json':
            try:
                if encoded_rom(json.loads(text)):
                    issue(name, 'ENCODED_CARTRIDGE_HEADER')
            except (ValueError, RecursionError):
                issue(name, 'INVALID_JSON')
        if path.suffix.lower() == '.py':
            try:
                tree = ast.parse(text)
                modules = [alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names]
                modules += [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
                if any(PRIVATE_IMPORT.match(module) for module in modules):
                    issue(name, 'PRIVATE_PROJECT_IMPORT')
            except SyntaxError:
                issue(name, 'INVALID_PYTHON')
    return {'status': 'PASS' if not findings else 'FAIL', 'selection': selection,
            'files_checked': len(selected), 'findings': findings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--tracked', action='store_true')
    args = parser.parse_args()
    try:
        result = audit_tree(args.root, tracked=args.tracked)
    except ValueError as exc:
        print(f'AUDIT=FAIL {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
