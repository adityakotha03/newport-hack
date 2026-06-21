# Prism 🔺

**One video in, a spectrum of brand integrations out.**

Prism helps YouTube creators re-monetize existing content by seamlessly inserting a *new*
brand's product into a video they already made. Paste a YouTube URL, name the brand, and Prism:

1. **Analyzes** the video with Gemini to find the most natural moments to integrate the brand
   (timestamps + scene + integration idea).
2. **Downloads** the video and cuts ~10s clips at the chosen moments.
3. **Edits** each clip to insert the product (real AI image edit), producing **before/after**
   clips you can play and download.

## Stack
- **Frontend:** React + Vite (`frontend/`)
- **Backend:** FastAPI (`backend/`)
- **AI:**
  - Analysis: `gemini-3.5-flash` on Vertex AI (reads the YouTube URL directly)
  - **Image** edit: `gemini-3.1-flash-image` (Nano Banana 2) — inserts the product into a keyframe
  - **Video** edit: Replicate `kwaivgi/kling-v3-omni-video` (video-to-video, `base` mode)
- **Media:** `yt-dlp` + bundled `ffmpeg` (via `imageio-ffmpeg`)

## Output modes
The UI lets the user pick per run:
- **Image** (cheap/fast): before keyframe + AI-edited after image (Nano Banana 2).
- **Video** (pricier): short before clip + Replicate video-to-video after clip (~$0.75 at 720p/5s).

## Setup

`.env` (project root) needs:
```
GOOGLE_API_KEY=...        # Vertex AI key (analysis + Nano Banana 2 image edits)
REPLICATE_API_TOKEN=...   # only required for VIDEO output mode (Kling)
```

### Backend
```
cd backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

### Frontend
```
cd frontend
npm install
npm run dev      # http://localhost:5173
```

## API
- `POST /analyze` `{youtube_url, brand_name, brand_description}` → `{video_id, opportunities[]}`
- `POST /generate` `{youtube_url, brand_name, brand_description, opportunities[]}` → `{job_id, …}`
- `GET  /jobs/{job_id}` → job status + before/after clip URLs
- `GET  /media/...` → generated clips

## Edit fallback chain
`edit_clip()` degrades gracefully so there's always a result:
1. `gemini-omni-flash` (video→video) — *needs OAuth + real project; off by default*
2. Veo insert/generate — *needs OAuth + real project; off by default*
3. **`gemini-2.5-flash-image`** — real AI product insertion on a keyframe → clip *(default)*
4. ffmpeg branded-badge overlay — deterministic safety net

Enable the first two once you have proper credentials: set `ENABLE_OMNI=1` / `ENABLE_VEO=1`.
## Storage
The downloaded source video is deleted after each job (try/finally). Only the final
before/after clips are kept in `backend/media/`.

Open the presentation at `/` and the live workspace at `/studio`.
