# DaneshRah — audit progress and final state

Audit date: **2026-10-30**. This file records what was actually run and observed locally. It is not a deployment certificate.

**Status:** code, data, documentation, local tests, and headless-browser checks are complete. Production startup and the public deployment are **not verified**. The live Render URL returned HTTP 503 (“Service Suspended”) during the audit.

## Environment

| Item | State |
| --- | --- |
| OS | Windows (`win32`) |
| Python | 3.14.7 |
| System Flask | 3.0.3 |
| Clean audit venv | Flask 3.1.3, Gunicorn 26.2.0 |
| Render target | Python 3.11.9 |
| Node | v24.20.0 |
| Browser | Headless Chrome 155.0.8059.85 |
| Accessibility engine | axe-core 4.10.2 |
| Data file | `data/guides.json` |
| Local test server | Flask development server on `127.0.0.1:5055` |

Gunicorn is Unix-only. On Windows, even `gunicorn.exe --version` fails before startup with:

```text
ModuleNotFoundError: No module named 'fcntl'
```

The package was installed successfully in the clean venv, but no Gunicorn worker was started.

## Baseline before changes

- 72 Python tests passed, 7 Node tests passed, and `guide_validation.py` reported 0 errors/0 warnings.
- All public routes returned 200; unknown countries/categories returned 404.
- The site had 43 data entries (42 countries plus `general`), 746 guide items, and 148 sources.
- Security headers were limited to `X-Content-Type-Options`, `Referrer-Policy`, and `X-Frame-Options`.
- The UI still used the old visual language and repeated creator branding; the homepage and footer repeated the creator identity.
- There was no `/about`, `/robots.txt`, `/sitemap.xml`, generic error page, or canonical/OG/JSON-LD system.
- Several inline styles prevented a CSP without `style-src 'unsafe-inline'`.
- The data contained unsupported/misattributed citation links, and the shared `last_updated` stamp could be read as per-country verification.

## Completed changes

### Branding and visual system

- Made **DaneshRah / دانش‌راه** the primary identity. The Persian spelling is standardized as «دانش‌راه».
- Removed repeated creator branding from the homepage, header, and footer. The creator credit now appears exactly once on `/about` (`id="creator"`), with project background and independence context.
- Rebuilt the design system around warm paper, deep ink/teal, brick/gold accents, fine rules, flat surfaces, and restrained motion.
- Added Vazirmatn body typography and Markazi Text display typography, with system-font fallbacks.
- Rebuilt the homepage, navigation, country discovery, country pages, guide pages, search, checklist, emergency directory, About page, and generic error page.
- Added light/dark themes, reduced-motion handling, print styles, responsive navigation, mobile search, focus-visible states, and 320 px-safe layouts.
- Added favicon, Apple touch icon, and a 1200×630 OG cover.
- Replaced decorative/inline styles with reusable classes. Templates contain no `style` attributes; the only runtime inline style is the reading-progress width written by JavaScript through CSSOM.

### Routes, SEO, and error handling

- Added `/about`, `/robots.txt`, `/sitemap.xml`, and a generic error template.
- Added canonical, Open Graph, Twitter, and JSON-LD metadata.
- Canonical origins use `PUBLIC_BASE_URL`, then `RENDER_EXTERNAL_URL`, then the configured default. The request `Host` header is not trusted.
- Added correct 400/404/405/413/500 handlers and styled error responses.
- Added `/search` and `/country/general*` to `noindex, follow`; `/search` is excluded from the sitemap.
- Search results now deep-link to `/country/<code>/<category>#item-N`; the guide page opens and highlights the target item.
- Dynamic counts are used in the header search hint, homepage metadata, and About page instead of hardcoded country/item totals.
- Removed dead `templates/404.html` and `templates/500.html`; the shared `error.html` now handles errors.

### Security and performance

