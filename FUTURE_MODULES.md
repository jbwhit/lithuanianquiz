# Future Module Ideas

Tracked ideas for new practice modules, roughly ordered by difficulty level.

---

## Level 1.5: Number Gender

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
- "Say 21 (feminine)" -> "dvidesmt viena"
- "viena -> ? (gender)" -> "feminine"

**What's needed:**
- Feminine forms can be hardcoded (~9 entries) -- no DB changes needed
- Small engine, ~15 relevant numbers for 1-20, more for 1-99
- Could reuse NumberEngine with a gender dimension added, or standalone engine
- Scope: small, a few hours of work

---

## Level 2: Age in Years

**Skill:** Express someone's age in Lithuanian.

Pattern: "[Name/pronoun] [number word] [metai/metu]."
- "Man 25 metai." (I am 25 years old.)
- "Jai 12 metu." (She is 12 years old.)

The DB already has a `years` column with the correct metai/metu form per number:
- `metai` (nom. plural) for 1-9 and compounds ending in 1-9
- `metu` (gen. plural) for 10-19 and exact decades (20, 30, ...)

**Exercise types:**
- Produce: "How do you say 'She is 25 years old'?" -> "Jai dvidesmt penki metai."
- Recognize: "Man penkiolika metu." -> "I am 15 years old."

**What's needed:**
- Pronoun set: man (I), tau (you), jam (him), jai (her) -- dative forms
- Number words from existing kokia_kaina column (+ compound)
- years column already in DB
- Engine generates (pronoun, number) pairs
- Adaptive tracking over: pronouns, number_patterns, exercise_types
- Scope: moderate, similar to time module

**Linguistic note:** Colloquial Lithuanian often uses the basic cardinal numbers
for age (as above). Formal/literary Lithuanian uses collective numerals
(vieneri, dveji, treji, ketveri, penkeri...) which are a separate paradigm.
Start with the colloquial pattern; collective numerals could be a Level 3 module.

---

## Level 2: Weather Temperature

**Skill:** Express temperature in Lithuanian.

Pattern: "[Number] [laipsnis form]" (degrees Celsius).
- "Siandien 20 laipsniu." (Today is 20 degrees.)
- "Minus 5 laipsniai." (Minus 5 degrees.)

The word "laipsnis" (degree) declines similarly to "euras":
- 1: laipsnis (nom. sg.)
- 2-9: laipsniai (nom. pl.)
- 10-19, decades: laipsniu (gen. pl.)

Negative temperatures add "minus" prefix -- number word stays the same.

**Exercise types:**
- Produce: "How do you say 15 degrees?" -> "penkiolika laipsniu"
- Produce: "How do you say -3 degrees?" -> "minus trys laipsniai"
- Recognize: "dvidesmt laipsniu" -> "20 degrees"

**What's needed:**
- Laipsnis declension forms: laipsnis/laipsniai/laipsniu (3 forms, hardcoded)
- Rules for which form to use (same pattern as metai/metu/eurai/euru)
- Temperature range: -20 to +40 (or similar realistic range)
- Negative numbers reuse existing number words with "minus" prefix
- Engine similar to age module but with the laipsnis noun
- Scope: moderate, very similar structure to age module

---

## Level 2.5: Number-Noun Agreement

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
  - Feminine: mergaite (girl), knyga (book), katė (cat)
- Engine that generates (number, noun, case) triples
- Correct answer builder that applies agreement rules
- Adaptive tracking over: gender, case, number_range, noun
- Scope: large -- needs noun declension data and complex agreement logic
- Consider starting with nominative + accusative only, add cases incrementally

---

## Other Ideas (not yet fleshed out)

### Ordinal Numbers
"What is 5th in Lithuanian?" -> "penktas" (m) / "penkta" (f).
Used for dates, floors, positions. Gender-dependent. Could pair with months
for a dates module.

### Dates
"January 15th" -> "sausio penkiolikta diena" (or just "sausio penkiolikta").
Requires: month names + ordinal numbers + genitive of month.

### Shopping Quantities (accusative practice)
"Give me 3 apples" -> "Duokite tris obuolius."
Focused accusative drill with common nouns. Subset of Number-Noun Agreement
but with a concrete, practical framing.

### Measurements
"5 kilograms" -> "penki kilogramai" / "penkiu kilogramu".
Similar to temperature/price pattern but with different unit nouns
(kilogramai, litrai, kilometrai). Good for reinforcing the number-noun
declension pattern across multiple nouns.

### Collective Numerals (advanced)
Formal age expressions: "Man treji metai" (I am 3 years old).
Separate number paradigm (vieneri, dveji, treji, ketveri, penkeri...).
Niche but important for formal/written Lithuanian.
