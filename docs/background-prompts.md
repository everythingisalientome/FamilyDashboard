# Ambient background — image-generation prompts

40 ready-to-paste prompts (4 seasons × 10 time-of-day phases) for pre-rendering
the Phase 6 ambient background as illustrated art. Jump to
[the 40 prompts](#the-40-prompts).

---

## JPEG or SVG? (and how weather stays animated)

Short answer: **generate JPEGs for the backdrop, and keep snow / rain / lightning
as the animated overlay we already have.** You lose no animation by using JPEG.

The scene is built in layers, and weather is its **own top layer**:

```
[ backdrop: sky + sun/moon + landscape ]   ← the image you generate (static)
[ weather overlay: rain, snow, clouds, fog, lightning ]   ← animated CSS/SVG, on top
```

- The **snow, rain, lightning, clouds and fog are already animated** in
  `background.css` as a separate layer that sits *on top* of the backdrop. They
  do **not** live inside the backdrop image. So whether the backdrop is a JPEG or
  hand-drawn SVG makes **no difference** to whether weather animates — it always
  animates.
- **Image generators produce raster (JPEG/PNG), not clean SVG.** "AI SVG" is
  almost always a bitmap wrapped in an `<svg>` tag or a mess of unusable paths —
  you can't cleanly re-color or animate it. Good, animatable SVG is *hand-authored*
  (which is exactly what the scene is today). So "get SVG right via an image tool"
  isn't a real option; the choice is really **hand-SVG scene vs generated-JPEG
  scene**, with the animated weather overlay unchanged either way.

So the two sensible paths are:

- **A — keep the current SVG scene** (default, already shipping): fully vector,
  fully animated, zero assets, cheapest on the Pi. Look is clean but flat.
- **B — generate 40 JPEG backdrops** (this doc): richer, painterly sky + scene per
  *season × phase*; **weather stays the animated overlay on top**. JPEG is the
  correct format; ~1080p at ~85% quality is tiny and a Pi displays a static JPEG
  effortlessly.

**My recommendation:** if the flat SVG look is fine, stay on A — it's the lowest-
risk, lowest-power option and it's done. If you want prettier art, go B with these
40 JPEGs and **do not bake weather into them** (leave that to the overlay). Either
way, don't chase SVG out of an image generator.

> Why 40, not 320: 10 phases × 8 weather × 4 seasons = 320 is impractical to make
> and would heat-throttle the Pi if they were animated loops. Weather is the
> animated overlay, so you only need one still per **season × phase** = 40.

### File naming (so we can wire it up)

`static/img/bg/<season>-<phase>.jpg` — e.g. `autumn-sunset.jpg`, `winter-night.jpg`.

`<season>` ∈ `spring summer autumn winter`
`<phase>` ∈ `twilight-dawn dawn sunrise morning noon afternoon sunset dusk twilight-dusk night`

Once the 40 exist under that path, `background.js` can swap `background-image` by
`<season>-<phase>` and keep the weather-class overlays on top — a small change I
can make on request.

---

## Negative prompt (use for all 40)

Paste this into the tool's **negative** field for every image:

> text, words, letters, numbers, watermark, signature, logo, UI, HUD, frame,
> border, people, person, faces, crowd, animals, cars, roads, power lines, busy,
> cluttered, high contrast, harsh shadows, oversaturated, neon, photorealistic
> clutter, lens flare over center

**Settings for all:** 16:9, 1920×1080, export JPEG ~85%. For a consistent set that
cross-fades cleanly, lock the framing/palette (reuse the same seed or the same
base image across phases within a season).

---

## The 40 prompts

Each prompt below is complete — copy the whole paragraph into the positive field.
Sky/light is calm and low-contrast on purpose: the dashboard panels sit over the
upper-right behind frosted glass, so keep the sky open there and avoid a bright
hotspot behind the right two-thirds.

### Spring

**1. `spring-twilight-dawn.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Pre-dawn twilight: deep indigo-navy sky, the faintest cool glow low on the left horizon, a few dim stars still out, no sun yet, quiet and dark. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**2. `spring-dawn.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Dawn: indigo sky washing to soft rose and magenta along the left horizon, brightening, the sun not yet risen, delicate cool-to-warm gradient. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**3. `spring-sunrise.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Sunrise: the sun low on the left horizon, warm golden-orange glow, long gentle light, peach-and-pink sky, soft distant mist. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**4. `spring-morning.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Morning: clear soft-blue sky, gentle warm sunlight from the lower left, fresh bright air, the sun low-to-mid on the left. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**5. `spring-noon.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Midday: bright but soft blue sky, sun high overhead near center, crisp even daylight, minimal shadows, calm and airy. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**6. `spring-afternoon.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Afternoon: warm slightly-golden blue sky, the sun descending toward the right, gently lengthening soft shadows. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**7. `spring-sunset.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Sunset: the sun low on the right horizon, rich golden-orange and red glow, warm golden-hour light over the scene, glowing sky. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**8. `spring-dusk.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Dusk: the sun just below the right horizon, deep orange fading up into violet and purple, a warm afterglow low on the right, cooling light. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**9. `spring-twilight-dusk.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Late twilight after sunset: deep blue-violet sky, the first stars appearing, a faint warm band lingering at the horizon, the cottage windows glowing warm. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**10. `spring-night.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Spring: fresh light-green foliage dotted with soft pink and white blossoms, tender new grass, a few drifting petals. Night: dark near-black navy sky full of stars with a bright moon, cool moonlight over the scene, the cottage windows glowing warm and inviting. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

### Summer

**11. `summer-twilight-dawn.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Pre-dawn twilight: deep indigo-navy sky, the faintest cool glow low on the left horizon, a few dim stars still out, no sun yet, quiet and dark. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**12. `summer-dawn.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Dawn: indigo sky washing to soft rose and magenta along the left horizon, brightening, the sun not yet risen, delicate cool-to-warm gradient. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**13. `summer-sunrise.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Sunrise: the sun low on the left horizon, warm golden-orange glow, long gentle light, peach-and-pink sky, soft distant mist. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**14. `summer-morning.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Morning: clear soft-blue sky, gentle warm sunlight from the lower left, fresh bright air, the sun low-to-mid on the left. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**15. `summer-noon.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Midday: bright but soft blue sky, sun high overhead near center, crisp even daylight, minimal shadows, calm and airy. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**16. `summer-afternoon.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Afternoon: warm slightly-golden blue sky, the sun descending toward the right, gently lengthening soft shadows. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**17. `summer-sunset.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Sunset: the sun low on the right horizon, rich golden-orange and red glow, warm golden-hour light over the scene, glowing sky. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**18. `summer-dusk.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Dusk: the sun just below the right horizon, deep orange fading up into violet and purple, a warm afterglow low on the right, cooling light. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**19. `summer-twilight-dusk.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Late twilight after sunset: deep blue-violet sky, the first stars appearing, a faint warm band lingering at the horizon, the cottage windows glowing warm. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**20. `summer-night.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Summer: lush deep-green full foliage, soft vivid green grass, warm and verdant. Night: dark near-black navy sky full of stars with a bright moon, cool moonlight over the scene, the cottage windows glowing warm and inviting. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

### Autumn

**21. `autumn-twilight-dawn.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Pre-dawn twilight: deep indigo-navy sky, the faintest cool glow low on the left horizon, a few dim stars still out, no sun yet, quiet and dark. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**22. `autumn-dawn.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Dawn: indigo sky washing to soft rose and magenta along the left horizon, brightening, the sun not yet risen, delicate cool-to-warm gradient. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**23. `autumn-sunrise.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Sunrise: the sun low on the left horizon, warm golden-orange glow, long gentle light, peach-and-pink sky, soft distant mist. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**24. `autumn-morning.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Morning: clear soft-blue sky, gentle warm sunlight from the lower left, fresh bright air, the sun low-to-mid on the left. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**25. `autumn-noon.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Midday: bright but soft blue sky, sun high overhead near center, crisp even daylight, minimal shadows, calm and airy. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**26. `autumn-afternoon.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Afternoon: warm slightly-golden blue sky, the sun descending toward the right, gently lengthening soft shadows. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**27. `autumn-sunset.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Sunset: the sun low on the right horizon, rich golden-orange and red glow, warm golden-hour light over the scene, glowing sky. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**28. `autumn-dusk.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Dusk: the sun just below the right horizon, deep orange fading up into violet and purple, a warm afterglow low on the right, cooling light. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**29. `autumn-twilight-dusk.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Late twilight after sunset: deep blue-violet sky, the first stars appearing, a faint warm band lingering at the horizon, the cottage windows glowing warm. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**30. `autumn-night.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle grassy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Autumn: foliage in warm amber, orange and russet, scattered fallen leaves on the grass and cottage roof, golden mellow tones. Night: dark near-black navy sky full of stars with a bright moon, cool moonlight over the scene, the cottage windows glowing warm and inviting. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

### Winter

**31. `winter-twilight-dawn.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Pre-dawn twilight: deep indigo-navy sky, the faintest cool glow low on the left horizon, a few dim stars still out, no sun yet, quiet and dark. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**32. `winter-dawn.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Dawn: indigo sky washing to soft rose and magenta along the left horizon, brightening, the sun not yet risen, delicate cool-to-warm gradient. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**33. `winter-sunrise.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Sunrise: the sun low on the left horizon, warm golden-orange glow over cold snow, long gentle light, peach-and-pink sky. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**34. `winter-morning.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Morning: clear pale-blue sky, gentle cool sunlight from the lower left, bright crisp winter air, the sun low-to-mid on the left. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**35. `winter-noon.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Midday: bright but soft pale-blue sky, sun high overhead near center, crisp even winter daylight, minimal shadows. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**36. `winter-afternoon.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Afternoon: cool slightly-golden pale-blue sky, the sun descending toward the right, long soft blue shadows on the snow. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**37. `winter-sunset.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Sunset: the sun low on the right horizon, rich rose-and-orange glow over cold snow, warm golden-hour light against blue shadows. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**38. `winter-dusk.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Dusk: the sun just below the right horizon, deep orange fading up into violet and cold blue, a faint warm afterglow low on the right. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**39. `winter-twilight-dusk.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Late twilight after sunset: deep blue-violet sky over pale snow, the first stars appearing, a faint warm band at the horizon, the cottage windows glowing warm. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.

**40. `winter-night.jpg`**
> A wide, calm illustrated landscape from a fixed low viewpoint: a distant mountain range on a low horizon, a small simple cottage with a pitched roof toward the right, a few rounded trees and low shrubs, and a gentle snowy foreground. Minimal softly stylized digital painting, smooth shapes, clean gradients, open sky in the upper two-thirds. Winter: bare snow-dusted trees, snow-covered ground, a snow-capped mountain, cool blue-white palette, crisp still air. Night: dark near-black navy sky full of stars with a bright moon, cold blue moonlight glinting on the snow, the cottage windows glowing warm and inviting. 16:9, 1920x1080, soft ambient lighting, muted palette, low contrast, no bright hotspot in the right two-thirds, flat painterly illustration, subtle grain.
