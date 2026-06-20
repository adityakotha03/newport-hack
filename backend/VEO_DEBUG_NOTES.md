# Why Veo (and gemini-omni-flash) don't work with the current key

## What we observed
- `.env` key starts with **`AQ.`** → this is a **Vertex AI express-mode API key**, bound to a
  Google-managed project (`277548333502`), not a project you own.
- `generate_content` works fine with it → **Gemini text** (`gemini-3.5-flash`) and the
  **nano-banana image editor** (`gemini-2.5-flash-image`) both succeed.
- `generate_videos` (Veo) fails for **every** model id (`veo-3.1-generate-preview`,
  `veo-3.0-generate-001`, `veo-3.0-fast-generate-001`, `veo-2.0-generate-001`) with the SAME
  error → so it is **not** a model-name / region issue:
  ```
  400 INVALID_ARGUMENT  reason: RESOURCE_PROJECT_INVALID
  method: PredictionService.PredictLongRunning
  ```
- `gemini-omni-flash` → `404 NOT_FOUND` (not available to this project).
- Same key via the Gemini Developer API (`vertexai=False`) → `403 PERMISSION_DENIED`
  (generativelanguage API not enabled on that managed project; also wrong key type).

## Root cause
Veo runs through **`PredictLongRunning`**, which requires the request to target a **real GCP
project resource that the caller owns**. Vertex **express-mode API keys don't provide that** —
they only support `generateContent`. Hence `RESOURCE_PROJECT_INVALID`. Image/text work because
they go through `generateContent`, not long-running predict.

## How to actually enable Veo (pick one)
1. **OAuth / ADC + your own project (recommended for Vertex):**
   ```
   gcloud auth application-default login
   gcloud services enable aiplatform.googleapis.com --project YOUR_PROJECT
   ```
   Then construct the client WITHOUT the api key:
   ```python
   genai.Client(vertexai=True, project="YOUR_PROJECT", location="us-central1")
   ```
   Make sure your project has Veo access enabled.
2. **AI Studio Gemini API key (format `AIza…`, paid tier):**
   ```python
   genai.Client(api_key="AIza…")   # vertexai=False
   c.models.generate_videos(model="veo-3.0-generate-001", prompt=...)
   ```
   The current `AQ.` key is NOT this type — get one from aistudio.google.com.

## In the app
- `ENABLE_VEO=1` / `ENABLE_OMNI=1` (env) turn those paths back on in the edit chain once you
  have working creds. Until then the effective edit path is **`gemini-2.5-flash-image`**
  (real AI product insertion on a keyframe → rendered to a clip), with the ffmpeg badge overlay
  as the final safety net.
- Re-run this probe anytime: `venv\Scripts\python.exe debug_veo.py`
