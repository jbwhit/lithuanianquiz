# Polish PR β — Mobile UX Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the existing MonsterUI hamburger navbar behavior on real and emulated mobile viewports, add regression tests that freeze the current mobile primitives in place, and apply smallest-possible fixes only for concrete issues found.

**Architecture:** No greenfield navbar design. MonsterUI's `NavBar` already produces an `md:hidden` hamburger button toggling an `#mobile-menu` wrapper containing every nav item. This plan verifies that primitive and adds regression tests so future refactors can't silently remove it. Fixes, if any, are tactical (responsive class adjustments), not structural.

**Tech Stack:** MonsterUI navbar primitive, Tailwind responsive utilities, Chrome DevTools device emulation.

**Background reading:**
- `docs/superpowers/specs/2026-04-17-polish-bucket-design.md` §PR β — the spec this plan implements.
- Ships AFTER the head-tags PR so the viewport meta is deployed and responsive classes actually fire on mobile.

**Working directory:** Commands assume `/Users/jonathan/projects/lithuanianquiz/.worktrees/polish-mobile-audit`. Task 0 creates it.

---

## File structure

**Modify:**
- `tests/test_ui.py` — add regression tests that the hamburger button, `#mobile-menu` wrapper, and all nav items inside it remain intact.
- `ui.py` — only if the audit finds concrete layout bugs. Likely untouched.

**No new files.**

---

## Task 0: Worktree setup

- [ ] **Step 1: Create worktree**

Run:
```bash
cd /Users/jonathan/projects/lithuanianquiz
git fetch origin
git worktree add -b polish-mobile-audit .worktrees/polish-mobile-audit origin/main
cd .worktrees/polish-mobile-audit
```

- [ ] **Step 2: Verify baseline**

Run: `uv run --extra dev pytest 2>&1 | tail -3`
Expected: all tests pass.

---

## Task 1: Add regression tests for the existing hamburger primitives

These tests freeze the current mobile nav structure. They do **not** add any new behavior — they guard against a future refactor accidentally removing the hamburger button or the mobile-menu wrapper.

**Files:**
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Write the tests**

Append to `tests/test_ui.py`:

```python
class TestNavbarMobilePrimitives:
    """Freeze the existing MonsterUI mobile-nav behavior.

    NavBar already emits an md:hidden hamburger toggling an #mobile-menu
    wrapper that contains every nav item (Modules dropdown, Stats, Input
    mode, Feedback, Language toggle, user/login). These tests ensure a
    future refactor can't silently remove that primitive.
    """

    def test_hamburger_button_present_and_md_hidden(self) -> None:
        html = _render(page_shell("body", page_title="Lithuanian Practice"))
        assert 'aria-controls="mobile-menu"' in html, (
            "hamburger button with aria-controls=mobile-menu not found"
        )
        assert 'icon="menu"' in html, "menu icon missing from hamburger"
        # Hamburger must be hidden at md+ (desktop shows the full nav inline).
        # MonsterUI's NavBar class string includes 'md:hidden' on the button.
        import re
        m = re.search(
            r'<button[^>]*aria-controls="mobile-menu"[^>]*class="([^"]*)"', html
        )
        assert m, "could not locate hamburger button's class attribute"
        assert "md:hidden" in m.group(1), (
            f"hamburger button missing md:hidden class; got: {m.group(1)!r}"
        )

    def test_mobile_menu_wrapper_present(self) -> None:
        html = _render(page_shell("body", page_title="Lithuanian Practice"))
        assert 'id="mobile-menu"' in html, "#mobile-menu wrapper missing"

    def test_all_nav_items_reachable_in_mobile_menu(self) -> None:
        """Assert each primary/secondary nav item is inside the mobile-menu
        wrapper. Catches the case where a future refactor renders an item
        outside #mobile-menu (so it'd disappear entirely on mobile)."""
        html = _render(
            page_shell(
                "body",
                page_title="Lithuanian Practice",
                lang="en",
                user_name="Jane",
            )
        )
        import re
        m = re.search(
            r'<div id="mobile-menu"[^>]*>(.*?)</div>\s*</nav>', html, re.DOTALL
        )
        assert m, "could not isolate #mobile-menu block"
        menu_html = m.group(1)

        for needle in (
            'href="/numbers"',
            'href="/stats"',
            "set-diacritic-mode",
            '"/set-language?lang=en"',
            '"/set-language?lang=lt"',
            "github.com/jbwhit/lithuanianquiz/issues/new",
            'href="/logout"',
        ):
            assert needle in menu_html, (
                f"expected {needle!r} inside #mobile-menu; got: ...{menu_html[:400]}..."
            )

    def test_anonymous_session_shows_login_in_mobile_menu(self) -> None:
        html = _render(page_shell("body", page_title="Lithuanian Practice"))
        assert 'href="/login"' in html
```

- [ ] **Step 2: Run**

