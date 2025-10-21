# KAM — Kometa Asset Manager

KAM is a small web app that makes Kometa/Plex artwork management painless. It lets you upload artwork for **movies, TV series, seasons, and collections** and will:

* **Import existing Plex assets** — movie posters/backgrounds, series posters/backgrounds, and **season posters** — into your mapped Kometa assets structure
* Convert uploads to **`.jpg`**
* **Replace** existing `poster.*`, `background.*`, or `SeasonNN.*` in the correct asset folder
* Keep everything in the **same structure Kometa expects**
* Provide a simple web UI with a **fallback** image to quickly spot missing artwork
* Let you **exclude** specific movies, shows, or collections from KAM until you re-include them

---

## ⚠️ Important constraints

> **KAM maps each Plex library to a single assets directory inside the container (e.g., Kids Movies → `/assets/Kids Movies`).**
>
> **Collections default to a shared `/assets/Collections` directory, but you can override that per library or even per Plex collection section from the Settings UI.**

What this means in practice:

* Pick **one** assets root for a given library and stick with it.
* If you have multiple libraries, each should have its **own** mapped directory or its own container.
* Use the default shared `Collections` directory unless you opt into per-library/section overrides (see **Settings → Libraries**).

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

⚠️ REMEMBER, this is an addon for Kometa, not a stand alone application.

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
      Season02.jpg
      Season03.jpg

  /Collections
    /Batman Collection
      poster.jpg
      background.jpg
```

> ✅ **Season posters** are stored as flat files **in the series folder** (`Season01.jpg`, `Season02.jpg`, …).
> ❌ No `Season 01/` subfolders are used by KAM.

### Collection directory overrides

By default, every Plex library shares the same `/assets/Collections` directory. If you organize collections in multiple roots, open **Settings → Libraries** and edit a library’s **Collection directories** list. Behind the scenes, each library supports a `collectionSections` array so you can:

* Point a whole library at a different collections path.
* Target a specific Plex collection section and bind it to its own directory.

Overrides inherit the normal sanitization rules, and the folder finder offers suggestions for any directories KAM sees under `/assets`.

---

## Requirements

* Docker (Unraid, Linux, macOS, or Windows)
* Read/write access to your media **assets** directories (bind-mounted)
* Optional: Reverse proxy (Caddy/Traefik/Nginx) if you want TLS or auth

---

## Quick Start (Docker)

### 1) Pull the image

```bash
docker pull ghcr.io/thedinz/kam:latest
```

### 2) Run (simple)

Expose KAM on **7171** (mapped to the container's port **8000**) and map your assets
and configuration storage:

```bash
docker run -d \
  --name kam \
  -p 7171:8000 \
  -v /mnt/user/appdata/kam:/config \
  -v /mnt/user/appdata/kam-data:/data \
  -v /mnt/user/media/assets:/assets \
  ghcr.io/thedinz/kam:latest
```

Open: `http://<your-host>:7171/`

> If your assets live elsewhere, just change the host side of `-v` (e.g., `-v /mystuff:/assets`).
> Mount `/data` (or set `KAM_STATE_ROOT`, `KAM_CONFIG_ROOT`, or `KAM_FOLDER_OVERRIDES_PATH`) to keep folder assignments stored in `folder_overrides.json` between container rebuilds.

### 3) Docker Compose

```yaml
services:
  kam:
    image: ghcr.io/thedinz/kam:latest
    container_name: kam
    ports:
      - "7171:8000"
    volumes:
      - /mnt/user/appdata/kam:/config
      - /mnt/user/appdata/kam-data:/data
      - /mnt/user/media/assets:/assets
    restart: unless-stopped
```

Bring it up:

```bash
docker compose up -d
```
Persist `/data` (or point `KAM_STATE_ROOT`, `KAM_CONFIG_ROOT`, or `KAM_FOLDER_OVERRIDES_PATH` at a mounted host directory) so folder overrides survive container recreations.

Edit the .env file to configure runtime basics.

Sample .env
```yaml
# Example environment file for KAM
# Copy to .env and edit values before running

# Runtime
PORT=8000

# Root path for collection posters
COLLECTIONS_ROOT=/assets/Collections

# Plex server certificate handling (set to "false" for self-signed HTTPS)
PLEX_VERIFY_SSL=true

# Plex credentials and library mappings are now configured through the web UI.
```

Set `PLEX_VERIFY_SSL=false` if your Plex server uses a self-signed certificate and you need KAM to skip TLS verification when contacting Plex.

---

## Persistent configuration

