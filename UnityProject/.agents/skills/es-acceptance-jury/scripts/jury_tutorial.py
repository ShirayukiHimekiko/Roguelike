"""Request the bundled offline tutorial in a browser; use its folder as a fallback.

Launch acceptance is reported separately from actual visible display. No model,
server, installation, global settings or product files are changed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import webbrowser


TUTORIAL_FILES = ('index.html', 'tutorial.css', 'tutorial.js')


def _open_folder(path: Path) -> bool:
    if os.name == 'nt':
        os.startfile(str(path))
    else:
        subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       timeout=10)
    return True


def open_tutorial(package_root: Path | None = None, *, folder: bool = False,
                  dry_run: bool = False) -> dict:
    root = Path(package_root).resolve() if package_root is not None else Path(__file__).resolve().parents[1]
    directory = root / 'assets' / 'tutorial'
    target = directory / 'index.html'
    result = dict(tutorialPath=str(target), folderPath=str(directory), fileUri=target.as_uri(),
                  actualDisplayVerified=False, modelInvoked=False, wrote=False)
    missing = [name for name in TUTORIAL_FILES if not (directory / name).is_file()]
    if missing:
        return dict(result, passed=False, state='missing-tutorial-assets', missing=missing,
                    browserLaunchAccepted=False, folderLaunchAccepted=False)
    if dry_run:
        return dict(result, passed=True, state='ready-not-launched',
                    requestedMode='folder' if folder else 'browser-first',
                    browserLaunchAccepted=False, folderLaunchAccepted=False)
    failures = []
    if not folder:
        try:
            if webbrowser.open(target.as_uri(), new=2):
                return dict(result, passed=True, state='browser-launch-requested',
                            browserLaunchAccepted=True, folderLaunchAccepted=False)
            failures.append('browser-did-not-accept-launch')
        except (OSError, webbrowser.Error):
            failures.append('browser-launch-failed')
    try:
        if _open_folder(directory):
            return dict(result, passed=True, state='folder-launch-requested',
                        browserLaunchAccepted=False, folderLaunchAccepted=True,
                        fallbackUsed=not folder, failures=failures)
        failures.append('folder-did-not-accept-launch')
    except (OSError, subprocess.SubprocessError):
        failures.append('folder-launch-failed')
    return dict(result, passed=False, state='launch-failed', failures=failures,
                browserLaunchAccepted=False, folderLaunchAccepted=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', action='store_true', help='Request the tutorial folder directly.')
    parser.add_argument('--dry-run', action='store_true', help='Resolve and check bundled files without opening anything.')
    args = parser.parse_args(argv)
    result = open_tutorial(folder=args.folder, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
