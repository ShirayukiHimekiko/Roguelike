"""Read exact Markdown sections without silently truncating obligations.

Paths are relative to this Skill. Explicit HTML anchors or exact heading text
are supported; links are navigation, not automatically consumed dependencies.
"""
import argparse
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 1024 * 1024
ROUND_REFERENCES = (
    'SKILL.md',
)
MAX_ROUND_BYTES = 24 * 1024
_ACTIVE_READ = ContextVar("jury_current_read", default=None)
_IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
MAX_PLAN_BYTES = 256 * 1024


def _structural_lines(content):
    """Expose real headings/anchors and standalone continuation metadata.

    Preserve source offsets while excluding fences and HTML comments. Code
    spans keep literal comment markers from hiding following real sections.
    """
    fence, comment = None, False
    for i, line in enumerate(content.splitlines(keepends=True)):
        mark = re.match(r' {0,3}(`{3,}|~{3,})', line)
        if fence:
            if (mark and mark[1][0] == fence[0] and len(mark[1]) >= len(fence)
                    and not line[mark.end():].strip()):
                fence = None
            continue
        if not comment and re.match(r'(?: {4}| {0,3}\t)', line):
            continue
        if not comment and mark:
            fence = mark[1]
            continue
        if not comment and re.fullmatch(r'\s*<!-- jury-read-continue: (\S+) -->\s*', line):
            yield i, line
            continue
        visible, offset = [], 0
        while offset < len(line):
            if comment:
                end = line.find('-->', offset)
                stop = len(line) if end < 0 else end + 3
                visible.append(re.sub(r'[^\r\n]', ' ', line[offset:stop]))
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
        yield i, ''.join(visible)


def _continuations(content, root):
    """Report explicit required reading targets; never read or follow them."""
    targets = []
    for _, line in _structural_lines(content):
        found = re.fullmatch(r'\s*<!-- jury-read-continue: (\S+) -->\s*', line)
        if not found:
            continue
        selector = found.group(1)
        name, separator, anchor = selector.partition('#')
        target = (root / name).resolve()
        if (not name or not target.is_relative_to(root) or target.suffix != '.md'
                or (separator and not anchor)):
            raise ValueError('invalid continuation selector: ' + selector)
        if selector not in targets:
            targets.append(selector)
        if len(targets) > 32:
            raise ValueError('at most 32 explicit continuation selectors')
    return targets


