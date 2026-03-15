# Neobrutalism Components Reference Guide

This document serves as the authoritative reference for AI agents and developers utilizing the official `neobrutalism.dev` component library.

## 1. Installation Protocol

These components are fully compatible with the shadcn/ui ecosystem. They must be installed individually via the shadcn CLI using the official neobrutalism registry.

**CRITICAL:** To install a component, you MUST use the following bash command:
```bash
npx shadcn@latest add https://neobrutalism.dev/r/<component-name>.json
```
*Do not attempt to install these components using standard shadcn registry commands (e.g., `npx shadcn add button`). You must use the full URL provided above.*

## 2. Available Components List

The following components are currently available in the neobrutalism.dev registry. Replace `<component-name>` in the installation protocol with any of the following:

- accordion
- alert
- alert-dialog
- avatar
- badge
- breadcrumb
- button
- calendar
- card
- carousel
- chart
- checkbox
- collapsible
- combobox
- command
- context-menu
- data-table
- dialog
- drawer
- dropdown-menu
- form
- hover-card
- image-card
- input-otp
- input
- label
- marquee
- menubar
- navigation-menu
- pagination
- popover
- progress
- radio-group
- resizable
- scroll-area
- select
- sheet
- sidebar
- skeleton
- slider
- sonner
- switch
- table
- tabs
- textarea
- tooltip

## 3. Neobrutalist Usage Guidelines

To maintain the distinct, high-contrast, and physical aesthetic of Neobrutalism, adhere strictly to the following composition rules:

- **Consistent CTAs:** Use the `Button` component for ALL calls-to-action. This ensures the signature physical "press" effect (translating down and right with shadow reduction) remains consistent across the entire application.
- **Card Composition:** Do not nest `Card` components inside other `Card` components without thick, high-contrast borders. The visual hierarchy must remain stark and clearly separated.
- **Shadows and Borders:** Neobrutalism relies on hard shadows and thick borders (typically 2px to 4px). Do not override these default component styles with soft drop-shadows or thin/subtle borders.
- **Color Palette:** Utilize bold, highly saturated background colors contrasted with stark black or white text. The components are designed to pop; do not dilute them with low-contrast pastel themes.
- **Spacing:** Maintain generous padding and margins. The brutalist aesthetic requires elements to feel substantial and unapologetic in their use of space.

## 5. Stars Implementation (Geometric Shapes)

The registry includes 40 unique geometric star shapes that are heavily used in Neobrutalism layouts as floating accents or badges.

1. **Installation:** Run `npx shadcn@latest add https://neobrutalism.dev/r/s<number>.json` (where `<number>` is between 1 and 40).
   - Example: `npx shadcn@latest add https://neobrutalism.dev/r/s1.json`
2. **Usage:** Import the component (e.g., `import Star1 from "@/components/stars/s1"`) and use it in your layout.
3. **Props:**
   - `color` (string): Fill color (defaults to `currentColor`).
   - `size` (number): Width and height in pixels.
   - `stroke` (string): Path stroke color (e.g., `"black"`).
   - `strokeWidth` (number): Stroke thickness.
   - Example: `<Star1 color="#fbbf24" stroke="black" strokeWidth={2} size={150} />`