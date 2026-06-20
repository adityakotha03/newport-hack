"""Batch-generate image samples for curation.

Downloads each video ONCE, analyzes per brand (gemini-3.5-flash), then inserts the product
into each opportunity's keyframe with Nano Banana 2 (gemini-3.1-flash-image).
Outputs descriptive filenames into media/: sample_<tag>_<brand>_r<run>_<i>_{before,after}.png
"""
import shutil
import uuid

import config
from gemini_client import analyze_video
from video_pipeline import (_clip_duration, _extract_frame, _gemini_edit_image,
                            download_video)

JOBS = [
    ("gta", "https://www.youtube.com/watch?v=eOrb93UZfPU", [
        ("Coca-Cola", "the classic cola soft drink in its iconic bright red can", 1),
        ("Red Bull", "the energy drink in its slim silver and blue can", 2),
        ("Corona Extra", "the Mexican lager in a clear glass bottle, often with a lime wedge", 2),
    ]),
    ("mrbeast", "https://www.youtube.com/watch?v=JFtlf8RoPZY", [
        ("Gatorade", "the sports hydration drink in a colorful bottle", 1),
        ("YETI", "the premium cooler and insulated tumbler brand", 1),
        ("Red Bull", "the energy drink in its slim silver and blue can", 1),
    ]),
]


def run():
    for tag, url, brands in JOBS:
        print(f"\n=== {tag}: downloading ===", flush=True)
        src = download_video(url)
        dur = _clip_duration(src)
        print(f"  duration ~{dur:.0f}s", flush=True)
        try:
            for brand, desc, runs in brands:
                bsafe = brand.lower().replace(" ", "")
                print(f" analyze [{brand}]", flush=True)
                opps = analyze_video(url, brand, desc)
                opps = [o for o in opps if o.end_sec <= dur - 1][:3]
                print(f"  usable opportunities: {len(opps)}", flush=True)
                for r in range(1, runs + 1):
                    for i, o in enumerate(opps):
                        base = f"sample_{tag}_{bsafe}_r{r}_{i}"
                        frame = config.TMP_DIR / f"f_{uuid.uuid4().hex[:6]}.png"
                        try:
                            _extract_frame(src, frame, at=max(0.5, (o.start_sec + o.end_sec) / 2))
                        except Exception as e:
                            print(f"   [skip] {base} frame: {e}", flush=True)
                            continue
                        if not frame.exists():
                            print(f"   [skip] {base} no frame", flush=True)
                            continue
                        before = config.MEDIA_DIR / f"{base}_before.png"
                        after = config.MEDIA_DIR / f"{base}_after.png"
                        shutil.copy(frame, before)
                        try:
                            ok = _gemini_edit_image(frame, brand, desc, o, after)
                            print(f"   {'OK ' if ok else 'NOIMG'} {base} :: {o.product_to_insert}", flush=True)
                        except Exception as e:
                            print(f"   [fail] {base}: {str(e)[:90]}", flush=True)
                        finally:
                            frame.unlink(missing_ok=True)
        finally:
            src.unlink(missing_ok=True)
    print("\nDONE", flush=True)


if __name__ == "__main__":
    run()
