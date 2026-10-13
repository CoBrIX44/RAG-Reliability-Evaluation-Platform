# Frontend design contract

Approved direction: a restrained research workspace focused on experiment comparison and evidence inspection.

## Source and precedence
Use this contract as the source of truth. Apply the user-requested ui-ux-pro-max and anti-ui-slop skills to implementation and review. Their catalogue suggestions are advisory. Local search returned relevant dashboard guidance but no verified overall layout match; marketing-page patterns were rejected. Do not persist or adopt those generated layouts.

## Hierarchy and navigation
Persistent desktop navigation: Experiments, Documents, Datasets, Comparisons, Settings. Experiment list is the default entry. Failure explorer is a detail route with breadcrumbs. Identify corpus/dataset versions beside run results. One primary action per screen; ordinary navigation is separated from deletion controls.

## Visual tokens (proposed implementation values)
Light background #F8FAFC, surface #FFFFFF, text #172033, secondary text #475569, primary #1E40AF, divider #CBD5E1. Verify actual foreground/background contrast before delivery. Amber marks warnings; red marks failures; status always includes text. Strategy colors remain stable across charts and tables and also use labels/shapes.

Use Fira Sans or a readable system sans-serif for headings/body; Fira Code or system monospace for SQL, configuration, and identifiers. Self-host fonts if introduced; do not require external font requests. Use tabular numerals for metrics. Base body size 16px; compact table labels may be 14px with adequate line height. Spacing scale: 4, 8, 12, 16, 24, 32, 48px. Modest corner radii, restrained borders, minimal elevation.

## Components and interaction
Semantic buttons, labeled inputs, sortable tables, filter bars, progress rows, evidence panes, accessible dialogs, inline alerts, labeled comparison charts. Consistent SVG icon family. Avoid decorative KPI tiles that repeat the table, gradients, ornamental motion, and invented activity or scores.

All screens cover loading, empty, error, success, disabled, and unavailable-access/configuration states. Failed forms preserve input and show field errors; multi-error forms expose a linked summary. Async actions provide immediate feedback and prevent duplicate submission. Dialogs support Escape and focus restoration. Upload supports file picker as an alternative to drag/drop.

## Charts and evidence
Comparison charts show units, metric definition, sample count, uncertainty method, and a table alternative. Missing measurements display unavailable, never zero. Evidence viewer distinguishes retrieved passages, delivered context, and gold evidence. Preserve code formatting and readable prose widths.

## Responsive and acceptance
At 375, 768, 1024, and 1440px: collapse navigation, stack evidence panes, wrap filters, and avoid page-level horizontal overflow. Wide tables may use a labeled local scroll container with accessible alternatives. Preserve browser zoom. Keyboard focus must stay visible. Honor reduced motion. Inspect rendered screens with real or clearly labeled fixture data for clipping, overlap, misleading content, contrast, and functioning controls.

Dark mode is deferred until independently verified; light mode is the first release requirement.
