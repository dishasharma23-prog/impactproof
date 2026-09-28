# ImpactProof Field

**Semantic memory that lives on the volunteer's device, works with no signal, and syncs sensibly when it can.**

Built for Code Cubicle 6.0, Problem Statement 03 (Qdrant Edge). Field workers in villages, forests
and flood zones spend most of the day without reliable internet. ImpactProof Field gives each
device its own vector memory (a Qdrant Edge shard) so they can capture photos, notes and site facts,
and search all of it by meaning, instantly and offline. When a connection appears, a sync policy
decides what goes to the shared Qdrant Server, what stays private, what waits for Wi-Fi, and what
to do when two people changed the same fact.

It is the field companion to ImpactProof (the Cloudinary submission in the parent folder): photos
taken in the field upload to ImpactProof HQ for verification, and HQ's verified evidence and site
list come back down for offline use.

## How it meets the problem statement

| PS3 goal | What ImpactProof Field does |
|---|---|
| Local, on-device vector memory | Each device holds a Qdrant Edge `EdgeShard` in its own folder with three vectors per item: `text` (bge-small, 384), `clip` (CLIP ViT-B/32, 512) and `bm25` (sparse, IDF computed on device). Survives restarts. |
| Works offline, low latency | Embedding models run on the device (fastembed, ONNX). Search needs no network; the UI shows "searched on this device with no network" and the time taken (about 1 to 5 ms). |
| Semantic retrieval | Four search modes: Everything (hybrid meaning + keywords fused with reciprocal-rank fusion), Meaning, Exact words, and What photos show (CLIP text-to-image, so "garbage bags" finds pictures with no caption match). |
| Synchronisation with a central server | Items sync to a `field_memory` collection on Qdrant Server with the same named vectors, so nothing is re-embedded. Other devices pull what is new since their last sync. Deletes travel as tombstones. |
| Intelligent sync policy | See the table below: privacy, near-duplicate suppression, priority order, Wi-Fi-only media, conflict detection, a memory budget. |
| Real-world usefulness | Offline field notes, before/after photos and counts for NGO projects; HQ's verified evidence available in the field. |

## Sync policy

| Situation | What happens | Why |
|---|---|---|
| Marked "keep on this device" | `local_only`, never sent | Volunteer's choice |
| Text contains a phone number, email or Aadhaar-like number | `local_only`, with the reason shown | Personal data stays on the device |
| Photo nearly identical (CLIP similarity ≥ 0.95) to one taken at the same place in the last 15 minutes | `skipped`, kept on device | Burst shots waste bandwidth |
| Everything else | `pending` until online, then `synced` | |
| Order when a connection appears | Facts, then notes, then photo details | The small, important things go first |
| On mobile data | Details and notes sync; photo files wait for Wi-Fi (switchable) | Data costs money in the field |
| Two devices changed the same fact offline | `conflict`: both values shown; keep mine, keep theirs, or enter a merged value. The choice is logged and synced. | Silent overwrites lose real data |
| Device memory full (default 500 items from elsewhere) | Least recently useful items from other devices and HQ are dropped first; your own items never are | Phones have limited storage |

Facts use a deterministic ID (UUID5 of the fact name), so "Library lawn: bags collected" is the same
record on every device. Each write carries a version and the version it was based on; a server copy
from another device that is newer than the base is a conflict.

## Architecture

```
Phone browser ── Field app (FastAPI, field/) ──────────────────────────────┐
                  ├── memory.py   Qdrant Edge shard: text + clip + bm25     │ offline
                  ├── embed.py    bge-small + CLIP on device (fastembed)    │
                  ├── policy.py   privacy, duplicates, priority             │
                  ├── exif.py     stamps time, GPS, device into each photo  ┘
                  └── sync.py  ── when online ──▶ Qdrant Server  (field_memory collection)
                                               └─▶ ImpactProof HQ (photo upload, sites, verified evidence)
```

## Running it (Windows)

You need Python 3.11+ and the Qdrant container from the main project (`docker compose up -d` in the
project folder starts it on port 6333). ImpactProof HQ (the backend) is optional.

**1. Install** (from the project folder, in a new terminal):

```
python -m venv .venv-field
.venv-field\Scripts\activate
pip install -r field\requirements.txt
```

**2. Download the on-device models once, while online** (about 450 MB):

