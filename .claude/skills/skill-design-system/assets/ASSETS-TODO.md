# Assets TODO: Swap in official vectors

**Status:** Open · flagged 2026-05-22 · owner: Creative team

The three SVG files in this folder are clean recreations built from the AF Brand Guidelines v5 PDF (pages 30 to 36). They follow the rules and read correctly in normal use, but they are not the official source vectors held by Creative.

## What needs to happen

Creative team to deliver the following files for drop-in replacement:

1. **logo-wordmark.svg** — the standalone wordmark, lowercase, Glacial Indifference Bold, with the ® mark in the correct position. Currently using a text-rendered version with DM Sans web fallback.
2. **logo-icon.svg** — the three-arch icon. Currently recreated with stroked paths at approximate proportions. Need the actual Illustrator-sourced vector.
3. **logo-lockup.svg** — the extended lockup (icon + wordmark together). Same situation.

## Constraints for the replacements

- Must use `currentColor` or `fill="#0F0F0F"` so they can be recolored via CSS
- Must include a `<title>` for accessibility
- Should be optimized (SVGO or similar), no embedded raster, no Illustrator metadata
- Should render correctly at 30pt minimum size

## Until then

The current SVGs are fine for internal tools, agent-generated dashboards, and prototypes. They should NOT be used for:
- Customer-facing materials (packaging, ads, social, retail)
- Anything going to a marketplace store page
- Press materials or partner pitches

For anything customer-facing, pull the official vectors from the Creative team directly.

## How to swap

When the official files arrive, just replace the three files in this directory with the new ones. Filenames stay the same. Nothing else in the skill needs to change. Bump the version in SKILL.md from 1.0 to 1.1.
