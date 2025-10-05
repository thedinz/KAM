# KAM — Kometa Asset Manager

KAM is a small web app that makes Kometa/Plex artwork management painless. It lets you upload artwork for **movies, TV series, seasons, and collections** and will:

* **Import existing Plex assets** — movie posters/backgrounds, series posters/backgrounds, and **season posters** — into your mapped Kometa assets structure
* Convert uploads to **`.jpg`**
* **Replace** existing `poster.*`, `background.*`, or `SeasonNN.*` in the correct asset folder
* Keep everything in the **same structure Kometa expects**
* Provide a simple web UI with a **fallback** image to quickly spot missing artwork

---

## ⚠️ Important constraints

> **At the current moment the app does NOT allow you to user a myriad of different asset directories, for now you need to pair 1 library with 1 directory. Example Kids Movies with `/assets/Kids Movies`. Similarly all collections must reside in 1 `Collections` directory.**

What this means in practice:

* Pick **one** assets root for a given library and stick with it.
* If you have multiple libraries, each should have its **own** mapped directory or its own container.
* Put **all Collections** in a single `Collections` directory under one assets root.

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

  * `/mnt/user/kometa/assets` → `/assets`
* Custom mapping

  * `/mystuff` → `/assets`

KAM only cares about the **internal** path (e.g., `/assets`). You choose what host path it points to.

**Typical Kometa-style structure under the mapped root:**

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

---

## Requirements

* Docker (Unraid, Linux, macOS, or Windows)
* Read/write access to your Kometa **assets** directories (bind-mounted)
* Read access to your Kometa **config** directory if you want automatic Kometa mapping (bind-mounted)
* Optional: Reverse proxy (Caddy/Traefik/Nginx) if you want TLS or auth

---

## Quick Start (Docker)

### 1) Pull the image

```bash
docker pull ghcr.io/thedinz/kam:latest
```

### 2) Run (simple)

Expose KAM on **7171** (mapped to the container's port **8000**) and map your assets and Kometa config directory:

```bash
docker run -d \
  --name kam \
  -p 7171:8000 \
  -v /mnt/user/kometa/assets:/assets \
  -v /mnt/user/kometa/config:/config:ro \
  -e KOMETA_CONFIG_PATH=/config/config.yml \
  ghcr.io/thedinz/kam:latest
```

Open: `http://<your-host>:7171/`

> If your assets live elsewhere, just change the host side of `-v` (e.g., `-v /mystuff:/assets`).

Once running, open the **Settings** page in KAM and set the Kometa config path (for example `/config/config.yml`). If you prefer to seed it automatically, you can still set the optional `KOMETA_CONFIG_PATH` environment variable when starting the container.

### 3) Docker Compose

```yaml
services:
  kam:
    image: ghcr.io/thedinz/kam:latest
    container_name: kam
    ports:
      - "7171:8000"
    environment:
      KOMETA_CONFIG_PATH: /config/config.yml
    volumes:
      - /mnt/user/kometa/assets:/assets
      - /mnt/user/kometa/config:/config:ro
    restart: unless-stopped
```

Bring it up:

```bash
docker compose up -d
```
Edit the .env file to configure

Sample .env
```yaml
# Example environment file for KAM
# Copy to .env and edit values before running

# Plex connection
PLEX_URL=http://192.168.1.XXX:32400
PLEX_TOKEN=CHANGE_ME

# Map Plex libraries to asset folders inside container
# e.g. Movies:/assets/Movies,Kids Movies:/assets/Kids Movies
LIBRARIES=Movies:/assets/Movies,Kids Movies:/assets/Kids Movies

# Optional: Path to your Kometa config inside the container
KOMETA_CONFIG_PATH=/config/config.yml

# Runtime
PORT=8000

# Root path for collection posters
COLLECTIONS_ROOT=/assets/Collections
```

---

## Unraid setup

Kometa Asset Manager can now be found in the Unraid app store. Simply mount your Kometa asset directory and edit the other easy to understand template variables and GO!

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
(Still follow the “1 library ↔ 1 directory” rule inside that root and keep a single `Collections/`.)

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

Only the shared assets (`app/web/fallback.png` and `app/web/show-react.html`) are tracked in Git.
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

* Ensure there is a **single** `Collections/` directory under one assets root, and you’re pointing KAM at that root when managing collections.

---

## FAQ

**Q: Can I use multiple asset roots at the same time?**  
A: Not currently. **One library ↔ one directory**, and all collections live in **one** `Collections/` folder.

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
