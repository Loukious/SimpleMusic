"""Regression checks for publication of installable, consistently signed Android APKs."""
from pathlib import Path
import re
import subprocess
import unittest

BASE = Path(__file__).resolve().parents[1]
WORKFLOW = BASE / ".github/workflows/fork-release.yml"


class ReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.yaml = WORKFLOW.read_text(encoding="utf-8")

    def test_signed_universal_apk_selected_by_exact_name(self):
        self.assertIn('APK="androidApp/build/outputs/apk/release/SimpleMusic-foss-universal-release.apk"', self.yaml)
        self.assertNotIn("APK=$(find ", self.yaml)

    def test_missing_key_fails_instead_of_generating_temporary_key(self):
        self.assertIn('if [ -z "$BASE_64_SIGNING_KEY" ]; then', self.yaml)
        self.assertIn("refusing a temporary signature", self.yaml)
        self.assertNotIn('keytool -genkeypair', self.yaml)

    def test_previous_release_signing_identity_pinned(self):
        self.assertIn("3f6d5b9742bc2510c1f7a1f2cf55fcefab57219c4e778e2b4ce129b8b0ce476a", self.yaml)
        self.assertIn("-storepass:env KEYSTORE_PASSWORD", self.yaml)
        self.assertIn('if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then', self.yaml)
        self.assertIn('grep -Fq "Signer #1 certificate SHA-256 digest: $EXPECTED_SHA256"', self.yaml)

    def test_required_abis_guarded(self):
        for arch in ("arm64-v8a", "armeabi-v7a", "x86_64"):
            self.assertIn(repr(arch), self.yaml)
        self.assertIn("required.issubset(abis)", self.yaml)

    def test_repair_is_manual_and_after_validation(self):
        self.assertIn("repair_existing_release:", self.yaml)
        self.assertIn("default: false", self.yaml)
        self.assertIn('gh release upload "v${VERSION}" "$ASSET" --clobber', self.yaml)
        self.assertLess(self.yaml.index("required.issubset(abis)"), self.yaml.index('gh release upload "v${VERSION}"'))

    def test_embedded_bash_scripts_parse(self):
        # All run blocks have 10-space literal-block indentation in this workflow.
        scripts = re.findall(r"^        run: \|\n((?:(?: {10}.*|)\n)+)", self.yaml, flags=re.M)
        self.assertGreaterEqual(len(scripts), 6)
        for n, block in enumerate(scripts):
            script = "\n".join(line[10:] if line.startswith(" "*10) else line for line in block.splitlines())
            check = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
            self.assertEqual(check.returncode, 0, f"script {n}: {check.stderr}")


if __name__ == "__main__":
    unittest.main()
