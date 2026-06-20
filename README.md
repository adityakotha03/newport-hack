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
- **AI:** Google `google-genai` on Vertex AI
  - Analysis: `gemini-3.5-flash` (reads the YouTube URL directly)
  - Edit: `gemini-2.5-flash-image` (nano-banana) — inserts the product into a keyframe, then
    renders it back to a clip
- **Media:** `yt-dlp` + bundled `ffmpeg` (via `imageio-ffmpeg`)

## Setup

`.env` (project root) needs:
```
GOOGLE_API_KEY=...   # Vertex AI key
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
See `backend/VEO_DEBUG_NOTES.md` for why a bare `AQ.` API key can't run Veo and how to fix it.

## Storage
The downloaded source video is deleted after each job (try/finally). Only the final
before/after clips are kept in `backend/media/`.
