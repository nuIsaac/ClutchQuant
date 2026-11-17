# 12:12 product system

The colon and tabular typography form the identity: 12:12 is the overtime scoreline,
pronounced twelve to twelve. Original stacked 12/12 favicon and typographic social
artwork use no Riot or team logos.

`apps/web/src/lib/brand.ts` owns display identity. `src/app/globals.css` owns semantic
background, foreground, surface, muted, line, accent, focus, warning, radius and
body/small typography tokens. The palette uses near-black, charcoal, off-white text and a restrained pale sage accent. Probabilities use tabular numerals; unknown values remain unknown.
Cards use small radii and clear borders. Decorative radar shapes and spotlight
rings are removed. The layout retains responsive grid/list views and live states.

Dashboard composition lives in `page.tsx`; icons, team initials, match cards,
forecast details and model information have separate components. Data decoding,
identity alignment, discovery, retries and persistence stay in `src/lib`. Team
initials are generated labels, not official team logos. No model math was changed.

Interaction requirements: visible focus, skip link, keyboard search shortcut,
native modal dialogs, clear selected filters, live announcements, explicit retry,
stale/unavailable messages, reduced-motion support and accessible probability text.
Current model estimates must remain distinguished from immutable saved forecasts.
No new runtime dependency or agent protocol is introduced.

The current workspace uses top navigation, a compact overview strip, default match
rows with aligned date/team/probability/tournament columns, optional grid view, and
a next-match/methodology context rail. Mobile stacks content without horizontal
scrolling. Search, tournament/date selectors and sort controls share one toolbar.
Dialog styles live in src/app/dialogs.css; general formatting in match-format.ts.
