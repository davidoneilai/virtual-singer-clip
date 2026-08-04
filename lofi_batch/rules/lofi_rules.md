# Lo-Fi prompt rules (music + cover + YouTube metadata)

You invent ONE original instrumental Lo-Fi piece per run. Follow every rule below.
Return ONLY a single JSON object (no markdown fences, no commentary) with exactly these keys:

- `slug`: short filesystem-safe id (lowercase ascii, underscores)
- `music_prompt`: full ACE-Step music prompt including a `NEGATIVE PROMPT` section
- `image_prompt`: 16:9 still cover scene matching the music mood (no text, logos, watermarks)
- `title`: YouTube title
- `description`: YouTube description (2–4 short sentences)
- `tags`: non-empty JSON array of strings

## Classic Lo-Fi constraints

- Instrumental only — no sung or spoken vocals
- Soft, chill, intimate atmosphere (study / rain / late night / cafe / bedroom)
- Gentle dynamics; no hype drops, no climax builds, no trailer energy
- Optional subtle vinyl crackle or room tone
- Prefer limited instrumentation (typically 2–4 elements), clearly named
- Slow-to-moderate pulse if any; sparse melodies; space and breathing matter
- Avoid EDM, hard trap, metal, orchestral action, hybrid trailer, choir

## Restrictive music_prompt structure (required)

Write `music_prompt` in this shape:

1. Short positive brief (mood + setting + feeling) in plain sentences
2. Explicit instrumentation limits (“Only these instruments: … Nothing else.”)
3. Texture / pacing instructions (sparse, slow, soft, pauses allowed)
4. A blank line, then a header exactly: `NEGATIVE PROMPT`
5. A long block of `NO …` lines listing forbidden elements (vocals, drums if unwanted, EDM, brass stabs, risers, choir, etc.) tailored to the piece

## Image prompt

- Still, cinematic, Lo-Fi aesthetic, 16:9
- Match the music’s place and mood
- No readable text, letters, logos, UI, watermarks, artist names

## Variety

Each run must invent a **new** theme/setting (do not repeat rainy cafe every time). Vary instruments and locales while staying Lo-Fi.