class _ReadSession:
    """One command's bytes/parse snapshot; never a persistent or mutable result cache."""
    def __init__(self, root, external=False):
        self.external = external
        self.requested_root = Path(root).absolute()
        self.root = self.requested_root.resolve()
        self.bindings, self.files, self.documents, self.sections = {}, {}, {}, {}

    def file_bytes(self, filename, limit=MAX_BYTES):
        supplied = Path(filename).absolute()
        path = supplied.resolve()
        if path == self.root or not path.is_relative_to(self.root):
            raise ValueError('input path escapes Skill')
        if supplied in self.bindings and self.bindings[supplied] != path:
            raise ValueError('reading-input-path-changed: ' + str(supplied))
        self.bindings[supplied] = path
        if path not in self.files:
            with path.open('rb') as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise ValueError('input exceeds byte capacity: ' + str(supplied))
            self.files[path] = raw
        raw = self.files[path]
        if len(raw) > limit:
            raise ValueError('input exceeds byte capacity: ' + str(supplied))
        return raw

    def verify(self):
        try:
            if self.requested_root.resolve() != self.root:
                raise ValueError('reading-root-changed')
            for supplied, path in self.bindings.items():
                if supplied.resolve() != path:
                    raise ValueError('reading-input-path-changed: ' + str(supplied))
            for path, raw in self.files.items():
                with path.open('rb') as stream:
                    current = stream.read(len(raw) + 1)
                if current != raw:
                    raise ValueError('reading-input-changed: ' + str(path))
        except OSError as exc:
            raise ValueError('reading-input-unavailable-at-return: ' + str(exc)) from exc

    def section(self, selector):
        if selector in self.sections:
            return self.copy_record(self.sections[selector])
        name, sep, anchor = selector.partition('#')
        path = (self.root / name).resolve()
        if not name or path == self.root or not path.is_relative_to(self.root) or path.suffix != '.md':
            raise ValueError('section must name a Markdown file within the Skill')
        raw = self.file_bytes(self.root / name)
        if path not in self.documents:
            content = raw.decode('utf-8-sig')
            lines = content.splitlines(keepends=True)
            headings, explicit_lines, anchors = [], set(), {}
            for i, line in _structural_lines(content):
                heading = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
                if heading:
                    headings.append((i, len(heading.group(1))))
                    anchors.setdefault(heading.group(2), []).append(i)
                explicit = re.fullmatch(r"\s*<a\s+id=[\"']([^\"']+)[\"']\s*>\s*</a>\s*", line)
                if explicit:
                    explicit_lines.add(i)
                    anchors.setdefault(explicit.group(1), []).append(i)
            self.documents[path] = (lines, headings, explicit_lines, anchors, hashlib.sha256(raw).hexdigest())
        lines, headings, explicit_lines, anchors, digest = self.documents[path]
        start, end = 0, len(lines)
        if sep:
            if not anchor:
                raise ValueError('empty section anchor')
            matches = anchors.get(anchor, [])
            if len(matches) != 1:
                raise ValueError('section anchor must resolve exactly once: ' + selector)
            start = matches[0]
            first = next(((i, level) for i, level in headings if i >= start), None)
            if first is None:
                raise ValueError('anchor has no section heading: ' + selector)
            end = next((i for i, level in headings if i > first[0] and level <= first[1]), len(lines))
            while end > first[0] + 1 and (not lines[end-1].strip() or end-1 in explicit_lines):
                end -= 1
        selected = ''.join(lines[start:end])
        continuations = [] if self.external else _continuations(selected, self.root)
        record = {'selector': selector, 'resolvedSelector': selector, 'compatibilityRedirect': False,
                  'sha256': digest, 'startLine': start+1, 'endLine': end, 'characters': len(selected),
                  'utf8Bytes': len(selected.encode('utf-8')), 'content': selected,
                  'continuationSelectors': continuations, 'continuationRequired': bool(continuations)}
        self.sections[selector] = record
        return self.copy_record(record)

    @staticmethod
    def copy_record(record):
        return {**record, 'continuationSelectors': list(record['continuationSelectors'])}


@contextmanager
def reading_session(root=ROOT):
    current = _ACTIVE_READ.get()
    if current is not None and current.root == Path(root).resolve():
        yield current
        return
    session = _ReadSession(root)
    token = _ACTIVE_READ.set(session)
    try:
        yield session
        session.verify()
    finally:
        _ACTIVE_READ.reset(token)


def package_bytes(filename, root=ROOT, limit=MAX_BYTES):
    session = _ACTIVE_READ.get()
    if session is None or session.root != Path(root).resolve():
        session = _ReadSession(root)
    return session.file_bytes(filename, limit)


def read_section(selector, root=ROOT):
    session = _ACTIVE_READ.get()
    if session is None or session.root != Path(root).resolve():
        session = _ReadSession(root)
    return session.section(selector)


def expanded_sections(selectors, root=ROOT):
    """Resolve explicit mandatory edges only, with the existing visible-body guard."""
    from jury_session import visible_text_present
    ordered, complete, active = [], set(), set()
    def visit(selector):
        if selector in active:
            raise ValueError('cyclic continuation: ' + selector)
        if selector in complete:
            return
        if len(ordered) >= 128:
            raise ValueError('too many reading dependencies')
        active.add(selector)
        record = read_section(selector, root)
        body = re.sub(r'(?m)^\s*#{1,6}[ \t]+[^\n]*$', '', record['content'])
        if not visible_text_present(body):
            raise ValueError('visible section body missing: ' + selector)
        ordered.append(record)
        for dependency in record['continuationSelectors']:
            visit(dependency)
        active.remove(selector)
        complete.add(selector)
    with reading_session(root):
        for selector in selectors:
            visit(selector)
    return ordered


def _round_context(root=None):
    """Render the current core entry; conditional references are explicitly selected."""
    root = Path(ROOT if root is None else root).resolve()
    parts = ['MUST READ — 当前核心入口全文；专项按动作读取，读取不是执行或验收证明。\n']
    total = 0
    for name in ROUND_REFERENCES:
        try:
            section = read_section(name, root)
        except (OSError, ValueError) as exc:
            raise ValueError('round-reference-unavailable:' + name + ':' + str(exc)) from exc
        if not section['content'].strip():
            raise ValueError('round-reference-empty:' + name)
        total += section['utf8Bytes']
        if total > MAX_ROUND_BYTES:
            raise ValueError('round-context-exceeds-24-KiB:no-partial-context')
        # stdout translates LF on Windows; avoid doubling existing CRLF lines.
        body = section['content'].replace('\r\n', '\n').replace('\r', '\n')
        parts.append('\nSource: ' + str(root / name) + '\nSHA-256: ' + section['sha256'] +
                     '\n\n' + body + '\n')
    return ''.join(parts)