```
python -m field.setup_models
```

After this the app needs no internet for search.

**3. Start two devices**, each in its own terminal (activate the venv in each):

```
python -m field --device alpha --name "Asha's phone" --port 8101 --hq http://127.0.0.1:8000 --project 1
```

```
python -m field --device beta --name "Ravi's phone" --port 8102 --hq http://127.0.0.1:8000 --project 1
```

Open http://localhost:8101 and http://localhost:8102 side by side. Leave out `--hq` if the ImpactProof
backend isn't running. To open it on a real phone with the camera, run a tunnel to port 8101
(`cloudflared tunnel --url http://localhost:8101`) and open the https address.

Each device keeps its data in `field\data\<device>`. Delete that folder to start a device fresh.

## Real phones and real volunteers

The laptop running the field app is the team's **edge device** (Qdrant Edge lives there). Volunteers use
their own phones as camera and screen, connected to the laptop's Wi-Fi hotspot, so nothing needs the internet.

1. **Register the volunteer** in ImpactProof: *Volunteers* → name + phone number → a 6-digit pairing code.
2. **Start the device over https** (phones only allow camera and GPS on https):
   ```
   python -m field --device disha --name "Disha's phone" --port 8101 --https --hq https://impactproof-api.onrender.com --qdrant https://YOUR-CLUSTER.cloud.qdrant.io --qdrant-key YOUR_KEY
   ```
   It prints the address to open, e.g. `https://192.168.137.1:8101`.
3. **On the phone:** join the laptop's hotspot (Windows: Settings → Network → Mobile hotspot), open that address,
   accept the certificate warning once, allow camera and location.
4. **Sign in:** *Sync* tab → *Volunteer* → phone number + code (needs internet once). From then on every photo
   uploads with the device's key and appears in ImpactProof as *Captured by Disha · +91 ••••• 43210*.
   Unpaired devices keep their photos; wrong or revoked keys are refused by HQ; removing a volunteer revokes the device.

Run one device per volunteer (ports 8101, 8102, …); each is its own Qdrant Edge shard and they sync through Qdrant Server.

## Demo script (3 minutes)

1. **Sync** tab on both devices: tick *Simulate no signal*. The pill turns red.
2. On Asha's phone, save a note ("Drain behind the library is blocked with plastic bottles"), a note
   with a phone number, two photos, then the same photo again. Show the reasons: the phone-number note
   stays on the device, the repeat photo is not sent.
3. **Search** with no signal: "where was the blocked drain". Point at "searched on this device with no
   network" and the milliseconds. Switch to *What photos show* and search "plastic bottles".
4. Set the same fact on both phones with different values ("Library lawn: bags collected" = 14 and 15).
5. Turn Ravi's signal back on, then Asha's with *Mobile data*. Notes and facts sync; photos wait for
   Wi-Fi. Asha's phone reports a conflict. Resolve it with a merged value and show it arrive on Ravi's.
6. Switch Asha to Wi-Fi: the photos upload to ImpactProof HQ and come back with HQ's verdict (Corroborated for genuine, in-site photos).
7. On Ravi's phone, go offline again and search for Asha's note: it is now in his memory too.
8. **Activity** tab: the full history, including the conflict and how it was resolved.

## Tests

```
python -m pytest -q field\tests
```

Two simulated devices share an in-memory Qdrant Server and a mock HQ. The tests cover offline capture
and search, the privacy and duplicate rules, device-to-device sync, Wi-Fi-only photos, the EXIF stamp,
deletes, conflicting facts and their resolution, the memory budget and persistence across restarts.

## Honest limits

- Qdrant Edge has no build for phone processors and can't run in a browser, so the edge device is a laptop
  (or any small computer) that phones connect to over a local hotspot. A native phone app is the next step.
- Pairing uses a code shown in ImpactProof rather than an SMS (that would need a paid SMS provider).

- The field app is a mobile web app served from the device. A production build would package it
  natively (the same Python core runs on Android via Chaquopy, or the Rust Qdrant Edge crate directly).
- If the models haven't been downloaded, it falls back to a simple word-hashing embedder so it still
  works, with weaker meaning search. The Sync tab says which is in use.
- The size shown on Windows includes space Qdrant reserves in advance, so it overstates real use.
- Conflicts are detected for facts (shared, changeable values). Notes and photos are append-only, so
  they never conflict.
