"""Real path/launch boundaries; browser UI is checked separately on actual file URLs."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import jury_tutorial as tutorial


class TutorialLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jury tutorial ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '中文 skill'
        self.directory = self.root / 'assets' / 'tutorial'
        self.directory.mkdir(parents=True)
        for name in tutorial.TUTORIAL_FILES:
            (self.directory / name).write_text('local tutorial', encoding='utf-8')

    def test_browser_uses_absolute_encoded_file_uri_and_does_not_launch_folder(self):
        with patch.object(tutorial.webbrowser, 'open', return_value=True) as browser, patch.object(tutorial, '_open_folder') as folder:
            result = tutorial.open_tutorial(self.root)
        browser.assert_called_once_with((self.directory / 'index.html').as_uri(), new=2)
        folder.assert_not_called()
        self.assertTrue(result['passed'])
        self.assertEqual(result['state'], 'browser-launch-requested')
        self.assertFalse(result['actualDisplayVerified'])
        self.assertFalse(result['modelInvoked'])

    def test_declined_browser_falls_back_once_to_the_tutorial_folder(self):
        with patch.object(tutorial.webbrowser, 'open', return_value=False) as browser, patch.object(tutorial, '_open_folder', return_value=True) as folder:
            result = tutorial.open_tutorial(self.root)
        self.assertEqual(browser.call_count, 1)
        folder.assert_called_once_with(self.directory)
        self.assertEqual(result['state'], 'folder-launch-requested')
        self.assertTrue(result['fallbackUsed'])
        self.assertFalse(result['browserLaunchAccepted'])
        self.assertFalse(result['actualDisplayVerified'])

    def test_browser_exception_can_still_open_folder(self):
        with patch.object(tutorial.webbrowser, 'open', side_effect=OSError('no browser')), patch.object(tutorial, '_open_folder', return_value=True):
            result = tutorial.open_tutorial(self.root)
        self.assertTrue(result['passed'])
        self.assertEqual(result['state'], 'folder-launch-requested')
        self.assertIn('browser-launch-failed', result['failures'])

    def test_explicit_folder_never_opens_browser(self):
        with patch.object(tutorial.webbrowser, 'open') as browser, patch.object(tutorial, '_open_folder', return_value=True) as folder:
            result = tutorial.open_tutorial(self.root, folder=True)
        browser.assert_not_called()
        folder.assert_called_once_with(self.directory)
        self.assertTrue(result['passed'])
        self.assertFalse(result['fallbackUsed'])

    def test_dry_run_does_not_launch_either_path(self):
        with patch.object(tutorial.webbrowser, 'open') as browser, patch.object(tutorial, '_open_folder') as folder:
            result = tutorial.open_tutorial(self.root, dry_run=True)
        browser.assert_not_called()
        folder.assert_not_called()
        self.assertEqual(result['state'], 'ready-not-launched')
        self.assertFalse(result['browserLaunchAccepted'])
        self.assertFalse(result['folderLaunchAccepted'])

    def test_missing_css_refuses_false_ready_and_does_not_launch(self):
        (self.directory / 'tutorial.css').unlink()
        with patch.object(tutorial.webbrowser, 'open') as browser, patch.object(tutorial, '_open_folder') as folder:
            result = tutorial.open_tutorial(self.root)
        browser.assert_not_called()
        folder.assert_not_called()
        self.assertFalse(result['passed'])
        self.assertEqual(result['missing'], ['tutorial.css'])

    def test_both_launch_paths_fail_without_a_success_claim(self):
        with patch.object(tutorial.webbrowser, 'open', return_value=False), patch.object(tutorial, '_open_folder', side_effect=OSError('no desktop')):
            result = tutorial.open_tutorial(self.root)
        self.assertFalse(result['passed'])
        self.assertEqual(result['state'], 'launch-failed')
        self.assertFalse(result['actualDisplayVerified'])
        self.assertEqual(Path(result['tutorialPath']), self.directory / 'index.html')

    def test_folder_timeout_is_failure_not_a_hang_or_browser_retry(self):
        with patch.object(tutorial.webbrowser, 'open', return_value=False) as browser, patch.object(tutorial, '_open_folder', side_effect=subprocess.TimeoutExpired('xdg-open', 10)) as folder:
            result = tutorial.open_tutorial(self.root)
        self.assertFalse(result['passed'])
        self.assertEqual(browser.call_count, 1)
        self.assertEqual(folder.call_count, 1)

    def test_cli_dry_run_resolves_its_package_not_current_directory(self):
        expected = Path(tutorial.__file__).resolve().parents[1] / 'assets' / 'tutorial' / 'index.html'
        with patch.object(tutorial.sys, 'stdout') as stream:
            with patch.object(tutorial.webbrowser, 'open') as browser:
                code = tutorial.main(['--dry-run'])
        rendered = ''.join(str(call.args[0]) for call in stream.write.call_args_list)
        record = json.loads(rendered)
        self.assertEqual(Path(record['tutorialPath']), expected)
        browser.assert_not_called()
        self.assertEqual(code, 0 if expected.is_file() else 2)


if __name__ == '__main__':
    unittest.main()
