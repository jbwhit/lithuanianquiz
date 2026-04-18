# Polish Bucket — Design

**Date:** 2026-04-17
**Scope:** Three independent PRs addressing site polish: (α) head tags — correct per-route titles, plus description and Open Graph meta; (β) mobile UX audit of the existing MonsterUI `NavBar` hamburger primitive, with targeted fixes only if audit reveals concrete issues; (γ) native-speaker review artifacts — a single generator emitting both a representative cross-module exercise doc and an exhaustive time-exercise doc (retiring `time_reference.py`).

**Rationale:** Each PR has a distinct review risk profile — head tags are near-risk-free (text in `<head>`), the mobile audit needs device testing and might be a no-op, the review docs are cross-check artifacts potentially driving follow-up LT content fixes — so they ship as three separate PRs in the order α → β → γ.

**Reality check from a pre-implementation review of this spec:**

- MonsterUI's `NavBar` already renders an `md:hidden` hamburger button toggling an `#mobile-menu` wrapper (`data-uk-toggle`). All nav items fall behind the hamburger below `md` by default — essentially "hamburger everything" collapse. Any design that layers a second hamburger system on top would conflict. PR β is therefore scoped as an audit plus targeted fixes, not a greenfield addition.
- The current production HTML already emits `<title>FastHTML page</title>` (a FastHTML default; `fast_app(title=...)` is silently ignored in 0.13.3) and a `viewport` meta tag with `viewport-fit=cover`. What's actually missing is the correct title value, description meta, and OG tags.
- `fasthtml.Titled(...)` adds a visible `<main><h1>...` wrapper to the body in addition to emitting a `<title>` — do not use it as a head-only primitive.

---

## Goals

1. Fix the "FastHTML page" tab title bug with correct, per-route, language-aware titles.
2. Add `<head>` hygiene we don't already have: description meta (search snippets) and OG tags (link-share previews). Viewport meta is already emitted by MonsterUI — no change there.
3. Audit the existing MonsterUI hamburger behavior on real phones; patch targeted layout issues only if any surface.
4. Give native-speaker reviewers two Markdown artifacts: a representative cross-module exercise reference (the "is each taxonomy branch correct?" review) and an exhaustive time-exercise reference (the "every time phrase at every hour" review, replacing `time_reference.py`).

## Non-goals

- No forked/customized `NavBar` to keep the Modules dropdown always visible at mobile widths. The default MonsterUI hamburger collapse is accepted; 2 taps to switch modules on mobile (hamburger → Modules) is fine for the current scale.
- No redesign of the existing landing cards, stats grid, examples sections, or quiz area. Those are already responsive.
- No PWA manifest, no service worker, no offline mode.
- No `og:image` share card. If we want one later, it's a separate PR.
- No migration of `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md` content into the new exercise-reference doc. Two different review passes covering different copy.
- No enumeration of exhaustive answers for Numbers/Age/Weather/Prices (1,600 rows would eye-glaze reviewers); representative coverage catches the same systemic errors. Time stays exhaustive because its space is small (48 rows).

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

- **Viewport:** already emitted by MonsterUI with `width=device-width, initial-scale=1, viewport-fit=cover`. No change in this PR.
- **Description (English-only, same tag on every page):** `Adaptive Lithuanian practice: numbers, age, weather, prices, and time. Type the answer in Lithuanian; the site adapts to your weak spots.`
- **Open Graph tags:**
  - `og:title` = `Lithuanian Practice` (static, English)
  - `og:description` = same as description meta
  - `og:type` = `website`
  - `og:url` = `https://lithuanian-practice.com/` (canonical; no per-page `og:url` variants for now)
- **No `og:image`** in this PR.

### Implementation approach

`page_shell` in `ui.py` currently returns a `Div(nav, *content, ...)`. FastHTML 0.13.3 wraps this in an HTML page but silently ignores the `title=` kwarg on `fast_app(...)`, falling through to its default `"FastHTML page"`.

`page_shell` will gain a `page_title` parameter and emit head elements explicitly using FastHTML's `Title(...)` and `Meta(...)` primitives (NOT `Titled(...)`, which adds a visible `<main><h1>` wrapper to the body and would cause a layout regression). FastHTML hoists `Title` / `Meta` elements to the `<head>` automatically even when returned as siblings of body content, so the integration point is:

