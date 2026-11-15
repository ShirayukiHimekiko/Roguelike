"""Mechanical checks for learned capability packs; no semantic or quality certification."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry
except ImportError:
    # 仍按合同输出 JSON + 退出码 2，调用方不必解析纯文本报错
    print(json.dumps(dict(passed=False, error='Missing dependency: jsonschema>=4.18. Use an isolated/project environment; '
                                             'python -m pip install jsonschema')))
    raise SystemExit(2)

SCHEMA = Path(__file__).resolve().parents[1] / 'assets' / 'contract.schema.json'
RESULT_SCHEMA = SCHEMA.with_name('learning-result.schema.json')
NONCLAIMS = ['Mechanical checks do not establish design intent, semantic correctness, visual/creative quality or permission.',
             'Only callers that consume this check result are gated; no global write interception or sandbox is installed.']


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError(f'JSON exceeds 2 MiB: {path}')
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError('Duplicate JSON key: ' + k)
            result[k] = v
        return result
    def reject(value):
        raise ValueError('Non-finite JSON constant: ' + value)
    def finite(text):
        value = float(text)
        if not math.isfinite(value):
            reject(text)  # 1e400 解析成 inf，parse_constant 拦不到
        return value
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique, parse_constant=reject, parse_float=finite)


def unique_identities(data):
    """Source paths, principle IDs and check IDs must each be unique (validate and compare share this rule)."""
    groups = ([s.get('path') for s in data.get('sources', [])], [p.get('id') for p in data.get('principles', [])],
              [c.get('id') for c in data.get('checks', [])])
    return all(len(g) == len(set(g)) for g in groups)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def inside(root, relative):
    root = Path(root).resolve(strict=True)
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Use a relative POSIX path: ' + str(relative))
    parts = PurePosixPath(relative)
    if parts.is_absolute() or any(p in ('..', '.') for p in relative.split('/')):
        raise ValueError('Path escapes its declared root: ' + relative)
    result = (root / relative).resolve(strict=True)
    if not result.is_relative_to(root):
        raise ValueError('Resolved path escapes its declared root: ' + relative)
    return result


def inline_schema(schema):
    """Accept local fragment refs only; never fetch a schema from the network."""
    if isinstance(schema, dict):
        for key in ('$ref', '$dynamicRef'):
            if key in schema and (not isinstance(schema[key], str) or not schema[key].startswith('#')):
                raise ValueError('Only inline fragment schema references are supported')
        # Traverse schema positions, not literal const/default/example payloads
        # or property names such as {"properties": {"$ref": {"type":"string"}}}.
        for key in ('$defs', 'definitions', 'properties', 'patternProperties', 'dependentSchemas'):
            if isinstance(schema.get(key), dict):
                for value in schema[key].values():
                    inline_schema(value)
        for key in ('additionalProperties', 'unevaluatedProperties', 'propertyNames', 'contains', 'items',
                    'additionalItems', 'unevaluatedItems', 'not', 'if', 'then', 'else', 'contentSchema'):
            inline_schema(schema.get(key))
        for key in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
            if isinstance(schema.get(key), list):
                for value in schema[key]:
                    inline_schema(value)


def reject_retrieval(uri):
    raise ValueError('External schema retrieval disabled: ' + uri)


def contract_file(pack):
    pack = Path(pack)
    return pack / 'contract.json' if pack.is_dir() else pack


def validate(pack, source_root):
    path = contract_file(pack)
    data = read_json(path)
    problems = [f'{list(e.path)}: {e.message}' for e in Draft202012Validator(read_json(SCHEMA)).iter_errors(data)]
    if problems:
        return data, problems
    source_paths = [s['path'] for s in data['sources']]
    checks = [p['id'] for p in data['checks']]
    if not unique_identities(data):
        problems.append('Source paths, principle IDs and check IDs must each be unique')
    for source in data['sources']:
        try:
            actual = inside(source_root, source['path'])
            if sha(actual) != source['sha256']:
                problems.append('source-drift: ' + source['path'])
        except (ValueError, OSError) as e:
            problems.append(str(e))
    for p in data['principles']:
        if p['kind'] == 'hard' and p['authority'] not in ('user_requirement', 'project_contract', 'validated_invariant'):
            problems.append('Unsupported hard-rule authority: ' + p['id'])
        if p['kind'] == 'hard' and p['authority'] == 'validated_invariant' and not p['check_ids']:
            problems.append('Validated invariant needs an actual check: ' + p['id'])
        for evidence in p['evidence']:
            if evidence['source'] not in source_paths:
                problems.append('Unknown evidence source for ' + p['id'])
        for check in p['check_ids']:
            if check not in checks:
                problems.append('Unknown check ID for ' + p['id'] + ': ' + check)
    for key in ('input_schema', 'output_schema'):
        try:
            inline_schema(data[key])
            Draft202012Validator.check_schema(data[key])
        except Exception as e:
            problems.append(key + ': ' + str(e))
    if data['status'] in ('trialed', 'adopted') and not any(t['result'] == 'passed' for t in data['trials']):
        problems.append('A trialed/adopted label must cite at least one successful transfer trial; label is not certification')
    return data, problems


def inspect_result(path, pack, workspace, contract, consumer_root=None):
    """Check declared result references, not learning depth, execution or effect."""
    problems = []
    result = read_json(path)
    errors = list(Draft202012Validator(read_json(RESULT_SCHEMA)).iter_errors(result))
    if errors:
        return dict(path=str(path), references_passed=False), [
            f'learning-result {list(error.path)}: {error.message}' for error in errors]

    def reference(root, relative, label, kind=None, nonempty=False):
        try:
            # Only the pack identity may name the workspace itself.
            resolved = (Path(root).resolve(strict=True) if label == 'capability_pack' and relative == '.'
                        else inside(root, relative))
            if kind == 'file' and not resolved.is_file():
                raise ValueError('Expected a readable file: ' + relative)
            if kind == 'directory' and not resolved.is_dir():
                raise ValueError('Expected a directory: ' + relative)
            if resolved.is_file():
                # Opening catches unreadable references; no file text is executed.
                with resolved.open('rb') as stream:
                    first = stream.read(1)
                if nonempty and not first:
                    raise ValueError('Empty referenced file: ' + relative)
            return resolved
        except (OSError, ValueError) as exc:
            problems.append('learning-result ' + label + ': ' + str(exc))
            return None

    reference(workspace, result['design_extraction'], 'design_extraction', 'file', True)
    actual_pack = reference(workspace, result['capability_pack'], 'capability_pack', 'directory')
    if actual_pack is not None and actual_pack != contract_file(pack).resolve(strict=True).parent:
        problems.append('learning-result capability_pack does not identify this checked pack')
    trial = result['transfer_trial']
    if trial['outcome'] != 'unobserved':
        artifact = reference(workspace, trial['artifact'], 'transfer_trial.artifact')
        if trial['outcome'] == 'passed' and artifact is not None:
            declared = []
            for item in contract['trials']:
                if item['result'] == 'passed':
                    try:
                        declared.append(inside(workspace, item['artifact']))
                    except (OSError, ValueError):
                        pass  # The normal check reports missing contract artifacts.
            if artifact not in declared:
                problems.append('learning-result passed transfer has no matching passed contract trial artifact')
    consumer = result.get('consumer_trial')
    if consumer and consumer['outcome'] != 'unobserved':
        reference(consumer_root or workspace, consumer['entry'], 'consumer_trial.entry', 'file', True)
        reference(workspace, consumer['artifact'], 'consumer_trial.artifact')
        reference(workspace, consumer['evidence'], 'consumer_trial.evidence', 'file', True)
    return dict(path=str(path), references_passed=not problems,
                transfer_outcome=trial['outcome'],
                consumer_outcome=consumer['outcome'] if consumer else 'not_declared',
                actual_execution_verified=False, learning_coverage_verified=False), problems


def windows_descendants(root_pid):
    """Snapshot every process and walk parent links from root_pid (Toolhelp32; no external tool needed)."""
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_void_p), ('th32ModuleID', wintypes.DWORD),
                    ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = kernel.CreateToolhelp32Snapshot(0x2, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return []
    children = {}
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(Entry)
        ok = kernel.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            children.setdefault(entry.th32ParentProcessID, []).append(entry.th32ProcessID)
            ok = kernel.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snap)
    found, stack = [], [root_pid]
    while stack:
        for pid in children.get(stack.pop(), []):
            if pid not in found and pid != root_pid:
                found.append(pid)
                stack.append(pid)
    return found


def kill_tree(process):
    """Kill a check and everything it spawned; killing only the direct child leaves grandchildren running.
    taskkill can be refused inside agent sandboxes, so descendants are also found and terminated directly."""
    if os.name == 'nt':
        try:
            descendants = windows_descendants(process.pid)
        except (OSError, AttributeError, ValueError):
            descendants = []
        try:
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
        for pid in descendants:
            try:
                os.kill(pid, 9)  # TerminateProcess on Windows
            except OSError:
                pass
    else:
        try:
            os.killpg(process.pid, 9)
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass
    process.wait(timeout=30)


def run_bounded(argv, cwd, env, timeout, tail=12000):
    """Run one check with output in temp files, not pipes: a grandchild holding a pipe open would block forever."""
    import tempfile
    import time
    flags = dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else dict(start_new_session=True)
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        started = time.monotonic()
        process = subprocess.Popen(argv, cwd=cwd, env=env, shell=False, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, **flags)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(process)
            code = None
        seconds = round(time.monotonic() - started, 2)
        texts = []
        for stream in (out, err):
            stream.seek(0)
            texts.append(stream.read().decode('utf-8', errors='replace')[-tail:])
    return code, texts[0], texts[1], seconds


def check(args):
    initial_contract_hash = sha(contract_file(args.pack))
    data, problems = validate(args.pack, args.source_root)
    results = []
    if problems:
        return dict(mechanical_passed=False, phase='preflight', issues=problems, checks=results, nonclaims=NONCLAIMS)
    workspace = Path(args.workspace).resolve(strict=True)
    result_path = getattr(args, 'result', None)
    if result_path:
        result_path = Path(result_path)
        if not result_path.is_absolute():
            result_path = workspace / result_path
    else:
        automatic = contract_file(args.pack).resolve(strict=True).parent / 'LEARNING-RESULT.json'
        result_path = automatic if automatic.exists() else None
    result_hash, result_inspection = None, None
    if result_path is not None:
        try:
            result_hash = sha(result_path)
            result_inspection, errors = inspect_result(result_path, args.pack, workspace, data,
                                                       getattr(args, 'consumer_root', None))
            problems.extend(errors)
        except (OSError, ValueError) as exc:
            problems.append('learning-result: ' + str(exc))
        if problems:
            return dict(mechanical_passed=False, phase='preflight', issues=problems, checks=[],
                        learning_result=result_inspection, nonclaims=NONCLAIMS)
    data_hashes = {}
    for name, path in (('input_schema', args.input), ('output_schema', args.output)):
        try:
            value = read_json(path)
            data_hashes[name] = sha(path)
            for error in Draft202012Validator(data[name], registry=Registry(retrieve=reject_retrieval)).iter_errors(value):
                problems.append(f'{name} {list(error.path)}: {error.message}')
        except Exception as e:
            problems.append(name + ': ' + str(e))
    for trial in data['trials']:
        if trial['result'] == 'passed':
            try:
                inside(workspace, trial['artifact'])
            except (OSError, ValueError) as e:
                problems.append('Missing trial artifact: ' + str(e))
    if data['checks'] and not args.run_checks:
        problems.append('Checks were not executed; pass --run-checks after inspecting their scope and authorization')
    if not problems and args.run_checks:
        for spec in data['checks']:
            argv = list(spec['argv'])
            if argv[0] in ('python', 'python3'):
                argv[0] = sys.executable
            environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8',
                           'LEARN_SOURCE_ROOT': str(Path(args.source_root).resolve())}
            try:
                code, stdout, stderr, seconds = run_bounded(argv, workspace, environment, spec['timeout_seconds'])
                if code is None:
                    result = dict(id=spec['id'], argv=argv, passed=False, seconds=seconds,
                                  outcome='timeout; process tree killed; dependent result remains unknown; no automatic retry',
                                  stdout=stdout, stderr=stderr)
                else:
                    result = dict(id=spec['id'], argv=argv, passed=code == 0, exit_code=code, seconds=seconds,
                                  stdout=stdout, stderr=stderr)
            except OSError as e:
                result = dict(id=spec['id'], passed=False, outcome=str(e))
            results.append(result)
            if not result['passed']:
                problems.append('check-failed: ' + spec['id'])
    if sha(contract_file(args.pack)) != initial_contract_hash:
        problems.append('contract-changed-during-checks: validate one stable generation')
    if result_path is not None:
        try:
            if sha(result_path) != result_hash:
                problems.append('learning-result-changed-during-checks: validate one stable generation')
            result_inspection, errors = inspect_result(result_path, args.pack, workspace, data,
                                                       getattr(args, 'consumer_root', None))
            problems.extend(errors)
        except (OSError, ValueError) as exc:
            problems.append('learning-result: ' + str(exc))
    for name, path in (('input_schema', args.input), ('output_schema', args.output)):
        if name in data_hashes:
            try:
                if sha(path) != data_hashes[name]:
                    problems.append(name + '-changed-during-checks: validate one stable generation')
            except OSError as e:
                problems.append(name + ': ' + str(e))
    _, after_problems = validate(args.pack, args.source_root)
    problems.extend('postcheck: ' + issue for issue in after_problems)
    return dict(mechanical_passed=not problems, phase='execution', issues=problems, checks=results,
                contract_sha256=initial_contract_hash, source_scope=data['scope'],
                learning_result=result_inspection,
                semantic_review_required=[p['id'] for p in data['principles']], nonclaims=NONCLAIMS)


def guard_output(destination, protected):
    """Reject our own output aliases; this is not a sandbox for check commands."""
    target = Path(destination).resolve()
    if target.is_dir():
        raise ValueError('Output must be a file: ' + str(destination))
    for item in [Path(__file__), SCHEMA, RESULT_SCHEMA, SCHEMA.with_name('learning-request.schema.json'), *protected]:
        item = Path(item).resolve()
        if target == item or (item.is_dir() and target.is_relative_to(item)):
            raise ValueError('Output aliases a protected input or artifact: ' + str(destination))
        if target.exists() and item.exists() and target.samefile(item):
            raise ValueError('Output aliases a protected input or artifact: ' + str(destination))


def declared_path(root, relative):
    """Normalize a declared output even when a failed trial never generated it."""
    root = Path(root).resolve(strict=True)
    if (not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative
            or PurePosixPath(relative).is_absolute()
            or any(part in ('.', '..') for part in relative.split('/'))):
        raise ValueError('Unsafe declared path: ' + str(relative))
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Resolved path escapes its declared root: ' + relative)
    return path


def check_report_inputs(args):
    """Declared read/evidence set; do not infer paths from free-text evidence."""
    contract = contract_file(args.pack).resolve(strict=True)
    workspace = Path(args.workspace).resolve(strict=True)
    protected = [contract, contract.parent / 'SKILL.md', Path(args.input), Path(args.output)]
    data = read_json(contract)
    if not Draft202012Validator(read_json(SCHEMA)).is_valid(data):
        raise ValueError('Cannot safely enumerate report inputs: invalid contract')
    protected.extend(declared_path(args.source_root, item['path']) for item in data['sources'])
    # All named trials are protected, but failed/unobserved ones need not exist.
    protected.extend(declared_path(workspace, item['artifact']) for item in data['trials'])
    for spec in data['checks']:
        argv = spec['argv']
        payloads = set()
        if Path(argv[0]).name.lower() in ('python', 'python3', 'python.exe', 'python3.exe',
                                         Path(sys.executable).name.lower()):
            index = 1
            # Interpreter flags end at the script, stdin or '--'. A script's
            # own -m/-c options may name actual input files and are not skipped.
            while index < len(argv):
                arg = argv[index]
                if arg in ('-c', '-m'):
                    payloads.add(index + 1)
                    break
                if arg in ('-W', '-X'):
                    payloads.add(index + 1)
                    index += 2
                    continue
                if arg.startswith(('-c', '-m')):
                    payloads.add(index)
                    break
                if arg in ('-', '--') or not arg.startswith('-'):
                    break
                index += 1
        for index, arg in enumerate(argv):
            if index in payloads:
                continue
            candidate = Path(arg)
            candidate = candidate if candidate.is_absolute() else workspace / candidate
            try:
                if candidate.is_file():
                    protected.append(candidate)
            except (OSError, ValueError):
                pass  # An ordinary argument may not be a filesystem path.
    result = getattr(args, 'result', None)
    if result:
        result = Path(result)
        result = result if result.is_absolute() else workspace / result
    else:
        automatic = contract.parent / 'LEARNING-RESULT.json'
        result = automatic if automatic.exists() else None
    if result is not None:
        protected.append(result)
        document = read_json(result)
        if not Draft202012Validator(read_json(RESULT_SCHEMA)).is_valid(document):
            raise ValueError('Cannot safely enumerate report inputs: invalid learning-result')
        protected.append(declared_path(workspace, document['design_extraction']))
        if document['transfer_trial']['outcome'] != 'unobserved':
            protected.append(declared_path(workspace, document['transfer_trial']['artifact']))
        consumer = document.get('consumer_trial')
        if consumer and consumer['outcome'] != 'unobserved':
            protected.append(declared_path(getattr(args, 'consumer_root', None) or workspace, consumer['entry']))
            protected.extend(declared_path(workspace, consumer[key]) for key in ('artifact', 'evidence'))
    # Directory artifacts include files whose other names may be hard links.
    for item in list(protected):
        if item.is_dir():
            protected.extend(path for path in item.rglob('*') if path.is_file())
    return protected


def compare(old, new):
    old, new = read_json(contract_file(old)), read_json(contract_file(new))
    validator = Draft202012Validator(read_json(SCHEMA))
    for label, data in (('old', old), ('new', new)):
        errors = list(validator.iter_errors(data))
        if errors:
            raise ValueError(label + ' contract is invalid: ' + errors[0].message)
        if not unique_identities(data):
            # 重复 id 会在下面按 id 建表时互相覆盖，把真实改动藏起来
            raise ValueError(label + ' contract has duplicate source paths, principle IDs or check IDs')
    conflicts = []
    material_fields = ('name', 'scope', 'capability', 'triggers', 'exclusions', 'limitations',
                       'dependencies', 'input_schema', 'output_schema',
                       'checks', 'parameter_notes', 'wiring_notes', 'space_notes')
    for field in material_fields:
        if old.get(field) != new.get(field):
            conflicts.append(dict(field=field, action='Review actual consumers and compatibility; not automatically breaking or compatible'))
    left = {p['id']: p for p in old.get('principles', [])}
    right = {p['id']: p for p in new.get('principles', [])}
    for identity in sorted(set(left) | set(right)):
        if left.get(identity) != right.get(identity):
            conflicts.append(dict(principle=identity, change='added' if identity not in left else 'removed' if identity not in right else 'changed'))
    if old.get('sources') != new.get('sources'):
        conflicts.append(dict(field='sources', action='Revisit affected claims and drift; do not refresh hashes merely to suppress failure'))
    for field in ('trials', 'status'):
        if old.get(field) != new.get(field):
            conflicts.append(dict(field=field, category='evidence_or_adoption',
                                  action='Review evidence and adoption decision; no automatic promotion or version bump'))
    changed = any(old.get(k) != new.get(k) for k in (*material_fields, 'sources', 'principles'))
    try:
        if changed and tuple(map(int, new['version'].split('.'))) <= tuple(map(int, old['version'].split('.'))):
            conflicts.append(dict(field='version', action='Substantive contract changes need an increased version'))
    except (KeyError, ValueError):
        conflicts.append(dict(field='version', action='Invalid semantic version'))
    return dict(review_required=bool(conflicts), conflicts=conflicts,
                applied=False, nonclaims=['Comparison flags differences; it does not decide semantic conflicts or merge packages.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fp = sub.add_parser('fingerprint')
    fp.add_argument('--source-root', required=True); fp.add_argument('--file', action='append', required=True); fp.add_argument('--out', required=True)
    val = sub.add_parser('validate'); val.add_argument('pack'); val.add_argument('--source-root', required=True)
    audit = sub.add_parser('check'); audit.add_argument('pack'); audit.add_argument('--source-root', required=True)
    audit.add_argument('--workspace', required=True); audit.add_argument('--input', required=True); audit.add_argument('--output', required=True)
    audit.add_argument('--run-checks', action='store_true'); audit.add_argument('--report')
    audit.add_argument('--result', help='Learning-result JSON, relative to workspace or absolute; auto-detects pack/LEARNING-RESULT.json')
    audit.add_argument('--consumer-root', help='Explicit root for consumer entry references; artifacts/evidence remain in workspace')
    diff = sub.add_parser('compare'); diff.add_argument('old'); diff.add_argument('new')
    args = parser.parse_args()
    try:
        if args.command == 'fingerprint':
            sources = [inside(args.source_root, p) for p in args.file]
            guard_output(args.out, sources)
            rows = [dict(path=p, sha256=sha(source)) for p, source in zip(args.file, sources)]
            guard_output(args.out, sources)
            Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
            report, code = dict(fingerprints=rows, interpretationPerformed=False), 0
        elif args.command == 'validate':
            data, issues = validate(args.pack, args.source_root)
            report = dict(structure_and_sources_passed=not issues, issues=issues, checks_executed=False, nonclaims=NONCLAIMS)
            code = 0 if not issues else 2
        elif args.command == 'check':
            protected = check_report_inputs(args) if args.report else []
            if args.report:
                guard_output(args.report, protected)
            report = check(args); code = 0 if report['mechanical_passed'] else 2
            if args.report:
                guard_output(args.report, [*protected, *check_report_inputs(args)])
                Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            report = compare(args.old, args.new); code = 3 if report['review_required'] else 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as e:
        # 只加字段不改名：同时给出本命令平时的判定键，调用方读 report[键] 不会 KeyError
        flags = dict(fingerprint={}, validate=dict(structure_and_sources_passed=False),
                     check=dict(mechanical_passed=False), compare=dict(review_required=True))[args.command]
        report, code = dict(passed=False, error=str(e) or type(e).__name__, **flags, nonclaims=NONCLAIMS), 2
    # stdout 用 ASCII 转义：GBK 控制台、PowerShell 5.1、UTF-8 调用方解析出的 JSON 完全相同；报告文件仍是 UTF-8 原文
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
