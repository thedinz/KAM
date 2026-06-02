# KAM — Kometa Asset Manager

KAM is a small web app that makes Kometa/Plex artwork management painless. It lets you upload artwork for **movies, TV series, seasons, and collections** and will:

* **Import existing Plex assets** — movie posters/backgrounds, series posters/backgrounds, and **season posters/backgrounds** — into your mapped Kometa assets structure
* Convert uploads to **`.jpg`**
* **Replace** existing `poster.*`, `background.*`, `SeasonNN.*`, or `SeasonNN_background.*` in the correct asset folder
* Keep everything in the **same structure Kometa expects**
* Provide a simple web UI with a **fallback** image to quickly spot missing artwork
* Let you **exclude** specific movies, shows, or collections from KAM until you re-include them
* Use either KAM's lightweight built-in login or authentication handled by your reverse proxy
* Run a **Setup Check** from Settings to confirm saved Plex credentials, writable asset paths, collection folders, and config persistence

---

## ⚠️ Important constraints

> **KAM maps each Plex library to a single assets directory inside the container (e.g., Kids Movies → `/assets/Kids Movies`).**
>
> **Collections can use a shared directory such as `/assets/Collections`, and you can override that per library or per Plex collection section from the Settings UI.**

What this means in practice:

* Pick **one** assets root for a given library and stick with it.
* If you have multiple Plex libraries, each should have its **own** mapped asset directory.
* Keep collection folders in a shared `Collections` directory, or opt into per-library/section overrides (see **Settings → Libraries**).

---

## Required Kometa settings

For KAM to function properly, Kometa needs to be configured to create and manage asset folders ahead of time.  
In your Kometa configuration (example shown for **Movies**), make sure these settings are enabled:

```yaml
Movies:
  operations:
    assets_for_all: true
    assets_for_all_collections: true
  settings:
    create_asset_folders: true
```

### Why this is required
- **KAM does not create folders.** It only places artwork into existing Kometa asset folders.  
- These Kometa options ensure asset folders are created automatically for every movie, show, and collection.  
- Once the folders exist, KAM will safely upload and replace artwork inside them.  

⚠️ If the folders don’t exist first, uploads from KAM will fail.

⚠️ REMEMBER, this is an addon for Kometa, not a standalone application.

---

## How asset mapping works (flexible)

Inside the container, KAM writes to an **assets root** (examples assume `/assets` inside the container).
You can bind-mount **any** host path to that internal path.

Examples:

* Unraid/host → container

  * `/mnt/user/media/assets` → `/assets`
* Custom mapping

  * `/mystuff` → `/assets`

KAM only cares about the **internal** path (e.g., `/assets`). You choose what host path it points to.

**Typical structure under the mapped root:**

```
/assets
  /Movies
    /The Matrix (1999)
      poster.jpg
      background.jpg

  /TV Shows
    /Breaking Bad
      poster.jpg
      background.jpg
      Season01.jpg
      Season01_background.jpg
      Season02.jpg
      Season02_background.jpg
      Season03.jpg
      Season03_background.jpg

  /Collections
    /Batman Collection
      poster.jpg
      background.jpg
```

> ✅ **Season posters and backgrounds** are stored as flat files **in the series folder** (`Season01.jpg`, `Season01_background.jpg`, …).
> ❌ No `Season 01/` subfolders are used by KAM.

### Collection directory overrides

KAM can read collections from `COLLECTIONS_ROOT` (commonly `/assets/Collections`) and from collection folders saved in **Settings → Libraries**. If you organize collections in multiple roots, set a library's **collections folder** or add collection-section overrides. Behind the scenes, each library supports a `collectionSections` array so you can:

* Point a whole library at a different collections path.
* Target a specific Plex collection section and bind it to its own collections directory.

Overrides inherit the normal sanitization rules, and the folder finder offers suggestions for any directories KAM sees under `/assets`.

---

## Requirements

* Docker (Unraid, Linux, macOS, or Windows)
* Read/write access to your media **assets** directories (bind-mounted)
* Optional: Reverse proxy (Caddy/Traefik/Nginx) if you want TLS or external auth

---

## Quick Start (Docker)

### 1) Pull the image

```bash
docker pull ghcr.io/thedinz/kam:latest
```

### 2) Run (simple)

