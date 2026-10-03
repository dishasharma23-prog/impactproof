# ImpactProof Field

**Offline semantic memory for NGO field workers, built on Qdrant Edge. Capture and search with no
signal; sync intelligently when it returns. Edge → cloud → edge.**

Code Cubicle 6.0 · **Problem Statement 03 (Qdrant Edge)**

-  **Demo video:** VIDEO_LINK_HERE
-  **Live HQ (the cloud side):** https://impactproof-web.onrender.com (free hosting: the first load can take up to a minute)
-  **Field app (the edge side):** [`field/`](field/README.md). It runs on the volunteer's device, so it is shown in the video
  and can be run locally in three commands (below).

## Why the field app is not a website

Field workers in villages, forests and flood zones spend most of the day without internet. A web app
would stop working exactly when they need it. So the field app runs **on the device**: every photo, note
and site fact is embedded by on-device models and stored in a **Qdrant Edge shard** on that device.
Search works in milliseconds with the network switched off (airplane mode in the video). When a
connection returns, the device syncs to **Qdrant Cloud** and to ImpactProof HQ.

## How it meets PS3

| PS3 goal | ImpactProof Field |
|---|---|
| Local, on-device vector memory | A Qdrant Edge `EdgeShard` per device with three named vectors: `text` (bge-small, 384), `clip` (CLIP ViT-B/32, 512) and `bm25` (sparse). Survives restarts. |
| Works offline, low latency | Models run on the device (fastembed, ONNX). No network needed for capture or search; searches take a few milliseconds. |
| Semantic retrieval | Hybrid search (meaning + keywords, reciprocal-rank fusion), meaning only, exact words, and **what photos show** (CLIP text-to-image). "clogged water outlet" finds "drain blocked with plastic bottles". |
| Sync with a central server | Points sync to a `field_memory` collection on Qdrant Cloud **with the same vectors, never re-embedded**. Other devices pull what is new; deletes travel as tombstones. |
| Intelligent sync policy | Personal data (phone numbers, emails, ID numbers) stays on the device; near-duplicate photos (CLIP ≥ 0.95) are not sent; facts go first, then notes, then photos; photo files wait for Wi-Fi on mobile data; a memory budget trims other devices' items first. |
| Conflict resolution | Site facts are versioned. If two volunteers change the same fact offline, the device that syncs second is asked: keep mine, keep theirs, or merge. Nothing is silently overwritten, and every decision is logged. |
| Edge-to-cloud AI workflow | Photos upload to HQ signed with the volunteer's device key; HQ verifies them (Cloudinary, Gemini, nine checks). The verdict and HQ's verified evidence **flow back down** into Qdrant Edge, so the next volunteer can search verified proof offline. |
| Real-world usefulness | Real volunteers register by phone number and sign in once with a single-use code; every photo is attributed ("Captured by Disha · +91 ••••• 73264"). Unknown or revoked devices are refused. |

## Edge → cloud → edge

1. **No signal.** A volunteer takes a photo and a note. The device embeds them on the spot and they are searchable instantly.
2. **Signal returns.** The sync policy decides what leaves the device; items sync to Qdrant Cloud and conflicts are caught.
3. **HQ verifies.** Photos reach ImpactProof HQ signed by the volunteer. Cloudinary stores them, Gemini and nine checks give a verdict.
4. **Back to the edge.** Verdicts and verified evidence flow back into every device's Qdrant Edge memory for offline search.
5. **Proof.** The NGO publishes a claim backed only by corroborated photos; donors scan a QR code to check it.

## Try the field app (about 5 minutes, no accounts needed)

```
python -m venv .venv-field
.venv-field\Scripts\activate            (macOS/Linux: source .venv-field/bin/activate)
pip install -r field/requirements.txt
python -m field.setup_models             (downloads the on-device models once, about 450 MB)
python -m field --device demo --port 8101
```

Open http://localhost:8101, add a note and a photo, then in **Sync** tick **Simulate no signal** (or turn on
airplane mode) and use **Search**. Syncing between devices, HQ uploads, real phones over a hotspot and the
conflict demo are described in [field/README.md](field/README.md).

## Architecture

```
Volunteer's phone ──(local hotspot, https)──▶ ImpactProof Field (on the edge device)
                                               ├── Qdrant Edge shard: text + clip + bm25
                                               ├── on-device models: bge-small, CLIP, BM25
                                               ├── sync policy: privacy, duplicates, priority, Wi-Fi, conflicts
                                               └── when online ──▶ Qdrant Cloud (field_memory, shared memory)
                                                               └──▶ ImpactProof HQ (FastAPI + Postgres + Next.js)
                                                                     ├── Cloudinary: storage, fingerprint, face blur
                                                                     ├── Gemini: what is really in the photo
                                                                     └── nine checks → verdict ──▶ back to the devices
```