```python
def page_shell(..., page_title: str, lang: str = "en"):
    head = (
        Title(page_title),
        Meta(name="description", content=DESCRIPTION_META),
        Meta(property="og:title", content="Lithuanian Practice"),
        Meta(property="og:description", content=DESCRIPTION_META),
        Meta(property="og:type", content="website"),
        Meta(property="og:url", content=CANONICAL_URL),
    )
    body = Div(nav, *content, cls="min-h-screen px-4")
    return (*head, body)
```

The `fast_app(title="Lithuanian Price Quiz", ...)` kwarg is removed in this PR (no longer relied upon).

### Tests

- `test_home_page_title_en` — render `/`, assert `<title>Lithuanian Practice</title>`.
- `test_home_page_title_lt` — same, `lang="lt"`, assert `<title>Praktika</title>`.
- `test_module_page_title_en` — parameterised over the five modules, assert `<title>Numbers — Lithuanian Practice</title>` etc.
- `test_module_page_title_lt` — parameterised, LT variants.
- `test_no_body_h1_wrapper_from_title` — regression guard: render home, assert there is no stray `<h1>` injected by a `Titled(...)` primitive at the top of the body.
- `test_description_meta_present` — assert `<meta name="description" content="...">` with the full English string.
- `test_og_tags_present` — assert `og:title`, `og:description`, `og:type`, `og:url`.
- `test_viewport_meta_still_present` — smoke check that MonsterUI's viewport meta survives our head-injection changes.

---

## PR β — Mobile UX audit

### What this PR is (and isn't)

**Is:** a structured audit of the existing mobile behavior post PR α (so the viewport meta is in place and responsive classes actually fire) with targeted fixes for any concrete issues found.

**Is not:** a greenfield hamburger design. MonsterUI's `NavBar` already produces an `md:hidden` hamburger that toggles an `#mobile-menu` wrapper containing every nav item. That's the baseline — we accept it.

### Existing behavior to keep (no-op unless something breaks)

Below `md` (768px), the current navbar emits:
- Brand + hamburger button (`md:hidden`, `data-uk-toggle="target: #mobile-menu; cls: hidden"`).
- `#mobile-menu` wrapper containing every nav item in a vertical stack (`flex-col items-end`), hidden by default, toggled visible by the hamburger.

At `md`+, all nav items render inline beside the brand.

At either width, the Modules dropdown is one item among the stack (at mobile, behind the hamburger — 2 taps to switch modules; at desktop, always-visible dropdown).

### Audit checklist

Performed during implementation with Chrome DevTools (iPhone SE 375px, iPhone 14 Pro 390px, Pixel 7 412px) + one real iOS Safari check:

1. Does the hamburger button have a reasonable tap target (≥44px hit area)?
2. When tapped, does the `#mobile-menu` expand in-flow without overlapping the quiz area behind it?
3. Do the two segmented controls (Input mode, Language toggle) render sensibly in the vertical stack? Specifically:
   - Does "Input: Strict Tolerant" fit on one row, or wrap awkwardly?
   - Does "English | Lietuviškai" fit on one row?
4. Is the landing-page module-card layout (`cols_sm=1`) readable without horizontal scroll?
5. Does the quiz input (`w-full uk-form-large`) stretch edge-to-edge?
6. Does the stats-panel 2×2 metric grid (`cols_sm=2`) fit without overflow?
7. Does the 🇱🇹 emoji + "Lithuanian / Practice" brand area fit next to the hamburger button without overflow on a 320px viewport?

### Fix policy

For each checklist item:
- **Passes:** no change. Commit a note in the PR description listing what was verified.
- **Concrete layout bug:** smallest-possible fix. Prefer adding a responsive utility class to the offending element over restructuring layout.
- **Subjective "could be nicer":** out of scope for this PR. Note it as a follow-up candidate.

### Files touched

Unknown in advance — depends on audit findings. Most likely either `ui.py` alone (responsive class tweaks) or zero files at all. Either way, test assertions cover the invariants.

### Tests