- Added a per-request CSP nonce for the single inline theme bootstrap.
- CSP no longer needs `style-src 'unsafe-inline'`; it allows same-origin assets plus Google Fonts and FlagCDN images.
- Added `Permissions-Policy`, COOP, CORP, `X-Permitted-Cross-Domain-Policies`, request IDs, and HSTS on HTTPS requests.
- Search queries are capped at 200 characters; API limits are clamped; request bodies are capped at 1 MiB.
- `/health` and `/ping` report data-load health; `/api/search` is `no-store`; `/api/countries`, `/robots.txt`, and `/sitemap.xml` are cacheable for five minutes.
- The app loads and validates the JSON file once, keeps the search index in memory, and avoids disk I/O per query.
- No accounts, sessions, or server-side user data were introduced.

### Data corrections and verification

- Corrected France CROUS meal/housing links and Australia housing/work citations.
- Removed the Turkey BTK citation and a batch of **46** unsupported/misattributed citation links, including USA/Canada examples. No replacement URLs were invented.
- France and Australia were given `2026-10-23` after targeted review.
- The other 41 entries (40 countries plus `general`) retain `2026-10-19`; they were not individually line-by-line rechecked.
- Updated the UI and About/guide copy to describe `last_updated` as a data-file edit stamp, not proof of per-country verification.
- The data validator remains clean: **43 entries, 42 countries, 746 items, 148 sources, 0 errors, 0 warnings**.

Targeted facts checked against official pages:

