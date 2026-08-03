---
name: skill-design-system
description: "Apply the Americanflat brand aesthetic to any tool, agent, dashboard, report, presentation, email template, or visual artifact built for AF. Use this skill whenever you create an HTML file, React component, dashboard, infographic, slide deck, internal tool UI, agent interface, or any other visual deliverable that will be seen by AF staff, partners, or customers. Triggers on: 'build a dashboard', 'create a tool', 'AF visual', 'on-brand', 'AF styling', 'AF look and feel', 'design system', any HTML/CSS work for an Americanflat project, or any time output will carry the AF name. Pulls colors, typography, logo, layout rules, and ready-to-paste tokens from the supporting files in this directory. Always read the tokens file before writing any CSS or component styling."
version: 1.0.0
owner: Kent Nunez (VP Ops / Supply Chain)
last_updated: 2026-05-22
applies_to: Americanflat Corporation, Loom Haven Corporation, Plus Haven Inc.
---

# Americanflat Design System

## Why this skill exists

Every tool, agent, and visual we ship at Americanflat should look like it came from the same company. A dashboard built by the ops team, a Slack brief from an automation agent, and a slide deck for a partner meeting should all share the same colors, typography, logo treatment, and overall feel. This skill is how we make that happen without anyone having to read the 90-page brand PDF.

## What "on-brand AF" feels like

If you only remember three things:

1. **White space wins.** 70% white, 20% near-black, 5% accents, 5% secondary. Resist the urge to fill space. Empty room is the look.
2. **Black is not black.** Use `#0F0F0F`, not `#000000`. It's a very dark grey. This single choice is most of the AF feel.
3. **One typeface, two weights.** Glacial Indifference Regular and Bold. That's it. No colored type. No all-caps headlines. No italics for emphasis.

The tone of voice is "the Everlane of home décor": casual but not childish, clean but not cold, simple but not dumbed down.

## How to use this skill

### Step 1: Read the tokens

Before you write any CSS, component, or HTML, open `tokens/tokens.css` and copy the `:root` block into your file. That gives you every color, font, spacing value, and radius as CSS custom properties. Use the variables, not the raw hex values, so anything we ship can be themed centrally later.

For React or Tailwind projects, use `tokens/tailwind.config.snippet.js` instead. It extends your Tailwind config with the AF palette and type scale.

For non-web outputs (Python charts, Slack message formatting, etc.), use `tokens/tokens.json`.

### Step 2: Use a template

`templates/` has ready-to-paste starters:

- `dashboard.html` for any interactive dashboard or tool
- `slack-brief.md` for AF-formatted Slack messages

Each template already has the tokens wired in, the logo placed, and the layout grid set up. Start from one of these, not from a blank file.

### Step 3: Drop in the logo

Use the SVGs in `assets/`:

- `logo-wordmark.svg` for headers and primary placement
- `logo-icon.svg` for favicons, avatars, and corner marks
- Never recolor, rotate, stretch, or add effects to either

Logo always goes top-center on single-page outputs, top-left for multi-page documents. Minimum size is 30pt for the wordmark.

### Step 4: Run the checklist

Before you call something done, glance at `REFERENCE.md` for the do-and-don't checklist. The common mistakes are: colored type, full black, too many accent colors, headlines in all-caps, cramped layouts.

## What this skill does NOT cover

- Logo design changes or new logo variants (talk to the creative team)
- Product photography and lifestyle imagery selection (covered in the full brand PDF, sections 45-49)
- Packaging and physical print specs (sections 53-58)
- Anything outside Americanflat brand work (personal projects, Dancing Littles, Tariff Tracker, Lean Without Walls)

## Source of truth

This skill is derived from `Americanflat_Brand_Guidelines_v5_20250227.pdf` (Feb 2025, v5). If a conflict ever comes up between this skill and the PDF, the PDF wins for design decisions, but flag it so this skill can be updated.

## Quick reference card

```
PRIMARY COLORS
  AF Black     #0F0F0F   (not true black, use everywhere "black" appears)
  White        #FFFFFF

GREYS
  AF Grey 4    #1A1A1A   (slightly lighter than AF Black, for dense backgrounds)
  AF Grey 3    #666666   (secondary text)
  AF Grey 2    #B3B3B3   (disabled, borders)
  AF Grey 1    #E6E6E6   (dividers, light fills)

ACCENTS (use sparingly, max 2 per asset besides black/white)
  AF Red       #CE0E2D   (Amazon contexts, alerts)
  AF Blue      #003595   (Amazon contexts, links in formal docs)

TYPOGRAPHY
  Family       Glacial Indifference (web fallback: DM Sans, Manrope, Inter)
  Weights      Regular (400), Bold (700)
  Scale        H1 48pt bold / H2 30pt bold / Subhead 24pt regular
               Body 21pt regular / Descriptor 24pt regular / Footer 12pt regular

LAYOUT
  Color balance     70% white / 20% black / 5% accent / 5% secondary
  Default BG        White (always, except covers/title pages/headers)
  Logo placement    Top center (single page) or top left (multi page)
  Logo min size     30pt
```
