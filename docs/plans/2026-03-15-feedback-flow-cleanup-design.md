# Feedback Flow Cleanup Design

## Summary

This pass focuses on reliability, not new features. The app currently builds feedback and stats from mutable session state that is also used to hold the next question. That makes the post-submit flow fragile across modules, especially when a handler generates the next exercise before every feedback consumer has finished reading the answered one.

## Goals

- Make wrong-answer feedback always describe the exercise that was just submitted.
- Apply the same fix shape across module routes and mixed practice mode.
- Remove or simplify any practice-page stats/history UI that cannot be proven stable in tests during this pass.
- Reduce copy-paste in answer handlers where shared helpers lower the chance of future regressions.

## Non-Goals

- No new learning features or new stats views.
- No redesign of the adaptive engines.
- No changes to scoring rules beyond fixing stale-state bugs.

## Root Cause

The app stores both the answered exercise and the next exercise in the same session namespace. Several handlers already preserve parts of the answered state, but the overall flow is inconsistent and easy to break because feedback, history, grammar hints, and OOB stats are assembled around mutable session keys. Any logic that reads from the session after `_new_*_question()` risks pulling details from the new prompt instead of the answered one.

## Chosen Approach

Use an immutable answered snapshot per submission:

1. Capture the answered question, normalized user input, correct answer, diff output, exercise metadata, and any module-specific rendering context before generating the next question.
2. Build feedback and history entries only from that snapshot.
3. Keep the new-question generation step separate from the answered snapshot so the UI can safely show "previous answer" and "current exercise" together.
4. Centralize the repeated feedback/history assembly in helper functions where that reduces route-specific drift.
5. If sidebar sections still depend on fragile live state, remove those sections from practice pages for now and keep only stable counters/history.

## Files In Scope

- `main.py`
- `ui.py`
- `tests/test_regressions.py`
- `tests/test_ui.py`

## Validation

- Add failing regression tests for the reproduced `6:15 -> blank -> 8:45` bug shape.
- Add at least one regression for another module route.
- Preserve the existing mixed-practice time regression coverage and extend it if the new helper changes that path.
- Run targeted tests during TDD, then run the full suite.

## Risks

- Shared helper refactors can accidentally erase module-specific context such as grammar hints or row-based explanations.
- Removing unstable sidebar content is safer than leaving misleading content live, but it temporarily narrows the UI.

## Rollback Preference

If a stats/history section cannot be made trustworthy quickly, prefer removing it from the practice page response and leaving the dedicated stats page for later cleanup.
