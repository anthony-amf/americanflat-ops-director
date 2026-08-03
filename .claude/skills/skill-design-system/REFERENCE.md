# AF Design System Reference

Quick lookup for the do's and don'ts. Open this when you're about to ship something and want a sanity check.

## The 60-second checklist

Before you call something done, run through this:

- [ ] Background is white (or AF Black for dark mode covers only)
- [ ] All "black" is `#0F0F0F`, never `#000000`
- [ ] Only 2 non-grey colors used in the asset, max
- [ ] No colored typography (text is AF Black or AF Grey 3 for muted)
- [ ] No all-caps headlines (eyebrows and labels can be uppercase, headlines cannot)
- [ ] Logo is at least 30pt, has clear space, is not stretched or recolored
- [ ] Body text is at least 21pt equivalent (about 16-18px on web with reasonable line height)
- [ ] Headlines are Bold, body is Regular, nothing is Italic
- [ ] No drop shadows on the logo, no gradients anywhere

If any of those fail, fix before shipping.

## Color rules

### Use AF Black, not pure black

`#0F0F0F` is the brand "black". It is intentionally a very dark grey. Pure `#000000` looks harsh and off-brand. This single switch is the most common AF tell.

### The 70/20/5/5 balance

- 70% white background
- 20% AF Black (text, dark sections, dark cards)
- 5% accent color (only AF Red or AF Blue, for emphasis)
- 5% secondary (lifestyle image color, photo content)

If your design is more than 30% non-white, it is probably off-brand.

### When to use AF Red vs AF Blue

- **AF Red** `#CE0E2D`: Amazon-specific contexts, urgent alerts, error states. Never as a fill background covering more than a small badge or icon.
- **AF Blue** `#003595`: Amazon-specific contexts, links in formal documents, info pills. Same rule on coverage.
- **For non-Amazon contexts**, prefer just black and white. Pull a single accent from product or lifestyle imagery if you need one. Maximum two non-grey colors per asset.

### Greys are for hierarchy, not decoration

- Grey 3 (`#666666`) = secondary text, captions, summary lines under headlines
- Grey 2 (`#B3B3B3`) = borders on heavier dividers, disabled states
- Grey 1 (`#E6E6E6`) = light dividers, subtle card borders, very light fills

## Typography rules

### Hierarchy is built with weight and size, not color

| Level         | Weight   | Size  | Use case                         |
|---------------|----------|-------|----------------------------------|
| H1            | Bold     | 48pt  | Hero headlines, page titles      |
| H2            | Bold     | 30pt  | Section heads                    |
| Subhead       | Regular  | 24pt  | Subsection labels, lead summary  |
| Descriptor    | Regular  | 24pt  | Eyebrow / category labels        |
| Body          | Regular  | 21pt  | Body copy, paragraphs            |
| Footer        | Regular  | 12pt  | Footers, legal, source notes     |

### What never to do

- Never color the type. Black or grey only. Pulling a brand accent into headline text is the fastest way to look off-brand.
- Never use all-caps headlines. UPPERCASE is for eyebrows, labels, and small UI elements only (footer pills, table headers).
- Never right-align body text. Left-align is the default. Center-align only for hero headlines and short callouts.
- Never use Italic for emphasis. Bold weight is the only emphasis treatment.
- Never use more than two weights (Regular and Bold). No Light, no Medium, no Black weight.
- Never reduce line height below 1.15. Tight cramped text is off-brand.
- Never reduce body text below the equivalent of 16px on web.

### Multilingual

For Japanese content, use Hiragino Kaku Gothic Pron (Regular and Bold). Any other language with a custom font must get approval from the design team first.

## Logo rules

### What never to do

- Do not recolor the logo (other than full white on dark backgrounds)
- Do not rotate, skew, or stretch
- Do not add a keyline or border
- Do not apply shadow or any effect
- Do not place icon directly next to wordmark (use the official lockup file)
- Do not place on a background that doesn't have enough contrast

### Placement

- **Single-page outputs** (dashboard, infographic, social post): logo top center
- **Multi-page documents** (reports, decks): wordmark top left on cover and first page, icon top left or bottom corner on subsequent pages
- **Tight spaces** (envelope, business card back): icon only, top left

### Clear space and minimum size

- Clear space on all sides equals the height of one character of the wordmark
- Wordmark minimum: 30pt
- Icon minimum: 16px web, 0.25 inch print

## Layout rules

### Default to white

Background is white unless the page is specifically a cover, title page, or section divider that calls for a dark treatment. Even then, AF Black, not pure black.

### Generous spacing

The brand reads minimal. Crowded layouts read off-brand. Use the 8pt spacing scale and lean toward the larger end. If something feels cramped, it probably is.

### Flat over skeumorphic

No drop shadows on cards (a 1px border is enough). No glossy buttons. No gradients except in image edges where naturally occurring. The brand is flat.

### Cards: bordered, not shadowed

Use a 1px `#E6E6E6` border on cards. Shadows are reserved for elements that genuinely float (modals, tooltips) and even then they should be subtle.

## Voice and tone

When the artifact has any prose in it (dashboard descriptions, email subject lines, button labels):

- Be the Everlane of home décor
- Casual but not child-like
- Clean but not cold
- Simple but not dumbed-down
- Optimistic but still practical
- Welcoming but not overly familiar

Concrete examples:

- ✅ "Walls that welcome you home"
- ❌ "Hey there! Let's make your house POP!"

- ✅ "We make it easy to instantly create the feeling of home."
- ❌ "Transformative wall solutions for the modern domicile."

- ✅ "Open invoices, by age"
- ❌ "AR Aging Report - All Open AR Items by Bucket"

## Photography rules

If the artifact includes images:

- Natural lighting, warm earthy tones
- Real lived-in spaces, not staged studios
- Subtle brand integration, not product-forward
- No heavy filters, no extreme color grading
- High resolution always

If you're generating placeholder imagery (charts, illustrations), keep them black on white with restrained use of a single accent color. Match the photography tone in spirit even when the medium is different.