| Fact | Result | Source |
| --- | --- | --- |
| Australia minimum wage | A$26.44/hour from 1 July 2026 | [Fair Work Ombudsman](https://www.fairwork.gov.au/pay-and-wages/minimum-wages) |
| Australia student work limit | 48 hours per fortnight during term | [Home Affairs — Student visa 500](https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/student-500) |
| France CROUS meal | €1 meal from 4 May 2026 with an active Izly account | [etudiant.gouv.fr](https://www.etudiant.gouv.fr/fr/comment-beneficier-du-repas-crous-1-eu-3123) |
| France APL | Eligibility rules changed from 1 July 2026 | [Service-Public — APL](https://www.service-public.gouv.fr/particuliers/vosdroits/F1563) |
| France SMIC | €12.31 gross/hour from 1 June 2026 | [Service-Public — SMIC](https://www.service-public.gouv.fr/particuliers/vosdroits/F2300) |

These checks do not constitute a full fact-check of the remaining countries. Rates, visa rules, and eligibility criteria change; the inline official links are the primary source trail.

### Bugs fixed during verification

- Jinja dict-method collisions: `stats.items`, `stats.sources`, and `cat.items` were rendering Python method objects instead of numbers. Switched to bracket access and added regression assertions.
- Horizontal overflow at 320/360/390 px caused by `.pills` and `.filter-search` flex minimums.
- Emergency page 300 px blank gap: `.filter-search` had `flex: 1 1 300px`, which became a 300 px height in the mobile column layout. Mobile now uses `flex: 0 0 auto`.
- Country emblem layout: the emoji fallback participated in flex layout and shifted/partially covered the flag image. It is now absolutely positioned, and image error handling includes `.country-emblem-flag`.
- General-guide search results no longer emit an empty `<img src="">` when there is no flag.
- Search disclosure `aria-label` is updated when opened/closed; country navigation uses correct `aria-current` semantics.
- Checklist inputs now have one visible label per checkbox; the old nested label/body structure was removed so links in the body remain independently reachable.
- Footer and dark-panel small text colors were raised for contrast; light-theme muted/faint/gold tokens were darkened.
- Removed nested complementary asides around page content where they were invalid; callouts use non-landmark containers.
- `/search` was removed from the sitemap, and general-guide pages received matching meta-robots tags.
- Added regression tests for the empty-flag image, single-label checklist markup, robots policies, stats rendering, and data corrections.

## Final test results

All commands were run from the project root on 2026-10-30.

| Command | Actual result |
| --- | --- |
| `python -m unittest discover -s tests -t .` | **Ran 95 tests — OK** (system Flask 3.0.3; exit 0) |
| Same command with clean venv Python | **Ran 95 tests — OK** (Flask 3.1.3; exit 0) |
| `node --test tests/js_utils.test.js` | **7 tests passed, 0 failed** (exit 0) |
| `python guide_validation.py` | **0 errors, 0 warnings** (exit 0) |

The Python test output also includes deliberate validator failure cases for a temporary broken JSON file; those are test fixtures, not failures of the real data file.

The test suite grew from 72 to 95 Python tests. New coverage includes security/SEO metadata, robots policies, canonical behavior, stats rendering, general search images, checklist markup, and France/Australia data corrections.

## Browser and accessibility observations

Browser checks used the local Flask server at `http://127.0.0.1:5055` with headless Chrome and Node CDP.

Passing checks included:

- Homepage country count, region filters, typography, alt text, no repeated creator credit, canonical URL, and stats rendering.
- About page: exactly one creator mention, genuine creator section, indexable robots tag, and no horizontal overflow.
- Theme toggle, persistence across reload, and switching back.
- Country text filtering; category counts; flag frame/fallback geometry; country page overflow at 320/390/768/1280 px.
- Guide accordion, deep links, copy button, progress bar, and responsive widths at 320/360/390/768/1024/1280/1440 px.
- Search results, deep-link targets, general-guide results without empty image sources, and mobile layout.
- Checklist persistence, progressbar state, reset behavior, and single-label layout.
- Emergency filter and 42-row table; no 300 px toolbar gap at 390/320 px.
- CSP console checks; no unexpected inline style attributes (only the JS progress width).

Axe-core scan result: **0 violations** across ten checks: homepage mobile/desktop/dark, country mobile/desktop, guide, search, checklist, emergency, and About. Remaining “incomplete” items were caused by overlapping elements or pseudo-element backgrounds that axe could not resolve; they were inspected and were not confirmed contrast failures.

Limitations: headless Chrome only; no real phone, Safari, Firefox, or screen-reader testing. The axe result is automated evidence, not full WCAG 2.2 AA certification.

Screenshots and browser evidence from the final run are in `C:\Users\Dell\AppData\Local\Temp\opencode\daneshrah-shots` (outside the repository).

## Production verification

- Local Flask health check: `GET /health` returned 200 with `status: ok`, `countries: 42`, `guides: 746`.
- Production start command is configured in `render.yaml`:
  `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`.
- Gunicorn 26.2.0 was installed in the clean venv, but cannot run on Windows (`fcntl`). **Gunicorn startup is unverified.**
- The configured public URL `https://daneshrah.onrender.com/health` returned **HTTP 503** with the body “This service has been suspended.” on 2026-10-30. No redeploy or resume was attempted.
- The optional GitHub Actions keep-alive workflow was not exercised against a working service; it requires the `RENDER_URL` repository secret.
- No production HTTPS/HSTS, custom-domain, canonical-origin, or cache behavior was verified.
- No commits or pushes were made; all changes remain in the working tree.

## Known limitations and work still needed

1. **Full data verification is incomplete.** Only France and Australia received targeted fact review; the other 40 country guides need a country-by-country check, especially wages, visa work limits, housing deposits, and emergency numbers.
2. **Production startup is unverified.** Run Gunicorn on Linux, hit `/health`, and verify headers, canonical URLs, robots, sitemap, and static assets in the deployed environment.
3. **The live service is suspended.** Resume/redeploy it before treating the public URL as a demo.
4. **Manual accessibility and cross-browser testing remain.** Test with a screen reader, keyboard only, Safari/Firefox, and at least one real phone.
5. **External dependencies remain.** Google Fonts and FlagCDN are network dependencies; self-host if privacy/offline behavior matters.
6. **Search is lexical.** It normalizes Persian variants but does not understand paraphrases or synonyms beyond the indexed text.
7. **No commit/push was performed.** Review the working tree and commit when ready.

## Relevant files

- `app.py` — routes, data loading, search, metadata, security headers, sitemap, health, errors.
- `data/guides.json` — all guide content and metadata.
- `templates/` — all pages, shared icons, About/error templates.
- `static/style.css` — design system, themes, responsive/accessibility/print rules.
- `static/app.js` — theme, menu/search, filters/favorites, guide interactions, checklist, emergency filter.
- `tests/test_app.py`, `tests/test_data.py`, `tests/test_js.py` — Python regressions.
- `tests/js_utils.test.js` — Node utility tests.
- `guide_validation.py` — standalone data validator.
- `requirements.txt` — Flask 3.1.3 and Gunicorn 26.2.0.
- `render.yaml` — Render service configuration.
- `README.md` — setup, data policy, test commands, and honest limitations.