def round_context(root=None):
    with reading_session(ROOT if root is None else root):
        return _round_context(root)


def _plan_bytes(filename):
    path = Path(filename)
    if not path.is_absolute():
        raise ValueError('absolute plan path required')
    with path.open('rb') as stream:
        raw = stream.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError('plan exceeds 256 KiB')
    return raw


def _plan_selectors(raw, role):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('duplicate plan key')
            value[key] = item
        return value
    def constant(value):
        raise ValueError('nonfinite plan JSON')
    try:
        plan = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=constant)
    except RecursionError as exc:
        raise ValueError('plan nesting exceeds capacity') from exc
    if (not isinstance(plan, dict) or type(plan.get('schemaVersion')) is not int or plan.get('schemaVersion') != 3
            or plan.get('autoExecute') is not False):
        raise ValueError('current nonexecuting schema 3 plan required')
    if role not in (None, 'progress', 'architecture'):
        raise ValueError('invalid requested role')
    if plan.get('status') == 'planned':
        roles = plan.get('roles')
        if (not isinstance(roles, list) or not 1 <= len(roles) <= 2
                or any(x not in ('progress', 'architecture') for x in roles)
                or len(set(roles)) != len(roles)):
            raise ValueError('candidate plan role scope invalid')
        if role is not None and roles != [role]:
            raise ValueError('generate a candidate plan for the requested role')
        selected = roles[0] if len(roles) == 1 else 'both'
        selectors = plan.get('readSelectors')
    elif plan.get('status') == 'prepared':
        calls = plan.get('dispatch')
        if (not isinstance(calls, list) or not 1 <= len(calls) <= 2
                or any(not isinstance(x, dict) or x.get('role') not in ('progress', 'architecture') for x in calls)
                or len({x['role'] for x in calls}) != len(calls)):
            raise ValueError('prepared role dispatch required')
        if role is None and len(calls) != 1:
            raise ValueError('select --role for a multi-role preparation')
        matches = [x for x in calls if role is None or x['role'] == role]
        if len(matches) != 1:
            raise ValueError('requested role absent from preparation')
        selected = matches[0]['role']
        selectors = matches[0].get('readSelectors')
    else:
        raise ValueError('only planned/prepared material can be read as a plan')
    if (not isinstance(selectors, list) or not 1 <= len(selectors) <= 128
            or any(not isinstance(x, str) or not x.strip() or len(x) > 2048 for x in selectors)):
        raise ValueError('plan requires 1..128 bounded selectors')
    return list(dict.fromkeys(selectors)), selected


def _validate_pagination(page, page_bytes, expect_snapshot):
    if type(page) is not int or page < 0:
        raise ValueError('page must be a nonnegative integer')
    if type(page_bytes) is not int or not 1 <= page_bytes <= MAX_BYTES:
        raise ValueError('page-bytes must be 1..1048576 body UTF-8 bytes')
    if expect_snapshot is not None and not re.fullmatch(r'[0-9a-fA-F]{64}', expect_snapshot):
        raise ValueError('expected snapshot must be a SHA256')


