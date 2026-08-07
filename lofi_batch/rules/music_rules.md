# Music prompt generation rules

You receive a Lo-Fi theme. Write a full ACE-Step music prompt for that theme.

Return ONLY a single JSON object (no markdown fences, no commentary) with exactly this key:

- `music_prompt`: full ACE-Step music prompt including a `NEGATIVE PROMPT` section

## Required structure

Write `music_prompt` in this shape:

1. Short positive brief (mood + setting + feeling) in plain sentences
2. Explicit instrumentation limits (“Only these instruments: … Nothing else.”)
3. Texture / pacing instructions (sparse, slow, soft, pauses allowed)
4. A blank line, then a header exactly: `NEGATIVE PROMPT`
5. A long block of `NO …` lines listing forbidden elements (vocals, drums if unwanted, EDM, brass stabs, risers, choir, etc.) tailored to the piece

## Classic Lo-Fi constraints

- Instrumental only — no sung or spoken vocals
- Soft, chill, intimate atmosphere
- Gentle dynamics; no hype drops, no climax builds, no trailer energy
- Optional subtle vinyl crackle or room tone
- Limited instrumentation (typically 2–4 elements), clearly named
- Slow-to-moderate pulse if any; sparse melodies; space and breathing matter
- Avoid EDM, hard trap, metal, orchestral action, hybrid trailer, choir
