# DaneshRah — audit progress & results

Audit date: 2026-10-22. Everything below was executed locally; results are copied from the actual runs.

## Environment / limitations

| Item | State |
| --- | --- |
| Python | 3.14.7 locally (Render uses 3.11.9) |
| Installed Flask | 3.0.3 (3.1.3 could **not** be installed: `files.pythonhosted.org` does not resolve from this machine) |
| pytest | not installable (same PyPI failure) → the suite uses the standard-library `unittest` runner |
| gunicorn | not installable and not runnable on Windows → production start command could not be exercised |
| Node | v24.20.0 → used for the front-end unit tests (`node --test`) |

## Baseline (before changes)

- All public routes returned 200; unknown country/category/path returned 404.
- Stats: 42 countries, 168 categories, 746 guide items; `general` holds 11 arrival steps.
- Security headers were only `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`.
- `data/guides.json` had no missing fields, duplicate titles, malformed Markdown, unsafe URLs or invalid dates.

## Defects fixed (each one is covered by a test)

| # | Defect | Fix | Test |
| --- | --- | --- | --- |
| 1 | Clipboard reported success on failure (`.then(done, done)`) and the fallback copied nothing | new `static/utils.js` with `copyText()` that returns a boolean and falls back to `execCommand('copy')`; the button now shows «کپی نشد» on failure | `tests/js_utils.test.js` (7 tests) |
| 2 | Accordion nested a `<button>` inside `role="button"` | heading now contains a real `<button>` with `aria-expanded`/`aria-controls`; body is a `role="region"` | `tests/test_html.py` |
| 3 | TOC and search links carried `role="listitem"` (link semantics lost) | TOC is a real `<ul>/<li>` list, search results are plain links | `tests/test_html.py` |
| 4 | Search snippets rendered `……` | template no longer adds its own ellipsis | `tests/test_html.py` |
| 5 | No CSP / HSTS / Permissions-Policy, inline `onerror` handlers | per-request CSP nonce, `Strict-Transport-Security` on HTTPS, `Permissions-Policy`; all inline handlers removed and replaced by a delegated `error` listener | `tests/test_app.py` |
| 6 | Unbounded search/API query length | `clean_query()` caps the query at 200 characters, API `limit` is clamped to 50 | `tests/test_app.py` |
| 7 | Data URLs rendered without scheme validation | `safe_url` Jinja filter (http/https only) for source links and item links | `tests/test_app.py`, `tests/test_data.py` |
| 8 | Corrupt localStorage could break favorites/checklist | type-checked storage reads; checklist state accepts only `true` | `tests/js_utils.test.js`, `static/app.js` |
| 9 | `role="checkbox"` container hid the links inside a checklist step | native `<input type="checkbox">` + `<label>` | `tests/test_html.py` |
| 10 | Emergency filter ignored currency/language/region | `data-search` now contains every column | `tests/test_html.py` |
| 11 | Footer started at `h4`; pages skipped heading levels | footer uses `h2`; hero banner and checklist steps re-levelled — no page skips a level any more | `tests/test_html.py` |
| 12 | `IntersectionObserver` for the counters was constructed unconditionally (a missing API aborted the rest of `app.js`) | guarded with `'IntersectionObserver' in window` | `tests/test_js.py` (static guard) |
| 13 | Mobile-menu handler dereferenced `navLinks` before the null check | null-safe | `static/app.js` |
| 14 | Theme choice was written to `localStorage` on first load, pinning the OS preference | only an explicit toggle persists the choice | `static/app.js` |
| 15 | `js` class was added in `<head>`, so a failing `app.js` could leave the page invisible | the class is added by `app.js` right before the reveal setup, and reveal failures fall back to visible content | `static/app.js` |
| 16 | Unbounded request bodies | `MAX_CONTENT_LENGTH` = 1 MiB | – |
| 17 | Cache/index reload was not thread-safe | `threading.RLock` around the guides cache and the search index | – |
| 18 | Keep-alive thread used `print` and could busy-loop with a bad interval | uses `logging`, interval clamped to 60–3600 s | – |

## Data corrections (verified against the official source, fetched 2026-10-22)

**France**

