---
name: landing-motion
description: Maintain the RAG Observatory landing page with Lenis and GSAP.
---

Read DESIGN_SYSTEM.md and the landing component before editing. Lenis and GSAP are libraries, not upstream agent skills. Official integration references: https://github.com/darkroomengineering/lenis and https://github.com/greensock/gsap.

Owner expanded motion and editorial typography to the actual workspace on2026-10-17. Keep one Lenis instance per active route, including workspace routes. Drive Lenis with GSAP ticker seconds converted to milliseconds; synchronize ScrollTrigger with scroll events. Never run a second animation-frame loop. Revert GSAP contexts and media, remove ticker/listeners and destroy Lenis on cleanup. Keep SSR content visible without JavaScript. Respect prefers-reduced-motion dynamically using matchMedia: native scroll and no entry/reveal animations. Do not alter global ticker lag settings and preserve native scrolling in nested evidence panes, sidebars and form fields.

Use next/font/local for Instrument Serif and Ostrich Sans; keep their OFL files and provenance. Instrument Serif supplies workspace prose/headings and Ostrich Sans its navigation/labels. Retain dedicated monospace for technical evidence, SQL and IDs. Preserve keyboard focus, links, anchors, mobile menu and semantic method selection. Never fabricate dashboard metrics, testimonials or research outcomes. The demo screenshot is actual software with synthetic evidence and must be labeled.

Run npm check, production build and Chromium tests. Verify desktop/mobile/light/dark, scroll reveal completion and route cleanup on a production preview. Do not rebuild frozen experiment API/worker images for frontend changes.
