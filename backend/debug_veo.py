"""Standalone Veo debugging — figure out why generate_videos fails with our key.

Run:  venv\Scripts\python.exe debug_veo.py
It probes several model IDs and request shapes and prints the precise error for each,
so we can tell whether it's auth (API key vs OAuth), model access, region, or params.
"""
import time
import traceback

from google import genai
from google.genai import types

import config


def make_client():
    print(f"API key present: {bool(config.GOOGLE_API_KEY)}")
    return genai.Client(vertexai=True, api_key=config.GOOGLE_API_KEY)


def short(e: Exception) -> str:
    return str(e).replace("\n", " ")[:280]


def try_text_to_video(client, model_id: str):
    """Simplest possible Veo call: text -> video, no input video, no extra config."""
    print(f"\n=== text->video :: {model_id} ===")
    try:
        op = client.models.generate_videos(
            model=model_id,
            prompt="a calm ocean wave at sunset, cinematic",
        )
        print("  submitted, polling…")
        for _ in range(3):
            if op.done:
                break
            time.sleep(5)
            op = client.operations.get(op)
        print("  done:", op.done)
        res = getattr(op, "result", None) or getattr(op, "response", None)
        vids = getattr(res, "generated_videos", None) if res else None
        print("  videos:", len(vids) if vids else 0)
    except Exception as e:  # noqa: BLE001
        print("  ERROR:", short(e))


def main():
    client = make_client()
    print("vertexai mode:", getattr(client, "_api_client", None) and
          getattr(client._api_client, "vertexai", "?"))

    # Candidate Veo model ids to probe
    for mid in [
        "veo-3.1-generate-preview",
        "veo-3.0-generate-001",
        "veo-3.0-fast-generate-001",
        "veo-2.0-generate-001",
    ]:
        try_text_to_video(client, mid)

    print("\n--- Interpretation hints ---")
    print("401 UNAUTHENTICATED / 'API keys are not supported' => Veo needs OAuth/ADC, not an API key.")
    print("404 NOT_FOUND => that model id isn't available to this project/region.")
    print("RESOURCE_PROJECT_INVALID => the request's project resource is invalid for this principal")
    print("   (typical when using a bare API key with long-running PredictLongRunning).")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
