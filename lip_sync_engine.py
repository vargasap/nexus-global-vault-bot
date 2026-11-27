"""
Compatibility wrappers forwarding legacy calls to sticker_engine.
Removes legacy 2D jaw/mouth warping that distorted faces.
"""

import os
import shutil

from sticker_engine import build_sticker_bundle


def generate_lipsync_sticker(image_path, audio_path, output_mp4, fps=25):
    """Generates a clean audio-synced MP4 sticker via sticker_engine. Returns (ok, face_detected)."""
    out_dir = os.path.dirname(os.path.abspath(output_mp4))
    base_name = os.path.splitext(os.path.basename(output_mp4))[0] + "_compat"
    bundle = build_sticker_bundle(
        image_path,
        audio_path,
        out_dir,
        base_name,
        effect="beat_pop",
        frame_style="cutout",
    )
    if bundle.get("mp4") and os.path.exists(bundle["mp4"]):
        shutil.move(bundle["mp4"], output_mp4)
        for k in ("webm", "webp_anim", "webp_static"):
            p = bundle.get(k)
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        return True, False
    return False, False


def generate_famous_sticker(image_path, audio_path, out_webm, out_mp4=None, cutout=True):
    """Compatibility wrapper returning the rich sticker_engine bundle formatted like the legacy dict."""
    out_dir = os.path.dirname(os.path.abspath(out_webm))
    base_name = os.path.splitext(os.path.basename(out_webm))[0]
    frame_style = "cutout" if cutout else "full"
    bundle = build_sticker_bundle(
        image_path,
        audio_path,
        out_dir,
        base_name,
        effect="beat_pop",
        frame_style=frame_style,
    )
    if bundle.get("webm") and bundle["webm"] != out_webm:
        shutil.move(bundle["webm"], out_webm)
    if out_mp4 and bundle.get("mp4") and bundle["mp4"] != out_mp4:
        shutil.move(bundle["mp4"], out_mp4)
    return {
        "ok": bool(bundle.get("ok")),
        "face": bool(bundle.get("used_ai_talk")),
        "cutout": bool(bundle.get("cutout_applied")),
        "start": 0.0,
        "webm": out_webm if os.path.exists(out_webm) else None,
        "mp4": out_mp4 if out_mp4 and os.path.exists(out_mp4) else bundle.get("mp4"),
        "mp4_ok": bool(out_mp4 and os.path.exists(out_mp4)),
        "webp_anim": bundle.get("webp_anim"),
        "webp_static": bundle.get("webp_static"),
    }
