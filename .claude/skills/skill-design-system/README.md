# af-design-system

The Americanflat design system, packaged as a skill that any AF agent or staff member can load when building tools, dashboards, agents, or any visual output that carries the AF name.

## What this is

A single source of truth for AF brand application in tools and software. Pulled directly from the Americanflat Brand Guidelines v5 (Feb 2025) and translated into things engineers and agents can actually use: CSS tokens, a Tailwind config snippet, JSON tokens, SVG logos, ready-to-paste HTML templates, and a do/don't checklist.

## Who uses it

- Anyone on the AF team building a tool, dashboard, internal app, or visual artifact
- Any agent in the `af-agents` fleet that produces visual output (HTML, slides, Slack posts, reports)
- Outside partners producing AF-branded materials

## How to use it (for humans)

1. Read `SKILL.md` first. It tells you what the skill covers and how to apply it.
2. Pick your output type:
   - Building HTML? Open `templates/dashboard.html` and start from there.
   - Building React? Add `tokens/tailwind.config.snippet.js` to your config.
   - Building a Python or Slack tool? Use `tokens/tokens.json`.
3. Use the logos from `assets/`. Do not redraw or recolor them.
4. Before shipping, run through the checklist in `REFERENCE.md`.

## How to use it (for agents)

Agents should load `SKILL.md` at the start of any task that produces visual output for AF. The skill triggers on phrases like "AF dashboard", "on-brand", "build a tool for ops", "create a visual for Americanflat", or any HTML/CSS work for an AF project.

Once loaded, the skill points to:

- `tokens/tokens.css` for the CSS variables to paste at the top of any stylesheet
- `templates/dashboard.html` for the starting structure
- `assets/logo-*.svg` for the logo files
- `REFERENCE.md` for the rules

## Repo layout

```
af-design-system/
├── SKILL.md                     The skill itself (start here)
├── README.md                    This file
├── REFERENCE.md                 Do/don't checklist and detailed rules
├── tokens/
│   ├── tokens.css               CSS custom properties, ready to paste
│   ├── tokens.json              Same tokens as JSON
│   └── tailwind.config.snippet.js   Tailwind theme extension
├── assets/
│   ├── logo-wordmark.svg
│   ├── logo-icon.svg
│   └── logo-lockup.svg
├── templates/
│   ├── dashboard.html           Interactive dashboard starter
│   └── slack-brief.md           Slack message format
└── examples/
    └── do-and-dont.md           Common mistakes and how to fix them
```

## Versioning

This is v1.0. Bumped each time the underlying brand guidelines change or we add a new template.

| Version | Date       | Notes                          |
|---------|------------|--------------------------------|
| 1.0     | 2026-05-22 | Initial release from BG v5.    |

## Source of truth

The PDF `Americanflat_Brand_Guidelines_v5_20250227.pdf` is the authoritative document for brand decisions. This repo is the working implementation of that document. If the two ever disagree, the PDF wins and this repo gets updated.

## Owner

Kent Nunez, VP Operations / Supply Chain. Open an issue or DM for changes.
