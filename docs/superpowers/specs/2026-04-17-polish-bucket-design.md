# Polish Bucket — Design

**Date:** 2026-04-17
**Scope:** Three independent PRs addressing site polish: (α) head tags — per-route titles, viewport, description, and Open Graph meta; (β) mobile UX — navbar hamburger collapse below 768px; (γ) native-speaker review doc — generated Markdown listing representative exercises across every module.

**Rationale:** Each PR has a distinct review risk profile — head tags are near-risk-free (text in `<head>`), mobile UX needs device testing and visual review, the review doc is a cross-check artifact potentially driving follow-up LT content fixes — so they ship as three separate PRs in the order α → β → γ.

---

## Goals

1. Fix the "FastHTML page" tab title bug with per-route, language-aware titles.
2. Add standard `<head>` hygiene: viewport meta (required for mobile), description meta (search snippets), OG tags (link-share previews).
3. Make the navbar usable on 375px–414px phones by collapsing secondary items behind a hamburger inline dropdown.
4. Give a native-speaker reviewer a single Markdown file listing every exercise type × taxonomy branch with its correct answer, without requiring the reviewer to run the app.

## Non-goals

- No redesign of the existing landing cards, stats grid, examples sections, or quiz area. Those are already responsive (`cols_sm=1`/`cols_sm=2` / `sm:grid-cols-2` / `w-full`).
- No PWA manifest, no service worker, no offline mode.
- No `og:image` share card. If we want one later, it's a separate PR.
- No migration of `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md` content into the new exercise-reference doc. Two different review passes covering different copy.
- No exhaustive enumeration of exercises (1,600 rows eye-glazes reviewers); representative coverage by taxonomy branch catches the same systemic errors.

---

## PR α — Head tags

### Files touched

- `ui.py` — `page_shell` gains a `page_title` parameter; emits `<title>` + meta tags into its returned structure.
- `main.py` — each route that currently calls `_render_page(...)` or `page_shell(...)` passes an explicit `page_title`. Affected: `get_home`, `get_about`, `get_login`, `get_stats`, `get_numbers` (inside `_make_number_routes`), `get_time`, `get_age`, `get_weather`, `get_prices` (inside the prices route), `get_practice_all` (mix mode), `_not_found`.
- `tests/test_ui.py` — new assertions for title / viewport / description / OG tags.

### Per-route title text

Format: `{Page} — Lithuanian Practice` for sub-pages; `Lithuanian Practice` for landing. Language-aware — LT variant used when `lang="lt"`.

| Route | EN title | LT title |
|---|---|---|
| `/` | `Lithuanian Practice` | `Praktika` |
| `/numbers` | `Numbers — Lithuanian Practice` | `Skaičiai — Praktika` |
| `/age` | `Age — Lithuanian Practice` | `Amžius — Praktika` |
| `/weather` | `Weather — Lithuanian Practice` | `Oras — Praktika` |
| `/prices` | `Prices — Lithuanian Practice` | `Kainos — Praktika` |
| `/time` | `Time — Lithuanian Practice` | `Laikas — Praktika` |
| `/practice-all` | `Practice All — Lithuanian Practice` | `Bendra praktika — Praktika` |
| `/stats` | `Stats — Lithuanian Practice` | `Statistika — Praktika` |
| `/about` | `About — Lithuanian Practice` | `Apie — Praktika` |
| `/login` | `Log in — Lithuanian Practice` | `Prisijungti — Praktika` |
| 404 | `Page not found — Lithuanian Practice` | `Puslapis nerastas — Praktika` |

### Other head tags

- **Viewport:** `<meta name="viewport" content="width=device-width, initial-scale=1">`. No `maximum-scale` / `user-scalable=no` — diacritic zooming is legitimate.
- **Description (English-only, same tag on every page):** `Adaptive Lithuanian practice: numbers, age, weather, prices, and time. Type the answer in Lithuanian; the site adapts to your weak spots.`
- **Open Graph tags:**
  - `og:title` = `Lithuanian Practice` (static, English)
  - `og:description` = same as description meta
  - `og:type` = `website`
  - `og:url` = `https://lithuanian-practice.com/` (canonical; no per-page `og:url` variants for now)
