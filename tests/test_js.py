"""Runs the Node-based unit tests for the front-end helpers.

Node is optional: when it is not installed the test is skipped instead of
failing the Python suite.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS_TEST = ROOT / "tests" / "js_utils.test.js"
APP_JS = ROOT / "static" / "app.js"


class NodeTestTests(unittest.TestCase):
    def test_node_is_available(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        result = subprocess.run(
            [node, "--test", str(JS_TEST)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"node --test failed:\n{result.stdout}\n{result.stderr}",
        )


class AppJsStaticTests(unittest.TestCase):
    """Cheap guards for the patterns that caused real bugs."""

    def setUp(self) -> None:
        self.source = APP_JS.read_text(encoding="utf-8")

    def test_copy_uses_the_shared_helper(self) -> None:
        self.assertIn("DaneshRahUtils", self.source)
        self.assertIn("copyText(url)", self.source)

    def test_copy_does_not_report_success_on_failure(self) -> None:
        # the old code called done() for both resolve and reject
        self.assertNotIn(".then(done, done)", self.source)
        self.assertIn("کپی نشد", self.source)

    def test_scroll_work_is_throttled(self) -> None:
        self.assertIn("scrollQueued", self.source)
        self.assertIn("requestAnimationFrame(updateScrollUI)", self.source)

    def test_no_html_injection(self) -> None:
        for pattern in ("innerHTML", "insertAdjacentHTML", "document.write"):
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, self.source)

    def test_mobile_menu_updates_aria_state(self) -> None:
        self.assertIn("setAttribute('aria-expanded'", self.source)

    def test_no_inline_event_handlers_in_js(self) -> None:
        self.assertNotIn("onerror", self.source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
