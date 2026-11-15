"""Validate current files and tests; never accept fingerprints, install or certify semantics."""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import html
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import unquote, urlsplit
import unittest


NAME = "es-acceptance-jury"
CORE_FILES = tuple('scripts/' + name + '.py' for name in ('jury_candidates','jury_read','jury_review_roles','jury_session','validate_package'))
INTEGRITY_TEST_MODULE = 'test_current_workflow'
REQUIRED_FILES = ('SKILL.md','README.md','package-info.json','agents/openai.yaml',*CORE_FILES,
 'scripts/test_current_workflow.py','scripts/candidate-routing.json','references/candidate-mechanism.md',
 'references/progress-correctness.md','references/architecture-ecology-playability.md',
 'references/review-standard.md','references/coordination.md')
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".ps1", ".toml"}
MAX_FILES = 256
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 1024
MAX_DEPTH = 16
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MANIFEST_FILE = "package-info.json"
METADATA_FIELDS = {"schemaVersion", "name", "version", "python", "dependencies", "sourceFiles"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON value: " + value)


def _manifest_path(relative):
    """Validate literal portable paths; never resolve manifest-controlled paths."""
    if not isinstance(relative, str) or not relative or relative != relative.strip():
        return False
    try:
        relative.encode("utf-8", errors="strict")
    except UnicodeError:
        return False
    if any(ord(char) < 32 or ord(char) == 127 or char in '\\<>:"|?*' for char in relative):
        return False
    parts = relative.split("/")
    if len(parts) > MAX_DEPTH or any(part in ("", ".", "..") or
                                    part != part.strip() or part.endswith(".") for part in parts):
        return False
    return not any(re.fullmatch(r"(?i)(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
                   for part in parts)


def _path_identity(relative):
    return unicodedata.normalize("NFC", relative).casefold()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plain_markdown(text: str) -> str:
    """Hide code blocks and comments without executing package helpers."""
    result = []
    fence, comment = None, False
    for line in text.splitlines():
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*$", line):
                fence = None
            result.append("")
            continue
        if not comment and re.match(r'(?: {4}| {0,3}\t)', line):
            result.append("")
            continue
        if not comment and opening:
            fence = (opening[1][0], len(opening[1]))
            result.append("")
            continue
        visible, offset = [], 0
        while offset < len(line):
            if comment:
                end = line.find('-->', offset)
                stop = len(line) if end < 0 else end + 3
                visible.append(' ' * (stop - offset))
                offset = stop
                if end < 0:
                    break
                comment = False
                continue
            token = re.search(r'<!--|`+', line[offset:])
            if token is None:
                visible.append(line[offset:])
                break
            start = offset + token.start()
            visible.append(line[offset:start])
            if token[0] == '<!--':
                slashes = len(line[:start]) - len(line[:start].rstrip('\\'))
                if slashes % 2:
                    visible.append(token[0])
                    offset = start + len(token[0])
                    continue
                comment = True
                offset = start
                continue
            run = token[0]
            tail = start + len(run)
            closing = re.search(r'(?<!`)' + re.escape(run) + r'(?!`)', line[tail:])
            stop = tail + closing.end() if closing else tail
            visible.append(line[start:stop])
            offset = stop
        result.append(''.join(visible))
    return "\n".join(result)


def _slug(heading: str) -> str:
    heading = html.unescape(re.sub(r"<[^>]+>", "", heading)).lower()
    heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading)
    heading = "".join(char for char in heading if char in "-_ " or
                      unicodedata.category(char)[0] in "LN" or char.isspace())
    return re.sub(r"\s", "-", heading)


def _anchors(text: str) -> set[str]:
    text = _plain_markdown(text)
    markup = re.sub(r"(`+).*?\1", "", text)
    anchors = set(re.findall(r"<(?:a|[a-z][a-z0-9]*)\b[^>]*\b(?:id|name)=[\"']([^\"']+)[\"']", markup, re.I))
    seen: dict[str, int] = {}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+\s*)?$", line)
        heading = match[1] if match else None
        if heading is None and index + 1 < len(lines) and line.strip() and re.fullmatch(r" {0,3}(?:=+|-+)\s*", lines[index + 1]):
            heading = line.strip()
        if heading is not None:
            base = _slug(heading)
            count = seen.get(base, 0)
            seen[base] = count + 1
            anchors.add(base if count == 0 else base + "-" + str(count))
    return anchors