Run: `uv run --extra dev pytest tests/test_ui.py::TestNavbarMobilePrimitives -v 2>&1 | tail -15`
Expected: all pass (these assert current behavior, not new behavior).

If any fail, the MonsterUI primitive changed shape in a newer version or our page_shell altered the output. Investigate before committing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ui.py
git commit -m "test(ui): regression tests for the existing mobile hamburger nav

Freeze MonsterUI's current mobile-nav primitives so a future refactor
can't silently remove them: hamburger button with aria-controls and
md:hidden class, #mobile-menu wrapper, and every nav item reachable
inside that wrapper.

These tests cover the current behavior only. PR β adds no new nav
design; audit-driven fixes (if any) follow in later tasks."
```

---

## Task 2: Mobile audit — run the checklist

Execute the audit checklist from spec §PR β and record findings. This task produces a Markdown note inside the PR description, not a code change.

- [ ] **Step 1: Start the dev server**

Run (in one terminal, from the worktree):
```bash
uv run python main.py
```
Expected: server listens on `http://localhost:5001/`.

- [ ] **Step 2: Open Chrome DevTools device emulation**

Open `http://localhost:5001/` in Chrome. Hit `⌘⌥I` (Mac) / `F12` to open DevTools. Click the device-toggle icon (or `⌘⇧M`). Select each of these presets in turn:

1. **iPhone SE** (375 × 667)
2. **iPhone 14 Pro** (393 × 852) — or any ~390px preset
3. **Pixel 7** (412 × 915)

- [ ] **Step 3: Work the checklist on each viewport**

For each preset, check each item and record the result in a scratch note:

1. **Hamburger tap target.** Tap-size ≥ 44×44px? (Eyeball or use DevTools to measure the button box.)
2. **Hamburger expansion behavior.** Tap the hamburger: does `#mobile-menu` expand in flow and push the quiz area down, or does it overlap content? (Expected: pushes down.)
3. **Segmented controls in stacked menu.** "Input: Strict Tolerant" — does it fit in one row inside the menu? "English | Lietuviškai" — same question.
4. **Landing-page cards readable.** No horizontal scroll; each card visually complete.
5. **Quiz input full-width.** Input stretches edge-to-edge minus the card padding.
6. **Stats panel 2×2 metrics.** At `/stats` or after answering a question, does the 2×2 grid fit without overflow?
7. **Brand area.** `🇱🇹 Lithuanian Practice` fits next to the hamburger button without the wordmark getting clipped or overflowing.

- [ ] **Step 4: Real iOS Safari check (if a phone is at hand)**

Point iOS Safari at `http://<mac-local-ip>:5001/` (find Mac IP via `ifconfig | grep "inet "`). Work the same checklist. Note any iOS-specific differences.

If no phone is available, note "DevTools emulation only; no real-phone check this round" in the PR description. DevTools emulation is acceptable for a hobby-scale audit.

- [ ] **Step 5: Summarize findings**

Write a scratch summary in the worktree root: `_audit-findings.md` (gitignored or deleted after PR):

```markdown
# Mobile audit findings — {date}

## iPhone SE (375px)

1. Hamburger tap target: PASS / FAIL (description)
2. Expansion behavior: PASS / FAIL
3. Segmented controls: PASS / FAIL
4. Landing cards: PASS / FAIL
5. Quiz input: PASS / FAIL
6. Stats 2×2: PASS / FAIL
7. Brand area: PASS / FAIL

## iPhone 14 Pro (393px)

... (same checklist)

## Pixel 7 (412px)

... (same checklist)

## iOS Safari (if available)

... (same checklist)
```

Compile the pass/fail results into the PR description later. Do **not** commit `_audit-findings.md`.

---

## Task 3: Apply targeted fixes for failing items (if any)

Only runs if Task 2 found concrete bugs. Skip entirely if everything passed.

**Files:**
- Modify: `ui.py` — per-finding scope; most fixes are adding or tweaking a single Tailwind/MonsterUI class.

- [ ] **Step 1: For each failing checklist item, decide the fix**

Each fix must be **the smallest class-level change that addresses the observed bug**. Do not restructure layout; do not add a new component. Examples by kind of bug:

- Overflow of a segmented control: add `flex-wrap` to its container.
- Overflow of the brand wordmark: add `truncate` or `min-w-0` to the wordmark span.
- Tap target too small: change `p-2` → `p-3` or add `min-w-[44px] min-h-[44px]` to the hamburger button.
- Expansion overlap: verify `#mobile-menu`'s class has `w-full` and the container below has enough `mt-*`.

If a bug is not fixable with a small class change, abort PR β per spec R5: "If the audit reveals a legitimately large issue, we close PR β without the fix and open a narrower follow-up PR rather than let scope balloon."

- [ ] **Step 2: Write a failing test first for each fix**

For example, if the fix is "add `truncate` to the brand wordmark":

