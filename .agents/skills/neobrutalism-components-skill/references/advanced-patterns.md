# Advanced Neobrutalism Patterns

When building neobrutalist interfaces, you can elevate the design by incorporating these advanced Tailwind CSS patterns, inspired by top-tier neobrutalism sites.

## 1. The "Text Stroke" Effect (Text Shadow)

Instead of relying on `-webkit-text-stroke` (which can render poorly on some browsers), use a multi-directional `text-shadow` to create a solid, sharp outline around text. This is perfect for large headings.

```html
<h1 class="text-white font-black [text-shadow:_-1.75px_-1.75px_0_#000,_1.75px_-1.75px_0_#000,_-1.75px_1.75px_0_#000,_1.75px_1.75px_0_#000]">
  Outlined Heading
</h1>
```
*Tip: Adjust the `1.75px` values to make the stroke thicker or thinner.*

## 2. Retro Grid Background

A subtle grid background adds texture and reinforces the retro/architectural feel of neobrutalism. You can achieve this entirely with Tailwind arbitrary values using linear gradients.

```html
<section class="bg-white bg-[linear-gradient(to_right,#80808033_1px,transparent_1px),linear-gradient(to_bottom,#80808033_1px,transparent_1px)] bg-[size:70px_70px]">
  <!-- Content goes here -->
</section>
```
*Tip: Change `#80808033` to adjust the grid line color and opacity, and `70px` to change the grid cell size.*

## 3. Thick Section Dividers

Instead of subtle 1px borders, separate major page sections with thick, solid borders to create distinct "blocks" of content.

```html
<section class="border-b-4 border-border py-20">
  <!-- Section Content -->
</section>
```

## 4. Interactive Accordions

For accordions or collapsible elements, use thick borders and solid shadows. When an item is opened, you can remove the bottom border radius to make it seamlessly connect with its content panel.

```html
<!-- Accordion Item Container -->
<div class="border-2 border-border shadow-shadow rounded-base mb-2 transition-all [&[data-state=open]]:rounded-b-none [&[data-state=open]]:border-b-2">
  <!-- Trigger -->
  <button class="flex w-full items-center justify-between bg-main p-4 font-bold">
    Click to expand
  </button>
  <!-- Content -->
  <div class="bg-white p-4 border-t-2 border-border">
    Hidden content here.
  </div>
</div>
```

## 5. "Floating" Cards with Offset Shadows

Standard neobrutalism cards use a solid shadow. To make them pop, ensure the background color contrasts well with the shadow, and use flexbox to align them in a grid.

```html
<div class="border-2 border-border shadow-shadow rounded-base bg-white p-6 text-black flex flex-col gap-4">
  <div class="flex items-center space-x-2">
    <div class="w-10 h-10 bg-main border-2 border-border rounded-full"></div>
    <h4 class="text-2xl font-heading">Card Title</h4>
  </div>
  <p class="font-base">Card description goes here. Keep it punchy.</p>
</div>
```

## 6. The "Pressable" Button

The quintessential neobrutalist button looks like a physical block that gets pressed down into the page.

```html
<button class="bg-main text-text border-2 border-border shadow-shadow hover:translate-x-boxShadowX hover:translate-y-boxShadowY hover:shadow-none transition-all px-8 py-4 text-xl font-black rounded-base">
  Try Now
</button>
```
*Note: This relies on the CSS variables `--box-shadow-x` and `--box-shadow-y` defined in your `globals.css`.*

## 7. "Riveted" or "Bolted" Dividers

A great structural pattern where small circular elements are absolutely positioned on the edges of a border to look like physical screws or pins holding the UI together.

```html
<div class="w-full border-t-2 border-border relative mt-8">
  <!-- Left Rivet -->
  <div class="size-6 rounded-full bg-background border-2 border-border absolute left-0 -top-3"></div>
  <!-- Right Rivet -->
  <div class="size-6 rounded-full bg-background border-2 border-border absolute right-0 -top-3"></div>
</div>
```

## 8. Overlapping Floating Badges

Break the grid by absolutely positioning a brightly colored, thick-bordered badge so it overlaps the top edge of its parent card. This adds a playful, unpolished feel.

```html
<div class="rounded-base shadow-shadow border-2 border-border bg-background relative p-8 mt-8">
  <!-- Floating Badge -->
  <div class="absolute -top-8 left-8 size-16 border-2 border-border rounded-base bg-main flex items-center justify-center text-text font-black">
    #1
  </div>
  <h3 class="text-xl font-heading mt-4">Card Content</h3>
  <p>This card has a floating badge breaking its top border.</p>
</div>
```

## 9. High-Contrast Focus States

Neobrutalism favors extremely visible accessibility outlines rather than subtle glows. Use thick, solid rings with an offset.

```html
<input 
  type="text" 
  class="border-2 border-border rounded-base p-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border focus-visible:ring-offset-2 ring-offset-background"
  placeholder="Focus me..."
/>
```

## 10. Thick Structural Grids (Comic-Book Style)

Use thick borders on specific sides of flex or grid children to create a comic-book style layout where elements are separated by harsh, solid lines.

```html
<div class="flex border-2 border-border rounded-base overflow-hidden">
  <div class="flex-1 p-6 bg-white hover:bg-main transition-colors">
    Left Panel
  </div>
  <div class="flex-1 p-6 bg-white border-l-2 border-border hover:bg-main transition-colors">
    Right Panel
  </div>
</div>
```

## 11. The "Rotated Container" (Chaotic Layout)

Break the rigid grid of modern web design by applying slight rotations to main content containers. This is a staple of the brutalist aesthetic.

```html
<div class="bg-white p-8 rotate-2 border-4 border-border shadow-shadow">
  <h2 class="text-5xl font-black">Rotated Content</h2>
</div>
```

## 12. Floating Geometric Accents

Use absolute positioning to place brightly colored, heavily bordered geometric shapes around the main content to create a chaotic, playful vibe.

```html
<div class="relative p-12 border-4 border-border bg-white mt-12">
  <!-- The Spinning Circle -->
  <div class="absolute -top-6 -right-6 w-14 h-14 bg-pink-500 border-4 border-border shadow-shadow rounded-full animate-spin-slow"></div>
  
  <!-- The Pulsing Square -->
  <div class="absolute -bottom-6 -left-6 w-10 h-10 bg-blue-400 border-4 border-border shadow-shadow rounded-md animate-pulse"></div>
  
  <!-- The Rotated Diamond -->
  <div class="absolute -top-14 -left-14 w-16 h-16 bg-yellow-500 border-4 border-border shadow-shadow transform rotate-45"></div>
  
  <p class="text-2xl font-bold">Content with floating accents.</p>
</div>
```

## 13. Highlighted "Stamp" Typography

Make headings pop out from the background by wrapping the text in a tight, thick-bordered, rotated inline block so it looks like a physical stamp or sticker.

```html
<h1 class="text-4xl md:text-6xl font-bold bg-white inline-block p-2 transform -rotate-2 border-4 border-border">
  Stamped Heading
</h1>
```

## 14. Interactive Hover-Tilt Cards

Instead of static rotation, some cards sit perfectly straight but tilt slightly when interacted with, adding a playful, chaotic feel.

```html
<div class="bg-main p-6 border-4 border-border transform hover:-rotate-1 transition-transform cursor-pointer">
  <h3 class="text-2xl font-bold">Hover to tilt</h3>
</div>
```