- **No `og:image`** in this PR.

### Implementation approach

`page_shell` in `ui.py` currently returns a `Div(nav, *content, ...)`. FastHTML then wraps this in an HTML page using the `title=` kwarg from `fast_app(...)`, but fasthtml 0.13.3 is silently dropping that value. Rather than debug the framework, `page_shell` will gain a `page_title` parameter and explicitly construct a `Head` list (`Title`, `Meta`, `Meta`, ...) alongside its current content, returned via `Titled(page_title, *content)` or equivalent primitive that FastHTML renders into `<head>`. Exact primitive to confirm during implementation — fallback is to return `(*head_tags, *body_tags)` tuple which FastHTML splits automatically.

The `fast_app(title="Lithuanian Price Quiz", ...)` kwarg is removed since we no longer rely on it.

### Tests

- `test_home_page_title_en` — render `/`, assert `<title>Lithuanian Practice</title>`.
- `test_home_page_title_lt` — same, `lang="lt"`, assert `<title>Praktika</title>`.
- `test_module_page_title_en` — parameterised over the five modules, assert `<title>Numbers — Lithuanian Practice</title>` etc.
- `test_module_page_title_lt` — parameterised, LT variants.
- `test_viewport_meta_present` — assert `<meta name="viewport" content="width=device-width, initial-scale=1">` in rendered home page.
- `test_description_meta_present` — assert `<meta name="description" content="...">` with the full English string.
- `test_og_tags_present` — assert `og:title`, `og:description`, `og:type`, `og:url`.

---

## PR β — Mobile UX (navbar hamburger collapse)

### Files touched

- `ui.py` — `page_shell`'s navbar-construction block.
- `tests/test_ui.py` — new assertions for navbar rendering at mobile breakpoint.

### Breakpoint

Tailwind's `md` = 768px. Below `md` = mobile layout; `md` and above = current desktop layout.

### Navbar behavior

**Always visible (at every width):**
- Brand (🇱🇹 + "Lithuanian / Practice" wordmark).
- Modules dropdown.

**Visible at `md`+ only (hidden on mobile):**
- Stats link.
- Input mode segmented control (`Strict | Tolerant`).
- Feedback link.
- Language segmented control (`English | Lietuviškai`).
- User name + Logout (or Login).

Implementation: add Tailwind `hidden md:inline-flex` (or `md:flex`, depending on display primitive) to each of these navbar items so they only show at `md`+.

**Visible below `md` only (hidden on desktop):**
- Hamburger button (`UkIcon("menu")` inside an `A` with `uk-btn uk-btn-ghost md:hidden`).

