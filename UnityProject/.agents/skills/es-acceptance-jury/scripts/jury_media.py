"""Small FFmpeg capture/frame-review helper; outputs evidence, never quality verdicts."""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

QUERY_TIMEOUT = 30
DECODE_TIMEOUT = 600

# This short-lived owner joins its job before starting any target process.
# The handle is non-inheritable and lives until the owner exits: killing the
# owner on timeout closes the job and its new descendants, including frontends
# that have already exited but left a worker holding an output pipe.
_WINDOWS_LAUNCHER = r'''
import ctypes as C
from ctypes import wintypes as W
import subprocess, sys, time

def own_job():
    class Basic(C.Structure):
        _fields_ = [('PerProcessUserTimeLimit', C.c_longlong), ('PerJobUserTimeLimit', C.c_longlong),
            ('LimitFlags', W.DWORD), ('MinimumWorkingSetSize', C.c_size_t), ('MaximumWorkingSetSize', C.c_size_t),
            ('ActiveProcessLimit', W.DWORD), ('Affinity', C.c_size_t), ('PriorityClass', W.DWORD), ('SchedulingClass', W.DWORD)]
    class Counters(C.Structure):
        _fields_ = [(name, C.c_ulonglong) for name in ('ReadOperationCount', 'WriteOperationCount',
            'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]
    class Extended(C.Structure):
        _fields_ = [('BasicLimitInformation', Basic), ('IoInfo', Counters), ('ProcessMemoryLimit', C.c_size_t),
            ('JobMemoryLimit', C.c_size_t), ('PeakProcessMemoryUsed', C.c_size_t), ('PeakJobMemoryUsed', C.c_size_t)]
    class Accounting(C.Structure):
        _fields_ = [(name, C.c_longlong) for name in ('TotalUserTime', 'TotalKernelTime',
            'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')] + [(name, W.DWORD) for name in
            ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses', 'TotalTerminatedProcesses')]
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = (C.c_void_p, W.LPCWSTR)
    kernel.CreateJobObjectW.restype = W.HANDLE
    kernel.SetInformationJobObject.argtypes = (W.HANDLE, C.c_int, C.c_void_p, W.DWORD)
    kernel.SetInformationJobObject.restype = W.BOOL
    kernel.AssignProcessToJobObject.argtypes = (W.HANDLE, W.HANDLE)
    kernel.AssignProcessToJobObject.restype = W.BOOL
    kernel.GetCurrentProcess.argtypes = ()
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.QueryInformationJobObject.argtypes = (W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p)
    kernel.QueryInformationJobObject.restype = W.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise C.WinError(C.get_last_error())
    limits = Extended()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)):
        raise C.WinError(C.get_last_error())
    if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        raise C.WinError(C.get_last_error())
    return kernel, job, Accounting

try:
    kernel, job, Accounting = own_job()
except (OSError, AttributeError) as exc:
    sys.stderr.write('Unable to establish owned media job before target launch: ' + str(exc) + '\n')
    sys.exit(126)
try:
    result = subprocess.run(sys.argv[1:], stdin=None, stdout=sys.stdout, stderr=sys.stderr,
                            creationflags=subprocess.CREATE_NO_WINDOW)
except OSError as exc:
    sys.stderr.write('Unable to launch media command: ' + str(exc) + '\n')
    sys.exit(127)
# Do not close the job at direct-frontend exit: its children may still be
# producing normal output. The caller's deadline covers this wait as well.
while True:
    accounting = Accounting()
    if not kernel.QueryInformationJobObject(job, 1, C.byref(accounting), C.sizeof(accounting), None):
        sys.stderr.write('Unable to inspect owned media job: ' + str(C.WinError(C.get_last_error())) + '\n')
        sys.exit(126)
    if accounting.ActiveProcesses <= 1:
        break
    time.sleep(.01)
sys.exit(result.returncode)
'''


