# CISD Hub — Interface Design System

**Direction:** Sophistication & Trust (enterprise/civic). Restrained palette, strong
typographic hierarchy, calm authority. Borders + subtle elevation, never loud.

> Generated for the CISD Hub launchpad. Reused across sessions. When adding UI,
> follow these tokens rather than inventing new values.

## Foundations

### Spacing — 4px base scale
`--sp-1: 4px · --sp-2: 8px · --sp-3: 12px · --sp-4: 16px · --sp-5: 24px · --sp-6: 32px · --sp-7: 48px · --sp-8: 64px`

### Radius
`--r-sm: 6px (chips/inputs) · --r-md: 10px (cards) · --r-lg: 16px (hero)`

### Color — foundation
- Ink (text):            `--ink: #14181f` / secondary `--ink-2: #4a5563` / muted `--ink-3: #8a94a3`
- Surface:               page `--bg: #f7f8fa` / card `--surface: #ffffff` / sunken `--surface-2: #eef1f5`
- Border:                `--line: #e2e6ec` / strong `--line-2: #cdd4de`
- Brand (trust navy):    `--brand: #1f3a5f` / hover `--brand-700: #16293f` / tint `--brand-50: #eef2f7`

### Color — per-site accents (kept muted, used for the card's left rule + icon)
- Meetings (slate-blue): `--c-meetings: #3b5b8c`
- Finance (teal-green):  `--c-finance: #2f7d6b`
- Books (warm clay):     `--c-books: #a4562f`
- Policy (indigo):       `--c-policy: #5a4b8a`

### Semantic
- Flag/alert:  `--warn: #b4690e` (amber, used for finance watchdog flags + pre-launch banner)
- Positive:    `--good: #2f7d6b`
- Danger:      `--bad: #b3261e`

### Typography
- Family: system stack — `-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
- Numerals: `font-variant-numeric: tabular-nums` on all metric values.
- Scale: display 30/36 700 · h2 20/28 600 · body 15/22 400 · label 12/16 600 uppercase
  letter-spacing .04em · fine-print 12/16 400 muted.

## Components

### Card (one per site)
- `--surface` bg, `1px solid --line`, `--r-md`, `padding --sp-5`.
- 3px left rule in the site accent color. Header row: icon + site name (h2) + "Open ↗" link.
- Default depth: border only. Hover: `box-shadow: 0 1px 3px rgba(20,24,31,.06), 0 8px 24px rgba(20,24,31,.06)` + `--line-2` border. 150ms ease.

### Metric (the 4-up grid inside finance/books/policy cards)
- 2×2 grid, gap `--sp-3`. Each cell: value (display size, tabular-nums, ink), label (label style, ink-3), optional sub (fine-print).

### Highlight box (meetings card — expand on tap)
- Sunken `--surface-2`, `--r-sm`, `1px solid --line`. Collapsed: shows title + first highlight, max-height clamp with fade. Tap/click toggles `aria-expanded`; expands to full bullet list. Chevron rotates 180°. Honors `prefers-reduced-motion`.

### Footer
- fine-print, `--ink-3`, centered. Holds the "Data as of <last run> · sources" line. Deliberately low-prominence.
```