def _targets(text: str) -> list[str]:
    """Extract inline destinations (balanced parentheses) and reference definitions."""
    text = _plain_markdown(text)
    text = re.sub(r"(`+).*?\1", "", text)
    targets = []
    for match in re.finditer(r"\]\(\s*", text):
        start = match.end()
        if start >= len(text):
            continue
        if text[start] == "<":
            end = text.find(">", start + 1)
            if end >= 0:
                targets.append(text[start + 1:end])
            continue
        depth, index = 0, start
        while index < len(text):
            char = text[index]
            if char == "\\" and index + 1 < len(text):
                index += 2
                continue
            if char == "(" :
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char.isspace() and depth == 0:
                break
            index += 1
        if index > start:
            targets.append(re.sub(r"\\([()])", r"\1", text[start:index]))
    for match in re.finditer(r"^ {0,3}\[[^]\n]+\]:\s*(?:<([^>]+)>|(\S+))", text, re.M):
        targets.append(match[1] or match[2])
    return targets


def _scalar(text: str, key: str, indent: str = "") -> str | None:
    match = re.search(r"^" + re.escape(indent + key) + r":\s*(.+?)\s*$", text, re.M)
    if not match:
        return None
    value = match[1]
    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    if value.startswith("'"):
        quoted = re.fullmatch(r"'((?:[^']|'')*)'(?:\s*#.*)?", value)
        return quoted[1].replace("''", "'") if quoted else None
    return value if value not in {"|", ">", "null", "~"} else None