- **APL** — the claim «تقریباً همه‌ی دانشجویان (حتی بین‌المللی‌ها) واجد شرایط» was wrong. Since **1 July 2026** a student from outside the EU/EEA/Switzerland holding a study residence permit only qualifies in three cases: a scholarship on social criteria, professional activity, or an apprenticeship/professionalisation contract. Refugee and stateless students and spouses of extra-EU students keep their APL. Sources: <https://www.service-public.gouv.fr/particuliers/actualites/A18981> (published 2026-07-01) and <https://www.service-public.gouv.fr/particuliers/vosdroits/F1563>.
- **Student work** — the item linked the SMIC page; it now links the student-work page <https://www.service-public.gouv.fr/particuliers/vosdroits/F2713> and states the real rule: up to **964 h/year without a work permit**, above that the employer needs an `autorisation de travail`, and the employer must file a nominative declaration with the prefecture at least two working days before hiring.
- **SMIC** — «از ژانویه ۲۰۲۶» was wrong: the page was verified on **1 June 2026** with **€12.31 gross/hour** and **€1,867.02 gross/month** (35 h week), based on the *arrêté du 22 mai 2026*. Source: <https://www.service-public.gouv.fr/particuliers/vosdroits/F2300>.
- The CROUS «€1 meal from 4 May 2026, other menus ≤ €3.30» claim could **not** be verified (etudiant.gouv.fr returned 503, crous-paris.fr was unreachable); it was rewritten without the unverified date and price cap and now points to the official pages.

**Other countries**

- Germany: blocked-account amount confirmed (992 €/month) on the DAAD page; the dead `make-it-in-germany.com` link was replaced, the DAAD work links now point to `…/work-career/` (HTTP 200).
- Canada: 24 h/week off campus confirmed on the IRCC page; the source link now points to that page.
- UK: minimum wage £12.71 from April 2026 confirmed on gov.uk — left unchanged.
- Germany: TK student contributions 141.16 € / 146.29 € from 01.01.2026 confirmed on tk.de — left unchanged.
- Sweden: 15 h/week limit for permits granted on/after 11 June 2026 confirmed on migrationsverket.se — text kept, the stale deep link was replaced with the current page.
- Australia: the A$26.44 figure could **not** be verified (fairwork.gov.au refuses connections from this network) — left unchanged and flagged below.
- Dead links replaced after verifying the replacements: DAAD (work), Chase (student checking), RBC (student account), Dubai Land → `dubailand.gov.ae` (without `www`) and its Ejari registration page, `job.am` (without `www`), `dot.abudhabi` → the official Abu Dhabi transport authority.

## New tooling

- `guide_validation.py` — standalone validator + CLI: required fields, ISO dates (no future dates), URL scheme checks for sources/item links/Markdown links, duplicate item titles, malformed Markdown, raw HTML in content, missing categories, and a warning when every entry shares one `last_updated`. Exit code 1 on errors.
- `tests/` — `unittest` suite (app/routes/API/security/search/XSS/errors/data/HTML semantics) plus the Node test for the front-end helpers.

## Test results (actual runs)

```text
python -m unittest discover -s tests -t .     ->  Ran 72 tests ... OK
node --test tests/js_utils.test.js             ->  7 pass, 0 fail
python guide_validation.py                     ->  0 error(s), 1 warning(s)
```

The single warning is the shared `last_updated` value (`2026-10-19` for all 43 entries) — the per-country freshness shown on the site is therefore a *file-level* stamp, not an individually verified date. This is now documented in the README.

## Link check (693 URLs)

Result: 434 × HTTP 200, 7 × 404, 123 network/TLS errors, 109 blocked (401/403/429), 4 × 503, 1 × 513, 1 × 502, 3 × 302, 2 × 202.

- The 7 confirmed 404s were fixed (see above).
- 401/403/429 are anti-bot responses, and the SSL/network errors are caused by this machine's TLS setup — they were **not** treated as broken links.
- `visale.fr` (502), `willhaben.at`, `job.am` and `educationusa.state.gov` were re-checked and respond normally from other paths, so they were left as they are.

## Still open / not verified

1. **Australia** — the July 2026 minimum wage (A$26.44) could not be verified from this network.
2. **France** — the exact CROUS €1 meal tariff and its start date could not be verified.
3. **All 42 countries** were *not* fact-checked line by line; only the items listed above were verified against primary sources. Every other figure in `data/guides.json` is unverified.
4. `Flask==3.1.3` in `requirements.txt` is **not** installed or tested here (PyPI unreachable); the suite ran against Flask 3.0.3. The app uses no API that changed between 3.0 and 3.1, but re-run the suite after the first install.
5. `gunicorn==22.0.0` was kept (no published advisories; 26.2.0 could not be installed or exercised). The production start command was never executed locally.
6. No browser was available, so the JavaScript was verified through unit tests and static checks, not through an end-to-end UI run.
