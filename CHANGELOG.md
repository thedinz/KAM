# Changelog

## 8.0.0 — 2026-10-16

KAM now requires a login before it can be used. **If your KAM has no login password,
it will ask you to create one after this update.**

- On first start (or after updating an install without a password), KAM shows a setup
  screen and serves nothing else until a login is created. To prove you own the server,
  enter the **setup code** from KAM's container log (on Unraid: **Docker** tab, KAM
  icon, **Logs**), then choose a username and a password of at least 8 characters.
  The code changes each time KAM restarts.
- Installs that already have a password, use reverse proxy auth, or set
  `KAM_AUTH_PASSWORD` are not affected.
- To keep running without a login, set `KAM_AUTH_MODE=none` on the container. Only
  do this if KAM can't be reached from anywhere you don't trust. This can't be switched
  on from the Settings page, and Settings no longer saves the built-in login with an
  empty password.

## 7.3.0 — 2026-10-14

- Pages load much faster on slow connections. Grids, cleanup lists and artwork previews
  now show resized copies of artwork instead of the full-size files (a typical poster
  drops from over 1 MB to under 100 KB). Copies of local artwork are kept in
  `/config/cache/thumbnails` and rebuilt when the artwork changes; Plex images are
  resized by Plex.
- Images you've already seen are kept by your browser instead of being downloaded or
  re-checked on every visit.
- When a library page has finished loading, KAM quietly loads the next page and its
  posters in the background, so **Next** is instant. This is skipped when your browser
  has data saver on or reports a very slow connection.
- With the built-in login on, files under `/assets` now require a login too.

## 7.2.2 — 2026-10-14

Security and reliability fixes. Updating is recommended.

- Library and collection folders must now be inside `/assets` (`KAM_ASSETS_ROOT`) or
  `COLLECTIONS_ROOT`. Folders elsewhere can't be saved; ones saved by older versions
  are ignored and flagged by **Setup Check**, so move them inside `/assets`.
- Orphan and duplicate cleanup never deletes a folder that holds a configured library
  or collections folder, and duplicate resolution keeps folders another item still uses.
- Imports only accept POST requests.
- The Plex token is sent only as a request header and kept out of logs, and Plex
  requests no longer follow redirects to other servers.
- Changing the login username, password or auth mode signs out existing sessions, and
  repeated failed sign-ins from one address are paused for 15 minutes.
- Uploads are limited to 50 MB and 100 megapixels per image, and Mediux zips to 5000
  entries and 2 GB unpacked.

## 7.2.1 — 2026-09-28

- Protect asset folders from orphan cleanup when their directory is shared with
  another library or with collections (for example one shared `Collections`
  folder), and fail collection audits instead of treating unreadable Plex
  collections as "no collections".
- Convert uploaded PNG/WebP artwork to real JPEG files again, remove leftover
  `poster.png`/`poster.webp` style variants, and reject invalid images without
  deleting existing artwork.
- Reject folder names that try to leave the asset library folder.
- Show local TV artwork for libraries mapped to folders not named after the
  library.
- Honor `PLEX_VERIFY_SSL` for every Plex request, only send the Plex token to the
  configured Plex server, and keep the token out of import error messages.
- Disable cross-origin API access by default; set `KAM_CORS_ORIGINS` to allow
  specific origins.

## 7.2.0 — 2026-08-30

- Extend **Orphaned Assets** and **Duplicate Folders** cleanup to mapped collection
  roots while keeping collection and normal-library audits safely separated.
- Preserve collection context throughout cleanup navigation and use library-neutral
  asset labels and counts on movie, TV, and collection pages.
- Switch KAM to a newly retained collection folder before deleting its verified
  alternatives, including staged **Process all** resolutions.
- Scope persistent orphan exclusions to either normal assets or collections so the
  same folder name can be reviewed independently in both roots.
- Fix duplicate resolution for distinct filesystem folders whose exact names compare
  equal case-insensitively or contain otherwise invisible differences.

## 7.1.0 — 2026-08-30

- Add a per-library **Orphaned Assets** audit that compares asset folders with
  current Plex items and rechecks matches before permanent deletion.
- Protect valid title, year, and edition folder variations from orphan cleanup,
  including conservative handling for ambiguous remakes.
- Let users exclude known orphan false positives, review those exclusions later,
  and restore them to the audit without removing their artwork.
- Add a **Duplicate Folders** workflow for choosing the folder to retain while
  switching KAM to that folder before deleting verified alternatives.
- Support staging retained-folder choices across the full duplicate list and
  processing them together with library-neutral asset labels and result counts.

## 7.0.0 — 2026-08-29

- Redesign the KAM interface around a responsive application sidebar, updated
  branding, clearer page hierarchy, and refreshed library, detail, settings,
  mapping, and status surfaces.
- Replace duplicate library selectors with navigation generated from mapped
  Plex libraries, including nested per-library Collections views.
- Consolidate readiness progress into a contextual **Needs Attention** workflow
  that preserves movie, TV, and collection scope, counts, navigation, and return
  paths.
- Refine series and season artwork layouts, including expanded season cards and
  more consistent poster, background, title-card, and action placement.
- Improve route synchronization, initial sidebar library loading, collection
  hierarchy connectors, detail header alignment, responsive behavior, and the
  KAM favicon.

## 6.2.0 — 2026-08-21

- Add username-and-password built-in authentication with username configuration
  in Settings.
- Migrate password-only installations by prompting for a username on the first
  login while retaining compatibility with password-only login API clients.

## 6.1.0 — 2026-07-29

- Add optional automatic Plex artwork updates after uploads.
- Add manual **Send to Plex** controls for movies, collections, series, seasons,
  backgrounds, and episode title cards.
- Preserve successful asset uploads when an automatic Plex update fails.

## 1.8.1 — 2025-09-28
- Fix: Bulk 'Import Assets' for **Movies** now imports both `poster.jpg` and `background.jpg` via new `/api/import/movie`.
- UI: `index.html` now calls the combined endpoint (better progress message too).
- Backend: Adds `/api/import/movie`, reuses existing helpers; `/api/import/poster` and `/api/import/background` still available.
- No breaking or config changes.
