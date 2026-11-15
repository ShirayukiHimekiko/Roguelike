"""Exact bounded JSON emission and single-writer raw candidate preservation.

These functions provide bytes and commit observations, never semantic approval,
reader consumption proof, a host interceptor, or a multi-file transaction.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def emission_page(value, page=0, max_bytes=6144, expect_sha=None):
    if type(page) is not int or page < 0:
        raise ValueError('emission page must be nonnegative')
    if type(max_bytes) is not int or not 2048 <= max_bytes <= 1048576:
        raise ValueError('emission bytes must be 2048..1048576')
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    identity = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    if expect_sha is not None and (not re.fullmatch(r'[0-9a-f]{64}', expect_sha) or expect_sha != identity):
        raise ValueError('emission output changed; restart current JSON reading')
    parts, current, size = [], [], 0
    for character in payload:
        cost = len(json.dumps(character, ensure_ascii=False).encode('utf-8')) - 2
        if current and size + cost > max_bytes - 1024:
            parts.append(''.join(current)); current, size = [], 0
        current.append(character); size += cost
    parts.append(''.join(current))
    if page >= len(parts):
        raise ValueError('emission page outside current JSON')
    result = {'status': 'json-emission-page', 'outputSHA256': identity,
              'page': page, 'pageCount': len(parts), 'text': parts[page],
              'nextEmissionPage': page + 1 if page + 1 < len(parts) else None,
              'maxSerializedUtf8Bytes': max_bytes, 'consumptionVerified': False}
    if len(json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8')) > max_bytes:
        raise ValueError('emission envelope exceeds requested budget')
    return result


class CandidateSaveError(RuntimeError):
    def __init__(self, phase, current, snapshot, reason):
        self.phase, self.current, self.snapshot = phase, str(current), str(snapshot) if snapshot else None
        super().__init__(str(reason))


def preserve_and_replace(current, candidate_bytes, history_dir):
    current, history_dir = Path(current), Path(history_dir)
    if type(candidate_bytes) is not bytes:
        raise TypeError('candidate must be exact raw bytes')
    existed = current.exists()
    before = current.read_bytes() if existed else None
    snapshot, stage, phase = None, None, 'before-commit'
    try:
        if existed:
            history_dir.mkdir(parents=True, exist_ok=True)
            snapshot = history_dir / (current.name + '.' + hashlib.sha256(before).hexdigest() + '.raw')
            try:
                with snapshot.open('xb') as stream:
                    stream.write(before); stream.flush(); os.fsync(stream.fileno())
            except FileExistsError:
                if snapshot.read_bytes() != before:
                    raise ValueError('history identity occupied by different raw bytes')
            if snapshot.read_bytes() != before:
                raise ValueError('history verification failed')
        descriptor, name = tempfile.mkstemp(prefix=current.name + '.candidate-', dir=current.parent)
        stage = Path(name)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(candidate_bytes); stream.flush(); os.fsync(stream.fileno())
        if stage.read_bytes() != candidate_bytes:
            raise ValueError('candidate stage readback mismatch')
        if current.exists() != existed or (existed and current.read_bytes() != before):
            raise ValueError('current changed before commit')
        # A replacement error or anything after this point requires actual terminal readback.
        phase = 'commit-outcome-unverified'
        os.replace(stage, current)
        if current.read_bytes() != candidate_bytes:
            raise ValueError('committed candidate readback mismatch')
        return {'status': 'saved-readback-verified', 'current': str(current),
                'snapshot': str(snapshot) if snapshot else None,
                'beforeSHA256': hashlib.sha256(before).hexdigest() if existed else None,
                'afterSHA256': hashlib.sha256(candidate_bytes).hexdigest(),
                'scope': 'single-file, unique-writer; no group transaction or power-loss guarantee'}
    except (OSError, ValueError) as exc:
        raise CandidateSaveError(phase, current, snapshot, exc) from exc
    finally:
        if stage is not None and stage.exists():
            try:
                stage.unlink()
            except OSError as exc:
                raise CandidateSaveError(phase, current, snapshot, 'stage cleanup failed: ' + str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', required=True)
    parser.add_argument('--candidate', required=True, help='Existing candidate file; read only')
    parser.add_argument('--history', required=True)
    args = parser.parse_args(argv)
    try:
        result = preserve_and_replace(args.current, Path(args.candidate).read_bytes(), args.history)
    except CandidateSaveError as exc:
        print(json.dumps({'status': 'save-error', 'phase': exc.phase, 'current': exc.current,
                          'snapshot': exc.snapshot, 'reason': str(exc),
                          'next': 'read actual current/snapshot before any retry'}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
