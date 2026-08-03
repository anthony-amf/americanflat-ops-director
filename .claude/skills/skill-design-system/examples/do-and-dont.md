# Common Mistakes and Fixes

Concrete examples of off-brand vs on-brand outputs, copied from the most common things agents get wrong.

## Color

### ❌ Off-brand

```css
body { background: #000000; color: #FFFFFF; }
.alert { color: red; }
.success { color: green; }
```

Three problems: pure black instead of AF Black, generic web color names (`red`, `green`), and using green which is not in the AF palette at all.

### ✅ On-brand

```css
body { background: var(--af-white); color: var(--af-black); }
.alert { color: var(--af-red); }       /* AF Red #CE0E2D */
.success { color: var(--af-black); }    /* "Success" is just normal text */
```

## Type

### ❌ Off-brand

```html
<h1 style="color: #003595; text-transform: uppercase; font-style: italic;">
  WALLS THAT WELCOME YOU HOME
</h1>
```

Three problems at once: colored headline, all-caps headline, italic for emphasis.

### ✅ On-brand

```html
<h1 class="af-h1">Walls that welcome you home</h1>
```

## Logo

### ❌ Off-brand

```html
<img src="logo.png" style="filter: hue-rotate(120deg); transform: rotate(-5deg);">
```

Don't recolor, don't rotate, don't apply effects.

### ✅ On-brand

```html
<img src="assets/logo-wordmark.svg" height="40" alt="Americanflat">
```

Inline SVG is even better because it inherits `currentColor` and can be sized cleanly:

```html
<svg class="af-logo" viewBox="0 0 480 80" style="color: var(--af-black);">
  <use href="assets/logo-wordmark.svg#wordmark"/>
</svg>
```

## Card design

### ❌ Off-brand

```css
.card {
  background: linear-gradient(135deg, #003595, #CE0E2D);
  color: white;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  border-radius: 24px;
}
```

Gradient using two accents at once, heavy shadow, large rounded corners. None of this is AF.

### ✅ On-brand

```css
.card {
  background: var(--af-white);
  color: var(--af-black);
  border: 1px solid var(--af-grey-1);
  border-radius: 8px;
  padding: 32px;
}
```

Flat, bordered, restrained corner radius. The brand is calm.

## Section header

### ❌ Off-brand

```html
<div style="background: #CE0E2D; padding: 40px; color: white;">
  <h2 style="font-size: 18px; font-weight: 600;">📊 Q3 SALES PERFORMANCE REPORT 📊</h2>
</div>
```

Red background, emoji decoration, all-caps subhead, undersized type.

### ✅ On-brand

```html
<section class="af-section">
  <div class="af-eyebrow">Q3 · Sales</div>
  <h2>How we performed</h2>
</section>
```

Eyebrow handles the categorization, headline handles the meaning. White background, generous spacing, no decoration.

## Slack message

### ❌ Off-brand

```
🎉🎉🎉 GREAT NEWS TEAM!!! 🎉🎉🎉

We have CRUSHED our Q3 numbers and want to give a HUGE shoutout to everyone who made it happen! 

📈 Sales: AMAZING
📦 Orders: THROUGH THE ROOF
💰 Revenue: STELLAR

Keep up the AMAZING work, team!!! Let's keep CRUSHING IT!!! 🚀🚀🚀
```

Caps lock, emoji storm, corporate cheerleading. None of this matches AF voice.

### ✅ On-brand

```
*Q3 wrap, in three numbers*
We hit plan on revenue and beat it on orders. Sales mix shifted toward DTC.

---
*Numbers*
• Revenue: $X.XM (101% of plan)
• Orders: XXk (108% of plan)
• DTC share: 34% (up from 28%)

*What changed*
• Wayfair POs slowed in September, made up by DTC
• Three new Amazon ASINs launched on time

---
_Auto-generated Mon 9:00 AM ET · Reply with questions._
```

Sentence case, real numbers, structure, one italic sign-off.
