# Metadata generation rules

You receive a Lo-Fi theme. Create YouTube metadata that matches it.

Return ONLY a single JSON object (no markdown fences, no commentary) with exactly these keys:

- `title`: YouTube title (under 100 characters, catchy but chill)
- `description`: 2–4 short sentences describing the vibe
- `tags`: non-empty JSON array of relevant strings (mix of broad and specific tags)

## Constraints

- Title should feel organic, not clickbait; no all-caps shouting
- Description must be instrumental/chill focused; no lyrics, no timestamps
- Tags should include: `lofi`, `lo-fi`, plus 3–6 mood/setting/instrument tags
- No hashtags in title or description