Expose KAM on **7171** (mapped to the container's port **8000**) and map your assets
and persistent configuration storage:

```bash
docker run -d \
  --name kam \
  -p 7171:8000 \
  -e KAM_ASSETS_ROOT=/assets \
  -e COLLECTIONS_ROOT=/assets/Collections \
  -v /mnt/user/appdata/kam:/config \
  -v /mnt/user/media/assets:/assets \
  ghcr.io/thedinz/kam:latest
```

Open: `http://<your-host>:7171/`

> If your assets live elsewhere, just change the host side of `-v` (e.g., `-v /mystuff:/assets`).
> The published image listens on container port `8000`; change the host side of `-p 7171:8000` if you want a different external port.

### 3) Docker Compose

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
      - /mnt/user/appdata/kam:/config
      - /mnt/user/media/assets:/assets
    restart: unless-stopped
```

Bring it up:

```bash
docker compose up -d
```

Set `PLEX_VERIFY_SSL=false` if your Plex server uses a self-signed certificate and you need KAM to skip TLS verification when contacting Plex.

### Migrating older Compose installs

Older Compose examples used `env_file: .env`. That still works because Docker passes
those values into KAM as normal environment variables.

To remove the extra file, copy any values you still use from `.env` into the
`environment:` block shown above, remove the `env_file:` block from your Compose
file, then run:

```bash
docker compose up -d
```

After the container starts with the inline values, the old `.env` file is no longer
needed.

---

## Persistent configuration

KAM stores persistent JSON files in `/config` by default. Bind-mount `/config` to a
directory on the host (for example, `/mnt/user/appdata/kam`) to persist these values
across image updates, container recreation, and Unraid upgrades.

The main files are:

* `settings.json` — theme, Plex URL/token, auth mode/password, and library mappings.
* `folder_overrides.json` — per-item folder assignments made by the folder finder.
* `exclusions.json` — movies, shows, and collections hidden from KAM until re-included.

You can split state into another mounted directory by setting `KAM_STATE_ROOT`, or use
the explicit file overrides `KAM_SETTINGS_PATH`, `KAM_FOLDER_OVERRIDES_PATH`, and
`KAM_EXCLUSIONS_PATH`. If an older install kept per-item folder assignments in a
separate location, set `KAM_LEGACY_STATE_ROOT` to that directory so KAM can still
read the old `folder_overrides.json` while it writes new state to the current
config location.

> Upgrades from previous versions automatically reuse an existing
> `/data/*.json` file if it is present and no newer `/config` file exists, so saved
> settings, folder assignments, and exclusions are retained while migrating to `/config`.
> Folder assignments are also merged from legacy fallback locations when the current
> `folder_overrides.json` is missing entries.

---

## Managing exclusions

Sometimes you may want to temporarily hide a title from KAM—for example, if you are
still preparing artwork or simply do not want it managed. Any movie, TV show, or
collection can be excluded directly from its detail page. The item will disappear from
library searches and lists while excluded.

To re-include an item, visit **Settings → Exclusions**. The page lists every excluded
item, including its library and type, with a one-click **Include** button that restores
it immediately. You can also refresh the list from the same screen if you make changes
from another browser tab.

---

## Unraid setup

Kometa Asset Manager can now be found in the Unraid app store. Mount both your Kometa
asset directory **and** a persistent config directory (e.g., `/mnt/user/appdata/kam ->
/config`), set `KAM_ASSETS_ROOT` and `COLLECTIONS_ROOT` to match the container paths,
set `PLEX_VERIFY_SSL=false` only if your Plex server uses a self-signed HTTPS
certificate, edit the template variables, and GO!

---

## Usage overview

1. Open the web UI.
2. Open **Settings → Setup Check** if you want to verify Plex, asset paths, collection folders, and config persistence before importing artwork.
3. Choose the item (movie, series, collection, or season) you want to update.
4. If the item shows a red “Not Ready” badge, activate it to open the **folder finder** dialog, browse/search your Kometa assets, and assign the correct folder. Once paired the badge flips to ✔ Ready.
5. Upload artwork. KAM will:

   * Convert to `.jpg`
   * Remove any existing `poster.*`, `background.*`, `SeasonNN.*`, or `SeasonNN_background.*` for that item
   * Save the new file with the correct name

If an item has **no** artwork yet, KAM shows a **fallback** image in the UI so you can spot what’s missing fast.

---

## Folder rules & naming (exact)

KAM follows Kometa’s layout and **does not** invent proprietary paths.

* **Movies**

  ```
  Movies/<Title (Year)>/
    poster.jpg
    background.jpg
  ```

* **TV Series** (series poster/background + seasons)

  ```
  TV Shows/<Show Name>/
    poster.jpg
    background.jpg
    Season01.jpg
    Season01_background.jpg
    Season02.jpg
    Season02_background.jpg
    Season03.jpg
    Season03_background.jpg
    ...
    # (Optionally Season00.jpg if you use Specials)
  ```

* **Collections**

  ```
  Collections/<Collection Name>/
    poster.jpg
    background.jpg
  ```

**Sanitization:** KAM applies a **sane level** of filename/folder sanitization to avoid OS/share problems while preserving Plex/Kometa conventions.

---

## Multiple libraries (recommended patterns)

Because of the “1 library ↔ 1 directory” constraint,

Keep all library roots **under one** top-level directory and mount that top-level to `/assets`.
Collections can share a single `/assets/Collections` directory, or you can map specific Plex libraries/sections to alternate collection directories using the **Settings → Libraries** overrides.

---

## Security & networking

KAM supports two authentication modes:

* **Built-in auth** — set **Settings → Login → Built-in auth** and enter a login password. You can also provide `KAM_AUTH_PASSWORD` as an environment variable.
* **Reverse proxy auth** — set **Settings → Login → Reverse proxy auth** or `KAM_AUTH_MODE=reverse_proxy`. In this mode KAM skips its own login screen and trusts the upstream proxy.

Additional auth environment variables:

* `KAM_AUTH_COOKIE` changes the session cookie name.
* `KAM_AUTH_TOKEN_TTL_SECONDS` changes the session lifetime.
* `KAM_AUTH_COOKIE_SECURE=true` forces the login cookie to be HTTPS-only.

Run KAM on a trusted LAN, or put it behind a reverse proxy (Caddy/Traefik/Nginx) for TLS and external access. Bind to localhost and reverse-proxy if you don't want it exposed directly.

**Example (Traefik labels)** — keep on your proxy if desired (not required):

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.kam.rule=Host(`kam.local`)"
  - "traefik.http.routers.kam.entrypoints=websecure"
  - "traefik.http.routers.kam.tls=true"
```

---

## Building the frontend SPA

The React single-page app lives under `frontend/`.
To rebuild the production bundle (outputs to `app/web/`):

```bash
cd frontend
npm install
npm run build
```

Only the shared fallback image (`app/web/fallback.png`) and the direct movie-page fallback (`app/web/movie.html`) are tracked in Git.
The compiled bundle (`app/web/index.html` and `app/web/spa-assets/`) is generated at build-time.
Re-run `npm run build` whenever frontend dependencies change or before packaging/deploying the app.
Because `app/web/` is also the build output directory, check `git status` after local builds and do not commit generated bundle files.

---

## Updates

```bash
docker pull ghcr.io/thedinz/kam:latest
docker stop kam && docker rm kam
# re-create with your docker run or docker compose up -d
```

> You can pin a release tag such as `ghcr.io/thedinz/kam:v4.5`, or use SHA tags if you prefer pinning a specific build (e.g., `ghcr.io/thedinz/kam:sha-xxxxxxxx`). On Unraid, use the **Update** action in the container UI.

---

## Troubleshooting

**Artwork isn’t appearing in Plex/Kometa**

* Plex may cache images. Try “Refresh Metadata” or give it time.
* Confirm the file exists and is correctly named in the expected asset folder.
* For **seasons**, verify the file names are `Season01.jpg`, `Season02.jpg`, `Season01_background.jpg`, etc. (no subfolders).

**Nothing changes after upload**

* Double-check your volume mapping: `-v <host-path>:/assets`.
* Ensure you’re pairing the right **library** with the right **directory** (see constraint).
* Verify filesystem **permissions** allow the container to write.

**Permission errors (EPERM/EACCES)**

* On Unraid, mapping under `/mnt/user/...` typically avoids permission headaches.
* Ensure your host user/group can read/write the assets directories.

**Fallback image shows**

* That item has no `poster.jpg` or `background.jpg` (or `SeasonNN.jpg` / `SeasonNN_background.jpg` for seasons).
* Upload the file, or confirm the item’s folder/filename matches exactly.

**Collections missing**

* Ensure KAM can reach the collections directory you configured—either the shared `/assets/Collections` folder or any override set under **Settings → Libraries**.

---

## FAQ

**Q: Can I use multiple asset roots at the same time?**
A: KAM expects one main container assets root for browsing, usually `/assets`. Each Plex library then maps to one directory under that root, and collections can use a shared folder or per-library/section overrides from **Settings → Libraries**.

**Q: Can I map the assets directory to any host path?**  
A: Yes. Bind-mount any host folder to the container’s internal assets path (examples use `/assets`).  
You could map `/mnt/user/kometa/assets` to `/assets` or map `/mystuff` to `/assets` — KAM doesn’t care.

**Q: What artwork types does KAM handle?**  
A: `poster.jpg` and `background.jpg` for movies, series, and collections; `SeasonNN.jpg` and `SeasonNN_background.jpg` for seasons (in the series folder).

**Q: Does KAM keep the old files?**  
A: No. It **replaces** any existing `poster.*`, `background.*`, `SeasonNN.*`, or `SeasonNN_background.*` for the selected item.

**Q: Which image formats can I upload?**  
A: Any common format; KAM converts to `.jpg` on save.

---

## Backup & restore

* Your artwork lives in the **host assets** directories you mapped (not inside the container).
* Back up those folders using your usual NAS/server backup tool.
* Container can be recreated at any time without losing artwork.
