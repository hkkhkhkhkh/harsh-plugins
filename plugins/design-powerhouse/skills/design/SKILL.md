---
name: design
description: "All-in-one design powerhouse. Combines UI/UX Pro Max (67 styles, 96 palettes, 57 font pairings), Framer Motion (animations), and 21st.dev Magic (100+ React components) to design and build anything — websites, landing pages, social media posts, dashboards, graphics, carousels, banners, and more. Trigger: /design"
---

# Design — All-in-One Creative Skill

Your unified design tool. Combines three powerhouses into one workflow:

| Tool | What It Does |
|------|-------------|
| **UI/UX Pro Max** | 67 styles, 96 color palettes, 57 font pairings, 99 UX guidelines, 25 chart types across 13 tech stacks |
| **Framer Motion** | Page transitions, hover effects, scroll reveals, entrance animations, micro-interactions |
| **21st.dev Magic** | 100+ production-ready React components via MCP (buttons, navbars, hero sections, cards, footers) |

---

## When to Trigger

Activate this skill when the user wants to:
- Build a website, landing page, or web app
- Design social media posts, carousels, or banners
- Create a dashboard, admin panel, or SaaS UI
- Design any visual content (graphics, posters, thumbnails)
- Build email templates or newsletter layouts
- Create presentation slides as HTML
- Design anything visual — if it has pixels, this skill handles it

---

## Workflow

### Phase 1: Understand the Brief

Ask only what's missing. Extract from the user's request:
- **What**: website, post, carousel, banner, dashboard, etc.
- **For whom**: target audience, industry, brand
- **Vibe**: dark, minimal, bold, playful, elegant, corporate, etc.
- **Platform**: web, Instagram, LinkedIn, Twitter/X, etc.
- **Tech stack**: React/Next.js (default for web), HTML/Tailwind, or static image

If the user gives enough context, skip questions and start building.

### Phase 2: Generate Design System

**Always run this first** to get a cohesive design foundation:

```bash
python3 skills/ui-ux-pro-max/scripts/search.py "<product_type> <industry> <keywords>" --design-system -p "<Project Name>"
```

This returns: recommended pattern, style, colors, typography, effects, and anti-patterns to avoid.

**For deeper exploration** (optional):
```bash
# More style options
python3 skills/ui-ux-pro-max/scripts/search.py "<keywords>" --domain style

# Font pairings
python3 skills/ui-ux-pro-max/scripts/search.py "<keywords>" --domain typography

# Color palettes
python3 skills/ui-ux-pro-max/scripts/search.py "<keywords>" --domain color

# Landing page structure
python3 skills/ui-ux-pro-max/scripts/search.py "<keywords>" --domain landing

# UX best practices
python3 skills/ui-ux-pro-max/scripts/search.py "<keywords>" --domain ux

# Chart/data viz recommendations
python3 skills/ui-ux-pro-max/scripts/search.py "<keywords>" --domain chart
```

**For stack-specific guidelines:**
```bash
python3 skills/ui-ux-pro-max/scripts/search.py "<keywords>" --stack html-tailwind
```

Available stacks: `html-tailwind`, `react`, `nextjs`, `vue`, `svelte`, `swiftui`, `react-native`, `flutter`, `shadcn`, `jetpack-compose`

### Phase 3: Pull Components (for web projects)

Use the **21st.dev Magic MCP** to search for production-ready components:
- Search for components that match the design (hero sections, navbars, cards, CTAs, footers, etc.)
- Pull them directly into the project instead of building from scratch
- Customize colors, typography, and spacing to match the design system

### Phase 4: Add Animations (for web projects)

Apply **Framer Motion** animations to make the design feel alive:

```tsx
import { motion } from "framer-motion";

// Fade in on scroll
<motion.div
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.5 }}
  viewport={{ once: true }}
>

// Staggered children
const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

// Hover effects
<motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>

// Page transitions
<motion.div
  initial={{ opacity: 0, x: -20 }}
  animate={{ opacity: 1, x: 0 }}
  exit={{ opacity: 0, x: 20 }}
>

// Smooth number counters
<motion.span>{Math.round(count)}</motion.span>
```

**Animation rules:**
- Duration: 150-300ms for micro-interactions, 300-600ms for page transitions
- Use `transform` and `opacity` only (GPU-accelerated)
- Always respect `prefers-reduced-motion`
- Stagger children by 0.05-0.15s for lists
- Use `viewport={{ once: true }}` for scroll animations (don't re-trigger)

### Phase 5: Build & Deliver

**For websites/web apps:**
1. Set up the project (Next.js + Tailwind + Framer Motion)
2. Build file by file — layout, pages, components
3. Make it fully responsive (375px, 768px, 1024px, 1440px)
4. Run the pre-delivery checklist (see below)

**For social media posts/carousels:**
1. Create as HTML files with inline styles
2. Use exact platform dimensions:
   - Instagram post: 1080x1080px
   - Instagram story/reel: 1080x1920px
   - LinkedIn post: 1200x627px
   - Twitter/X post: 1600x900px
   - Carousel slides: 1080x1350px (Instagram), 1080x1080px (LinkedIn)
3. Export-ready — user can screenshot or use a headless browser to convert to image

**For dashboards/admin panels:**
1. Use shadcn/ui components as base
2. Apply design system colors and typography
3. Add data visualization with recommended chart types
4. Ensure information hierarchy is clear

---

## Pre-Delivery Checklist

Before delivering ANY design work:

### Visual Quality
- [ ] No emojis used as icons — use SVG icons (Heroicons, Lucide, Simple Icons)
- [ ] Consistent icon set throughout
- [ ] Brand logos verified (Simple Icons)
- [ ] Hover states don't cause layout shift
- [ ] Color contrast meets 4.5:1 minimum (WCAG AA)

### Interaction
- [ ] All clickable elements have `cursor-pointer`
- [ ] Hover states provide clear visual feedback
- [ ] Transitions are smooth (150-300ms)
- [ ] Focus states visible for keyboard navigation

### Responsiveness
- [ ] Works at 375px (mobile)
- [ ] Works at 768px (tablet)
- [ ] Works at 1024px (laptop)
- [ ] Works at 1440px (desktop)
- [ ] No horizontal scroll on any viewport

### Animations
- [ ] Framer Motion used for all animations
- [ ] `prefers-reduced-motion` respected
- [ ] Scroll animations use `viewport={{ once: true }}`
- [ ] No janky or stuttering animations

### Typography & Color
- [ ] Font pairing is intentional (from design system)
- [ ] Body text is minimum 16px on mobile
- [ ] Line height 1.5-1.75 for body text
- [ ] Line length 65-75 characters max
- [ ] Light and dark mode both work (if applicable)

---

## Rules

1. **Always generate a design system first** — never skip Phase 2
2. **Use 21st.dev components when available** — don't reinvent the wheel
3. **Every animation uses Framer Motion** — no CSS keyframes for interactive elements
4. **Mobile-first** — design for 375px first, then scale up
5. **No generic AI look** — use the design system to create something that looks professionally designed
6. **Ship complete work** — don't deliver half-built designs. Every deliverable should be polished and ready to use
7. **Ask before assuming** — if the brief is unclear, ask one focused question rather than guessing wrong
