# Mindspace — Frontend

React + Vite single-page app implementing the **Mindspace** design (imported from
Claude Design), wired to the Vivid Space Django API.

## Run

```powershell
npm install
npm run dev      # http://localhost:5173  (proxies /api and /media to :8000)
```

Start the backend first (`backend/README.md`). The Vite dev server proxies `/api`
and `/media` to `http://localhost:8000`, so the whole app is same-origin.

## Structure

- `src/pages/Landing.jsx` — the public site (hero, solutions, membership packages,
  spaces, gallery, testimonials, FAQ, book-a-tour form, footer). Login/register,
  the booking flow, and the member dashboard live here as **modals** — there are no
  separate `/auth` or `/portal` routes. Admins are sent to `/admin` after login.
- `src/pages/Admin.jsx` — the admin panel (overview, users, reservations, spaces,
  packages, gallery, FAQ, promo codes, tour requests, calendar blocking, website
  content). CRUD is driven by a shared `FormModal`/`RecordModal`.
- `src/lib/services.js` — all REST calls (public, member, admin).
- `src/lib/ms.js` — Mindspace design tokens (`MS`, `TONES`) and helpers
  (`useVW`, `buildCalendar`, `fmtDate`, `apiError`).
- `src/context/AuthContext.jsx` — JWT auth (login/register/reset/logout).
- `src/lib/api.js` — axios instance with bearer token + refresh-on-401.

## Design source

The layout, palette (warm cream `#F5F1ED`, soft purple `#9B7EBD`) and typography
(Playfair Display + Inter) come from the Claude Design project `Mindspace.dc.html`
and `Mindspace Admin.dc.html`. Every screen that reads or writes data is bound to
the API in `services.js`.
