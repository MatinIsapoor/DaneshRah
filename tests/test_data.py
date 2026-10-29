"""Data-file tests: the shipped ``data/guides.json`` and the validator."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

import guide_validation
from guide_validation import is_safe_url, validate_guides

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "guides.json"

with open(DATA_PATH, "r", encoding="utf-8") as handle:
    GUIDES = json.load(handle)


def minimal_country(code: str = "testland") -> dict:
    return {
        code: {
            "name": "تست‌لند",
            "flag": "\U0001F1F9\U0001F1EA",
            "blurb": "یک کشور آزمایشی",
            "meta": {
                "capital": "پایتخت",
                "currency": "یورو",
                "language": "فارسی",
                "emergency": "۱۱۲",
                "region": "europe",
                "region_label": "اروپا",
            },
            "last_updated": "2026-01-01",
            "categories": {
                "shopping": {"title": "خرید", "items": [{"title": "سوپرمارکت", "content": "متن"}]},
                "housing": {"title": "مسکن", "items": [{"title": "خانه", "content": "متن"}]},
                "admin": {"title": "اداری", "items": [{"title": "اقامت", "content": "متن"}]},
                "work": {"title": "کار", "items": [{"title": "شغل", "content": "متن"}]},
            },
            "sources": [
                {"title": "منبع", "url": "https://example.com/", "cat": "work"}
            ],
        }
    }


class ValidatorTests(unittest.TestCase):
    def test_shipped_data_has_no_errors(self) -> None:
        issues = validate_guides(GUIDES)
        errors = [i for i in issues if i.severity == "error"]
        self.assertEqual(errors, [], "\n".join(str(e) for e in errors))

    def test_shipped_data_does_not_claim_a_single_shared_date(self) -> None:
        issues = validate_guides(GUIDES)
        warnings = [i for i in issues if i.severity == "warning"]
        self.assertFalse(
            any("share last_updated" in w.message for w in warnings),
            "reviewed countries must be allowed to carry a distinct date",
        )
        dates = {
            country["last_updated"]
            for code, country in GUIDES.items()
            if code != "general"
        }
        self.assertGreater(len(dates), 1)
        self.assertEqual(GUIDES["france"]["last_updated"], "2026-10-23")
        self.assertEqual(GUIDES["australia"]["last_updated"], "2026-10-23")

    def test_minimal_country_is_valid(self) -> None:
        issues = validate_guides(minimal_country())
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_missing_required_fields_are_reported(self) -> None:
        data = minimal_country()
        del data["testland"]["name"]
        del data["testland"]["meta"]["capital"]
        issues = validate_guides(data)
        errors = [str(i) for i in issues if i.severity == "error"]
        self.assertTrue(any("name" in e for e in errors))
        self.assertTrue(any("capital" in e for e in errors))

    def test_unsafe_urls_are_rejected(self) -> None:
        data = minimal_country()
        data["testland"]["sources"][0]["url"] = "javascript:alert(1)"
        data["testland"]["categories"]["work"]["items"][0]["link"] = "data:text/html,x"
        errors = [str(i) for i in validate_guides(data) if i.severity == "error"]
        self.assertTrue(any("javascript" in e for e in errors))
        self.assertTrue(any("data:text/html" in e for e in errors))

    def test_duplicate_item_titles_are_reported(self) -> None:
        data = minimal_country()
        items = data["testland"]["categories"]["work"]["items"]
        items.append({"title": items[0]["title"], "content": "تکراری"})
        warnings = [str(i) for i in validate_guides(data) if i.severity == "warning"]
        self.assertTrue(any("duplicate item title" in w for w in warnings))

    def test_invalid_and_future_dates_are_reported(self) -> None:
        data = minimal_country()
        data["testland"]["last_updated"] = "19-10-2026"
        errors = [str(i) for i in validate_guides(data) if i.severity == "error"]
        self.assertTrue(any("YYYY-MM-DD" in e for e in errors))

        data = minimal_country()
        data["testland"]["last_updated"] = "2099-01-01"
        warnings = [str(i) for i in validate_guides(data) if i.severity == "warning"]
        self.assertTrue(any("future" in w for w in warnings))

    def test_missing_category_is_reported(self) -> None:
        data = minimal_country()
        del data["testland"]["categories"]["work"]
        warnings = [str(i) for i in validate_guides(data) if i.severity == "warning"]
        self.assertTrue(any("missing category" in w for w in warnings))

    def test_malformed_markdown_is_reported(self) -> None:
        data = minimal_country()
        data["testland"]["categories"]["work"]["items"][0]["content"] = (
            "Broken [label](https://example.com/ link"
        )
        issues = validate_guides(data)
        self.assertTrue(
            any(i.severity == "warning" and "malformed" in i.message for i in issues)
        )

    def test_raw_html_in_content_is_reported(self) -> None:
        data = minimal_country()
        data["testland"]["categories"]["work"]["items"][0]["content"] = "<b>پررنگ</b>"
        issues = validate_guides(data)
        self.assertTrue(
            any(i.severity == "warning" and "raw HTML" in i.message for i in issues)
        )

    def test_is_safe_url(self) -> None:
        self.assertTrue(is_safe_url("https://example.com"))
        self.assertTrue(is_safe_url("http://example.com/path?x=1"))
        self.assertFalse(is_safe_url("javascript:alert(1)"))
        self.assertFalse(is_safe_url("data:text/html;base64,AA"))
        self.assertFalse(is_safe_url("/relative"))
        self.assertFalse(is_safe_url("https://example.com/\nSet-Cookie: x"))
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url(None))

    def test_cli_exit_codes(self) -> None:
        self.assertEqual(guide_validation.main([str(DATA_PATH)]), 0)
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.json"
            broken.write_text(
                json.dumps({"x": {"name": "بدون دسته", "last_updated": "2026-01-01"}}),
                encoding="utf-8",
            )
            self.assertEqual(guide_validation.main([str(broken)]), 1)


class ShippedDataTests(unittest.TestCase):
    def test_top_level_shape(self) -> None:
        self.assertIsInstance(GUIDES, dict)
        self.assertIn("general", GUIDES)
        self.assertGreaterEqual(len(GUIDES) - 1, 40)

    def test_every_source_url_is_http(self) -> None:
        for code, country in GUIDES.items():
            for source in country.get("sources", []) or []:
                with self.subTest(code=code, title=source.get("title")):
                    self.assertTrue(is_safe_url(source.get("url")))

    def test_every_item_link_is_http(self) -> None:
        for code, country in GUIDES.items():
            for category in country.get("categories", {}).values():
                for item in category.get("items", []):
                    link = item.get("link")
                    if link is None:
                        continue
                    with self.subTest(code=code, title=item.get("title")):
                        self.assertTrue(is_safe_url(link))

    def test_no_dangerous_schemes_in_the_file(self) -> None:
        raw = DATA_PATH.read_text(encoding="utf-8")
        for pattern in ("javascript:", "data:text/html", "onerror="):
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, raw)

    def test_last_updated_values_are_iso_dates(self) -> None:
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for code, country in GUIDES.items():
            with self.subTest(code=code):
                self.assertRegex(country["last_updated"], pattern)

    def test_emergency_numbers_contain_digits(self) -> None:
        for code, country in GUIDES.items():
            if code == "general":
                continue
            with self.subTest(code=code):
                self.assertRegex(country["meta"]["emergency"], r"[0-9۰-۹٠-٩]")

    def test_checklist_has_steps(self) -> None:
        arrival = GUIDES["general"]["categories"]["arrival"]
        self.assertGreaterEqual(len(arrival["items"]), 5)


class FranceContentTests(unittest.TestCase):
    """Regression tests for the 2026 corrections (APL, CROUS, student work, SMIC)."""

    def _france(self) -> dict:
        return GUIDES["france"]

    def test_crous_meal_item_uses_the_1_euro_rule_and_official_page(self) -> None:
        item = self._france()["categories"]["shopping"]["items"][3]
        content = item["content"]
        self.assertIn("۴ مه ۲۰۲۶", content)
        self.assertIn("Izly", content)
        self.assertIn(
            "etudiant.gouv.fr/fr/comment-beneficier-du-repas-crous-1-eu-3123",
            content,
        )
        self.assertNotIn("نرخ‌ها و شرایط هر سال عوض می‌شود", content)

    def test_apl_item_reflects_the_1_july_2026_rule(self) -> None:
        item = self._france()["categories"]["housing"]["items"][3]
        content = item["content"]
        self.assertIn("۱ ژوئیه ۲۰۲۶", content)
        self.assertIn("bourse sur critères sociaux", content)
        self.assertIn("apprentissage", content)
        self.assertIn("F1563", content)
        # the old, wrong claim must be gone
        self.assertNotIn("تقریباً همه‌ی دانشجویان", content)

    def test_student_work_item_links_the_student_work_page(self) -> None:
        item = self._france()["categories"]["work"]["items"][0]
        self.assertIn("F2713", item["content"])
        self.assertNotIn("F2300", item["content"])

    def test_smic_item_uses_the_current_rate_and_date(self) -> None:
        item = self._france()["categories"]["work"]["items"][1]
        self.assertIn("۱۲٫۳۱", item["content"])
        self.assertIn("۱ ژوئن ۲۰۲۶", item["content"])
        self.assertNotIn("ژانویه ۲۰۲۶", item["content"])

    def test_france_sources_use_the_canonical_domain(self) -> None:
        for source in self._france()["sources"]:
            with self.subTest(title=source.get("title")):
                self.assertNotIn("www.service-public.fr", source["url"])

    def test_crous_source_uses_the_direct_meal_page(self) -> None:
        urls = {source["url"] for source in self._france()["sources"]}
        self.assertIn(
            "https://www.etudiant.gouv.fr/fr/comment-beneficier-du-repas-crous-1-eu-3123",
            urls,
        )


class AustraliaContentTests(unittest.TestCase):
    def _australia(self) -> dict:
        return GUIDES["australia"]

    def test_minimum_wage_is_current(self) -> None:
        content = self._australia()["categories"]["work"]["items"][1]["content"]
        self.assertIn("۲۶٫۴۴", content)
        self.assertIn("۱ ژوئیه ۲۰۲۶", content)
        self.assertIn("fairwork.gov.au", content)

    def test_student_work_cap_links_home_affairs_not_minimum_wage(self) -> None:
        content = self._australia()["categories"]["work"]["items"][0]["content"]
        self.assertIn("۴۸", content)
        self.assertIn("immi.homeaffairs.gov.au", content)
        self.assertNotIn("minimum-wages", content)

    def test_housing_links_the_tenant_rights_page(self) -> None:
        items = self._australia()["categories"]["housing"]["items"]
        combined = "\n".join(item["content"] for item in items)
        self.assertIn("studyaustralia.gov.au", combined)
        self.assertNotIn("minimum-wages", combined)
        self.assertIn("Condition Report", combined)


class CitationIntegrityTests(unittest.TestCase):
    """Guards against known copy-paste citation mistakes found in the audit."""

    def test_unrelated_citations_are_not_reintroduced(self) -> None:
        bad = [
            ("australia", "housing", "minimum-wages"),
            ("turkey", "housing", "btk.gov.tr"),
            ("turkey", "work", "btk.gov.tr"),
            ("usa", "housing", "studyinthestates.dhs.gov"),
            ("canada", "shopping", "study-canada/work.html"),
            ("france", "housing", "crous-paris.fr"),
            ("egypt", "housing", "tra.gov.eg"),
            ("india", "housing", "indianfrro.gov.in"),
            ("new_zealand", "shopping", "immigration.govt.nz"),
        ]
        for code, category, fragment in bad:
            items = GUIDES[code]["categories"][category]["items"]
            for item in items:
                with self.subTest(code=code, category=category, title=item["title"]):
                    self.assertNotIn(fragment, item["content"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