def _scan_package(skill_root: Path):
    """Bound the actual inventory; manifest keys never select files to read."""
    skill = skill_root.absolute()
    package = skill
    issues: list[dict] = []
    files: dict[str, Path] = {}
    texts: dict[Path, str] = {}
    hashes: dict[str, str] = {}
    identities: set[str] = set()
    entries_seen = 0
    total_bytes = 0

    def issue(code: str, path: Path | str, detail: str):
        label = str(path)
        if isinstance(path, Path) and path.is_relative_to(package):
            label = path.relative_to(package).as_posix()
        issues.append({"code": code, "path": label, "detail": detail})

    try:
        root_info = package.lstat()
        root_reparse = stat.S_ISLNK(root_info.st_mode) or getattr(root_info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if root_reparse:
            issue("reparse-entry", package, "Validate the actual installation directory, not a reparse alias.")
        pending = [] if root_reparse else [package]
    except OSError as exc:
        issue("unreadable-directory", package, str(exc))
        pending = []
    while pending:
        directory = pending.pop()
        try:
            entries = directory.iterdir()
            # Do not materialize an unbounded directory before applying the limit.
            bounded_entries = []
            for path in entries:
                entries_seen += 1
                if entries_seen > MAX_ENTRIES:
                    issue("package-limit", package, "Package exceeds the 1024-entry inspection limit.")
                    return files, texts, hashes, issues
                bounded_entries.append(path)
            entries = sorted(bounded_entries, key=lambda path: path.name)
        except OSError as exc:
            issue("unreadable-directory", directory, str(exc))
            continue
        for path in entries:
            relative = path.relative_to(package).as_posix()
            if not _manifest_path(relative):
                issue("nonportable-payload-path", path, "Requires canonical portable relative paths within 16 levels.")
                continue
            identity = _path_identity(relative)
            if identity in identities:
                issue("payload-path-collision", path, "Case or Unicode normalization aliases are not portable.")
                continue
            identities.add(identity)
            try:
                info = path.lstat()
            except OSError as exc:
                issue("unreadable-entry", path, str(exc))
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                issue("reparse-entry", path, "Links and reparse points are not distributable package content.")
                continue
            name = path.name.lower()
            if name in {"__pycache__", ".pytest_cache", ".git", ".env", "model-choice.json", ".ds_store", "thumbs.db"} or path.suffix.lower() in {".pyc", ".pyo", ".lock"}:
                issue("private-or-generated-content", path, "Private preferences or generated content must remain outside the package.")
                continue
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                files[relative] = path
                if len(files) > MAX_FILES:
                    issue("package-limit", package, "Package exceeds 256 files; bounded validation stopped.")
                    pending.clear()
                    break
                if info.st_size > MAX_FILE_BYTES:
                    issue("file-size-limit", path, "Validation limit is 2 MiB per file.")
                    continue
                try:
                    with path.open("rb") as stream:
                        data = stream.read(MAX_FILE_BYTES + 1)
                    if len(data) > MAX_FILE_BYTES:
                        issue("file-size-limit", path, "File grew beyond the 2 MiB limit during inspection.")
                        continue
                    observed = path.lstat()
                    if (not stat.S_ISREG(observed.st_mode) or
                            getattr(observed, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or
                            (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) !=
                            (observed.st_dev, observed.st_ino, observed.st_size, observed.st_mtime_ns) or
                            len(data) != info.st_size):
                        issue("payload-changed-during-inspection", path, "File identity or contents changed during inspection.")
                        continue
                    total_bytes += len(data)
                    if total_bytes > MAX_TOTAL_BYTES:
                        issue("package-limit", package, "Package exceeds the 32 MiB inspection limit.")
                        pending.clear()
                        break
                    hashes[relative] = hashlib.sha256(data).hexdigest()
                    if path.suffix.lower() in TEXT_SUFFIXES:
                        text = data.decode("utf-8-sig", errors="strict")
                        if "\ufffd" in text or "\x00" in text:
                            raise ValueError("Contains replacement or NUL characters.")
                        texts[path] = text
                except (UnicodeError, ValueError) as exc:
                    issue("invalid-utf8-text", path, str(exc))
                except OSError as exc:
                    issue("unreadable-file", path, str(exc))
            else:
                issue("unsupported-entry", path, "Only regular files and directories are allowed.")

    return files, texts, hashes, issues


def _fingerprints(value, field, issue, metadata_path):
    if type(value) is not dict or len(value) > MAX_FILES:
        issue("invalid-fingerprint-map", metadata_path, field + " must be a bounded path-to-SHA256 object.")
        return {}
    fingerprints = {}
    identities = set()
    for relative, digest in value.items():
        if not _manifest_path(relative):
            issue("invalid-fingerprint-path", metadata_path, field + ": " + repr(relative))
            continue
        identity = _path_identity(relative)
        if identity in identities:
            issue("fingerprint-path-collision", metadata_path, field + ": " + relative)
            continue
        identities.add(identity)
        if identity == MANIFEST_FILE:
            issue("manifest-self-reference", metadata_path, field + " cannot fingerprint package-info.json itself.")
            continue
        if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
            issue("invalid-fingerprint-hash", metadata_path, field + ": " + relative)
            continue
        fingerprints[relative] = digest
    return fingerprints


def inspect_structure(skill_root: Path, *, require_full_integrity: bool = False) -> dict:
    """Inspect this installation without repairing or accepting new fingerprints."""
    skill = skill_root.absolute()
    package = skill
    files, texts, hashes, issues = _scan_package(skill)
    # Reuse only this scan's snapshot; a later inspection must observe edits.
    resolved_package = package.resolve()
    destinations, anchor_sets = {}, {}

    def issue(code: str, path: Path | str, detail: str):
        label = path.relative_to(package).as_posix() if isinstance(path, Path) and path.is_relative_to(package) else str(path)
        issues.append({"code": code, "path": label, "detail": detail})

    for relative in REQUIRED_FILES:
        path = skill / relative
        if path not in files.values():
            issue("missing-required-file", path, relative)

    skill_text = texts.get(skill / "SKILL.md", "")
    frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", skill_text, re.S)
    if not frontmatter:
        issue("invalid-frontmatter", skill / "SKILL.md", "Requires initial YAML name and description frontmatter.")
    elif _scalar(frontmatter[1], "name") != NAME or skill.name != NAME or not _scalar(frontmatter[1], "description"):
        issue("frontmatter-mismatch", skill / "SKILL.md", "Name must match the Skill folder; description must be nonempty.")

    yaml_path = skill / "agents/openai.yaml"
    yaml_text = texts.get(yaml_path, "")
    prompt = _scalar(yaml_text, "default_prompt", "  ")
    if not re.search(r"^interface:\s*$", yaml_text, re.M) or not all(_scalar(yaml_text, key, "  ") for key in ("display_name", "short_description", "default_prompt")):
        issue("invalid-agent-metadata", yaml_path, "Requires interface with three nonempty scalar display/prompt fields.")
    elif "$" + NAME not in prompt:
        issue("agent-skill-mismatch", yaml_path, "Default prompt must invoke this Skill's stable name.")
    if prompt and re.search(r"\bTerra\b", prompt):
        issue("model-metadata-mismatch", yaml_path, "Current preflight and model policy use Luna, not Terra.")

    for path, text in texts.items():
        if path.suffix.lower() != ".md":
            continue
        for target in _targets(text):
            try:
                parts = urlsplit(target)
            except ValueError as exc:
                issue("invalid-link", path, target + ": " + str(exc))
                continue
            if parts.scheme in {"https", "http", "mailto", "app"}:
                continue
            if parts.scheme or parts.netloc or parts.path.startswith(("/", "\\")):
                issue("nonportable-link", path, target)
                continue
            destination = path
            if parts.path:
                destination_key = (path.parent, unquote(parts.path))
                if destination_key not in destinations:
                    destinations[destination_key] = (path.parent / destination_key[1]).resolve()
                destination = destinations[destination_key]
            if not destination.is_relative_to(resolved_package):
                issue("outside-package-link", path, target)
            elif not destination.exists():
                issue("broken-link", path, target)
            elif parts.fragment:
                destination_text = texts.get(destination)
                if destination_text is not None and destination not in anchor_sets:
                    anchor_sets[destination] = _anchors(destination_text)
                if destination_text is None or unquote(parts.fragment) not in anchor_sets[destination]:
                    issue("missing-anchor", path, target)

    metadata = "checked"
    metadata_path = skill / MANIFEST_FILE
    integrity = {"status": "unverified", "schemaVersion": None, "fullCoverage": False,
                 "sourceFilesChecked": 0, "payloadFilesChecked": 0,
                 "excludedFiles": [MANIFEST_FILE],
                 "nonClaims": ["Hashes do not authenticate authorship, authorization or semantic correctness.",
                               "The manifest and validator are local files, not an external trust anchor."]}
    if metadata_path in texts:
        try:
            manifest = json.loads(texts[metadata_path], object_pairs_hook=_unique_object,
                                  parse_constant=_reject_constant)
            if type(manifest) is not dict:
                raise ValueError("Package metadata must be a JSON object.")
            schema = manifest.get("schemaVersion")
            if type(schema) is not int or schema not in (1, 2):
                raise ValueError("Unsupported package metadata schemaVersion; expected integer 1 or 2.")
            integrity["schemaVersion"] = schema
            allowed = METADATA_FIELDS | ({"payloadFiles"} if schema == 2 else set())
            if set(manifest) - allowed:
                issue("unknown-package-metadata", metadata_path, "Unknown fields: " + ", ".join(sorted(set(manifest) - allowed)))
            if manifest.get("name") != NAME or not isinstance(manifest.get("version"), str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", manifest["version"]):
                issue("package-metadata-mismatch", metadata_path, "Requires matching Skill name and semantic version.")
            if manifest.get("python") != ">=3.10":
                issue("package-requirements-mismatch", metadata_path, "Expected Python >=3.10.")
            originals = _fingerprints(manifest.get("sourceFiles"), "sourceFiles", issue, metadata_path)
            for extra in sorted(set(originals) - set(CORE_FILES)):
                issue("unexpected-core-fingerprint", metadata_path, "sourceFiles preserves the current executable source records: " + extra)
            for relative in CORE_FILES:
                expected = originals.get(relative)
                if expected is None:
                    issue("missing-core-fingerprint", metadata_path, relative)
                elif relative in hashes:
                    integrity["sourceFilesChecked"] += 1
                    if hashes[relative] != expected:
                        issue("core-source-mismatch", skill / relative, "Core source differs from its recorded provenance; review and explicitly update the source record after an authorized change.")
            if schema == 1:
                integrity["status"] = "legacy-core-only"
                integrity["recovery"] = ("Review the intended source/version, review the current sourceFiles records, "
                                         "then explicitly emit and adopt payloadFiles with schemaVersion 2; "
                                         "rerun validation. Never refresh hashes merely to hide an unexplained mismatch.")
                if require_full_integrity:
                    issue("payload-integrity-required", metadata_path, "Schema 1 checks only declared executable files; full payload integrity requires schema 2.")
            else:
                integrity_test = "scripts/" + INTEGRITY_TEST_MODULE + ".py"
                if integrity_test not in files:
                    issue("missing-required-file", skill / integrity_test, "Schema 2 requires the bundled integrity regressions.")
                payload = _fingerprints(manifest.get("payloadFiles"), "payloadFiles", issue, metadata_path)
                actual = set(files) - {MANIFEST_FILE}
                for relative in sorted(actual - set(payload)):
                    issue("missing-payload-fingerprint", skill / relative, "Actual payload file is absent from payloadFiles.")
                for relative in sorted(set(payload) - actual):
                    issue("unexpected-payload-fingerprint", metadata_path, "No corresponding payload file: " + relative)
                for relative in sorted(actual & set(payload) & set(hashes)):
                    integrity["payloadFilesChecked"] += 1
                    if hashes[relative] != payload[relative]:
                        issue("payload-source-mismatch", skill / relative, "Payload differs from the reviewed manifest; restore expected content or explicitly review and record the intended change.")
                integrity["status"] = "payload-verified" if not issues and set(hashes) == set(files) else "failed"
                integrity["fullCoverage"] = integrity["status"] == "payload-verified"
        except (AttributeError, KeyError, TypeError, ValueError, OSError, RecursionError) as exc:
            issue("invalid-package-metadata", metadata_path, str(exc))
    else:
        metadata = "missing-or-unreadable"

    for path, text in texts.items():
        if path.suffix.lower() == ".json":
            try:
                value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
                if isinstance(value, dict) and {"environment", "selection", "frozenAtUtc"} <= value.keys():
                    issue("private-preference-record", path, "Personal model preference records must not be distributed.")
            except (ValueError, RecursionError) as exc:
                issue("invalid-json", path, str(exc))
        elif path.suffix.lower() == ".py":
            try:
                ast.parse(text, filename=str(path))
            except SyntaxError as exc:
                issue("invalid-python", path, str(exc))

    # Syntax, links and inventory failures cannot support a whole-package claim.
    if issues and integrity["status"] == "payload-verified":
        integrity.update(status="failed", fullCoverage=False)
    snapshot = hashlib.sha256(json.dumps(hashes, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    return {"passed": not issues, "issues": issues, "filesChecked": len(files),
            "metadata": metadata, "integrity": integrity, "snapshotSha256": snapshot,
            "packageRoot": str(package), "skillRoot": str(skill)}


def emit_payload_files(skill_root: Path) -> dict:
    """Produce a reviewable candidate only, including validator and reference bytes."""
    skill = skill_root.absolute()
    files, texts, hashes, issues = _scan_package(skill)
    if MANIFEST_FILE not in files:
        issues.append({"code": "missing-required-file", "path": MANIFEST_FILE,
                       "detail": "Maintain the existing package metadata before generating a payload candidate."})
    for path, text in texts.items():
        if path.suffix.lower() == ".json":
            try:
                value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
                if isinstance(value, dict) and {"environment", "selection", "frozenAtUtc"} <= value.keys():
                    issues.append({"code": "private-preference-record", "path": path.relative_to(skill).as_posix(),
                                   "detail": "Personal model preference records must not become payload candidates."})
            except (ValueError, RecursionError) as exc:
                issues.append({"code": "invalid-json", "path": path.relative_to(skill).as_posix(), "detail": str(exc)})
    candidate = {name: hashes[name] for name in sorted(hashes) if name != MANIFEST_FILE}
    return {"status": "failed" if issues else "candidate-generated", "schemaVersion": 2,
            "payloadFiles": candidate if not issues else {}, "issues": issues,
            "excludedFiles": [MANIFEST_FILE], "manifestWritten": False, "validationPerformed": False,
            "nextAction": "Review the diff and sourceFiles provenance, explicitly adopt the candidate as payloadFiles in schema 2 metadata, then validate.",
            "nonClaims": ["Observed bytes are not proof of authorization, provenance or semantic correctness.",
                          "Generating hashes does not repair or accept a failed package."]}



def run_tests(skill,timeout=600):
    modules=sorted(p.stem for p in (skill/'scripts').glob('test_*.py'))
    if not modules: return dict(passed=False,reason='current regression material missing')
    try:
        # -B covers this interpreter; the env covers every subprocess the regressions spawn,
        # so running the bundled tests cannot write __pycache__ into the package it is grading.
        environment={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        completed=subprocess.run([sys.executable,'-X','utf8','-B','-m','unittest',*modules],cwd=skill/'scripts',capture_output=True,text=True,encoding='utf-8',timeout=timeout,env=environment)
        return dict(passed=completed.returncode==0,exitCode=completed.returncode,modules=modules,diagnostics=(completed.stdout+completed.stderr)[-65536:])
    except subprocess.TimeoutExpired as exc:
        def decoded(value):
            return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else (value or '')
        diagnostics = ''.join(label + '\n' + value + '\n' for label,value in
                              (('[stdout]',decoded(exc.stdout)),('[stderr]',decoded(exc.stderr))) if value)
        return dict(passed=False,reason='test timeout',modules=modules,timeoutSeconds=timeout,
                    diagnostics=diagnostics[-65536:],diagnosticsTruncated=len(diagnostics)>65536)

def main(argv=None):
    parser=argparse.ArgumentParser(description='Validate current package inventory, links, fingerprints and current tests; no semantic certification.')
    parser.add_argument('--skill-root',type=Path,default=Path(__file__).resolve().parents[1]); parser.add_argument('--structure-only',action='store_true')
    parser.add_argument('--require-full-integrity',action='store_true'); parser.add_argument('--emit-payload-files',action='store_true')
    parser.add_argument('--timeout',type=int,default=600); args=parser.parse_args(argv)
    if not 1<=args.timeout<=1800: parser.error('timeout must be 1..1800 seconds')
    if args.emit_payload_files:
        result=emit_payload_files(args.skill_root); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if not result['issues'] else 2
    result=inspect_structure(args.skill_root,require_full_integrity=args.require_full_integrity)
    if result['passed'] and not args.structure_only:
        before=result['snapshotSha256']; result['tests']=run_tests(args.skill_root,args.timeout)
        after=inspect_structure(args.skill_root,require_full_integrity=args.require_full_integrity)
        if after['snapshotSha256']!=before or not after['passed']:
            result['issues'].append(dict(code='package-changed-during-tests',path='',detail='Validate one stable generation.'))
        result['passed']=result['tests']['passed'] and not result['issues']
    result['nonClaims']=['Structure/tests do not certify role identity, semantic review, installation or Unity quality.']
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['passed'] else 2
if __name__=='__main__': raise SystemExit(main())
