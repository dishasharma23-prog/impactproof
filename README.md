# ImpactProof

**Evidence you can trace. Impact you can trust.**

ImpactProof turns field photos from NGOs and sustainability teams into verified evidence, and
turns verified evidence into claims donors can check for themselves. Built for Code Cubicle 6.0,
Problem Statement 02 (Cloudinary).

**Field app (Problem Statement 03, Qdrant Edge):** see [field/README.md](field/README.md), an
offline-first companion with on-device semantic memory that syncs into ImpactProof.

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

## Architecture

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