```python
def test_brand_wordmark_is_truncate_safe(self) -> None:
    """Regression guard for an observed wordmark overflow at 320px."""
    html = _render(page_shell("body", page_title="Lithuanian Practice"))
    # The <h3> inside the brand should carry the truncate class so it
    # doesn't push the hamburger off-screen at narrow widths.
    import re
    m = re.search(r'<h3[^>]*class="([^"]*)"[^>]*>Lithuanian</h3>', html)
    assert m, "brand wordmark h3 not found"
    assert "truncate" in m.group(1), (
        f"brand wordmark missing truncate class; got: {m.group(1)!r}"
    )
```

- [ ] **Step 3: Run to confirm failure**

Run: `uv run --extra dev pytest tests/test_ui.py::<new_test> -v`
Expected: FAIL (class not yet present).

- [ ] **Step 4: Apply the smallest-possible fix in `ui.py`**

For the example above: find the `H3(...)` in `page_shell` and add `truncate` to its cls tuple.

- [ ] **Step 5: Run test — passes**

Run: `uv run --extra dev pytest tests/test_ui.py::<new_test> -v`
Expected: PASS.

- [ ] **Step 6: Re-verify the affected viewport in DevTools**

Reload the dev server's rendered page at the viewport that originally failed. Confirm the bug is gone.

- [ ] **Step 7: Full suite + ruff after all fixes**

Run: `uv run --extra dev pytest && uv run --extra dev ruff check . && uv run --extra dev ruff format --check .`
Expected: all green.

- [ ] **Step 8: Commit per fix** (one commit per logical fix, not one commit per step above)

Example:
```bash
git add ui.py tests/test_ui.py
git commit -m "fix(ui): truncate brand wordmark to prevent 320px overflow

Audit at iPhone SE found the 'Lithuanian / Practice' h3 pushing the
hamburger button off-screen on very narrow viewports. Added truncate
to the wordmark's class set.
"
```

---

## Task 4: PR + deploy + production smoke

- [ ] **Step 1: Push**

```bash
git push -u origin polish-mobile-audit
```

- [ ] **Step 2: Open PR**

Run:
```bash
gh pr create --base main --head polish-mobile-audit \
  --title "feat: mobile nav audit + regression tests (polish β)" \
  --body "$(cat <<'EOF'
## Summary

Implements spec §PR β of `docs/superpowers/specs/2026-04-17-polish-bucket-design.md`.

Accepts the existing MonsterUI hamburger primitive (md:hidden button toggling #mobile-menu) as the mobile nav design. This PR adds regression tests that freeze the current primitive in place, plus any targeted fixes surfaced by the audit checklist.

## Audit results

### Chrome DevTools — iPhone SE (375px)

1. Hamburger tap target: PASS
2. Expansion behavior: PASS
3. Segmented controls: PASS
4. Landing cards: PASS
5. Quiz input: PASS
6. Stats 2×2: PASS
7. Brand area: PASS

### Chrome DevTools — iPhone 14 Pro (393px)

(copy findings from `_audit-findings.md` here)

### Chrome DevTools — Pixel 7 (412px)

(copy findings from `_audit-findings.md` here)

### iOS Safari

(copy findings from `_audit-findings.md` here, or note 'DevTools emulation only this round')

## Fixes applied

(list commits with 'fix:' prefix, or state 'None — audit found no concrete bugs.')

## Test plan

- [x] New `TestNavbarMobilePrimitives` regression tests pass.
- [x] Any per-fix tests pass.
- [x] Full suite green.
- [ ] CI green.
- [ ] Post-merge: one more DevTools pass on the deployed site at lithuanian-practice.com.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, merge, deploy**

```bash
gh pr merge <pr-number> --squash
cd /Users/jonathan/projects/lithuanianquiz
git checkout main
git pull --ff-only origin main
git worktree remove .worktrees/polish-mobile-audit
git branch -d polish-mobile-audit
git push origin --delete polish-mobile-audit
railway up --detach
```

Poll `railway service status` until `SUCCESS`.

- [ ] **Step 4: Post-deploy smoke**

Open `https://lithuanian-practice.com/` on a phone (or DevTools emulation). Tap the hamburger. Verify all items reachable. Confirm no horizontal scroll on the landing page.

---

## Self-review notes

**Spec coverage:**
- Audit checklist → Task 2.
- Regression tests → Task 1.
- Fix policy (smallest-possible-fix for concrete bugs) → Task 3.
- Fixes deferred if big → Task 3 Step 1 explicit fallback.
- Manual smoke → Task 2 Step 4, Task 4 Step 4.

**Placeholder scan:** every step has concrete commands or code — no TBDs. The Task 3 code sample uses "if observed bug is X, fix is Y" framing because fixes are contingent on audit findings; that's correct for an audit-driven PR.

**Type consistency:** N/A — no new types or APIs introduced.
