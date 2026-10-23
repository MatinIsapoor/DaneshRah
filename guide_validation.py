"""Standalone validator for ``data/guides.json``.

Checks the structural contract of the content file so that broken data is
caught before it reaches the rendered pages:

* required fields / types for countries, categories, items and sources
* duplicate item titles inside a category
* URL scheme validation for source links, item links and Markdown links
* well-formed Markdown links, no stray HTML markup
* ISO ``YYYY-MM-DD`` dates that are not in the future
* cross-file consistency (shared ``last_updated`` value, country names)

Run it from the project root::

    python guide_validation.py            # validates data/guides.json
    python guide_validation.py path.json  # validates another file

Exit code is ``1`` when at least one *error* was found, ``0`` otherwise
(warnings never fail the run).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

__all__ = [
    "Issue",
    "validate_guides",
    "is_safe_url",
    "main",
]

DATA_PATH = Path(__file__).parent / "data" / "guides.json"

#: Category codes the app knows how to render.
COUNTRY_CATEGORIES = ("shopping", "housing", "admin", "work")
GENERAL_CATEGORIES = ("arrival",)
KNOWN_REGIONS = {"europe", "north_america", "asia", "oceania", "other"}

#: Codes must be usable inside a URL path segment.
CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
REGIONAL_INDICATOR_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]")
DIGIT_RE = re.compile(r"[0-9۰-۹٠-٩]")

#: A ``last_updated`` older than this many days is flagged as stale.
STALE_AFTER_DAYS = 540


@dataclass(frozen=True)
class Issue:
    """A single validation finding."""

    severity: str  # "error" | "warning"
    path: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.severity}] {self.path}: {self.message}"


def is_safe_url(value: Any) -> bool:
    """Return ``True`` for absolute ``http(s)`` URLs that are safe to render.

    Anything else (``javascript:``, ``data:``, relative paths, values with
    whitespace or control characters) is rejected.
    """
    if not isinstance(value, str):
        return False
    url = value.strip()
    if not url:
        return False
    if any(ch in url for ch in "\r\n\t "):
        return False
    if any(ord(ch) < 32 for ch in url):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme.lower() not in ("http", "https"):
        return False
    if not parts.netloc:
        return False
    return True


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_date(
    value: Any, path: str, issues: list[Issue], today: date
) -> None:
    if not isinstance(value, str) or not value.strip():
        issues.append(Issue("error", path, "last_updated is missing"))
        return
    raw = value.strip()
    if not DATE_RE.match(raw):
        issues.append(
            Issue("error", path, f"last_updated {raw!r} is not YYYY-MM-DD")
        )
        return
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        issues.append(Issue("error", path, f"last_updated {raw!r} is not a real date"))
        return
    if parsed > today:
        issues.append(
            Issue("warning", path, f"last_updated {raw!r} is in the future")
        )
    elif (today - parsed).days > STALE_AFTER_DAYS:
        issues.append(
            Issue(
                "warning",
                path,
                f"last_updated {raw!r} is older than {STALE_AFTER_DAYS} days",
            )
        )


def _check_markdown(
    content: str, path: str, issues: list[Issue]
) -> None:
    """Validate Markdown links and flag leftover markup."""
    for match in MD_LINK_RE.finditer(content):
        label, url = match.group(1), match.group(2)
        if not label.strip():
            issues.append(Issue("error", path, "markdown link has an empty label"))
        if not is_safe_url(url):
            issues.append(
                Issue("error", path, f"markdown link target is not a safe http(s) URL: {url!r}")
            )
    # Any "](" that was not consumed by a well-formed link is malformed.
    residue = MD_LINK_RE.sub("", content)
    if "](" in residue:
        issues.append(
            Issue("warning", path, "possible malformed markdown link (unbalanced brackets)")
        )
    if HTML_TAG_RE.search(content):
        issues.append(
            Issue("warning", path, "content contains raw HTML tags; they are shown as text")
        )


def _check_flag(flag: Any, path: str, issues: list[Issue]) -> None:
    if not _is_str(flag):
        issues.append(Issue("error", path, "flag is missing or empty"))
        return
    indicators = REGIONAL_INDICATOR_RE.findall(flag)
    if len(indicators) != 2:
        issues.append(
            Issue("warning", path, f"flag {flag!r} is not made of two regional indicators")
        )


def _check_sources(
    country_code: str, sources: Any, path: str, issues: list[Issue]
) -> None:
    if sources is None:
        return
    if not isinstance(sources, list):
        issues.append(Issue("error", path, "sources must be a list"))
        return
    seen_urls: dict[str, int] = {}
    for index, source in enumerate(sources):
        src_path = f"{path}[{index}]"
        if not isinstance(source, dict):
            issues.append(Issue("error", src_path, "source must be an object"))
            continue
        if not _is_str(source.get("title")):
            issues.append(Issue("error", src_path, "source title is missing or empty"))
        url = source.get("url")
        if not _is_str(url):
            issues.append(Issue("error", src_path, "source url is missing or empty"))
        elif not is_safe_url(url):
            issues.append(
                Issue("error", src_path, f"source url is not a safe http(s) URL: {url!r}")
            )
        else:
            seen_urls[url] = seen_urls.get(url, 0) + 1
        cat = source.get("cat")
        if cat is not None and not _is_str(cat):
            issues.append(Issue("error", src_path, "source cat must be a string"))
    for url, count in seen_urls.items():
        if count > 1:
            issues.append(
                Issue("warning", path, f"source url listed {count} times: {url}")
            )


def _check_items(
    country_code: str,
    category_code: str,
    items: Any,
    path: str,
    issues: list[Issue],
) -> None:
    if not isinstance(items, list):
        issues.append(Issue("error", path, "items must be a list"))
        return
    if not items:
        issues.append(Issue("warning", path, "category has no items"))
    seen_titles: dict[str, int] = {}
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            issues.append(Issue("error", item_path, "item must be an object"))
            continue
        title = item.get("title")
        if not _is_str(title):
            issues.append(Issue("error", item_path, "item title is missing or empty"))
        else:
            key = title.strip()
            seen_titles[key] = seen_titles.get(key, 0) + 1
        content = item.get("content")
        if not _is_str(content):
            issues.append(Issue("error", item_path, "item content is missing or empty"))
        else:
            _check_markdown(content, item_path, issues)
        link = item.get("link")
        if link is not None:
            if not _is_str(link):
                issues.append(Issue("error", item_path, "item link must be a string"))
            elif not is_safe_url(link):
                issues.append(
                    Issue("error", item_path, f"item link is not a safe http(s) URL: {link!r}")
                )
    for title, count in seen_titles.items():
        if count > 1:
            issues.append(
                Issue("warning", path, f"duplicate item title {count} times: {title!r}")
            )


def validate_guides(
    data: Any, today: date | None = None
) -> list[Issue]:
    """Validate a parsed ``guides.json`` document.

    Returns a list of :class:`Issue` objects. ``severity == "error"`` means the
    data is structurally broken; ``"warning"`` means it is usable but worth a
    second look (for example a shared ``last_updated`` value).
    """
    today = today or date.today()
    issues: list[Issue] = []

    if not isinstance(data, dict):
        issues.append(Issue("error", "$", "top level must be an object"))
        return issues
    if not data:
        issues.append(Issue("error", "$", "top level object is empty"))
        return issues

    general = data.get("general")
    if general is None:
        issues.append(Issue("warning", "general", "no 'general' entry (checklist will be empty)"))

    seen_names: dict[str, str] = {}
    updated_values: dict[str, list[str]] = {}

    for code, country in data.items():
        path = f"{code}"
        if not isinstance(code, str) or not CODE_RE.match(code):
            issues.append(Issue("error", path, "country code must be lower-case ascii"))
        if code == "general":
            expected = GENERAL_CATEGORIES
        else:
            expected = COUNTRY_CATEGORIES
        if not isinstance(country, dict):
            issues.append(Issue("error", path, "country entry must be an object"))
            continue

        if code != "general":
            if not _is_str(country.get("name")):
                issues.append(Issue("error", path, "name is missing or empty"))
            else:
                name = country["name"].strip()
                if name in seen_names:
                    issues.append(
                        Issue(
                            "error",
                            path,
                            f"country name {name!r} is already used by {seen_names[name]!r}",
                        )
                    )
                else:
                    seen_names[name] = code
            _check_flag(country.get("flag"), f"{path}.flag", issues)

            meta = country.get("meta")
            if not isinstance(meta, dict):
                issues.append(Issue("error", f"{path}.meta", "meta must be an object"))
            else:
                for field in ("capital", "currency", "language", "emergency"):
                    if not _is_str(meta.get(field)):
                        issues.append(
                            Issue("error", f"{path}.meta.{field}", "field is missing or empty")
                        )
                emergency = meta.get("emergency")
                if isinstance(emergency, str) and emergency.strip():
                    if not DIGIT_RE.search(emergency):
                        issues.append(
                            Issue(
                                "warning",
                                f"{path}.meta.emergency",
                                f"emergency number {emergency!r} contains no digits",
                            )
                        )
                region = meta.get("region")
                if not _is_str(region):
                    issues.append(Issue("error", f"{path}.meta.region", "region is missing"))
                elif region not in KNOWN_REGIONS:
                    issues.append(
                        Issue(
                            "warning",
                            f"{path}.meta.region",
                            f"unknown region {region!r}; it will be shown under «سایر»",
                        )
                    )

        _check_date(country.get("last_updated"), f"{path}.last_updated", issues, today)
        if isinstance(country.get("last_updated"), str):
            updated_values.setdefault(country["last_updated"], []).append(code)

        categories = country.get("categories")
        if not isinstance(categories, dict) or not categories:
            issues.append(Issue("error", f"{path}.categories", "categories must be a non-empty object"))
            continue
        for cat_code, category in categories.items():
            cat_path = f"{path}.categories.{cat_code}"
            if cat_code not in expected:
                issues.append(
                    Issue(
                        "warning",
                        cat_path,
                        f"unexpected category {cat_code!r} (expected one of {', '.join(expected)})",
                    )
                )
            if not isinstance(category, dict):
                issues.append(Issue("error", cat_path, "category must be an object"))
                continue
            if not _is_str(category.get("title")):
                issues.append(Issue("error", cat_path, "category title is missing or empty"))
            _check_items(code, cat_code, category.get("items"), f"{cat_path}.items", issues)
        for missing in expected:
            if missing not in categories:
                issues.append(
                    Issue("warning", f"{path}.categories", f"missing category {missing!r}")
                )

        _check_sources(code, country.get("sources"), f"{path}.sources", issues)

    if len(updated_values) == 1 and len(data) > 1:
        value, codes = next(iter(updated_values.items()))
        issues.append(
            Issue(
                "warning",
                "$",
                f"all {len(codes)} entries share last_updated {value!r}; "
                "per-country freshness cannot be inferred from this file",
            )
        )

    return issues


def _format_issues(issues: Iterable[Issue]) -> str:
    return "\n".join(str(issue) for issue in issues)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = Path(argv[0]) if argv else DATA_PATH
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        print(f"error: file not found: {path}")
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: {path} is not valid JSON: {exc}")
        return 2

    issues = validate_guides(data)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    for issue in issues:
        print(str(issue))

    print(
        f"\n{path}: {len(errors)} error(s), {len(warnings)} warning(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
