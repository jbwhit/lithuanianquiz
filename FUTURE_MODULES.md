# Future Work

Everything still to do — UI polish, new modules, and open issues.

---

## UI / UX Polish

### Mobile UX
Layout hasn't been tested on phones. The 4-column stats grid may be cramped. The navbar with 7+ links likely needs a hamburger menu on small screens.

---

## Practice-All Mode

A "Practice All" option that randomly pulls exercises from any module the user has tried. Could weight toward weaker modules using existing Thompson Sampling data. Would need a unified question/answer interface that dispatches to the right engine.

---

## Native Speaker Spot Check

~~Generate a document with all exercise types and their correct answers for native speaker review.~~ **Done.** `scripts/generate_exercise_reference.py` produces two review docs: representative cross-module `docs/reviews/exercise-reference.md` (52 rows) and exhaustive `docs/reviews/time-reference.md` (48 rows).

Open question: is "Pusė trečios" (ordinal genitive) or "Pusė trijų" (cardinal genitive) the standard form for half past? This needs native speaker verification.

---

## New Modules (roughly ordered by difficulty)

### Level 1.5: Number Gender

**Skill:** Produce the masculine or feminine form of a number.

Lithuanian numbers 1-9 (and their compound ones digits) have gender:
- 1: vienas / viena
- 2: du / dvi
- 3: trys / trys (same)
- 4: keturi / keturios
- 5: penki / penkios
- 6: seši / sesios
- 7: septyni / septynios
- 8: astuoni / astuonios
- 9: devyni / devynios

Numbers 10+ have no gender distinction (except compound ones digits: 21, 32, etc.).

**Exercise types:**
- "Say 5 (feminine)" -> "penkios"
- "Say 21 (feminine)" -> "dvidesimt viena"
- "viena -> ? (gender)" -> "feminine"

**What's needed:**
- Feminine forms can be hardcoded (~9 entries) -- no DB changes needed
- Small engine, ~15 relevant numbers for 1-20, more for 1-99
- Could reuse NumberEngine with a gender dimension added, or standalone engine
- Scope: small

---

### Level 2.5: Number-Noun Agreement

**Skill:** Use numbers with concrete nouns in the correct gender and case.

This is the full integration: number + noun + gender agreement + case.
- "3 girls (nom.)" -> "trys mergaites"
- "2 boys (acc.)" -> "du berniukus"
- "5 books (gen.)" -> "penkiu knygu"

**Rules by number range:**
| Range | Gender agreement? | Noun form |
|-------|-------------------|-----------|
| 1 | Yes | Singular, same case as context |
| 2-9 | Yes (for 1-9 digits) | Plural, number & noun both decline |
| 10-19 | No | Genitive plural always |
| 20, 30... | No | Genitive plural always |
| Compounds | Ones digit rules | Ones digit determines pattern |

**What's needed:**
- A set of common nouns (5-10) with full declension tables, mix of masculine and feminine
  - Masculine: berniukas (boy), namas (house), automobilis (car)
  - Feminine: mergaite (girl), knyga (book), kate (cat)
- Engine that generates (number, noun, case) triples
- Correct answer builder that applies agreement rules
- Adaptive tracking over: gender, case, number_range, noun
- Scope: large -- needs noun declension data and complex agreement logic
- Consider starting with nominative + accusative only, add cases incrementally

---

### Other Ideas (not yet fleshed out)

**Ordinal Numbers** — "What is 5th in Lithuanian?" -> "penktas" (m) / "penkta" (f). Used for dates, floors, positions. Gender-dependent. Could pair with months for a dates module.

**Dates** — "January 15th" -> "sausio penkiolikta diena". Requires: month names + ordinal numbers + genitive of month.

**Shopping Quantities (accusative practice)** — "Give me 3 apples" -> "Duokite tris obuolius." Focused accusative drill with common nouns. Subset of Number-Noun Agreement but with a concrete, practical framing.

**Measurements** — "5 kilograms" -> "penki kilogramai" / "penkiu kilogramu". Similar to temperature/price pattern but with different unit nouns (kilogramai, litrai, kilometrai).

**Collective Numerals (advanced)** — Formal age expressions: "Man treji metai" (I am 3 years old). Separate number paradigm (vieneri, dveji, treji, ketveri, penkeri...). Niche but important for formal/written Lithuanian.

---

## Done

- ~~**Age in Years**~~ — Implemented. Dative pronouns (Man/Tau/Jam/Jai) + number words + metai/metu. Ages 2-99, produce/recognize, Thompson Sampling. Seeds from numbers.
- ~~**Weather Temperature**~~ — Implemented. Number words + laipsnis/laipsniai/laipsnių. Range -20 to +40, produce/recognize, Thompson Sampling. Seeds from numbers.
- ~~**Numbers 0-99**~~ — Implemented. Consolidated from earlier 1-20 / 1-99 split.
- ~~**Prices**~~ — Implemented.
- ~~**Time**~~ — Implemented. Whole hours, half past, quarter past, quarter to.
- ~~**Landing page card alignment**~~ — Flexbox bottom-aligned buttons.
- ~~**404 page**~~ — Friendly page with Back to Home link.
- ~~**/error route**~~ — OAuth failure page with Try Again / Home links.
- ~~**Input autocorrect**~~ — spellcheck=false + autocorrect=off on answer input.
