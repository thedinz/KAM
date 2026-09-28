# KAM — Kometa Asset Manager

KAM is a web app for managing the artwork in your [Kometa](https://kometa.wiki) asset
folders. It connects to your Plex server, shows every movie, TV show, and collection
next to the artwork Kometa will use, and lets you upload, import, and clean up that
artwork from your browser. Files are always saved with the exact names and layout
Kometa expects.

> KAM is an add-on for Kometa, not a replacement. Kometa still applies the artwork to
> Plex on its normal runs; KAM manages the files in its asset directories.

**Latest release:** [github.com/thedinz/KAM/releases/latest](https://github.com/thedinz/KAM/releases/latest)

---

## Contents

- [What KAM does](#what-kam-does)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
  - [1. Prepare Kometa](#1-prepare-kometa)
  - [2. Run KAM with Docker Compose](#2-run-kam-with-docker-compose)
  - [Docker run](#docker-run)
  - [Unraid](#unraid)
  - [3. First-time setup](#3-first-time-setup)
- [Using KAM](#using-kam)
- [Configuration reference](#configuration-reference)
- [Security](#security)
- [Updating](#updating)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Development](#development)

---

## What KAM does

**Browse your libraries**
- Every mapped Plex library appears in the sidebar, with its collections nested below it.
- Each item shows its local poster (or the Plex poster, when there is no local one) and
  whether KAM found its Kometa asset folder.
- Search, sort by title or recently added, and filter to items that **Need Attention**.

**Manage artwork**
- Upload posters and backgrounds for movies, shows, and collections.
- Upload season posters, season backgrounds, and episode title cards for TV shows.
- Uploads are converted to `.jpg`, and any older `poster.png` / `poster.webp` style
  variants are removed so Kometa uses the new file.
- **Import Assets** copies the artwork currently in Plex into your asset folders, for a
  single item or a whole library at once.
- **Import Mediux zip** on a show page maps a Mediux set (show poster, backdrop,
  seasons, and title cards) to Kometa file names automatically.
- **Send to Plex** pushes a saved asset straight to Plex, or enable it automatically
  after every upload.

**Keep folders matched**
- KAM matches Plex items to existing asset folders, tolerating year, edition, and
  punctuation differences.
- Anything it cannot match safely is marked **Not Ready**; pick the right folder with
  the built-in folder finder.
- **Mapping Scan** checks a whole library at once and lets you confirm matches in bulk.

**Clean up**
- **Orphaned Assets** finds folders that no longer belong to anything in Plex.
- **Duplicate Folders** finds items with more than one folder and keeps the one you
  choose.
- Exclude items from KAM, or mark known orphan false positives, and restore them later.

**Everything else**
- **Setup Check** confirms Plex access, writable asset paths, collection folders, and
  that your settings will survive container updates.
- Optional built-in login, or hand authentication to your reverse proxy.
- Light and dark themes.

---

## How it works

KAM reads your library contents from Plex and reads/writes files in the asset folders
you mount into its container. It never creates asset folders; Kometa does that. The
layout KAM writes is Kometa's standard asset layout:

```
/assets
├── Movies
│   └── The Matrix (1999)
│       ├── poster.jpg
│       └── background.jpg
├── TV Shows
│   └── Breaking Bad
│       ├── poster.jpg
│       ├── background.jpg
│       ├── Season01.jpg              ← season poster
│       ├── Season01_background.jpg   ← season background
│       ├── S01E01.jpg                ← episode title card
│       └── ...
└── Collections
    └── Batman Collection
        ├── poster.jpg
        └── background.jpg
```

Season artwork and title cards are flat files in the show folder. KAM does not use
`Season 01/` subfolders.

---

## Requirements

- **Docker** (Linux, Unraid, macOS, or Windows).
- **Plex Media Server** and a Plex token
  ([how to find your token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)).
- **Kometa** set up to create asset folders (see below).
- Read/write access to your Kometa asset directory.

---

## Installation

### 1. Prepare Kometa

KAM only writes into folders that already exist, so Kometa must create a folder for
every item. In your Kometa config, enable these for each library you want to manage:

```yaml
libraries:
  Movies:
    operations:
      assets_for_all: true
      assets_for_all_collections: true
    settings:
      create_asset_folders: true
```

Run Kometa once afterwards so the folders exist. If a folder is missing, KAM reports
the item as **Not Ready** and uploads for it fail.

### 2. Run KAM with Docker Compose

Create a `docker-compose.yml`:

```yaml
services:
  kam:
    image: ghcr.io/thedinz/kam:latest
    container_name: kam
    ports:
      - "7171:8000"
    environment:
      KAM_ASSETS_ROOT: /assets
      COLLECTIONS_ROOT: /assets/Collections
      PLEX_VERIFY_SSL: "true"
    volumes:
      - /path/to/kam/config:/config
      - /path/to/kometa/assets:/assets
    restart: unless-stopped
```

Replace the two host paths on the left of each volume:

| Volume | What to point it at |
|---|---|
| `/config` | An empty folder where KAM stores its settings. Required, or settings are lost when the container is recreated. |
| `/assets` | Your Kometa asset directory (the folder Kometa's `asset_directory` uses). |

Then start it:

```bash
docker compose up -d
```

Open `http://<your-server>:7171/`.

The container listens on port `8000`. Change the left side of `7171:8000` to use a
different port.

### Docker run

The same setup without Compose:

```bash
docker run -d \
  --name kam \
  -p 7171:8000 \
  -e KAM_ASSETS_ROOT=/assets \
  -e COLLECTIONS_ROOT=/assets/Collections \
  -v /path/to/kam/config:/config \
  -v /path/to/kometa/assets:/assets \
  --restart unless-stopped \
  ghcr.io/thedinz/kam:latest
```

### Unraid

Install **Kometa Asset Manager** from Community Applications, then in the template:

1. Map a config folder such as `/mnt/user/appdata/kam` to `/config`.
2. Map your Kometa asset folder (for example `/mnt/user/appdata/kometa/assets`) to `/assets`.
3. Leave `KAM_ASSETS_ROOT=/assets` and `COLLECTIONS_ROOT=/assets/Collections` unless your
   collection folders live elsewhere.
4. Set `PLEX_VERIFY_SSL=false` only if Plex uses a self-signed HTTPS certificate.

### 3. First-time setup

Open KAM and go to **Settings**:

1. **Plex** — enter your Plex URL (for example `http://192.168.1.10:32400`) and Plex
   token, then save.
2. **Libraries** — for each Plex library you want to manage, choose its **asset folder**
   inside `/assets` (for example `/assets/Movies`). Optionally set a **collections
   folder** if that library's collections are not in `COLLECTIONS_ROOT`.
3. **Setup Check** — run it to confirm Plex, folders, and config persistence are working.
4. **Login** (optional) — set a username and password, or choose reverse proxy auth. See
   [Security](#security).

Your mapped libraries now appear in the sidebar.

> Give each Plex library its own asset folder. Collections can share one folder such as
> `/assets/Collections`, or be overridden per library.

---

## Using KAM

### Uploading artwork

Open a movie, show, or collection and use the upload button on any artwork card. Any
common image format works; KAM saves it as `poster.jpg`, `background.jpg`,
`SeasonNN.jpg`, `SeasonNN_background.jpg`, or `SNNENN.jpg` and replaces the previous
file.

On a show page, **Import Mediux zip** accepts a Mediux set with names such as
`Show (2024).jpg`, `Show (2024) - Backdrop.jpg`, `Show (2024) - Season 1.jpg`, and
`Show (2024) - S1 E1.jpg`.

### Importing artwork from Plex

Use **Import Assets** on a library to copy what Plex currently shows into your asset
folders, choosing which artwork types to include. Individual detail pages also have
import buttons. Anything that fails is listed under **Import Errors** so you can retry.

### Sending artwork to Plex

Each saved asset has **Send to Plex**, which uploads the local file to the matching Plex
item without changing the asset. To do this automatically after every upload, enable
**Send artwork to Plex automatically after uploads** under **Settings → Plex** (off by
default). If Plex rejects the update, the upload is still saved. If you use Kometa
overlays, Kometa re-applies them on its next run.

### Fixing unmatched items

Items without a matched folder show a **Not Ready** badge and are listed under
**Needs Attention**. Click the badge to open the folder finder, browse or search your
asset folders, and assign the right one. KAM remembers the choice.

For a whole library, open **Mapping Scan** to review suggested matches and assign them in
bulk.

### Excluding items

Exclude any movie, show, or collection from its detail page to hide it from KAM.
Restore it from **Settings → Exclusions**.

### Cleaning up folders

The **Library maintenance** section of the sidebar has two tools. Open them from a
library to audit its asset folder, or from that library's **Collections** view to audit
the collections folder. The page always shows the exact folder being checked.

- **Orphaned Assets** lists folders that nothing in Plex claims. Select folders to
  delete, or mark a false positive **Exclude — asset exists** to hide it from future
  audits (use **Show excluded** to bring it back).
- **Duplicate Folders** lists items that match more than one folder. Pick the folder to
  keep on each card, then **Keep selected folder** or **Process all**. KAM switches to the
  kept folder before removing the others.

Folders shared with other libraries or collections are protected, and KAM re-checks Plex
immediately before deleting anything.

> **Deletion is permanent.** Review the list and keep a backup of your asset folders.

---

## Configuration reference

Most settings are made in the UI and saved to `/config/settings.json`. Environment
variables cover paths and deployment options.

### Paths

| Variable | Default | Purpose |
|---|---|---|
| `KAM_ASSETS_ROOT` | `/assets` | Asset root inside the container. |
| `COLLECTIONS_ROOT` | `<assets root>/Collections` | Default folder for collection assets. |
| `KAM_STATE_ROOT` | `/config` | Folder for KAM's saved state. |
| `KAM_SETTINGS_PATH` | `<state root>/settings.json` | Override the settings file location. |
| `KAM_FOLDER_OVERRIDES_PATH` | `<state root>/folder_overrides.json` | Override the saved folder assignments file. |
| `KAM_EXCLUSIONS_PATH` | `<state root>/exclusions.json` | Override the excluded items file. |
| `KAM_ORPHAN_EXCLUSIONS_PATH` | `<state root>/orphan_exclusions.json` | Override the orphan audit exclusions file. |
| `KAM_LEGACY_STATE_ROOT` | — | Older state folder to read folder assignments from after a migration. |

### Plex and logging

| Variable | Default | Purpose |
|---|---|---|
| `PLEX_VERIFY_SSL` | `true` | Set to `false` for a Plex server with a self-signed HTTPS certificate. |
| `KAM_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |

### Authentication and access

| Variable | Default | Purpose |
|---|---|---|
| `KAM_AUTH_MODE` | from Settings | `builtin` or `reverse_proxy`. |
| `KAM_AUTH_USERNAME` | from Settings | Built-in login username. |
| `KAM_AUTH_PASSWORD` | from Settings | Built-in login password. Setting a password turns the login on. |
| `KAM_AUTH_COOKIE` | `kam_auth` | Session cookie name. |
| `KAM_AUTH_TOKEN_TTL_SECONDS` | `604800` (7 days) | How long a login lasts. |
| `KAM_AUTH_COOKIE_SECURE` | auto | `true` forces an HTTPS-only cookie; auto-detected otherwise. |
| `KAM_CORS_ORIGINS` | off | Comma-separated origins allowed to call the API from another website. |

### Saved files

| File | Contents |
|---|---|
| `settings.json` | Theme, Plex URL and token, login settings, and library mappings. |
| `folder_overrides.json` | Folders you assigned with the folder finder or Mapping Scan. |
| `exclusions.json` | Items hidden from KAM. |
| `orphan_exclusions.json` | Folders hidden from the orphan audit. |

Installs that stored these files in `/data` are migrated automatically: KAM keeps using
an existing `/data/*.json` file until a `/config` copy exists.

---

## Security

KAM can read your Plex token and delete asset folders, so do not expose it to the
internet without protection.

- **Built-in login:** set a username and password under **Settings → Login** (or with
  `KAM_AUTH_USERNAME` / `KAM_AUTH_PASSWORD`). Without a password, anyone who can reach KAM
  can use it.
- **Reverse proxy auth:** choose **Reverse proxy auth** (or `KAM_AUTH_MODE=reverse_proxy`)
  if a proxy such as Authelia, Authentik, or an Nginx/Traefik/Caddy auth layer already
  protects KAM. KAM then skips its own login, so only use this behind a proxy that
  enforces authentication.
- For remote access, put KAM behind a reverse proxy with HTTPS rather than forwarding the
  port directly.

Installs that only had a password from older versions keep working. The first login asks
you to choose a username.

---

## Updating

```bash
docker compose pull
docker compose up -d
```

With `docker run`, pull `ghcr.io/thedinz/kam:latest`, remove the old container, and
start it again with the same options. On Unraid, use **Update** on the container.

Your settings and artwork are safe as long as `/config` and `/assets` are mounted from
the host.

**Image tags**

| Tag | Use |
|---|---|
| `latest` | Current stable release. |
| `vX.Y.Z` | A specific release, for pinning or rolling back. |
| `dev` | Development builds. May be unstable. |

See [CHANGELOG.md](CHANGELOG.md) for what changed in each release.

---

## Troubleshooting

**No libraries in the sidebar**
Add Plex credentials under **Settings → Plex**, then map at least one library under
**Settings → Libraries**.

**Everything is Not Ready**
The library's asset folder is probably wrong, or Kometa has not created folders yet.
Check the mapping, run **Setup Check**, and confirm `assets_for_all` and
`create_asset_folders` are enabled in Kometa.

**"Plex connect failed" or certificate errors**
Check the Plex URL is reachable from inside the container (use the server's IP rather
than `localhost`). For a self-signed HTTPS certificate, set `PLEX_VERIFY_SSL=false`.

**Uploads fail with a permission error**
The container needs write access to your asset folders. Check the folder's owner and
permissions on the host.

**New artwork does not show in Plex**
KAM saves files for Kometa, which applies them on its next run. Use **Send to Plex** for
an immediate update. Plex may also cache images for a while.

**Settings disappear after an update**
`/config` is not mapped to a host folder. Add the volume and save your settings again.

**Collections are missing or show the wrong folder**
Check `COLLECTIONS_ROOT` and any collections folder set for the library under
**Settings → Libraries**.

**More detail**
Set `KAM_LOG_LEVEL=DEBUG` and check the container logs with `docker logs kam`.

---

## FAQ

**Does KAM change my Plex library?**
Only when you use **Send to Plex** or turn on automatic sending. Otherwise it only reads
from Plex.

**Does KAM keep old artwork?**
No. Uploading replaces the existing file for that asset. Back up your asset folders if you
want history.

**Which image formats can I upload?**
JPEG, PNG, and WebP. Non-JPEG uploads are converted to `.jpg`; JPEG uploads are saved
unchanged.

**Can I map any host folder?**
Yes. Only the path inside the container matters, so mount your Kometa asset folder at
`/assets` from wherever it lives.

**Can two libraries share one asset folder?**
Give each library its own folder. Collections can share a single folder.

---

## Development

KAM is a FastAPI backend (`app/`) with a React + Vite frontend (`frontend/`).

**Backend**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest httpx
uvicorn app.main:app --reload --port 8000
pytest
```

**Frontend**

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173, proxies API calls to port 8000
npm test
npm run build   # writes the production bundle to app/web/
```

The production bundle in `app/web/` is generated at build time and is not committed;
only `fallback.png` and `movie.html` are tracked there. Check `git status` after a local
build.

**Docker image**

```bash
docker build -t kam .
```
