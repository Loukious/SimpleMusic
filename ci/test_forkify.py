"""Regression tests for the fork's independently signed Android APKs."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forkify


class ForkSigningCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        entries = [e for e in forkify.EXACT_EDITS if e[0].endswith('/MainActivity.kt')]
        assert len(entries) == 1, 'Exactly one shared MainActivity override is required'
        cls.edit = entries[0]

    def run_script(self, original):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / self.edit[0]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)
            old_edits, old_argv = forkify.EXACT_EDITS, sys.argv
            forkify.EXACT_EDITS = [self.edit]
            sys.argv = ['forkify.py', td]
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    result = forkify.main()
                    output = path.read_bytes()
                    repeat = forkify.main() if result == 0 else None
                    after_repeat = path.read_bytes()
            finally:
                forkify.EXACT_EDITS, sys.argv = old_edits, old_argv
            return result, output, repeat, after_repeat

    def test_release_check_removed(self):
        status, output, _, _ = self.run_script(self.edit[1].encode())
        self.assertEqual(status, 0)
        self.assertNotIn(b'viewModel.checkOfficialBuild(', output)
        self.assertIn(b'Fork releases are independently signed', output)

    def test_idempotence(self):
        status, first, second_status, second = self.run_script(self.edit[1].encode())
        self.assertEqual((status, second_status), (0, 0))
        self.assertEqual(first, second)

    def test_crlf_is_preserved(self):
        status, output, _, _ = self.run_script(self.edit[1].replace('\n', '\r\n').encode())
        self.assertEqual(status, 0)
        self.assertIn(b'\r\n', output)
        self.assertNotIn(b'\n', output.replace(b'\r\n', b''))

    def test_upstream_drift_fails_closed(self):
        original = self.edit[1].replace('viewModel.checkOfficialBuild(', 'viewModel.changedAPI(')
        status, output, _, _ = self.run_script(original.encode())
        self.assertEqual(status, 1)
        self.assertEqual(output, original.encode())

    def test_other_activity_code_is_untouched(self):
        original = ('BEFORE\n' + self.edit[1] + '\nAFTER\n').encode()
        status, output, _, _ = self.run_script(original)
        self.assertEqual(status, 0)
        self.assertTrue(output.startswith(b'BEFORE\n'))
        self.assertTrue(output.endswith(b'\nAFTER\n'))


if __name__ == '__main__':
    unittest.main()
