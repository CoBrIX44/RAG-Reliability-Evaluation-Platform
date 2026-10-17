# Frontend design contract

Approved direction: a restrained research workspace focused on experiment comparison and evidence inspection.

## Source and precedence
Use this contract as the source of truth. Apply the user-requested design-taste-frontend, gpt-taste, ui-ux-pro-max, design-taste-frontend-v1, anti-ui-slop and anti-slop-design skills contextually to implementation and review. This is product UI: preserve research workflows; cinematic marketing heroes, scroll pinning, random layout changes and decorative perpetual motion do not apply. Their catalogue suggestions are advisory. Local search returned relevant dashboard guidance but no verified overall layout match; marketing-page patterns were rejected. Do not persist or adopt those generated layouts.

## Hierarchy and navigation
Persistent desktop navigation: Experiments, Documents, Datasets, Comparisons, Settings. Experiment list is the default entry. Failure explorer is a detail route with breadcrumbs. Identify corpus/dataset versions beside run results. One primary action per screen; ordinary navigation is separated from deletion controls.

## Visual tokens (proposed implementation values)
Light tokens: background #F2F5F3, surface #FCFEFC, text #1C2B24, muted #53635B, primary #1B6650, subtle border #D9E3DC. Dark tokens: background #111A16, surface #19251E, text #E8F0EB, muted #AEBFB4, primary #99D5B5. Primary foreground switches per theme; status colors remain semantic, separate from the single green action accent. Verify actual foreground/background contrast before delivery. Amber marks warnings; red marks failures; status always includes text. Strategy colors remain stable across charts and tables and also use labels/shapes.

Use Outfit (variable400-700) for headings/body and IBM Plex Mono400/500 for SQL, configuration, identifiers and numeric columns. Local WOFF2 assets use next/font/local with swap; only the primary interface font is preloaded. Font binaries total61,888 bytes. Retain bundled SIL OFL licenses and source SHA-256 records in apps/web/src/app/fonts/. No runtime Google Fonts request or font dependency is required. Use tabular numerals for metrics. Base body size 16px; compact table labels may be 14px with adequate line height. Spacing scale: 4, 8, 12, 16, 24, 32, 48px. Modest corner radii, restrained borders, minimal elevation.

## Components and interaction
Semantic buttons, labeled inputs, sortable tables, filter bars, progress rows, evidence panes, accessible dialogs, inline alerts, labeled comparison charts. Consistent SVG icon family. Avoid decorative KPI tiles that repeat the table, gradients, ornamental motion, and invented activity or scores.

All screens cover loading, empty, error, success, disabled, and unavailable-access/configuration states. Failed forms preserve input and show field errors; multi-error forms expose a linked summary. Async actions provide immediate feedback and prevent duplicate submission. Dialogs support Escape and focus restoration. Upload supports file picker as an alternative to drag/drop.

## Charts and evidence
Comparison charts show units, metric definition, sample count, uncertainty method, and a table alternative. Missing measurements display unavailable, never zero. Evidence viewer distinguishes retrieved passages, delivered context, and gold evidence. Preserve code formatting and readable prose widths.

## Responsive and acceptance
At 375, 768, 1024, and 1440px: collapse navigation, stack evidence panes, wrap filters, and avoid page-level horizontal overflow. Wide tables may use a labeled local scroll container with accessible alternatives. Preserve browser zoom. Keyboard focus must stay visible. Honor reduced motion. Inspect rendered screens with real or clearly labeled fixture data for clipping, overlap, misleading content, contrast, and functioning controls.

2026-10-17 refresh introduces system/light/dark appearance with persistent local preference. Verify contrast independently per theme. Theme changes suppress color interpolation to prevent transient unreadable controls. Navigation, route slugs, field names/order and backend contracts are preserved. Saved runs appear above experiment configuration, with page-scoped state filtering and a keyboard-focusable New experiment shortcut. Retrieval preview and workflow guidance use native expandable disclosures. Desktop navigation remains sticky; mobile uses the existing menu and stacked page controls. UI preview/build runs natively on3001; do not restart/rebuild frozen experiment services or change Python/package locks mid-campaign.


## Refresh design decisions

Design variance5 /motion2 /density7: product-specific hierarchy and restrained interaction feedback. The real seeded typography choice selected Outfit; choosing arbitrary marketing layouts would harm repeatable research tasks. Catalogue search returned useful data-density guidance and next/font advice, but its Enterprise Gateway/Contact Sales layout was rejected as irrelevant. Existing semantic CSS and icon family are retained; no new UI/animation dependency or package-lock change. Radius scale:10px content surfaces,7px controls,9px brand container. Data tables keep local accessible scrolling; do not conceal overflow globally.

Measured token pairs: light text14.59:1, muted5.79:1, primary-button6.77:1; dark text13.66:1, muted9.22:1, primary-button9.20:1. Control borders3.36:1 light /4.94:1 dark. These are calculated token contrast values, not certification of every composed state. Browser axe checks and visual inspection remain required.

## Public landing page — 2026-10-17
The owner explicitly requested a landing page, Lenis, GSAP, Instrument Serif and Ostrich Sans. This extends the earlier workspace-only contract: `/` is now the public-facing product introduction; `/experiments` remains the workspace entry. The dashboard retains Outfit/Plex for dense research workflows. The landing uses locally bundled Instrument Serif regular and Ostrich Sans bold with upstream OFL notices/source hashes. Paper/ink/rust colors have light/dark variants. The actual read-only demo screenshot is explicitly synthetic; no benchmark claims or invented activity.

Lenis1.3.27 and GSAP3.15.0 are exact frontend dependencies. GSAP ticker drives Lenis and synchronizes ScrollTrigger; effects are scoped and destroyed on navigation. No global ticker timing mutation. Reduced motion uses native scrolling and static content. Sections use finite reveals, no pinned scroll or perpetual animation. Mobile menu, method buttons, skip link and theme selection remain keyboard accessible. See skills/landing-motion/SKILL.md.

## Workspace editorial expansion — 2026-10-17 (current)
The owner explicitly requested the landing identity, fonts, GSAP and Lenis throughout the actual project pages. This supersedes earlier workspace-only Outfit/green/no-motion guidance and the landing-only restriction. Layout/workflows remain recognizable: sidebar, saved runs, evidence editors, comparison tables and settings retain actions, routes, review provenance and unavailable metrics. Shared next/font assets are defined in app/fonts.ts and applied in root layout. Instrument Serif supplies headings/prose/inputs; Ostrich Sans supplies labels/navigation/actions at readable sizes. IBM Plex Mono remains exclusively for technical evidence, SQL, raw identifiers and numeric tables. No runtime font service.

Workspace uses landing paper/ink/rust colors in both themes, restrained square outlines and an underlined active navigation item. Color remains semantic for errors/warnings/success. Motion variance3/motion2/density7: finite12px GSAP heading movement without opacity changes preserves text contrast; live result rows do not move. Each workspace route owns one Lenis instance, driven by GSAP ticker. Route cleanup and dynamic reduced-motion cleanup remove it; nested source panes, preformatted evidence, sidebars and form fields keep native scrolling. Native anchors/focus controls remain available. No scroll pinning, looping effects or backend behavior changes.