def _execute(argv, timeout):
    command = ([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-u', '-c', _WINDOWS_LAUNCHER, *argv]
               if os.name == 'nt' else argv)
    result = subprocess.run(command, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    result.args = argv
    return result


def ffmpeg_path(explicit=None):
    if explicit:
        path = shutil.which(explicit) or (str(Path(explicit).resolve()) if Path(explicit).is_file() else None)
    else:
        path = shutil.which('ffmpeg')
        if not path and os.environ.get('IMAGEIO_FFMPEG_EXE'):
            selected = os.environ['IMAGEIO_FFMPEG_EXE']
            path = shutil.which(selected) or (str(Path(selected).resolve()) if Path(selected).is_file() else None)
            if not path:
                raise ValueError('Configured IMAGEIO_FFMPEG_EXE is unavailable: ' + selected
                                 + '; correct this selection or pass --ffmpeg explicitly.')
        if not path and (spec := importlib.util.find_spec('imageio_ffmpeg')):
            # The provider resolver executes an unbounded -version check. Read
            # installed path metadata only; actual execution belongs to run().
            candidates, metadata_error = [], None
            try:
                definitions = importlib.import_module('imageio_ffmpeg._definitions')
                filename = definitions.FNAME_PER_PLATFORM[definitions.get_platform()]
                candidates += [Path(folder) / 'binaries' / filename
                               for folder in spec.submodule_search_locations or ()]
            except (ImportError, AttributeError, KeyError, TypeError, OSError) as exc:
                metadata_error = str(exc)
            candidates.append(Path(sys.prefix) / ('Library/bin/ffmpeg.exe' if sys.platform == 'win32' else 'bin/ffmpeg'))
            path = next((str(candidate.resolve()) for candidate in candidates if candidate.is_file()), None)
            if not path:
                raise ValueError('Installed imageio_ffmpeg has no discoverable local FFmpeg binary'
                                 + (': ' + metadata_error if metadata_error else '')
                                 + '. Pass --ffmpeg with an existing compatible binary; official source: https://ffmpeg.org/download.html.')
    if not path:
        raise ValueError('FFmpeg unavailable. Propose an install from https://ffmpeg.org/download.html; do not install automatically.')
    return path


def run(argv, log=None, timeout=None):
    timeout = finite(DECODE_TIMEOUT if timeout is None else timeout, 'timeout', True)
    try:
        result = _execute(argv, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if log:
            output = exc.stderr or b''
            log.write_bytes(output if isinstance(output, bytes) else output.encode('utf-8'))
        details = []
        for name, output in (('stdout', exc.stdout), ('stderr', exc.stderr)):
            if output:
                details.append(name + ': ' + (output.decode('utf-8', errors='replace')
                                              if isinstance(output, bytes) else output)[-1800:])
        raise ValueError(f'Media command timed out after {timeout:g} seconds; partial outputs may remain. '
                         + ('Retained log: ' + str(log) + '. ' if log else '')
                         + 'Inspect diagnostics and partial outputs before retrying; increase --timeout for a known slow workload. '
                         + '\n'.join(details)) from exc
    if log:
        log.write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError('FFmpeg failed; inspect the retained log. ' + result.stderr[-1800:])
    return result


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def finite(value, name, positive=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(name + ' must be finite and ' + ('positive' if positive else 'nonnegative'))
    return value


def rectangle(value):
    parts = tuple(int(x) for x in value.split(','))
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        raise ValueError('Region/ROI must be x,y,width,height with positive dimensions')
    return parts


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def plain_path(value):
    path = Path(value).absolute()
    # Inspect the supplied path before resolve can hide a symlink/junction.
    for part in (path, *path.parents):
        try:
            state = part.lstat()
        except FileNotFoundError:
            continue
        if part.is_symlink() or getattr(state, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Sample paths must not contain links/reparse points: ' + str(part))
    return path.resolve()


def sample_signature(source, start, end, every, box, executable):
    from PIL import __version__
    return {'schema': 1, 'source': str(source), 'sourceSha256': file_sha256(source),
            'start': start, 'end': end, 'everySeconds': every,
            'roi': list(box) if box else None, 'helperSha256': file_sha256(__file__),
            'ffmpegSha256': file_sha256(executable), 'pillowVersion': __version__}


def sample_result(record, out, reused=False):
    return {'status': record['status'], 'frames': len(record['frames']),
            'manifest': str(out / 'frames.json'), 'contactSheets': record['contactSheets'],
            'review': str(out / 'review.html'), 'continuousObserved': False, 'reused': reused}


def manifest_sha256(record):
    payload = {key: value for key, value in record.items() if key != 'manifestSha256'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def reuse_sample(out, signature):
    manifest = plain_path(out / 'frames.json')
    try:
        record = json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(record, dict):
            raise ValueError('Sample manifest is not a complete record; old evidence retained')
        if (record['manifestSha256'] != manifest_sha256(record) or
                record['status'] != 'extracted-not-observed' or
                record['cacheSignature'] != signature or
                record['continuousObserved'] is not False or record['audioObserved'] is not False):
            raise ValueError('Sample input, parameters or producer changed; old evidence retained')
        for key in ('source', 'start', 'end', 'everySeconds', 'roi'):
            if record[key] != signature[key]:
                raise ValueError('Sample manifest parameters are inconsistent; old evidence retained')
        frame_names = [entry['file'] for entry in record['frames']]
        sheets = record['contactSheets']
        if (not frame_names or not sheets or
                any(not isinstance(name, str) or not re.fullmatch(r'frames/frame-\d{6,}\.png', name)
                    for name in frame_names) or
                any(not isinstance(name, str) or not re.fullmatch(r'contact-\d{3,}\.png', name)
                    for name in sheets)):
            raise ValueError('Sample artifact paths are invalid; old evidence retained')
        required = frame_names + sheets + ['source-frames.log', 'extract.log', 'review.html']
        if len(set(required)) != len(required) or set(record['artifactSha256']) != set(required):
            raise ValueError('Sample artifact set is incomplete or duplicated; old evidence retained')
        actual = set()
        for folder, directories, files in os.walk(out, followlinks=False):
            for name in directories:
                plain_path(Path(folder) / name)
            for name in files:
                path = plain_path(Path(folder) / name)
                actual.add(path.relative_to(out).as_posix())
        if actual != set(required) | {'frames.json'}:
            raise ValueError('Sample output contains missing or unexpected files; old evidence retained')
        for name in required:
            path = plain_path(out / name)
            if file_sha256(path) != record['artifactSha256'][name]:
                raise ValueError('Sample artifact changed: ' + name + '; old evidence retained')
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('No complete reusable sample manifest; old evidence retained') from exc
    return sample_result(record, out, reused=True)


def doctor(executable=None, timeout=None):
    exe, version, device_text, error, phase = None, None, '', None, 'ffmpeg-discovery'
    try:
        deadline = finite(QUERY_TIMEOUT if timeout is None else timeout, 'timeout', True)
        exe = ffmpeg_path(executable)
        phase = 'version-query'
        version_text = run([exe, '-version'], timeout=deadline).stdout.splitlines()
        if not version_text:
            raise ValueError('FFmpeg version query returned no version text')
        version = version_text[0]
        phase = 'device-query'
        devices = run([exe, '-hide_banner', '-devices'], timeout=deadline)
        device_text = devices.stdout + devices.stderr
        error = None
    except (OSError, ValueError) as exc:
        error = str(exc)
    pillow = importlib.util.find_spec('PIL') is not None
    recommendations = []
    if error:
        recommendations.append({'capability': 'record/decode media', 'source': 'https://ffmpeg.org/download.html', 'reason': error})
    elif sys.platform == 'win32' and 'gdigrab' not in device_text:
        recommendations.append({'capability': 'Windows window/region capture', 'source': 'https://ffmpeg.org/download.html', 'reason': 'Current FFmpeg has no gdigrab input; reuse a suitable recorder or propose a compatible build.'})
    if not pillow:
        recommendations.append({'capability': 'contact sheets and image differences', 'source': 'https://pillow.readthedocs.io/en/stable/installation/basic-installation.html', 'command': 'python -m pip install Pillow'})
    return {'status': 'failed' if error else 'checked', 'error': error, 'failedPhase': phase if error else None,
            'ffmpeg': exe, 'version': version, 'gdigrab': 'gdigrab' in device_text,
            'pillow': pillow, 'ffprobe': shutil.which('ffprobe'), 'recommendations': recommendations,
            'continuousObserver': 'Not inferred from installed tools; verify actual video/audio input and observation separately.'}


def capture_command(exe, output, seconds, fps, hwnd=None, region=None):
    seconds, fps = finite(seconds, 'seconds', True), finite(fps, 'fps', True)
    if (hwnd is None) == (region is None):
        raise ValueError('Choose exactly one explicit --hwnd or --region; no default whole-desktop capture')
    args = [exe, '-hide_banner', '-nostdin', '-n', '-f', 'gdigrab', '-framerate', str(fps), '-draw_mouse', '0']
    if hwnd is not None:
        if int(hwnd) <= 0:
            raise ValueError('Window handle must be positive')
        target = 'hwnd=' + str(int(hwnd))
    else:
        x, y, width, height = rectangle(region)
        args += ['-offset_x', str(x), '-offset_y', str(y), '-video_size', f'{width}x{height}']
        target = 'desktop'
    return args + ['-i', target, '-t', str(seconds), '-an', '-c:v', 'ffv1', str(Path(output) / 'capture.mkv')]


def capture(output, seconds, fps, hwnd=None, region=None, executable=None, dry_run=False, timeout=None):
    query_timeout = finite(QUERY_TIMEOUT if timeout is None else timeout, 'timeout', True)
    exe = ffmpeg_path(executable)
    out = Path(output).resolve()
    args = capture_command(exe, out, seconds, fps, hwnd, region)
    if dry_run:
        return {'status': 'planned-only', 'argv': args, 'audioCaptured': False, 'targetBindingVerified': False}
    if sys.platform != 'win32':
        raise ValueError('This capture command is for native Windows; use an existing recorder for the current host.')
    devices = run([exe, '-hide_banner', '-devices'], timeout=query_timeout)
    if 'gdigrab' not in devices.stdout + devices.stderr:
        raise ValueError('Current FFmpeg lacks gdigrab. Propose a compatible recorder/build from the official download entry.')
    out.mkdir(parents=True, exist_ok=False)
    started, monotonic = datetime.now(timezone.utc).isoformat(), time.monotonic()
    run(args, out / 'capture.log', timeout=float(seconds) + 30 if timeout is None else timeout)
    video = out / 'capture.mkv'
    if not video.is_file() or not video.stat().st_size:
        raise ValueError('Capture command returned without a nonempty video')
    record = {'status': 'recorded-not-observed', 'file': str(video), 'startedUtc': started,
              'elapsedSeconds': time.monotonic() - monotonic, 'requestedFps': float(fps),
              'requestedSeconds': float(seconds), 'hwnd': hwnd, 'region': region,
              'audioCaptured': False, 'targetBindingVerified': False, 'argv': args}
    write_json(out / 'capture.json', record)
    return record


def sample(source, output, start, end, every=0, roi=None, executable=None, reuse=False, timeout=None):
    from PIL import Image, ImageChops, ImageDraw, ImageStat
    deadline = finite(DECODE_TIMEOUT if timeout is None else timeout, 'timeout', True)
    start, end, every = finite(start, 'start'), finite(end, 'end'), finite(every, 'every')
    if end <= start:
        raise ValueError('end must be greater than start')
    # A read-through source path is legitimate; bind once to its real file.
    # Output roots and generated artifacts remain strictly link-free.
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError('Source must be an existing local video file')
    box = rectangle(roi) if roi else None
    if box and (box[0] < 0 or box[1] < 0):
        raise ValueError('ROI x/y must be nonnegative image coordinates')
    exe = ffmpeg_path(executable)
    out = plain_path(output)
    if out.exists() and not reuse:
        raise FileExistsError('Output already exists; use --reuse only for unchanged complete evidence')
    source_state = source.stat()
    signature = sample_signature(source, start, end, every, box, exe)
    if out.exists():
        result = reuse_sample(out, signature)
        current = source.stat()
        if ((source_state.st_size, source_state.st_mtime_ns, source_state.st_ino) !=
                (current.st_size, current.st_mtime_ns, current.st_ino) or
                file_sha256(source) != signature['sourceSha256']):
            raise ValueError('Source changed during reuse validation; old evidence retained')
        return result
    out.mkdir(parents=True, exist_ok=False)
    frames_dir = out / 'frames'
    frames_dir.mkdir()
    # FFmpeg may rebuild filters and hold encoder geometry on a size/format change.
    # Inspect the whole decoded prefix, including before a selected late interval,
    # and refuse unsupported reinitialization rather than silently alter evidence.
    probe = run([exe, '-hide_banner', '-nostdin', '-t', str(end), '-i', str(source),
                 '-map', '0:v:0', '-an', '-vf', 'showinfo', '-vsync', '0', '-f', 'null', '-'],
                out / 'source-frames.log', timeout=deadline)
    formats, contexts, source_times = set(), set(), []
    for line in probe.stderr.splitlines():
        if 'showinfo' not in line or not re.search(r'\bn:\s*\d+', line):
            continue
        geometry = re.search(r'\bs:(\d+)x(\d+)', line)
        pixel_format = re.search(r'\bfmt:(\S+)', line)
        context = re.search(r'\[Parsed_showinfo_\d+ @ ([^\]]+)\]', line)
        stamp = re.search(r'\bpts_time:\s*([-+0-9.eE]+)', line)
        if geometry and pixel_format:
            formats.add((int(geometry[1]), int(geometry[2]), pixel_format[1]))
        if context:
            contexts.add(context[1])
        if stamp:
            source_times.append(float(stamp[1]))
    if not formats or not source_times:
        raise ValueError('No decoded source frame metadata; inspect source-frames.log')
    if len(formats) != 1 or len(contexts) > 1 or any(b < a for a,b in zip(source_times,source_times[1:])):
        raise ValueError('Unsupported changing frame size/format or discontinuous filter timeline. Original retained; inspect source-frames.log and use a decoder that preserves these transitions.')
    source_width, source_height, _ = next(iter(formats))
    expression = f'gte(t,{start:.12g})*lt(t,{end:.12g})'
    if every:
        expression += f'*if(isnan(prev_selected_t),1,gte(t-prev_selected_t,{max(0,every-1e-9):.12g}))'
    filters = f"setpts=PTS-STARTPTS,select='{expression}',showinfo"
    args = [exe, '-hide_banner', '-nostdin', '-n', '-t', str(end), '-i', str(source),
            '-map', '0:v:0', '-an', '-vf', filters, '-vsync', '0', '-threads', '1',
            str(frames_dir / 'frame-%06d.png')]
    result = run(args, out / 'extract.log', timeout=deadline)
    times = []
    for line in result.stderr.splitlines():
        match = re.search(r'\bn:\s*\d+.*?\bpts_time:\s*([-+0-9.eE]+)', line) if 'showinfo' in line else None
        if match:
            times.append(float(match[1]))
    paths = sorted(frames_dir.glob('frame-*.png'), key=lambda path: int(path.stem[6:]))
    if not paths or len(paths) != len(times):
        raise ValueError('Selected frames and decoded timestamp records are missing or inconsistent; inspect extract.log')
    entries, sheets, previous = [], [], None
    thumbnails = []
    for index, (path, timestamp) in enumerate(zip(paths, times)):
        with Image.open(path) as image:
            full = image.convert('RGB')
        if full.size != (source_width, source_height):
            raise ValueError('Decoded PNG dimensions differ from source; no successful evidence manifest produced.')
        measured = full
        if box:
            x, y, width, height = box
            if x + width > full.width or y + height > full.height:
                raise ValueError('ROI extends outside the original frame; originals retained')
            measured = full.crop((x, y, x + width, y + height))
        difference = None
        changed_size = previous is not None and previous.size != measured.size
        if previous is not None and not changed_size:
            difference = sum(ImageStat.Stat(ImageChops.difference(previous, measured)).mean) / 3
        entries.append({'file': path.relative_to(out).as_posix(), 'timeSeconds': timestamp,
                        'deltaSeconds': timestamp-times[index-1] if index else None,
                        'size': list(full.size), 'meanAbsoluteRgbDifference': difference,
                        'dimensionsChanged': changed_size})
        previous = measured
        thumb = full.copy()
        thumb.thumbnail((320, 200))
        thumbnails.append(thumb)
        if len(thumbnails) == 12 or index == len(paths)-1:
            first = index + 1 - len(thumbnails)
            sheet = Image.new('RGB', (960, ((len(thumbnails)+2)//3)*230), '#202525')
            draw = ImageDraw.Draw(sheet)
            for offset, thumb in enumerate(thumbnails):
                x, y = (offset % 3)*320, (offset // 3)*230
                sheet.paste(thumb, (x, y))
                item = entries[first + offset]
                draw.text((x+5, y+204), f"#{first+offset+1:06d}  t={item['timeSeconds']:.6f}s", fill='white')
            name = f'contact-{len(sheets)+1:03d}.png'
            sheet.save(out / name)
            sheets.append(name)
            thumbnails = []
    transitions = sorted((e for e in entries if e['meanAbsoluteRgbDifference'] is not None),
                         key=lambda e: e['meanAbsoluteRgbDifference'], reverse=True)
    record = {'status': 'extracted-not-observed', 'source': str(source), 'start': start, 'end': end,
              'everySeconds': every, 'roi': list(box) if box else None, 'frames': entries, 'contactSheets': sheets,
              'timestampBasis': 'Decoded video PTS normalized to the first decoded video frame; not wall-clock or inferred constant FPS.',
              'differenceBasis': 'Raw adjacent sampled-frame RGB difference in the selected ROI; candidates only, never a freeze/jump/quality verdict.',
              'sourceFrameGeometry': [source_width, source_height],
              'sourceFormatCheck': 'Decoded prefix checked for size/format/filter reinitialization; changing formats are explicitly unsupported.',
              'rankedTransitions': [e['file'] for e in transitions], 'audioObserved': False,
              'continuousObserved': False, 'sourceModified': False, 'argv': args}
    images = ''.join(f'<p><img src="{html.escape(name, quote=True)}" alt="Timestamped contact sheet"></p>' for name in sheets)
    uri = html.escape(source.as_uri(), quote=True)
    page = '<!doctype html><meta charset="utf-8"><title>Media review</title><style>body{background:#202525;color:#eee;font:16px sans-serif}img,video{max-width:100%}a{color:#9ed}</style>'
    page += f'<h1>Media review</h1><p>Original video; verify normal-speed playback and audio with an actual observer.</p><video controls preload="metadata" src="{uri}"></video>'
    page += '<p>Contact sheets are sampled evidence. They do not certify continuous playback, sound, or game quality. Exact frame paths/times and raw change signals: <a href="frames.json">frames.json</a>.</p>' + images
    (out / 'review.html').write_text(page, encoding='utf-8')
    artifacts = ([entry['file'] for entry in entries] + sheets +
                 ['source-frames.log', 'extract.log', 'review.html'])
    record['cacheSignature'] = signature
    record['artifactSha256'] = {name: file_sha256(out / name) for name in artifacts}
    record['manifestSha256'] = manifest_sha256(record)
    current = source.stat()
    if ((source_state.st_size, source_state.st_mtime_ns, source_state.st_ino) !=
            (current.st_size, current.st_mtime_ns, current.st_ino) or
            file_sha256(source) != signature['sourceSha256']):
        raise ValueError('Source changed during extraction; partial output retained without a success manifest')
    # Publish success last: partial/failed runs can never be reused.
    write_json(out / 'frames.json', record)
    return sample_result(record, out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', help='Existing FFmpeg executable; falls back to PATH or installed imageio_ffmpeg')
    parser.add_argument('--timeout', type=float, help='Positive finite seconds per external command; defaults: queries 30, decode 600, recording duration + 30. Place before the subcommand.')
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('doctor')
    grab = sub.add_parser('capture')
    grab.add_argument('--output', required=True)
    grab.add_argument('--seconds', type=float, required=True)
    grab.add_argument('--fps', type=float, required=True)
    target = grab.add_mutually_exclusive_group(required=True)
    target.add_argument('--hwnd', type=lambda value: int(value, 0))
    target.add_argument('--region', help='Physical desktop pixels: left,top,width,height')
    grab.add_argument('--dry-run', action='store_true')
    extract = sub.add_parser('sample')
    extract.add_argument('source')
    extract.add_argument('--output', required=True)
    extract.add_argument('--start', type=float, required=True)
    extract.add_argument('--end', type=float, required=True)
    extract.add_argument('--every', type=float, required=True, help='Choose explicitly: 0 keeps every decoded frame; positive values select actual frames at this minimum interval')
    extract.add_argument('--reuse', action='store_true', help='Read existing complete output only when source, parameters, producer and artifacts match; never overwrite it')
    extract.add_argument('--roi', help='Analysis-only x,y,width,height; exported full frames are preserved')
    args = parser.parse_args(argv)
    try:
        if args.operation == 'doctor':
            result = doctor(args.ffmpeg, args.timeout)
        elif args.operation == 'capture':
            result = capture(args.output, args.seconds, args.fps, args.hwnd, args.region, args.ffmpeg, args.dry_run, args.timeout)
        else:
            result = sample(args.source, args.output, args.start, args.end, args.every, args.roi, args.ffmpeg, args.reuse, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('status') == 'failed' else 0
    except (OSError, ValueError, ImportError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc), 'partialOutputsMayRemain': True,
                          'nextAction': 'Inspect the specific dependency/target/log; preserve originals and propose missing capabilities, not a blind reinstall.'}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
