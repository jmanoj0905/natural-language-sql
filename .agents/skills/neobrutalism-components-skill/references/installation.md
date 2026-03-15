# Installation & Setup

Neobrutalism components are built on top of Shadcn UI and **Tailwind CSS v4**.

## 1. Initialize Shadcn UI

First, initialize Shadcn UI in your Next.js or React project:

```bash
npx shadcn@latest init
```

*Note: Neobrutalism components only support CSS variables components, not utility class components. The base color you choose during initialization doesn't matter, as the Neobrutalism CSS will override it.*

## 2. Add Global Styling

Replace the existing styling in your `globals.css` (or `app/globals.css`) with the Neobrutalism base styles.

Here is the default Neobrutalism CSS configuration for **Tailwind v4**:

```css
@import "tailwindcss";

@plugin "@tailwindcss/typography";

@custom-variant dark (&:is(.dark *));

:root {
  --border-radius: 5px;
  --box-shadow-x: 4px;
  --box-shadow-y: 4px;
  --reverse-box-shadow-x: -4px;
  --reverse-box-shadow-y: -4px;

  --heading-font-weight: 700;
  --base-font-weight: 500;

  /* Base Colors */
  --background: oklch(93.46% 0.0304 254.32);
  --secondary-background: oklch(100% 0 0);
  --foreground: oklch(0% 0 0);
  --main-foreground: oklch(0% 0 0);

  /* Primary Brand Color */
  --main: oklch(67.47% 0.1725 259.61);
  
  /* Borders and Overlays */
  --border: oklch(0% 0 0);
  --ring: oklch(0% 0 0);
  --overlay: oklch(0% 0 0 / 0.8);

  /* Neobrutalism Shadow */
  --shadow: var(--box-shadow-x) var(--box-shadow-y) 0px 0px var(--border);

  /* Chart Colors */
  --chart-1: oklch(67.47% 0.1726 259.49);
  --chart-2: oklch(67.28% 0.2147 24.22);
  --chart-3: oklch(86.03% 0.176 92.36);
  --chart-4: oklch(79.76% 0.2044 153.08);
  --chart-5: oklch(66.34% 0.1806 277.2);
  --chart-active-dot: #000;
}

.dark {
  --background: oklch(29.12% 0.0633 270.86);
  --secondary-background: oklch(23.93% 0 0);
  --foreground: oklch(92.49% 0 0);
  --main-foreground: oklch(0% 0 0);

  --border: oklch(0% 0 0);
  --ring: oklch(100% 0 0);

  --shadow: var(--box-shadow-x) var(--box-shadow-y) 0px 0px var(--border);

  --chart-active-dot: #fff;
}

@theme inline {
  --color-background: var(--background);
  --color-secondary-background: var(--secondary-background);
  --color-foreground: var(--foreground);
  --color-main-foreground: var(--main-foreground);
  --color-main: var(--main);
  --color-border: var(--border);
  --color-ring: var(--ring);
  --color-overlay: var(--overlay);
  
  --radius-base: var(--border-radius);
  
  --shadow-shadow: var(--shadow);
  
  --spacing-boxShadowX: var(--box-shadow-x);
  --spacing-boxShadowY: var(--box-shadow-y);
  --spacing-reverseBoxShadowX: var(--reverse-box-shadow-x);
  --spacing-reverseBoxShadowY: var(--reverse-box-shadow-y);
  
  --font-weight-heading: var(--heading-font-weight);
  --font-weight-base: var(--base-font-weight);
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground font-base;
    font-feature-settings: "rlig" 1, "calt" 1;
  }
  h1, h2, h3, h4, h5, h6 {
    @apply font-heading;
  }
}
```

## 3. Installing Components

To install a component, use the Shadcn CLI with the `neobrutalism.dev` registry URL:

```bash
npx shadcn@latest add https://neobrutalism.dev/r/button.json
```

This will automatically download the component with the correct Neobrutalism styling (e.g., `border-2 border-border shadow-shadow hover:translate-x-boxShadowX hover:translate-y-boxShadowY hover:shadow-none`) and place it in your `components/ui` directory.

### Available Components

You can install any of the following components by replacing `[component]` in the URL `https://neobrutalism.dev/r/[component].json`:

- `accordion`
- `alert`
- `alert-dialog`
- `avatar`
- `badge`
- `breadcrumb`
- `button`
- `calendar`
- `card`
- `carousel`
- `chart`
- `checkbox`
- `collapsible`
- `combobox`
- `command`
- `context-menu`
- `data-table`
- `dialog`
- `drawer`
- `dropdown-menu`
- `form`
- `hover-card`
- `image-card`
- `input-otp`
- `input`
- `label`
- `marquee`
- `menubar`
- `navigation-menu`
- `pagination`
- `popover`
- `progress`
- `radio-group`
- `resizable`
- `scroll-area`
- `select`
- `sheet`
- `sidebar`
- `skeleton`
- `slider`
- `sonner`
- `switch`
- `table`
- `tabs`
- `textarea`
- `tooltip`