- `test_navbar_hamburger_button_exists` — regression guard: render `page_shell`, assert an `md:hidden` element with icon `menu` is present. Ensures future refactors don't silently remove the primitive MonsterUI gives us.
- `test_navbar_mobile_menu_wrapper_exists` — regression guard: assert `#mobile-menu` id is emitted.
- `test_navbar_all_items_reachable_in_mobile_menu` — assert Modules, Stats, Input-mode controls, Feedback, Language controls, and Login/Logout markup are all present inside the `#mobile-menu` container (so the audit can't later accidentally hide one without noticing).

### Merge criteria

- The three regression tests pass.
- Audit checklist completed with each item marked pass or linked to a specific commit that patches it.
- One real-phone manual verification screenshot posted in the PR description (or a note that no phone was available and the DevTools-only audit is the gate). For a hobby-scale project, DevTools emulation is acceptable.

---

## PR γ — Native-speaker exercise review docs

### Files created

- `scripts/generate_exercise_reference.py` — generator script, idempotent. Emits **two** output documents:
  - `docs/reviews/exercise-reference.md` (representative, cross-module, ~66 rows)
  - `docs/reviews/time-reference.md` (exhaustive, all 48 time expressions across 12 hours × 4 types)

### Files retired

- `time_reference.py` (at repo root) — its exhaustive output is subsumed into `docs/reviews/time-reference.md` produced by the new generator.

### Docs that need updating in the same PR

The old `time_reference.py` is referenced in:
- `CLAUDE.md` — the file-structure section lists it as a live tool.
- `HANDOFF.md` — probably mentions it as part of project context.
- `FUTURE_MODULES.md` — mentions it under the native-speaker-spot-check section.

Each reference is updated to point at `scripts/generate_exercise_reference.py` and its two output docs.

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
- Representative-mode exercise lists stored as explicit tuples per module near the top of the script, grouped by subsection heading. Reviewers who want more examples can edit the tuple list and rerun.
- Exhaustive-time mode iterates over the full 12 hours × 4 time types = 48 combinations using `TimeEngine` directly. Grouped in the output by time type (whole_hour / half_past / quarter_past / quarter_to).
- Writes both documents, overwriting.
- Top of each generated doc includes a one-line header: `<!-- Generated by scripts/generate_exercise_reference.py on YYYY-MM-DD. Do not edit by hand. -->`.

### Tests (in `tests/test_regressions.py`)

- `test_exercise_reference_doc_in_sync` — runs the generator into temp buffers, strips the date-line from both buffers and both committed docs, asserts byte equality for each. Guarantees neither committed doc can silently drift from engine output.

### Relationship to existing docs

- `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md` (interface chrome: navbar, card labels, reset modal copy) — unchanged.
- `time_reference.py` (standalone time-exercise enumeration script) — deleted; replaced by `docs/reviews/time-reference.md` which the new generator produces.

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

**R1. `Title`/`Meta` returned alongside body tags doesn't hoist to `<head>` on this FastHTML version.** Likelihood: low but non-zero. Mitigation: test locally immediately after wiring up `page_shell`'s new return shape. If hoisting doesn't work, fallback is to pass `hdrs=[Title(...), Meta(...), ...]` to `fast_app(...)` once and have `page_shell` never change the title (single static title) — but that surrenders per-route titles. Verify before writing the implementation code.

**R2. Representative coverage in PR γ misses a real error mode.** Likelihood: always non-zero. Mitigation: the generator tuples are easy to extend — if the reviewer spots a missing branch, we add examples and regenerate. Not a merge blocker.

**R3. `og:image` absence makes shared links look bland.** Acceptable. Follow-up PR can add a minimal share card if/when we care about virality.

**R4. `_not_found` page currently renders outside the normal `_render_page` path** (it has its own direct `page_shell` call with exception context). Needs explicit title plumbing in its handler too. Mitigation: part of PR α's scope — handler gets `page_title="Page not found — Lithuanian Practice"` (or LT equivalent).

**R5. Mobile audit surfaces something big and open-ended.** PR β fix policy caps scope at smallest-possible fixes for concrete bugs; subjective nits are deferred. If the audit reveals a legitimately large issue (e.g. the hamburger primitive is actively broken on iOS Safari), we close PR β without the fix and open a narrower follow-up PR rather than let scope balloon.

---

## Success criteria

- **α:** Every route serves the right `<title>`; description + OG tags present in the home page HTML; no stray `<h1>` body injection. Test suite assertions hold.
- **β:** Audit checklist completed with each item pass-or-patched. No horizontal scroll on a 375px viewport. The three regression tests (hamburger button exists, mobile-menu wrapper exists, all items reachable) hold.
- **γ:** Both `docs/reviews/exercise-reference.md` (representative) and `docs/reviews/time-reference.md` (exhaustive) exist and can be reviewed on GitHub. `scripts/generate_exercise_reference.py` re-runs cleanly and produces identical output for both. `time_reference.py` is deleted. `CLAUDE.md` / `HANDOFF.md` / `FUTURE_MODULES.md` references updated. Test asserts both committed docs are in sync with the engines.
