"""HTTP-level tests for the DaneshRah Flask app (standard-library unittest).

Run from the project root:

    python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import json
import re
import unittest
from unittest import mock

import app as app_module


class AppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app_module.app.config.update(TESTING=True)
        cls.client = app_module.app.test_client()

    def get(self, path: str, **kwargs):
        return self.client.get(path, **kwargs)


class TestRoutes(AppTestCase):
    def test_public_pages_return_200(self) -> None:
        paths = [
            "/",
            "/search",
            "/checklist",
            "/emergency",
            "/about",
            "/robots.txt",
            "/sitemap.xml",
            "/health",
            "/ping",
            "/api/countries",
            "/api/search?q=syym",
            "/country/france",
            "/country/france/work",
            "/country/france/housing",
            "/country/general",
            "/country/general/arrival",
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 200, path)

    def test_unknown_paths_return_404(self) -> None:
        for path in ["/nope", "/country/atlantis", "/country/france/nope", "/api/nope"]:
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 404, path)

    def test_post_to_read_only_route_is_405(self) -> None:
        self.assertEqual(self.client.post("/").status_code, 405)

    def test_health_payload(self) -> None:
        for path in ("/health", "/ping"):
            payload = self.get(path).get_json()
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["app"], "DaneshRah")

    def test_api_countries_shape(self) -> None:
        data = self.get("/api/countries").get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 40)
        codes = {row["code"] for row in data}
        self.assertNotIn("general", codes)
        for row in data:
            self.assertTrue(row["name"])
            self.assertIn("region", row)
            self.assertIn("last_updated", row)

    def test_api_search_limit_is_clamped(self) -> None:
        payload = self.get("/api/search?q=ودیعه&limit=9999").get_json()
        self.assertLessEqual(len(payload["results"]), app_module.MAX_SEARCH_LIMIT)
        self.assertEqual(payload["limit"], app_module.MAX_SEARCH_LIMIT)

        payload = self.get("/api/search?q=ودیعه&limit=abc").get_json()
        self.assertEqual(payload["limit"], app_module.DEFAULT_SEARCH_LIMIT)
        self.assertTrue(payload["results"])

        payload = self.get("/api/search?q=ودیعه&limit=-5").get_json()
        self.assertEqual(payload["limit"], 1)
        self.assertLessEqual(len(payload["results"]), 1)

    def test_api_search_without_query_is_empty(self) -> None:
        payload = self.get("/api/search").get_json()
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["query"], "")

    def test_api_search_rejects_oversized_query(self) -> None:
        payload = self.get("/api/search?q=" + "a" * 500).get_json()
        self.assertEqual(len(payload["query"]), app_module.MAX_QUERY_LENGTH)
        self.assertTrue(payload["truncated"])


class TestSecurityHeaders(AppTestCase):
    def test_baseline_headers(self) -> None:
        headers = self.get("/").headers
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("Referrer-Policy", headers)
        self.assertIn("camera=()", headers["Permissions-Policy"])

    def test_csp_is_present_and_matches_the_inline_script_nonce(self) -> None:
        response = self.get("/")
        csp = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("https://flagcdn.com", csp)

        script_src = [part for part in csp.split(";") if part.strip().startswith("script-src")][0]
        self.assertNotIn("unsafe-inline", script_src)
        self.assertIn("'nonce-", script_src)

        body = response.get_data(as_text=True)
        nonce = re.search(r'<script nonce="([^"]+)"', body)
        self.assertIsNotNone(nonce, "the inline bootstrap script must carry a nonce")
        self.assertIn("'nonce-%s'" % nonce.group(1), script_src)

    def test_csp_nonce_differs_between_requests(self) -> None:
        first = self.get("/").headers["Content-Security-Policy"]
        second = self.get("/").headers["Content-Security-Policy"]
        self.assertNotEqual(first, second)

    def test_hsts_only_on_https(self) -> None:
        self.assertIsNone(self.get("/").headers.get("Strict-Transport-Security"))
        https_response = self.get("/", base_url="https://localhost")
        self.assertIn("max-age=", https_response.headers["Strict-Transport-Security"])

    def test_no_inline_event_handlers_in_rendered_pages(self) -> None:
        for path in ("/", "/country/france", "/country/france/work", "/search", "/checklist", "/emergency"):
            body = self.get(path).get_data(as_text=True)
            with self.subTest(path=path):
                self.assertNotIn("onerror=", body)
                self.assertNotIn("onload=", body)
                self.assertNotIn("javascript:", body)

    def test_health_is_not_cached(self) -> None:
        self.assertEqual(self.get("/health").headers.get("Cache-Control"), "no-store")

    def test_security_headers_on_error_pages(self) -> None:
        response = self.get("/definitely-not-here")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("Content-Security-Policy", response.headers)

    def test_no_inline_styles_are_rendered(self) -> None:
        paths = (
            "/",
            "/about",
            "/country/france",
            "/country/france/work",
            "/search",
            "/checklist",
            "/emergency",
        )
        for path in paths:
            body = self.get(path).get_data(as_text=True)
            with self.subTest(path=path):
                self.assertNotIn(" style=", body)
                self.assertNotIn("style='", body)
                self.assertNotIn("style=\"", body)

    def test_csp_does_not_allow_inline_styles(self) -> None:
        csp = self.get("/").headers["Content-Security-Policy"]
        style_src = [part for part in csp.split(";") if part.strip().startswith("style-src")][0]
        self.assertNotIn("unsafe-inline", style_src)
        self.assertIn("'self'", style_src)


class TestDiscovery(AppTestCase):
    def test_about_page_is_indexable_and_has_one_creator_credit(self) -> None:
        response = self.get("/about")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-Robots-Tag", response.headers)
        self.assertIn('id="creator"', body)
        self.assertEqual(body.count("متین"), 1)
        self.assertNotIn("متین", self.get("/").get_data(as_text=True))

    def test_canonical_uses_the_configured_site_url_not_the_host_header(self) -> None:
        response = self.get("/", headers={"Host": "evil.example"})
        body = response.get_data(as_text=True)
        self.assertIn(
            f'<link rel="canonical" href="{app_module.SITE_URL}/">',
            body,
        )
        self.assertNotIn("evil.example", body)

        about = self.get("/about", headers={"Host": "evil.example"}).get_data(as_text=True)
        self.assertIn(
            f'<link rel="canonical" href="{app_module.SITE_URL}/about">',
            about,
        )

    def test_robots_points_to_the_sitemap_and_blocks_private_routes(self) -> None:
        response = self.get("/robots.txt")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"Sitemap: {app_module.SITE_URL}/sitemap.xml", body)
        for private in ("/api/", "/health", "/search"):
            self.assertIn(f"Disallow: {private}", body)
        self.assertEqual(response.headers["Cache-Control"], "public, max-age=300")

    def test_sitemap_lists_public_pages_and_no_generic_duplicate(self) -> None:
        response = self.get("/sitemap.xml")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response.headers["Content-Type"])
        self.assertIn(f"<loc>{app_module.SITE_URL}/about</loc>", body)
        self.assertIn(f"<loc>{app_module.SITE_URL}/country/france</loc>", body)
        self.assertIn(f"<loc>{app_module.SITE_URL}/country/france/housing</loc>", body)
        self.assertNotIn(f"<loc>{app_module.SITE_URL}/country/general</loc>", body)
        self.assertNotIn(f"<loc>{app_module.SITE_URL}/search</loc>", body)
        self.assertIn("<lastmod>2026-10-23</lastmod>", body)

    def test_search_and_generic_page_are_noindex(self) -> None:
        for path in ("/search", "/country/general", "/country/general/arrival"):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, follow")
                body = response.get_data(as_text=True)
                self.assertIn('name="robots" content="noindex, follow"', body)
                self.assertNotIn('name="robots" content="index, follow"', body)

    def test_health_reports_degraded_and_503_when_data_breaks(self) -> None:
        with mock.patch.object(
            app_module, "get_guides", side_effect=RuntimeError("broken data")
        ):
            response = self.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "degraded")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex")

    def test_public_cache_policy(self) -> None:
        self.assertEqual(
            self.get("/sitemap.xml").headers["Cache-Control"], "public, max-age=300"
        )
        self.assertEqual(
            self.get("/api/search?q=ودیعه").headers["Cache-Control"], "no-store"
        )

    def test_stats_are_rendered_as_numbers_not_dict_methods(self) -> None:
        guides = app_module.get_guides()
        stats = app_module.get_stats(guides)
        expected_items = app_module.fa_digits(stats["items"])
        expected_sources = app_module.fa_digits(stats["sources"])
        for path in ("/", "/about"):
            with self.subTest(path=path):
                body = self.get(path).get_data(as_text=True)
                self.assertNotIn("built-in method", body)
                self.assertNotIn("dict object", body)
                self.assertIn(expected_items, body)
                self.assertIn(expected_sources, body)

        country_body = self.get("/country/france").get_data(as_text=True)
        self.assertNotIn("built-in method", country_body)
        self.assertNotIn("dict object", country_body)


class TestSearch(AppTestCase):
    def test_normalize_fa_variants(self) -> None:
        normalize = app_module.normalize_fa
        self.assertEqual(normalize("سیم‌کارت"), normalize("سیم کارت"))
        self.assertEqual(normalize("۹۱۱"), "911")
        self.assertEqual(normalize("٩١١"), "911")
        self.assertEqual(normalize("کتاب"), normalize("كتاب"))
        self.assertEqual(normalize("وُدیعَه"), normalize("ودیعه"))

    def test_search_is_insensitive_to_spacing(self) -> None:
        zwnj = app_module.search_guides("سیم‌کارت")
        space = app_module.search_guides("سیم کارت")
        plain = app_module.search_guides("سیمکارت")
        self.assertTrue(zwnj)
        self.assertEqual(
            [(r["country_code"], r["item_title"]) for r in zwnj],
            [(r["country_code"], r["item_title"]) for r in space],
        )
        self.assertTrue(plain, "the space-less spelling must still find results")

    def test_search_finds_country_by_name(self) -> None:
        results = app_module.search_guides("آلمان")
        self.assertTrue(results)
        self.assertIn("germany", {r["country_code"] for r in results})

    def test_search_ranks_title_matches_first(self) -> None:
        results = app_module.search_guides("ودیعه")
        self.assertTrue(results)
        self.assertEqual(results[0]["matched_in"], "title")

    def test_search_with_no_match_returns_empty(self) -> None:
        self.assertEqual(app_module.search_guides("zzzzqqq"), [])
        self.assertEqual(app_module.search_guides(""), [])
        self.assertEqual(app_module.search_guides("a"), [])

    def test_search_limit_is_bounded(self) -> None:
        self.assertLessEqual(len(app_module.search_guides("ا", limit=0)), 1)
        self.assertLessEqual(len(app_module.search_guides("سیم", limit=10_000)), app_module.MAX_SEARCH_LIMIT)


    def test_search_results_deep_link_to_the_matching_item(self) -> None:
        body = self.get("/search?q=ودیعه").get_data(as_text=True)
        self.assertRegex(
            body,
            r'href="/country/[a-z_]+/(?:shopping|housing|admin|work)#item-\d+"',
        )

    def test_search_limit_note_uses_the_configured_limit(self) -> None:
        body = self.get("/search?q=" + "a" * 500).get_data(as_text=True)
        self.assertIn(f"{app_module.MAX_QUERY_LENGTH}", body)
        self.assertNotIn(f"به {200}", body)

    def test_general_search_results_do_not_emit_empty_flag_images(self) -> None:
        body = self.get("/search?q=فرودگاه").get_data(as_text=True)
        self.assertIn("قدم‌های اول", body)
        self.assertNotIn('src=""', body)


class TestMarkupAccessibility(AppTestCase):
    def test_checklist_has_one_visible_label_per_checkbox(self) -> None:
        body = self.get("/checklist").get_data(as_text=True)
        inputs = body.count("data-check-input")
        labels = body.count('class="check-label"')
        self.assertGreater(inputs, 0)
        self.assertEqual(labels, inputs)
        self.assertNotIn("check-box-label", body)


class TestInputHandling(AppTestCase):
    def test_query_length_is_capped(self) -> None:
        response = self.get("/search?q=" + "a" * 500)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertNotIn("a" * 300, body)
        self.assertIn("کوتاه شد", body)

    def test_query_is_escaped(self) -> None:
        response = self.get("/search?q=<script>alert(1)</script>")
        body = response.get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_control_characters_are_removed(self) -> None:
        cleaned = app_module.clean_query("a\x00b\x07 c")
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("\x07", cleaned)
        self.assertEqual(cleaned, "ab c")

    def test_clean_query_collapses_whitespace(self) -> None:
        self.assertEqual(app_module.clean_query("  a   b  "), "a b")


class TestSafeUrls(AppTestCase):
    def test_safe_url_filter(self) -> None:
        self.assertEqual(app_module.safe_url("https://example.com/x"), "https://example.com/x")
        self.assertEqual(app_module.safe_url("http://example.com"), "http://example.com")
        for bad in [
            "javascript:alert(1)",
            "data:text/html;base64,PHNjcmlwdD4=",
            "/relative/path",
            "https://example.com/\nset-cookie",
            "",
            None,
            42,
        ]:
            with self.subTest(value=bad):
                self.assertEqual(app_module.safe_url(bad), "")

    def test_rendered_source_links_are_http_only(self) -> None:
        for code in ("france", "germany", "canada", "uae"):
            body = self.get(f"/country/{code}").get_data(as_text=True)
            for href in re.findall(r'href="([^"]+)"', body):
                if href.startswith("http"):
                    with self.subTest(code=code, href=href):
                        self.assertTrue(
                            href.startswith("http://") or href.startswith("https://"),
                            f"unexpected external scheme in {href}",
                        )


class TestErrorHandling(AppTestCase):
    def test_404_page_renders(self) -> None:
        response = self.get("/definitely-not-here")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Content-Security-Policy", response.headers)

    def test_unhandled_error_returns_500_page(self) -> None:
        app_module.app.config["PROPAGATE_EXCEPTIONS"] = False
        try:
            with mock.patch.object(
                app_module, "get_guides", side_effect=RuntimeError("boom")
            ):
                response = self.get("/")
        finally:
            app_module.app.config["PROPAGATE_EXCEPTIONS"] = True
        self.assertEqual(response.status_code, 500)
        body = response.get_data(as_text=True)
        self.assertNotIn("boom", body)
        self.assertIn("Content-Security-Policy", response.headers)


class TestDataConsistency(AppTestCase):
    def test_stats_match_the_data_file(self) -> None:
        guides = app_module.get_guides()
        stats = app_module.get_stats(guides)
        countries = [k for k in guides if k != "general"]
        self.assertEqual(stats["countries"], len(countries))
        expected_items = sum(
            len(cat.get("items", []))
            for code in countries
            for cat in guides[code].get("categories", {}).values()
        ) + sum(
            len(cat.get("items", []))
            for cat in guides.get("general", {}).get("categories", {}).values()
        )
        self.assertEqual(stats["items"], expected_items)

    def test_every_country_has_the_four_categories(self) -> None:
        guides = app_module.get_guides()
        for code, country in guides.items():
            if code == "general":
                continue
            with self.subTest(code=code):
                self.assertEqual(
                    set(country.get("categories", {})),
                    {"shopping", "housing", "admin", "work"},
                )

    def test_cache_reload_returns_equal_data(self) -> None:
        before = app_module.get_guides()
        after = app_module.get_guides(force_reload=True)
        self.assertEqual(list(before.keys()), list(after.keys()))

    def test_api_is_valid_json(self) -> None:
        response = self.get("/api/countries")
        self.assertEqual(response.headers["Content-Type"], "application/json")
        json.loads(response.get_data(as_text=True))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