def _section_page(records, identity, selection_args, page, page_bytes,
                  expect_snapshot, measure, selection_name):
    """Keep section and plan readers on the same complete-body paging boundary."""
    snapshot = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False,
                                        separators=(',', ':')).encode('utf-8')).hexdigest()
    if expect_snapshot is not None and snapshot != expect_snapshot.lower():
        raise ValueError('reading-snapshot-changed: read the current ' + selection_name +
                         ' again; old page order is not reusable')
    pages, group, size = [], [], 0
    for record in records:
        amount = record['utf8Bytes']
        if amount > page_bytes:
            raise ValueError('section exceeds page target: ' + record['selector'] +
                             '; needs ' + str(amount) + ' UTF-8 bytes; retry --page-bytes ' + str(amount))
        if group and size + amount > page_bytes:
            pages.append(group)
            group, size = [], 0
        group.append(record)
        size += amount
    if group:
        pages.append(group)
    if page >= len(pages):
        raise ValueError('page outside current ' + selection_name + ': ' + str(page))
    sections = [_ReadSession.copy_record(x) for x in pages[page]]
    next_args = None
    if page + 1 < len(pages):
        next_args = [*selection_args, '--page', str(page + 1), '--page-bytes', str(page_bytes),
                     '--expect-snapshot', snapshot]
        if measure:
            next_args += ['--measure']
    result = {'status': 'measured-page' if measure else 'read-page',
              'snapshot': snapshot, 'page': page, 'pageCount': len(pages),
              'pageBodyTargetUtf8': page_bytes, 'pageBodyUtf8Bytes': sum(x['utf8Bytes'] for x in sections),
              'totalSelectors': len(records), 'returnedSelectors': len(sections), 'nextArgs': next_args,
              'tokensMeasured': False, 'dependenciesAutoLoaded': True, 'sourceAuthenticated': False,
              'allPagesConsumptionVerified': False, 'sections': sections}
    if measure:
        for record in sections:
            record.pop('content')
    return result


def read_plan_page(filename, root=ROOT, role=None, page=0, page_bytes=MAX_ROUND_BYTES,
                   expect_snapshot=None, measure=False):
    """Return one whole-section page, never certify earlier pages or understanding."""
    _validate_pagination(page, page_bytes, expect_snapshot)
    raw = _plan_bytes(filename)
    selectors, selected = _plan_selectors(raw, role)
    with reading_session(root):
        records = expanded_sections(selectors, root)
        identity = {'planSha256': hashlib.sha256(raw).hexdigest(),
                    'root': str(Path(root).resolve()), 'role': selected, 'pageBodyTarget': page_bytes,
                    'readerImplementationSha256': _IMPLEMENTATION_SHA256,
                    'sections': [(x['selector'], x['sha256'], x['utf8Bytes']) for x in records]}
        selection_args = ['--from-plan', str(Path(filename).absolute())]
        if selected != 'both':
            selection_args += ['--role', selected]
        result = _section_page(records, identity, selection_args, page, page_bytes,
                               expect_snapshot, measure, 'plan')
        result.update(planPath=str(Path(filename).absolute()), planSha256=identity['planSha256'],
                      selectedRole=selected)
    if _plan_bytes(filename) != raw:
        raise ValueError('plan-input-changed-at-return')
    return result


def read_section_page(selectors, root=ROOT, page=0, page_bytes=MAX_ROUND_BYTES,
                      expect_snapshot=None, measure=False):
    """Follow explicit required continuations without constructing a review plan."""
    _validate_pagination(page, page_bytes, expect_snapshot)
    if (not isinstance(selectors, (list, tuple)) or not 1 <= len(selectors) <= 32
            or any(not isinstance(x, str) or not x.strip() for x in selectors)):
        raise ValueError('1..32 nonempty section selectors required')
    selectors = list(dict.fromkeys(selectors))
    with reading_session(root):
        records = expanded_sections(selectors, root)
        identity = {'sectionSelectors': selectors, 'root': str(Path(root).resolve()),
                    'pageBodyTarget': page_bytes, 'readerImplementationSha256': _IMPLEMENTATION_SHA256,
                    'sections': [(x['selector'], x['sha256'], x['utf8Bytes']) for x in records]}
        selection_args = [arg for selector in selectors for arg in ('--section', selector)] + ['--follow']
        result = _section_page(records, identity, selection_args, page, page_bytes,
                               expect_snapshot, measure, 'section selection')
        result.update(selectionKind='sections', selectedSections=selectors)
    return result