KAM stores UI settings—including Plex credentials, library mappings, and exclusion
preferences—in `/config/settings.json` inside the container. Bind-mount `/config` to a
directory on the host (for example, `/mnt/user/appdata/kam`) to persist these values
across image updates, container recreation, and Unraid upgrades.

Per-item folder assignments live in `folder_overrides.json`. By default that file is written to `/data`, so mount `/data` (or set `KAM_STATE_ROOT`, `KAM_CONFIG_ROOT`, or `KAM_FOLDER_OVERRIDES_PATH` to point somewhere persisted) to keep your folder pairings intact.

> Upgrades from previous versions automatically reuse an existing
> `/data/settings.json` file if it is present, so your saved settings are retained while
> migrating to the new `/config` location.

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
/config`), plus a persistent state directory for folder overrides (e.g., `/mnt/user/appdata/kam-data -> /data`), edit the template variables, and GO!

---

## Usage overview

1. Open the web UI.
2. Choose the item (movie, series, collection, or season) you want to update.
3. If the item shows a red “Not Ready” badge, activate it to open the **folder finder** dialog, browse/search your Kometa assets, and assign the correct folder. Once paired the badge flips to ✔ Ready.
4. Upload artwork. KAM will:

   * Convert to `.jpg`
   * Remove any existing `poster.*`, `background.*`, or `SeasonNN.*` for that item
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
    Season02.jpg
    Season03.jpg
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

* KAM has **no built-in authentication**.

  * Run it on a trusted LAN, or
  * Put it behind a reverse proxy (Caddy/Traefik/Nginx) and add auth/TLS there.
* Bind to localhost and reverse-proxy if you don’t want it exposed directly.

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

Only the shared asset (`app/web/fallback.png`) is tracked in Git.
The compiled bundle (`app/web/index.html` and `app/web/spa-assets/`) is generated at build-time.
Re-run `npm run build` whenever frontend dependencies change or before packaging/deploying the app.

---

## Updates

```bash
docker pull ghcr.io/thedinz/kam:latest
docker stop kam && docker rm kam
# re-create with your docker run or docker compose up -d
```

> You can also use SHA tags if you prefer pinning a specific build (e.g., `ghcr.io/thedinz/kam:sha-xxxxxxxx`). On Unraid, use the **Update** action in the container UI.

---

## Troubleshooting

**Artwork isn’t appearing in Plex/Kometa**

* Plex may cache images. Try “Refresh Metadata” or give it time.
* Confirm the file exists and is correctly named in the expected asset folder.
* For **seasons**, verify the file names are `Season01.jpg`, `Season02.jpg`, etc. (no subfolders).

**Nothing changes after upload**

* Double-check your volume mapping: `-v <host-path>:/assets`.
* Ensure you’re pairing the right **library** with the right **directory** (see constraint).
* Verify filesystem **permissions** allow the container to write.

**Permission errors (EPERM/EACCES)**

* On Unraid, mapping under `/mnt/user/...` typically avoids permission headaches.
* Ensure your host user/group can read/write the assets directories.

**Fallback image shows**

* That item has no `poster.jpg` or `background.jpg` (or `SeasonNN.jpg` for seasons).
* Upload the file, or confirm the item’s folder/filename matches exactly.

**Collections missing**

* Ensure KAM can reach the collections directory you configured—either the shared `/assets/Collections` folder or any override set under **Settings → Libraries**.

---

## FAQ

**Q: Can I use multiple asset roots at the same time?**
A: Not currently. **One library ↔ one directory.** Collections default to a shared `/assets/Collections` folder, but you can assign per-library/section overrides from **Settings → Libraries** if you maintain multiple collections directories.

**Q: Can I map the assets directory to any host path?**  
A: Yes. Bind-mount any host folder to the container’s internal assets path (examples use `/assets`).  
You could map `/mnt/user/kometa/assets` to `/assets` or map `/mystuff` to `/assets` — KAM doesn’t care.

**Q: What artwork types does KAM handle?**  
A: `poster.jpg` and `background.jpg` for movies, series, and collections; `SeasonNN.jpg` for seasons (in the series folder).

**Q: Does KAM keep the old files?**  
A: No. It **replaces** any existing `poster.*`, `background.*`, or `SeasonNN.*` for the selected item.

**Q: Which image formats can I upload?**  
A: Any common format; KAM converts to `.jpg` on save.

---

## Backup & restore

* Your artwork lives in the **host assets** directories you mapped (not inside the container).
* Back up those folders using your usual NAS/server backup tool.
* Container can be recreated at any time without losing artwork.
