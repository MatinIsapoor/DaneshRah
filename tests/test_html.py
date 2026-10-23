"""HTML semantics / accessibility regression tests (standard-library only).

The pages are parsed with :mod:`html.parser` so the checks do not depend on a
third-party HTML validator.
"""

from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser

import app as app_module

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class PageInspector(HTMLParser):
    """Collects the structural facts the tests care about."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict]] = []
        self.headings: list[str] = []
        self.nested_buttons: list[str] = []
        self.links_with_role: list[dict] = []
        self.images_without_alt: list[str] = []
        self.external_links_without_noopener: list[str] = []
        self.checkbox_inputs: list[dict] = []
        self.labels: list[dict] = []
        self.roles_with_interactive_children: list[str] = []
        self.buttons: list[dict] = []
        self.ids: set[str] = set()
        self.guide_heads: list[dict] = []
        self.toc_links: list[dict] = []
        self.aria_controls: list[str] = []
        self.duplicate_ids: list[str] = []

    # -- helpers ---------------------------------------------------------
    def _ancestors(self) -> list[str]:
        return [tag for tag, _ in self.stack]

    def _has_interactive_ancestor(self, tags: tuple[str, ...]) -> bool:
        return any(tag in tags for tag in self._ancestors())

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag: str, attrs_list) -> None:
        attrs = dict(attrs_list)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                self.duplicate_ids.append(attrs["id"])
            self.ids.add(attrs["id"])
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(tag)
        if tag == "button":
            if self._has_interactive_ancestor(("button", "a")):
                self.nested_buttons.append(attrs.get("id", "<anonymous>"))
            self.buttons.append(attrs)
            if "data-guide-head" in attrs:
                self.guide_heads.append(attrs)
        if tag == "a":
            if "role" in attrs:
                self.links_with_role.append(attrs)
            href = attrs.get("href", "")
            if href.startswith("http") and "noopener" not in attrs.get("rel", ""):
                self.external_links_without_noopener.append(href)
            if "data-toc-link" in attrs:
                self.toc_links.append({"attrs": attrs, "ancestors": self._ancestors()})
        if tag == "img" and "alt" not in attrs:
            self.images_without_alt.append(attrs.get("src", "<no src>"))
        if tag == "input" and attrs.get("type") == "checkbox":
            self.checkbox_inputs.append(attrs)
        if tag == "label":
            self.labels.append(attrs)
        if "aria-controls" in attrs:
            self.aria_controls.append(attrs["aria-controls"])
        if tag not in VOID_TAGS:
            self.stack.append((tag, attrs))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)


class HtmlSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app_module.app.config.update(TESTING=True)
        cls.client = app_module.app.test_client()
        cls.paths = [
            "/",
            "/country/france",
            "/country/france/work",
            "/country/general/arrival",
            "/search?q=%D8%B3%DB%8C%D9%85",
            "/checklist",
            "/emergency",
        ]
        cls.pages = {}
        for path in cls.paths:
            response = cls.client.get(path)
            assert response.status_code == 200, path
            body = response.get_data(as_text=True)
            inspector = PageInspector()
            inspector.feed(body)
            cls.pages[path] = (body, inspector)

    def test_no_nested_interactive_elements(self) -> None:
        for path, (_body, inspector) in self.pages.items():
            with self.subTest(path=path):
                self.assertEqual(inspector.nested_buttons, [])

    def test_links_do_not_carry_list_roles(self) -> None:
        for path, (_body, inspector) in self.pages.items():
            with self.subTest(path=path):
                self.assertEqual(inspector.links_with_role, [])

    def test_heading_levels_never_skip_a_step(self) -> None:
        for path, (_body, inspector) in self.pages.items():
            with self.subTest(path=path):
                levels = [int(tag[1]) for tag in inspector.headings]
                self.assertTrue(levels)
                self.assertEqual(levels.count(1), 1, "exactly one h1 per page")
                for previous, current in zip(levels, levels[1:]):
                    self.assertLessEqual(
                        current, previous + 1, f"heading jump {previous}->{current}"
                    )

    def test_images_have_alt_attributes(self) -> None:
        for path, (_body, inspector) in self.pages.items():
            with self.subTest(path=path):
                self.assertEqual(inspector.images_without_alt, [])

    def test_external_links_open_safely(self) -> None:
        for path, (_body, inspector) in self.pages.items():
            with self.subTest(path=path):
                self.assertEqual(inspector.external_links_without_noopener, [])

    def test_no_duplicate_ids(self) -> None:
        for path, (_body, inspector) in self.pages.items():
            with self.subTest(path=path):
                self.assertEqual(inspector.duplicate_ids, [])

    def test_guide_accordion_uses_a_native_button(self) -> None:
        body, inspector = self.pages["/country/france/work"]
        self.assertTrue(inspector.guide_heads)
        for attrs in inspector.guide_heads:
            self.assertEqual(attrs.get("aria-expanded"), "true")
            self.assertIn("aria-controls", attrs)
            self.assertIn(attrs["aria-controls"], inspector.ids)
        # the old markup put a button inside a role="button" wrapper
        self.assertNotIn('role="button"', body)
        self.assertIn('class="g-head-btn"', body)

    def test_toc_entries_are_list_items(self) -> None:
        _body, inspector = self.pages["/country/france/work"]
        self.assertTrue(inspector.toc_links)
        for entry in inspector.toc_links:
            self.assertIn("li", entry["ancestors"])

    def test_checklist_uses_native_checkboxes(self) -> None:
        body, inspector = self.pages["/checklist"]
        self.assertTrue(inspector.checkbox_inputs)
        self.assertNotIn('role="checkbox"', body)
        label_targets = {label.get("for") for label in inspector.labels}
        for attrs in inspector.checkbox_inputs:
            self.assertIn("id", attrs)
            self.assertIn(attrs["id"], label_targets)

    def test_emergency_filter_covers_every_column(self) -> None:
        body, _inspector = self.pages["/emergency"]
        row = re.search(r'data-search="([^"]+)"', body)
        self.assertIsNotNone(row)
        fields = row.group(1).split()
        # name + emergency + capital + currency + language + region
        self.assertGreaterEqual(len(fields), 6)

    def test_search_results_have_no_double_ellipsis(self) -> None:
        body, _inspector = self.pages["/search?q=%D8%B3%DB%8C%D9%85"]
        self.assertNotIn("\u2026\u2026", body)

    def test_checklist_progressbar_is_exposed(self) -> None:
        body, _inspector = self.pages["/checklist"]
        self.assertIn('role="progressbar"', body)
        self.assertIn("aria-valuenow", body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