def read_material_page(filename, anchor=None, pointer=None, page=0, page_bytes=MAX_ROUND_BYTES,
                       expect_snapshot=None, measure=False):
    """Exact caller-named raw material, not typed state, instructions, source authority or a latest-block guess."""
    supplied=Path(filename).absolute(); path=supplied.resolve()
    if not Path(filename).is_absolute(): raise ValueError('material path must be absolute')
    if anchor is not None and pointer is not None: raise ValueError('choose material anchor or JSON pointer')
    _validate_pagination(page,page_bytes,expect_snapshot)
    with path.open('rb') as stream: raw=stream.read(4*1024*1024+1)
    if len(raw)>4*1024*1024: raise ValueError('material exceeds 4 MiB')
    digest=hashlib.sha256(raw).hexdigest()
    text=raw.decode('utf-8-sig'); start,end=1,len(text.splitlines())
    if pointer is not None:
        def pairs(items):
            value={}
            for key,member in items:
                if key in value:raise ValueError('duplicate material JSON key: '+key)
                value[key]=member
            return value
        value=json.loads(text,object_pairs_hook=pairs,
                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite material JSON')))
        if pointer and not pointer.startswith('/'): raise ValueError('JSON pointer must be empty or start with /')
        for token in pointer.split('/')[1:] if pointer else []:
            if re.search(r'~(?![01])',token): raise ValueError('invalid JSON pointer escape')
            token=token.replace('~1','/').replace('~0','~')
            if isinstance(value,dict):
                if token not in value: raise ValueError('JSON pointer object member absent')
                value=value[token]
            elif isinstance(value,list):
                if not re.fullmatch(r'0|[1-9][0-9]*',token) or int(token)>=len(value): raise ValueError('JSON pointer array index absent')
                value=value[int(token)]
            else: raise ValueError('JSON pointer traverses scalar')
        text=json.dumps(value,ensure_ascii=False,indent=2)
    elif anchor is not None:
        if path.suffix.lower()!='.md': raise ValueError('material anchor requires Markdown')
        session=_ReadSession(path.parent,external=True)
        record=session.section(path.name+'#'+anchor)
        session.verify()
        if record['sha256']!=digest: raise ValueError('material changed during selection')
        text=record['content'];start=record['startLine'];end=record['endLine']
    # Character-safe pieces preserve all text; outer jury_io handles JSON framing separately.
    pieces=[]; current=[]; size=0
    for char in text:
        cost=len(char.encode('utf-8'))
        if current and size+cost>page_bytes: pieces.append(''.join(current));current=[];size=0
        current.append(char);size+=cost
    pieces.append(''.join(current))
    identity=dict(path=str(supplied),resolvedPath=str(path),fileSHA256=digest,anchor=anchor,pointer=pointer,
                  pageBodyTarget=page_bytes,readerImplementationSha256=_IMPLEMENTATION_SHA256)
    snapshot=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    if expect_snapshot is not None and expect_snapshot!=snapshot: raise ValueError('material snapshot changed; restart exact selection')
    if page>=len(pieces): raise ValueError('material page outside selection')
    args=['--material-file',str(supplied)]
    if anchor is not None:args+=['--material-anchor',anchor]
    if pointer is not None:args+=['--json-pointer',pointer]
    next_args=[*args,'--page',str(page+1),'--page-bytes',str(page_bytes),'--expect-snapshot',snapshot] if page+1<len(pieces) else None
    if next_args and measure:next_args+=['--measure']
    result=dict(status='measured-material' if measure else 'read-material',selectionKind='external-material',
      materialIdentity=identity,snapshot=snapshot,page=page,pageCount=len(pieces),nextArgs=next_args,
      startLine=start,endLine=end,utf8Bytes=len(text.encode('utf-8')),pageBodyUtf8Bytes=len(pieces[page].encode('utf-8')),
      content=pieces[page],dependenciesAutoLoaded=False,sourceAuthenticated=False,typedStateValidated=False,
      authorityAuthenticated=False,allPagesConsumptionVerified=False)
    if measure:result.pop('content')
    if supplied.resolve()!=path or path.read_bytes()!=raw: raise ValueError('material-input-changed-at-return')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--section', action='append')
    selection.add_argument('--material-file', help='Absolute exact external material; no instruction/typed-state certification')
    selection.add_argument('--profile', choices=('general','maintenance','unity'))
    parser.add_argument('--review-stage', choices=('planning','review'))
    parser.add_argument('--material-anchor', help='Exact unique Markdown heading or anchor, never newest/tail')
    parser.add_argument('--json-pointer', help='RFC6901 pointer including numeric/boolean business values')
    selection.add_argument('--from-plan', help='Absolute saved candidate plan or prepared role JSON')
    selection.add_argument('--round-context', action='store_true',
                           help='Print the current SKILL.md core entry; select conditional references with --section')
    parser.add_argument('--measure', action='store_true', help='Only counts; does not count as reading')
    parser.add_argument('--follow', action='store_true',
                        help='With --section, follow explicit required continuations and return whole-section pages')
    parser.add_argument('--role', choices=('progress', 'architecture', 'target', 'worker', 'dialogue'))
    parser.add_argument('--page', type=int, default=0)
    parser.add_argument('--page-bytes', type=int, default=MAX_ROUND_BYTES, help='Target body UTF-8 bytes, excluding JSON metadata')
    parser.add_argument('--expect-snapshot', help='Previous page snapshot, including role and page target')
    parser.add_argument('--emit-page', type=int, help='Bound final serialized JSON; separately reassemble before following inner nextArgs')
    parser.add_argument('--emit-bytes', type=int, default=None, help='Requires --emit-page; final serialized UTF-8 budget including envelope (default 6144 when emitting)')
    parser.add_argument('--expect-emission', help='Bind resumed emission pages to the prior complete JSON SHA256')
    args = parser.parse_args(argv)
    def emit(result):
        if args.emit_page is not None:
            try:
                from jury_io import emission_page
            except ImportError as exc:
                raise ValueError('bounded emission requires jury_io.py from the complete package') from exc
            result = emission_page(result, args.emit_page, 6144 if args.emit_bytes is None else args.emit_bytes, args.expect_emission)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    try:
        if args.emit_bytes is not None and args.emit_page is None:
            raise ValueError('--emit-bytes requires --emit-page; use --emit-page 0 with a budget in 2048..1048576')
        if args.round_context and args.measure:
            parser.error('--round-context emits full bodies; --measure is for --section only')
        if args.expect_emission is not None and args.emit_page is None:
            raise ValueError('--expect-emission requires --emit-page')
        if args.round_context and args.emit_page is not None:
            raise ValueError('JSON emission requires section or plan input')
        if (args.material_anchor is not None or args.json_pointer is not None) and not args.material_file:
            raise ValueError('material locator requires --material-file')
        if args.review_stage is not None and not args.profile:
            raise ValueError('--review-stage requires --profile')
        if args.follow and not args.section:
            raise ValueError('--follow requires --section')
        if not args.from_plan and not args.profile and args.role is not None:
            raise ValueError('--role requires --from-plan')
        if not args.from_plan and not args.follow and not args.material_file and not args.profile and (args.page or args.page_bytes != MAX_ROUND_BYTES or args.expect_snapshot is not None):
            raise ValueError('pagination options require --from-plan or --section --follow')
        if args.material_file:
            emit(read_material_page(args.material_file,args.material_anchor,args.json_pointer,args.page,
                 args.page_bytes,args.expect_snapshot,args.measure))
            return 0
        if args.profile:
            if not args.review_stage or not args.role: raise ValueError('profile needs explicit role and review stage')
            import jury_candidates
            route=jury_candidates.read_profile(role=args.role,stage=args.review_stage,domain=args.profile)
            with reading_session():
                records=expanded_sections(route['readSelectors'])
                identity=dict(role=args.role,stage=args.review_stage,domain=args.profile,pageBodyTarget=args.page_bytes,
                  implementation=_IMPLEMENTATION_SHA256,sections=[(r['selector'],r['sha256']) for r in records])
                selection_args=['--profile',args.profile,'--review-stage',args.review_stage,'--role',args.role]
                result=_section_page(records,identity,selection_args,args.page,args.page_bytes,args.expect_snapshot,args.measure,'profile')
            result['routeAuthority']=route['routeAuthority']
            emit(result)
            return 0
        if args.from_plan:
            result = read_plan_page(args.from_plan, role=args.role, page=args.page, page_bytes=args.page_bytes,
                                    expect_snapshot=args.expect_snapshot, measure=args.measure)
            emit(result)
            return 0
        if args.follow:
            result = read_section_page(args.section, page=args.page, page_bytes=args.page_bytes,
                                       expect_snapshot=args.expect_snapshot, measure=args.measure)
            emit(result)
            return 0
        if args.round_context:
            print(round_context(), end='')
            return 0
        if len(args.section) > 32:
            raise ValueError('at most 32 selectors per call')
        with reading_session():
            sections = [read_section(s) for s in dict.fromkeys(args.section)]
        result = {'status': 'measured' if args.measure else 'read',
                  'characters': sum(s['characters'] for s in sections),
                  'utf8Bytes': sum(s['utf8Bytes'] for s in sections),
                  'tokensMeasured': False, 'dependenciesAutoLoaded': False,
                  'sections': sections}
        if args.measure:
            for section in sections:
                section.pop('content')
        emit(result)
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({'status': 'invalid-input', 'reason': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
