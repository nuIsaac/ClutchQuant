# 12:12 web

Next.js 16 / React 19 / TypeScript / Tailwind 4. Use Node.js 24 (matching CI).

```sh
npm ci
# Use your intended API; no environment file is silently overwritten.
API_URL=http://127.0.0.1:8000/api/v1 npm run dev
npm test
npm run lint
npm run typecheck
npm run build
```

Open http://localhost:3000. Supply SITE_URL at build time for a deployed public
origin; Vercel's production URL is also supported. Keep API_URL server-only.

The dashboard preserves real upstream match data, discovery filters, watchlists,
current previews and saved-forecast provenance. Brand constants live in
`src/lib/brand.ts`; design tokens in `src/app/globals.css`; focused views in
`src/app/components`. Read `../../docs/design-system.md` and
`../../docs/rebrand-compatibility.md` before deployment changes.

Watchlists migrate on the same browser origin. Read failures show the existing
storage warning; migration write failures do not discard readable saved items.