**Hamburger dropdown contents** (inline, pushes page content down when open — uses MonsterUI's `DropDownNavContainer` like the existing Modules dropdown):
- Stats link (as a menu row).
- Input mode segmented control — preserved as segmented, vertically stacked with its "Input:" label above the two buttons.
- Feedback link (as a menu row).
- Language segmented control — preserved as segmented (both buttons visible in one row).
- User name (as a static row) + Logout link (as a menu row) — or Login link if anonymous.

The segmented controls render **twice** in the DOM — once in the desktop navbar (wrapped in `hidden md:inline-flex`) and once inside the hamburger-panel dropdown (wrapped in `md:hidden` — it only exists in the below-`md` layout). Render duplication is accepted rather than try to share a single element across two DOM locations with CSS. Each pair of buttons uses the same `href`, so clicking either the desktop or the hamburger-panel "English" button does the same thing — the active-class computation is shared via a helper that takes the current state and returns the classes.

### Non-navbar layout

**No changes.** Existing responsive utilities are already correct:
- Landing `_module_card` grid: `cols_md=2, cols_sm=1` — one card per row on phones.
- Stats metrics: `cols=4, cols_sm=2` — 2×2 on phones.
- Examples sections: `grid grid-cols-1 sm:grid-cols-2` — one column on phones.
- Quiz input: `cls="uk-input uk-form-large w-full"` — fluid.
- Performance cards on stats page: `cols_md=1, cols_lg=2, cols_xl=3` — stack on phones.

The existing responsive utilities only take effect once the viewport meta from PR α is present. Prior to α, mobile browsers render at a simulated desktop width so breakpoints never fire.

### Tests

- `test_navbar_hamburger_button_present` — render `page_shell`, assert a `menu` icon button is in the output with class `md:hidden`.
- `test_navbar_hamburger_panel_contains_secondary_items` — assert Stats, Input-mode markup, Feedback, Language-toggle markup, and Login/Logout are inside the hamburger dropdown container.
- `test_navbar_desktop_items_hidden_below_md` — assert each desktop-only nav item has `hidden md:*` class.
- `test_navbar_brand_and_modules_always_visible` — assert brand and Modules dropdown do not carry any `hidden` or `md:hidden` class (visible at every width).

### Manual smoke (post-merge, noted in PR description — not a merge blocker)

- Chrome DevTools device emulation: iPhone SE (375px), iPhone 14 Pro (390px), Pixel 7 (412px). Tap the hamburger, verify all items reachable.
- One real-phone check (iOS Safari).
- Follow-up PR if any cramped element surfaces; spec does not pre-commit to fixes.

---

## PR γ — Native-speaker exercise review doc

### Files created

- `scripts/generate_exercise_reference.py` — generator script, idempotent.
- `docs/reviews/exercise-reference.md` — the rendered Markdown doc, committed.

### Files retired

- `time_reference.py` (at repo root) — superseded by the new generator, which covers time as one section.

### Output structure

One H2 section per module, in this order: Numbers, Age, Weather, Prices, Time. Inside each, H3 subsections grouped by taxonomy branch. Each subsection has a small Markdown table of hand-picked representative rows.

Example:

````markdown
## Numbers (/numbers)

Range 0-99. Two exercise types: `produce` (say the number in Lithuanian) and `recognize` (identify the number from its Lithuanian form).

### Single-digit (0-9)

| Exercise | Prompt | Correct answer |
|---|---|---|
| produce | How do you say 0? | nulis |
| produce | How do you say 5? | penki |
| recognize | What number is septyni? | 7 |

### Teens (10-19)

| Exercise | Prompt | Correct answer |
|---|---|---|
| produce | How do you say 13? | trylika |
| recognize | What number is devyniolika? | 19 |

### Decade (20, 30, ..., 90)

... etc
````

### Representative coverage per module

Approximate row counts per module. Final list curated inside the generator script as explicit tuples so additions/edits are reviewable in code.

- **Numbers (~12 rows):** produce × {0, 5, 13, 20, 45, 99}; recognize × same 6.
- **Age (~14 rows):** produce × pronoun (Man, Tau, Jam, Jai) × {5, 10, 20} covering `metai`/`metų` boundary + 21/22 compound-collective edges (`dvidešimt vieneri` vs `dvidešimt dveji`); recognize × 2.
- **Weather (~12 rows):** produce × {0, 5, 15, 25} positive; produce × {-1, -10, -15} negative; recognize × 4.
- **Prices (~12 rows):** produce `kokia` × {1, 5, 15, 21, 45, 99}; produce `kiek` × same 6 (covering nominative-vs-accusative declension).
- **Time (~16 rows):** produce × 4 exercise types × 3 hours (1, 6, 12) covering the hour-wraparound case for `quarter_to` / `half_past` / `quarter_past` when the next hour is 1 (from 12).

Total target: ~66 rows.

### Generator behavior

- Imports engines directly (`NumberEngine`, `AgeEngine`, `WeatherEngine`, `ExerciseEngine`, `TimeEngine`). Calls their `format_question` + `correct_answer` methods, same as the app. No LT string duplication.
- Exercise lists stored as explicit tuples per module near the top of the script, grouped by subsection heading. Reviewers who want more examples can edit the tuple list and rerun.
- Writes to `docs/reviews/exercise-reference.md`, overwriting.
- Top of the generated doc includes a one-line header: `<!-- Generated by scripts/generate_exercise_reference.py on YYYY-MM-DD. Do not edit by hand. -->`.

### Test (in `tests/test_regressions.py`)

- `test_exercise_reference_doc_in_sync` — runs the generator into a temp buffer, strips the date-line from both buffer and committed doc, asserts byte equality. Guarantees the committed doc can't silently drift from engine output.

### Relationship to existing docs

- `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md` (interface chrome: navbar, card labels, reset modal copy) — unchanged.
- `time_reference.py` (standalone time-exercise enumeration) — deleted; superseded.

---

## Testing + deploy plan

Each PR ships on its own branch, gets its own PR, own CI, own merge, own Railway deploy, own production smoke. Suggested order:

1. **α (head tags)** first — unblocks mobile work (viewport meta is required for β breakpoints to fire correctly).
2. **β (mobile UX)** second — real mobile behavior requires α already deployed.
3. **γ (review doc)** third — independent of both, can actually run in parallel with α or β if convenient.

Post-deploy smoke for each:

- **α:** `curl` the home page, assert `<title>Lithuanian Practice</title>` and the viewport / description / og meta tags present in the HTML.
- **β:** DevTools mobile emulation on the deployed site; tap hamburger, verify all items reachable; one real-phone check.
- **γ:** no production smoke; it's a doc-only PR. Send the rendered `docs/reviews/exercise-reference.md` link to jbagd for review.

---

## Risks and mitigations

**R1. `page_shell` `Head`-injection pattern doesn't work with FastHTML 0.13.3's page wrapper.** Likelihood: non-zero — this is the reason the `fast_app(title=...)` kwarg is being dropped in the first place. Mitigation: test locally before pushing α; fallback to emitting the head tags as part of the returned body structure (FastHTML typically hoists `Title`/`Meta` to `<head>` regardless of position in the returned tuple).

**R2. Mobile hamburger dropdown collides with the existing Modules dropdown z-index.** Both are `DropDownNavContainer` instances positioned absolutely. Likelihood: moderate. Mitigation: visual check during DevTools smoke; fix with a `z-*` class bump if needed.

**R3. Representative coverage in PR γ misses a real error mode.** Likelihood: always non-zero. Mitigation: the generator tuples are easy to extend — if the reviewer spots a missing branch, we add examples and regenerate. Not a merge blocker.

**R4. `og:image` absence makes shared links look bland.** Acceptable. Follow-up PR can add a minimal share card if/when we care about virality.

**R5. `_not_found` page currently renders outside the normal `_render_page` path** (it has its own direct `page_shell` call with exception context). Needs explicit title plumbing in its handler too. Mitigation: part of PR α's scope — handler gets `page_title="Page not found — Lithuanian Practice"` (or LT equivalent).

---

## Success criteria

- **α:** Every route serves the right `<title>`; viewport + description + OG tags present in the home page HTML. Test suite assertions hold.
- **β:** Below 768px, the navbar shows only brand + Modules + hamburger; all other items are inside the hamburger dropdown. No horizontal scroll on a 375px viewport. Navigation works without JS keyboard-accessibility regressions from the current state.
- **γ:** `docs/reviews/exercise-reference.md` exists and can be reviewed on GitHub. `scripts/generate_exercise_reference.py` re-runs cleanly and produces identical output. Test asserts the committed doc is in sync with the engines.