Qdrant Edge has no build for phone processors yet and cannot run in a browser, so a laptop (or any small
computer) acts as the team's edge device and phones connect to it over a local hotspot as camera and
screen. A native phone app is the next step.

---

# ImpactProof HQ (the cloud side)

**Evidence you can trace. Impact you can trust.** HQ turns field photos into verified evidence and
verified evidence into claims donors can check for themselves.

## The problem

Donors increasingly doubt impact photos: pictures recycled from last year's drive, photos from a
different place, stock images, and now AI-generated images. NGOs have no simple way to prove
their evidence is genuine, and assembling a report by hand takes days.

## How it works

AI observes, rules decide, people resolve.

1. **Capture or upload.** Photos come in through the in-app camera (live GPS and server time,
   ghost overlay of the last photo at that site) or as files. The exact bytes are fingerprinted
   (SHA-256) before anything else happens.
2. **Store.** The untouched original goes to Cloudinary with perceptual hash and metadata
   extraction. Cloudinary's stored copy is compared against the fingerprint.
3. **Observe.** Gemini describes only what is visible: activity, rough counts, readable text,
   wet ground, signs of collage, screenshots or AI generation. Interpretive sentences are removed.
4. **Decide.** Nine explainable checks produce a verdict: Corroborated, Needs review,
   Suspicious or Unverifiable. Every check gives a one-sentence reason.
5. **Resolve.** Anything uncertain goes to a review queue. Decisions need a name and a reason and
   land in an append-only audit log.
6. **Claim.** Claims link to evidence. Only corroborated photos count as support. Each claim gets
   an impact brief with a QR code that opens a public verification page (faces blurred,
   locations rounded).

## The nine checks

| Check | Passes when | Fails or warns when | No data when |
|---|---|---|---|
| Capture method | Taken with the in-app camera with a good GPS fix | Token expired or reused, GPS off (warn) | Uploaded file |
| Location | Inside a project site's radius | Outside every site (fail) | No GPS in file |
| Capture date | Inside the project period | Outside it, or later than upload (fail) | No date in file |
| Reuse | No near-duplicate, or a repeat photo of the same view showing visible change | Near-copy of earlier evidence (fail); same view with no visible change (warn) | Hash failed |
| Content credentials (C2PA) | Camera capture or credentials without AI generation | Declares AI generation (fail), AI editing (warn), broken signature (fail) | None attached |
| Camera metadata | Complete | Saved by editing software (warn) | Stripped |
| Visual content | Shows the project's kind of work | Screenshot, stock, collage, visual signs of AI, off-topic (warn) | AI off |
| Visible text | Consistent with the project | A year outside the project period, or another organisation's name (warn) | No text |
| Weather | Matches Open-Meteo records for that place and hour | Wet ground with no recorded rain, etc. (warn) | No GPS or time |

The score is a weighted average over the checks that had data, so missing metadata lowers
coverage, never the score. Unknown is never treated as fake.

## Gallery: intelligent organisation

Every photo is sorted automatically, four ways: by work stage (before, during, after the work), by
activity (waste, planting, water, construction and more), by site and by day. Gemini proposes the
stage and activity; a person can correct them on the evidence page, and the correction is logged
and written to Cloudinary as structured metadata (`ip_stage`, `ip_category`) and tags.

## Sustainable Development Goals

Each project picks the UN SDGs it works towards. Gemini tags every photo with the goals it visibly
supports (limited to the project's goals), and the dashboard, impact brief and public page count
verified photos per goal, e.g. "38 corroborated photos supporting SDG 15, Life on land".

## Cloudinary usage

- **Structured Metadata**: ImpactProof creates its own fields in the account (verdict, trust score,
  project, site, capture date, SHA-256, SDGs) and fills them on every asset, so the Media Library can
  be searched and filtered by verdict. Falls back to tags and context if the plan lacks it.
- **Upload Widget** (signed): volunteers upload from a phone, the camera or a web link straight to
  Cloudinary. ImpactProof then fetches the stored original, checks it against Cloudinary's MD5 ETag
  and runs the same checks.
- Originals uploaded untouched with `phash` and `image_metadata`; public IDs name the evidence.
- ETag (MD5) compared with the fingerprint taken on receipt, shown as chain of custody.
- Verdicts and AI tags written back to each asset's context and tags, so the Media Library shows
  which evidence is trustworthy (`trust_corroborated`, `trust_suspicious`, …).
- Smart-cropped, auto-format thumbnails (`c_fill,g_auto,q_auto,f_auto`).
- Face-blurred copies (`e_blur_faces`) for public verification pages.
- Campaign images in three formats with caption and an evidence stamp, built as derived URLs.
  The original is never modified.

## HQ architecture

```
Browser ── Next.js 16 (frontend/) ──/api, /media──▶ FastAPI (backend/app)
                                                    ├── services/pipeline.py        intake, sealing, orchestration
                                                    ├── services/trust_engine.py    nine deterministic checks
                                                    ├── services/provenance_service C2PA + IPTC source type
                                                    ├── services/vision_service     Gemini, strict observation prompt
                                                    ├── services/weather_service    Open-Meteo history
                                                    ├── services/pairing.py         before/after by viewpoint
                                                    ├── services/claim_service.py   support status, site coverage
                                                    ├── services/cloudinary_service upload, write-back, derivatives
                                                    ├── services/qdrant_service     semantic search (Gemini embeddings)
                                                    └── Postgres (evidence, reviews, audit log)
```

## Running it (Windows)

You need Docker Desktop (for Postgres and Qdrant), Python 3.11+ and Node 20+.

**1. Start the databases** (from the project folder):

```
docker compose up -d
```

**2. Backend** (new terminal):

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend\.env` and add your Cloudinary and Gemini keys. Then:

```
python -m uvicorn app.main:app --reload
```

On first start the backend adds any new database columns automatically. Existing evidence is
kept and re-checked.

**3. Frontend** (another terminal):

```
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

**4. Set up the project.** Go to *Project*: set the name, organisation, what the project does,
and the start and end dates. Place sites on the map (or upload photos first and use the
suggested sites). Every change re-checks all evidence.

## Landing page video

The landing page plays a full-screen video. To use your own, upload it to Cloudinary and put its URL
(with `f_auto,q_auto` in it, so each device gets a small, fast version) in `frontend\.env.local`:

```
NEXT_PUBLIC_HERO_VIDEO=https://res.cloudinary.com/<cloud>/video/upload/f_auto,q_auto/<your-video>.mp4
NEXT_PUBLIC_STORY_VIDEO=https://res.cloudinary.com/<cloud>/video/upload/f_auto,q_auto/<your-explainer>.mp4
```

`NEXT_PUBLIC_STORY_VIDEO` is optional: when set, "Watch the story" plays it. Restart the frontend after changing it.

## Early access

The landing page has a form for NGOs and CSR teams to request a pilot. Requests appear on the
*Early access* page in the app, which gives you a real count for the pitch.

## Demo dataset

- Real photos with their original metadata (transfer by cable, Google Photos download or email
  attachment, not WhatsApp). iPhone: Settings > Camera > Formats > Most Compatible.
- Before/after pairs: photograph a littered spot, clean it, photograph it again from the same
  place. Use the in-app camera's ghost overlay for the second shot.
- Planted test cases, from three different photos of yours:
  `python -m scripts.make_test_cases photo1.jpg photo2.jpg photo3.jpg` writes a reused copy of
  photo1, a wrong-location copy of photo2 and a WhatsApp-style stripped copy of photo3 to
  `backend\test_cases`. Upload photo1 itself first; do not upload photo2 or photo3. Each case then
  shows exactly one problem (Suspicious: reused, Suspicious: wrong place, Unverifiable).
- One real ChatGPT image, downloaded directly (not screenshotted), to show the C2PA check.
- Say in the pitch that the planted cases are a controlled test set.
- Bulk load a folder: `python -m scripts.ingest_folder path\to\folder --project 1`.
- Start over before recording: `python -m scripts.reset_demo` (keeps projects and sites;
  `--all` removes them too). On Postgres it restarts numbering at EV-0001.

## Phone demo (camera and QR code)

Phones only allow the camera on https. Run a tunnel to the frontend, for example:

```
cloudflared tunnel --url http://localhost:3000
```

Open the `https://….trycloudflare.com` address on the phone. Set `PUBLIC_APP_URL` in
`backend\.env` to that address and restart the backend so QR codes point to it. The frontend
forwards `/api` to the backend, so one tunnel is enough.

## Tests

```
cd backend
python -m pytest -q tests
```

The end-to-end test uploads generated photos through the API (AI and weather simulated) and
checks every verdict path, reviewer decisions, claims, the public page and the QR code. It
includes an image carrying real C2PA credentials that declare AI generation.

## Honest limits

- Visual AI-generation detection is unreliable, so it only ever warns. The hard AI check relies
  on C2PA content credentials, which screenshots remove.
- The in-app camera's token proves freshness through the app, not hardware attestation.
- Perceptual hashing cannot tell a re-used photo from an unchanged scene shot from the same spot;
  those cases go to a person.

## Roadmap

- Native field app with hardware-backed signing (C2PA at capture). Offline capture with Qdrant Edge
  is built: see `field/`.
- Satellite vegetation change for plantation sites (Sentinel-2).
- Sun-angle and shadow consistency.
- Video evidence with transcription of beneficiary interviews.
