"""
Nexus Sticker Studio Engine v3
------------------------------
Motor profesional, limpio y 100% compatible con la nube para crear stickers
estilo WhatsApp (Sticker.ly) + Telegram + Video con Audio Unido:
  - Recorte universal de fondo (u2netp ONNX 4.3 MB + selfie_segmenter para personas)
  - 4 estilos de marco: cutout (borde blanco die-cut + sombra), full, circle, meme
  - Texto meme blanco con borde negro grueso (Impact / Arial Bold / DejaVu)
  - 5 animaciones limpias sincronizadas al audio (sin deformar rostros) + Lip-Sync IA Neural en la nube
  - Exportación triple en una sola pasada:
      1) Telegram Animated Sticker (.webm VP9 yuva420p <= 2.9s, <= 255 KB)
      2) WhatsApp Animated/Static Sticker (.webp yuva420p <= 495 KB / <= 98 KB)
      3) Sticker + Audio Unido (.mp4 H.264 + AAC 192k)
"""

import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import cv2
import imageio_ffmpeg
import mediapipe as mp
import numpy as np
import onnxruntime as ort
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

U2NETP_PATH = os.path.join(MODELS_DIR, "u2netp.onnx")
U2NETP_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"

SEG_PATH = os.path.join(MODELS_DIR, "selfie_segmenter.tflite")
SEG_URL = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"

FACE_PATH = os.path.join(MODELS_DIR, "face_landmarker.task")
FACE_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

STICKER_FPS = 30
STICKER_MAX_FRAMES = 87  # 2.9 s (límite oficial Telegram video sticker <= 3.0 s)

_U2NETP_SESS = None
_SEG_MODEL = None
_FACE_MODEL = None


def _get_ffmpeg():
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _ensure_model(path, url):
    if not os.path.exists(path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            urllib.request.urlretrieve(url, path)
        except Exception as e:
            print(f"[StickerEngine] Error descargando modelo {os.path.basename(path)}: {e}")
    return os.path.exists(path)


def _get_u2netp():
    global _U2NETP_SESS
    if _U2NETP_SESS is None and _ensure_model(U2NETP_PATH, U2NETP_URL):
        _U2NETP_SESS = ort.InferenceSession(U2NETP_PATH, providers=["CPUExecutionProvider"])
    return _U2NETP_SESS


def _get_segmenter():
    global _SEG_MODEL
    if _SEG_MODEL is None and _ensure_model(SEG_PATH, SEG_URL):
        opts = mp_vision.ImageSegmenterOptions(
            base_options=mp_python.BaseOptions(model_asset_path=SEG_PATH),
            output_confidence_masks=True,
            output_category_mask=False,
        )
        _SEG_MODEL = mp_vision.ImageSegmenter.create_from_options(opts)
    return _SEG_MODEL


def _get_face_landmarker():
    global _FACE_MODEL
    if _FACE_MODEL is None and _ensure_model(FACE_PATH, FACE_URL):
        opts = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=FACE_PATH),
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=4,
            min_face_detection_confidence=0.22,
            min_face_presence_confidence=0.22,
        )
        _FACE_MODEL = mp_vision.FaceLandmarker.create_from_options(opts)
    return _FACE_MODEL


def _load_source_image(image_path):
    """Carga imagen BGR + info si ya trae transparencia real (recortada) o solo bordes letterbox."""
    raw = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        return None, False

    if raw.ndim == 2:
        bgra = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGRA)
        return bgra, False
    if raw.shape[2] == 3:
        return cv2.cvtColor(raw, cv2.COLOR_BGR2BGRA), False

    alpha = raw[..., 3]
    transparent_pct = float((alpha < 245).mean())
    if transparent_pct < 0.02:
        raw = raw.copy()
        raw[..., 3] = 255
        return raw, False

    ys, xs = np.where(alpha >= 128)
    if len(ys) == 0:
        return raw, False
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    inside_fill = float((alpha[y0:y1, x0:x1] >= 128).mean())

    # Si el canal alfa solo son bandas/márgenes rectangulares (letterbox), recortar y tratar como foto normal
    if inside_fill > 0.95:
        cropped = raw[y0:y1, x0:x1].copy()
        cropped[..., 3] = 255
        return cropped, False

    return raw, True


def detect_primary_face_box(bgr):
    """
    Detecta el rostro principal con escaneo multiescala (sirve tanto para selfies como planos amplios).
    Retorna (x0, y0, x1, y1) en coordenadas de `bgr`, o None si no hay rostro humano.
    """
    landmarker = _get_face_landmarker()
    if landmarker is None:
        return None
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    regions = [
        (0.0, 0.0, 1.0, 1.0),
        (0.18, 0.10, 0.82, 0.80),
        (0.18, 0.30, 0.82, 0.98),
        (0.0, 0.10, 0.60, 0.80),
        (0.40, 0.10, 1.0, 0.80),
    ]
    for (rx0, ry0, rx1, ry1) in regions:
        x0, y0 = int(rx0 * w), int(ry0 * h)
        x1, y1 = int(rx1 * w), int(ry1 * h)
        sub = rgb[y0:y1, x0:x1]
        if sub.size == 0:
            continue
        pw, ph = sub.shape[1], sub.shape[0]
        if max(pw, ph) != 512:
            patch = cv2.resize(sub, (512, 512), interpolation=cv2.INTER_CUBIC if max(pw, ph) < 512 else cv2.INTER_AREA)
        else:
            patch = sub
        res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=patch))
        if res.face_landmarks:
            best_box = None
            best_score = -1.0
            cx_img, cy_img = w * 0.5, h * 0.5
            for lm_list in res.face_landmarks:
                pts = np.array([[x0 + lm.x * pw, y0 + lm.y * ph] for lm in lm_list], dtype=np.float32)
                bx0, by0 = pts.min(axis=0)
                bx1, by1 = pts.max(axis=0)
                bw, bh = float(bx1 - bx0), float(by1 - by0)
                if bw < 12 or bh < 12:
                    continue
                fcx, fcy = 0.5 * (bx0 + bx1), 0.5 * (by0 + by1)
                dist_penalty = 1.0 / (1.0 + np.hypot(fcx - cx_img, fcy - cy_img) / max(w, h))
                score = bw * bh * dist_penalty
                if score > best_score:
                    best_score = score
                    best_box = (float(bx0), float(by0), float(bx1), float(by1))
            if best_box is not None:
                return best_box
    return None


def _run_u2netp_mask(bgr):
    """Ejecuta u2netp.onnx sobre `bgr` y devuelve máscara float32 [0..1] del tamaño exacto."""
    sess = _get_u2netp()
    if sess is None:
        return None
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = cv2.resize(rgb, (320, 320), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    im = (im - mean) / std
    blob = np.transpose(im, (2, 0, 1))[None, ...]
    inp_name = sess.get_inputs()[0].name
    out = sess.run(None, {inp_name: blob})[0][0, 0]
    mi, ma = float(out.min()), float(out.max())
    if ma - mi > 1e-6:
        out = (out - mi) / (ma - mi)
    return cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)


def _run_selfie_mask(bgr):
    """Ejecuta MediaPipe selfie_segmenter sobre `bgr` y devuelve máscara float32 [0..1]."""
    seg = _get_segmenter()
    if seg is None:
        return None
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    res = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not res.confidence_masks:
        return None
    m = res.confidence_masks[-1].numpy_view().astype(np.float32)
    if m.ndim == 3:
        m = m[..., 0]
    return cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)


def _floodfill_solid_bg_mask(bgr):
    """
    Si al menos 3 esquinas muestran un fondo sólido uniforme parecido,
    aplica flood-fill SOLO desde los bordes exteriores para quitar el fondo
    conservando el 100% de la ilustración, texto o zonas blancas interiores.
    """
    h, w = bgr.shape[:2]
    if h < 20 or w < 20:
        return None
    ps = max(6, min(10, min(h, w) // 16))
    patches = [
        ("tl", bgr[:ps, :ps], (0, 0)),
        ("tr", bgr[:ps, -ps:], (w - 1, 0)),
        ("bl", bgr[-ps:, :ps], (0, h - 1)),
        ("br", bgr[-ps:, -ps:], (w - 1, h - 1)),
    ]
    uniform = []
    for name, p, seed in patches:
        pf = p.astype(np.float32)
        std_val = float(pf.std(axis=(0, 1)).max())
        if std_val < 14.0:
            uniform.append((pf.mean(axis=(0, 1)), seed))
    if len(uniform) < 3:
        return None

    med_col = np.median(np.array([c for c, _ in uniform]), axis=0)
    close_seeds = [seed for col, seed in uniform if float(np.linalg.norm(col - med_col)) < 22.0]
    if len(close_seeds) < 3:
        return None

    smooth = cv2.GaussianBlur(bgr, (3, 3), 0)
    ff_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY
    lo_up = (20, 20, 20)

    # Añadir puntos medios de borde que coincidan con el color de fondo para limpiar zonas aisladas en los bordes
    edge_candidates = list(close_seeds) + [
        (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)
    ]
    for sx, sy in edge_candidates:
        if float(np.linalg.norm(smooth[sy, sx].astype(np.float32) - med_col)) < 22.0:
            if ff_mask[sy + 1, sx + 1] == 0:
                cv2.floodFill(smooth, ff_mask, (sx, sy), 255, loDiff=lo_up, upDiff=lo_up, flags=flags)

    fg = (ff_mask[1:-1, 1:-1] == 0).astype(np.float32)
    fg = cv2.GaussianBlur(fg, (3, 3), 0)
    fg_pct = float((fg > 0.5).mean())
    if 0.12 <= fg_pct <= 0.94:
        return fg
    return None


def _clean_mask(mask, keep_point=None, single_component=False):
    """
    Limpia ruido de máscara.
      - single_component=True (personas reales): aísla al sujeto principal.
      - single_component=False (dibujos, mascotas, objetos): conserva todos los componentes
        significativos (>= 2% del mayor o >= 0.5% de la imagen) para no mutilar partes.
    """
    binm = (mask > 0.45).astype(np.uint8)
    k_morph = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binm = cv2.morphologyEx(binm, cv2.MORPH_OPEN, k_morph)
    binm = cv2.morphologyEx(binm, cv2.MORPH_CLOSE, k_morph)

    num_labels, labels = cv2.connectedComponents(binm)
    if num_labels > 2:
        h, w = binm.shape
        areas = [int((labels == idx).sum()) for idx in range(1, num_labels)]
        if single_component:
            if keep_point is not None:
                kx = int(np.clip(keep_point[0], 0, w - 1))
                ky = int(np.clip(keep_point[1], 0, h - 1))
                lab = int(labels[ky, kx])
            else:
                lab = 0
            if lab == 0 and areas:
                lab = 1 + int(np.argmax(areas))
            if lab > 0:
                keep = (labels == lab).astype(np.float32)
                dil = cv2.dilate(keep, np.ones((15, 15), np.uint8))
                mask = mask * dil
        elif areas:
            max_area = max(areas)
            img_thresh = (h * w) * 0.005
            rel_thresh = max_area * 0.02
            keep = np.zeros((h, w), dtype=np.float32)
            for idx, area in enumerate(areas, start=1):
                if area >= rel_thresh or area >= img_thresh:
                    keep[labels == idx] = 1.0
            if keep.max() > 0:
                dil = cv2.dilate(keep, np.ones((7, 7), np.uint8))
                mask = mask * dil

    soft = np.clip((mask - 0.30) / 0.42, 0.0, 1.0)
    soft = cv2.GaussianBlur(soft, (5, 5), 0)
    return soft


def remove_background_universal(bgr, face_box=None):
    """
    Recorte universal de fondo estilo Sticker.ly:
      - Con rostro humano: combina selfie_segmenter + u2netp en componente único (persona).
      - Sin rostro (dibujos, mascotas, objetos): primero prueba flood-fill de fondo sólido uniforme
        para no cortar detalles interiores; si el fondo es complejo usa u2netp conservando partes.
    Retorna máscara float32 [0..1] o None si conviene mantener tarjeta completa.
    """
    h, w = bgr.shape[:2]
    mask = None
    keep_pt = None

    if face_box is not None:
        bx0, by0, bx1, by1 = face_box
        keep_pt = (0.5 * (bx0 + bx1), min(h - 1.0, by1 + (by1 - by0) * 0.75))
        human_m = _run_selfie_mask(bgr)
        if human_m is not None:
            hm_clean = _clean_mask(human_m, keep_point=keep_pt, single_component=True)
            pct = float((hm_clean > 0.5).mean())
            if 0.04 <= pct <= 0.92:
                u_m = _run_u2netp_mask(bgr)
                if u_m is not None:
                    roi = cv2.dilate((hm_clean > 0.25).astype(np.float32), np.ones((13, 13), np.uint8))
                    if float((u_m * roi > 0.4).mean()) >= pct * 0.55:
                        mask = np.clip(hm_clean * 0.65 + (u_m * roi) * 0.35, 0.0, 1.0)
                    else:
                        mask = hm_clean
                else:
                    mask = hm_clean

    if mask is None and face_box is None:
        solid_m = _floodfill_solid_bg_mask(bgr)
        if solid_m is not None:
            return solid_m

    if mask is None:
        u_m = _run_u2netp_mask(bgr)
        if u_m is not None:
            mask = _clean_mask(u_m, keep_point=keep_pt, single_component=(face_box is not None))

    if mask is None:
        return None
    fg_pct = float((mask > 0.5).mean())
    min_fg = 0.03 if face_box is not None else 0.14
    if fg_pct < min_fg or fg_pct > 0.96:
        return None
    return mask


def _crop_with_pad_bgra(bgra, x0, y0, x1, y1):
    h, w = bgra.shape[:2]
    pl, pt_, pr, pb = max(0, -x0), max(0, -y0), max(0, x1 - w), max(0, y1 - h)
    if pl or pt_ or pr or pb:
        bgra = cv2.copyMakeBorder(bgra, pt_, pb, pl, pr, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
        x0 += pl
        x1 += pl
        y0 += pt_
        y1 += pt_
    return bgra[y0:y1, x0:x1].copy()


def _sharpen_subtle(bgr):
    """Realce suave sin artefactos ni sobre-enfoque."""
    blur = cv2.GaussianBlur(bgr, (0, 0), 1.0)
    return cv2.addWeighted(bgr, 1.25, blur, -0.25, 0)


def _rounded_rect_mask(h, w, radius=36):
    mask = np.zeros((h, w), dtype=np.uint8)
    r = min(radius, h // 4, w // 4)
    cv2.rectangle(mask, (r, 0), (w - r, h), 255, -1)
    cv2.rectangle(mask, (0, r), (w, h - r), 255, -1)
    for cx, cy in [(r, r), (w - r, r), (r, h - r), (w - r, h - r)]:
        cv2.circle(mask, (cx, cy), r, 255, -1)
    return mask


def add_sticker_outline(bgra, thickness=10, add_shadow=True):
    """Añade borde blanco die-cut grueso y sombra sutil alrededor del sticker RGBA."""
    if thickness <= 0:
        return bgra
    a = bgra[..., 3]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * thickness + 1, 2 * thickness + 1))
    dil = cv2.dilate(a, k)
    dil = cv2.GaussianBlur(dil, (3, 3), 0)

    af = a.astype(np.float32)[..., None] / 255.0
    rgb = bgra[..., :3].astype(np.float32) * af + 255.0 * (1.0 - af)
    out_a = dil.astype(np.float32) / 255.0

    if add_shadow:
        shadow = cv2.GaussianBlur(dil, (0, 0), 5).astype(np.float32) / 255.0 * 0.30
        shadow = np.roll(shadow, 4, axis=0)
        shadow[:4, :] = 0.0
        out_a = np.maximum(out_a, shadow)
        shadow_only = np.clip(shadow - dil.astype(np.float32) / 255.0, 0.0, 1.0)[..., None]
        rgb = rgb * (1.0 - shadow_only)

    out = np.zeros_like(bgra)
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(out_a * 255.0, 0, 255).astype(np.uint8)
    return out


def prepare_sticker_subject(image_path, frame_style="cutout", outline=True):
    """
    Prepara un lienzo base 512x512 RGBA nítido según el estilo elegido:
      - cutout: recorte de fondo (u2netp / selfie_segmenter) + borde blanco die-cut
      - full: foto completa centrada con esquinas redondeadas y borde blanco
      - circle: recorte circular con aro blanco
      - meme: lienzo cuadrado 512x512 con fondo blanco clásico
    Regla crítica: nunca amplía > 1.65x fotos pequeñas para mantener nitidez natural.
    Retorna (canvas_512_bgra, metadata_dict).
    """
    src, already_cutout = _load_source_image(image_path)
    meta = {"ok": False, "cutout_applied": False, "face_box": None, "frame_style": frame_style}
    if src is None:
        return None, meta

    H, W = src.shape[:2]
    bgr = src[..., :3]
    face_box = detect_primary_face_box(bgr)
    meta["face_box"] = face_box

    canvas = np.zeros((512, 512, 4), dtype=np.uint8)

    if frame_style == "cutout":
        if not already_cutout:
            # Si hay rostro en un plano abierto, recortar alrededor de la persona manteniendo resolución (evitar bordes de puerta)
            if face_box is not None:
                bx0, by0, bx1, by1 = face_box
                fw, fh = bx1 - bx0, by1 - by0
                if max(W, H) > max(fw, fh) * 2.8:
                    crop_side = int(round(max(fw, fh) * 3.8))
                    cx = int(round(0.5 * (bx0 + bx1)))
                    cy = int(round(by0 + fh * 1.15))
                    sx0 = max(0, cx - crop_side // 2)
                    sy0 = max(0, cy - crop_side // 2)
                    sx1 = min(W, sx0 + crop_side)
                    sy1 = min(H, sy0 + crop_side)
                    if sx1 - sx0 >= 80 and sy1 - sy0 >= 80:
                        src = src[sy0:sy1, sx0:sx1].copy()
                        bgr = src[..., :3]
                        face_box = (bx0 - sx0, by0 - sy0, bx1 - sx0, by1 - sy0)
                        H, W = src.shape[:2]

            fg_mask = remove_background_universal(bgr, face_box=face_box)
            if fg_mask is not None:
                src = src.copy()
                src[..., 3] = np.clip(fg_mask * 255.0, 0, 255).astype(np.uint8)
                meta["cutout_applied"] = True
        else:
            meta["cutout_applied"] = True

        # Recortar exactamente al bounding box del sujeto recortado para aprovechar el lienzo
        ys, xs = np.where(src[..., 3] >= 64)
        if len(ys) > 0:
            x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
            subj = src[y0:y1, x0:x1].copy()
        else:
            subj = src.copy()

        sh, sw = subj.shape[:2]
        # Margen interior de 432 px para dejar espacio cómodo al borde blanco die-cut + movimiento sin recortes
        max_dim = 432.0
        scale = min(max_dim / max(sw, 1), max_dim / max(sh, 1))
        # Tope 2.05x para llenar bien el lienzo manteniendo el rostro nítido
        if scale > 2.05:
            scale = 2.05

        nw, nh = max(16, int(round(sw * scale))), max(16, int(round(sh * scale)))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
        resized_bgr = cv2.resize(subj[..., :3], (nw, nh), interpolation=interp)
        resized_bgr = _sharpen_subtle(resized_bgr)
        resized_a = cv2.resize(subj[..., 3], (nw, nh), interpolation=cv2.INTER_LINEAR)

        ox = (512 - nw) // 2
        oy = (512 - nh) // 2
        canvas[oy:oy + nh, ox:ox + nw, :3] = resized_bgr
        canvas[oy:oy + nh, ox:ox + nw, 3] = resized_a

        if not meta["cutout_applied"]:
            # Si el recorte falló, aplicar bordes redondeados limpios al sujeto encuadrado
            rr = _rounded_rect_mask(nh, nw, radius=32)
            canvas[oy:oy + nh, ox:ox + nw, 3] = np.minimum(canvas[oy:oy + nh, ox:ox + nw, 3], rr)

        if outline:
            canvas = add_sticker_outline(canvas, thickness=10, add_shadow=True)

    elif frame_style == "circle":
        # Encuadre centrado en cara si existe
        if face_box is not None:
            bx0, by0, bx1, by1 = face_box
            side = int(round(max(bx1 - bx0, by1 - by0) * 2.5))
            cx, cy = int(round(0.5 * (bx0 + bx1))), int(round(0.5 * (by0 + by1) + (by1 - by0) * 0.25))
            crop = _crop_with_pad_bgra(src, cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)
        else:
            side = min(H, W)
            cx, cy = W // 2, H // 2
            crop = src[cy - side // 2:cy + side // 2, cx - side // 2:cx + side // 2].copy()

        d = 444
        interp = cv2.INTER_AREA if max(crop.shape[:2]) > d else cv2.INTER_LANCZOS4
        bgr_c = _sharpen_subtle(cv2.resize(crop[..., :3], (d, d), interpolation=interp))
        circ_mask = np.zeros((d, d), dtype=np.uint8)
        cv2.circle(circ_mask, (d // 2, d // 2), d // 2 - 2, 255, -1)
        off = (512 - d) // 2
        canvas[off:off + d, off:off + d, :3] = bgr_c
        canvas[off:off + d, off:off + d, 3] = circ_mask
        if outline:
            canvas = add_sticker_outline(canvas, thickness=10, add_shadow=True)

    elif frame_style == "meme":
        # Fondo blanco completo 512x512 + imagen centrada (ideal para memes con texto arriba/abajo)
        canvas[:, :, :3] = 255
        canvas[:, :, 3] = 255
        scale = min(480.0 / W, 480.0 / H)
        if scale > 1.65:
            scale = 1.65
        nw, nh = max(16, int(round(W * scale))), max(16, int(round(H * scale)))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
        bgr_c = _sharpen_subtle(cv2.resize(bgr, (nw, nh), interpolation=interp))
        ox, oy = (512 - nw) // 2, (512 - nh) // 2
        canvas[oy:oy + nh, ox:ox + nw, :3] = bgr_c

    else:
        # "full": foto completa con esquinas redondeadas + borde blanco sobre fondo transparente
        scale = min(444.0 / W, 444.0 / H)
        if scale > 1.65:
            scale = 1.65
        nw, nh = max(16, int(round(W * scale))), max(16, int(round(H * scale)))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
        bgr_c = _sharpen_subtle(cv2.resize(bgr, (nw, nh), interpolation=interp))
        rr = _rounded_rect_mask(nh, nw, radius=34)
        ox, oy = (512 - nw) // 2, (512 - nh) // 2
        canvas[oy:oy + nh, ox:ox + nw, :3] = bgr_c
        canvas[oy:oy + nh, ox:ox + nw, 3] = rr
        if outline:
            canvas = add_sticker_outline(canvas, thickness=8, add_shadow=True)

    meta["ok"] = True
    return canvas, meta


def _load_meme_font(size):
    candidates = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/seguisb.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(draw, text, font, max_width):
    words = text.strip().split()
    if not words:
        return []
    lines = []
    curr = words[0]
    for w in words[1:]:
        test = curr + " " + w
        box = draw.textbbox((0, 0), test, font=font)
        if (box[2] - box[0]) <= max_width:
            curr = test
        else:
            lines.append(curr)
            curr = w
    lines.append(curr)
    return lines[:2]


def parse_caption_text(caption):
    """Convierte 'ARRIBA | ABAJO' o 'TEXTO' en (top_text, bottom_text)."""
    clean = re.sub(r"/(sticker|stiker)\b", "", str(caption or ""), flags=re.IGNORECASE).strip()
    if not clean or clean.lower() in {"borrar", "ninguno", "none", "clear", "quitar"}:
        return "", ""
    if "|" in clean:
        parts = clean.split("|", 1)
        return parts[0].strip(), parts[1].strip()
    return "", clean


def draw_meme_text_rgba(bgra, top_text="", bottom_text="", text_color=(255, 255, 255, 255)):
    """Superpone texto estilo meme blanco con contorno negro grueso sobre lienzo 512x512 BGRA."""
    top_t = (top_text or "").strip().upper()
    bot_t = (bottom_text or "").strip().upper()
    if not top_t and not bot_t:
        return bgra

    pil_rgba = Image.fromarray(cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA), "RGBA")
    draw = ImageDraw.Draw(pil_rgba)

    def render_zone(txt, is_top):
        if not txt:
            return
        font_size = 46
        lines = [txt]
        while font_size >= 24:
            font = _load_meme_font(font_size)
            lines = _wrap_text(draw, txt, font, 464)
            too_wide = any((draw.textbbox((0, 0), ln, font=font)[2] - draw.textbbox((0, 0), ln, font=font)[0]) > 472 for ln in lines)
            if not too_wide:
                break
            font_size -= 4
        font = _load_meme_font(font_size)
        stroke = max(3, int(round(font_size * 0.11)))
        line_h = int(round(font_size * 1.12))
        total_h = line_h * len(lines)
        start_y = 18 if is_top else max(18, 512 - 18 - total_h)

        for idx, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            tx = (512 - tw) // 2
            ty = start_y + idx * line_h
            draw.text(
                (tx, ty),
                line,
                font=font,
                fill=text_color,
                stroke_width=stroke,
                stroke_fill=(0, 0, 0, 255),
            )

    render_zone(top_t, is_top=True)
    render_zone(bot_t, is_top=False)
    return cv2.cvtColor(np.array(pil_rgba), cv2.COLOR_RGBA2BGRA)


def extract_audio_envelope(audio_path, fps=STICKER_FPS, max_duration=20.0):
    """
    Extrae energía RMS normalizada y picos de ataque (onset) frame a frame,
    además de detectar el segundo exacto donde comienza el sonido relevante.
    """
    ffmpeg_exe = _get_ffmpeg()
    sr = 16000
    cmd = [
        ffmpeg_exe, "-y", "-i", audio_path,
        "-t", str(max_duration),
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ac", "1", "-ar", str(sr),
        "pipe:1",
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
        raw = res.stdout
    except Exception:
        raw = b""

    if not raw or len(raw) < 320:
        n_def = int(fps * 2.5)
        return np.zeros(n_def, dtype=np.float32), np.zeros(n_def, dtype=np.float32), 0.0, 2.5

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    duration = len(samples) / float(sr)
    n_frames = max(1, int(round(duration * fps)))
    hop = max(1, int(sr / fps))

    energy = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        s = i * hop
        chunk = samples[s:min(len(samples), s + hop * 2)]
        if len(chunk) >= 4:
            energy[i] = float(np.sqrt(np.mean(chunk * chunk)))

    max_rms = float(np.max(energy))
    p95 = float(np.percentile(energy, 95)) if max_rms > 0.0005 else 1.0
    if p95 < 1e-4:
        p95 = max_rms + 1e-5
    energy = np.clip(energy / p95, 0.0, 1.15)
    energy = np.where(energy < 0.08, 0.0, (energy - 0.08) / 0.92)
    energy = np.clip(energy, 0.0, 1.0)

    smooth_e = np.zeros_like(energy)
    for i in range(n_frames):
        prev = smooth_e[i - 1] if i > 0 else 0.0
        alpha = 0.65 if energy[i] > prev else 0.38
        smooth_e[i] = prev + alpha * (energy[i] - prev)

    onset = np.clip(np.maximum(0.0, np.diff(smooth_e, prepend=0.0)) * 3.5 + smooth_e * 0.4, 0.0, 1.0)

    above = np.where(smooth_e > 0.14)[0]
    start_frame = max(0, int(above[0]) - 2) if len(above) > 0 else 0
    if n_frames - start_frame < int(fps * 1.2) and n_frames >= int(fps * 1.2):
        start_frame = max(0, n_frames - int(fps * 2.5))
    start_sec = start_frame / float(fps)

    return smooth_e, onset, start_sec, duration


def _prepare_clean_portrait_for_cloud(image_path, out_png):
    """Recorta el rostro/torso en 512x512 RGB limpio para que Wav2Lip/EchoMimic detecten la cara sin fallos."""
    src, _ = _load_source_image(image_path)
    if src is None:
        return False
    H, W = src.shape[:2]
    # Componer sobre blanco si trae transparencia
    a = src[..., 3:4].astype(np.float32) / 255.0
    bgr = (src[..., :3].astype(np.float32) * a + 255.0 * (1.0 - a)).astype(np.uint8)
    face_box = detect_primary_face_box(bgr)
    if face_box is None:
        return False

    bx0, by0, bx1, by1 = face_box
    fw, fh = bx1 - bx0, by1 - by0
    side = int(round(max(fw, fh) * 2.8))
    cx = int(round(0.5 * (bx0 + bx1)))
    cy = int(round(0.5 * (by0 + by1) + fh * 0.20))

    crop = _crop_with_pad_bgra(
        cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA),
        cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2
    )
    bgr_c = crop[..., :3]
    out_512 = cv2.resize(bgr_c, (512, 512), interpolation=cv2.INTER_LANCZOS4 if max(bgr_c.shape[:2]) < 512 else cv2.INTER_AREA)
    cv2.imwrite(out_png, out_512)
    return os.path.exists(out_png)


def run_cloud_ai_lipsync(image_path, audio_path, out_mp4, timeout_sec=35):
    """
    Habla IA Neural real en HuggingFace ZeroGPU vía gradio_client:
      1) Intenta pragnakalp/Wav2lip-ZeroGPU (/run_infrence)
      2) Respaldo fffiloni/EchoMimic (/generate_video)
    Si ambos están ocupados/caídos o no hay rostro humano, devuelve False sin lanzar excepciones.
    """
    try:
        from gradio_client import Client, handle_file
    except Exception as e:
        print(f"[AI LipSync] gradio_client no disponible: {e}")
        return False

    tmp_dir = tempfile.mkdtemp(prefix="nx_ailip_")
    try:
        portrait_png = os.path.join(tmp_dir, "portrait.png")
        if not _prepare_clean_portrait_for_cloud(image_path, portrait_png):
            return False

        trimmed_wav = os.path.join(tmp_dir, "audio_trim.wav")
        ffmpeg_exe = _get_ffmpeg()
        subprocess.run(
            [ffmpeg_exe, "-y", "-i", audio_path, "-t", "5.5", "-ac", "1", "-ar", "16000", trimmed_wav],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15
        )
        if not os.path.exists(trimmed_wav):
            return False

        def _extract_video_path(res):
            if isinstance(res, dict):
                return res.get("video") or res.get("path") or res.get("url")
            if isinstance(res, (list, tuple)) and res:
                return _extract_video_path(res[0])
            if isinstance(res, str) and os.path.exists(res):
                return res
            return None

        def _call_wav2lip():
            client = Client("pragnakalp/Wav2lip-ZeroGPU", verbose=False)
            res = client.predict(
                input_image=handle_file(portrait_png),
                input_audio=handle_file(trimmed_wav),
                api_name="/run_infrence",
            )
            return _extract_video_path(res)

        def _call_echomimic():
            client = Client("fffiloni/EchoMimic", verbose=False)
            res = client.predict(
                uploaded_img=handle_file(portrait_png),
                uploaded_audio=handle_file(trimmed_wav),
                width=512,
                height=512,
                length=120,
                seed=420,
                facemask_dilation_ratio=0.1,
                facecrop_dilation_ratio=0.5,
                context_frames=12,
                context_overlap=3,
                cfg=2.5,
                steps=18,
                sample_rate=16000,
                fps=24,
                device="cuda",
                api_name="/generate_video",
            )
            return _extract_video_path(res)

        for fn_name, fn in [("Wav2Lip-ZeroGPU", _call_wav2lip), ("EchoMimic", _call_echomimic)]:
            ex = ThreadPoolExecutor(max_workers=1)
            fut = ex.submit(fn)
            try:
                vid_path = fut.result(timeout=timeout_sec)
                if vid_path and os.path.exists(vid_path) and os.path.getsize(vid_path) > 2048:
                    shutil.copyfile(vid_path, out_mp4)
                    return True
            except FuturesTimeoutError:
                print(f"[AI LipSync] Timeout ({timeout_sec}s) en {fn_name}")
            except Exception as e:
                print(f"[AI LipSync] {fn_name} no disponible: {e}")
            finally:
                ex.shutdown(wait=False, cancel_futures=True)
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _animate_frame_clean(base_bgra, effect, energy, onset, t_sec, progress, border_mode):
    """
    Aplica animaciones limpias y profesionales sin deformar jamás el rostro:
      - beat_pop: entrada pop elástica + latido/inclinación solo cuando suena el audio
      - shake: sacudida cómica + micro-zoom solo en picos del audio
      - bounce: squash & stretch suave <= 8% al ritmo
      - zoom: zoom dramático sincronizado al clímax del audio
      - static: inmóvil
    """
    if effect == "static":
        return base_bgra.copy()

    # Envolvente de bucle perfecto para que el final empate suavemente con el inicio
    loop_env = 1.0
    if progress < 0.08:
        loop_env = progress / 0.08
    elif progress > 0.88:
        loop_env = max(0.0, (1.0 - progress) / 0.12)

    e = float(energy) * loop_env
    on = float(onset) * loop_env

    sx, sy, rot, tx, ty = 1.0, 1.0, 0.0, 0.0, 0.0
    if effect == "beat_pop":
        pop_in = 0.88 + 0.12 * min(1.0, progress / 0.10) if progress < 0.10 else 1.0
        scale = pop_in * (1.0 + 0.045 * abs(np.sin(t_sec * 4.5)) * loop_env + e * 0.055)
        sx = scale
        sy = scale
        rot = np.sin(t_sec * 4.5) * (3.2 + e * 3.5) * loop_env
        ty = -(abs(np.sin(t_sec * 4.5)) * 7.0 * loop_env + on * 9.0)
    elif effect == "shake":
        amp = (0.35 + e * 0.65 + on * 0.6) * loop_env
        sx = 1.0 + amp * 0.055
        sy = sx
        tx = np.sin(t_sec * 38.0) * 9.0 * amp
        ty = np.cos(t_sec * 31.0) * 7.0 * amp
        rot = np.sin(t_sec * 24.0) * 3.5 * amp
    elif effect == "bounce":
        b = abs(np.sin(t_sec * 5.8)) * (0.45 + e * 0.65) * loop_env
        sx = 1.0 + (0.045 - b * 0.03)
        sy = 1.0 + (-0.03 + b * 0.075)
        ty = -b * 18.0
    elif effect == "zoom":
        scale = 1.0 + (0.09 * abs(np.sin(progress * np.pi)) + e * 0.055) * loop_env
        sx, sy = scale, scale
        rot = np.sin(t_sec * 3.5) * e * 2.0
    else:
        scale = 1.0 + (0.045 * abs(np.sin(t_sec * 4.5)) + e * 0.05) * loop_env
        sx, sy = scale, scale

    M = cv2.getRotationMatrix2D((256.0, 256.0), float(rot), float(0.5 * (sx + sy)))
    if abs(sx - sy) > 1e-3:
        M[0, 0] *= sx / (0.5 * (sx + sy))
        M[0, 1] *= sx / (0.5 * (sx + sy))
        M[1, 0] *= sy / (0.5 * (sx + sy))
        M[1, 1] *= sy / (0.5 * (sx + sy))
    M[0, 2] += tx
    M[1, 2] += ty

    return cv2.warpAffine(
        base_bgra,
        M,
        (512, 512),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_mode,
    )


def _encode_webm_alpha(frames_bgra, out_webm, fps=STICKER_FPS):
    """Exporta Sticker Animado oficial de Telegram (.webm VP9 yuva420p, <= 255 KB, sin audio)."""
    ffmpeg_exe = _get_ffmpeg()
    raw = b"".join(f.tobytes() for f in frames_bgra)
    for br, crf in [("420k", "31"), ("280k", "37"), ("170k", "44"), ("105k", "50")]:
        cmd = [
            ffmpeg_exe, "-y", "-f", "rawvideo", "-pix_fmt", "bgra",
            "-s", "512x512", "-r", str(fps), "-i", "pipe:0",
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
            "-b:v", br, "-crf", crf, "-deadline", "good", "-cpu-used", "7",
            "-auto-alt-ref", "0", "-an", out_webm,
        ]
        try:
            res = subprocess.run(cmd, input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
            if res.returncode == 0 and os.path.exists(out_webm) and os.path.getsize(out_webm) <= 255 * 1024:
                return True
        except Exception:
            pass
    return os.path.exists(out_webm) and os.path.getsize(out_webm) <= 256 * 1024


def _encode_webp_anim(frames_bgra, out_webp, fps=STICKER_FPS):
    """Exporta Sticker Animado oficial de WhatsApp (.webp transparente, 512x512, <= 495 KB)."""
    step = 3 if fps >= 24 else 2
    sampled = frames_bgra[::step]
    wa_fps = fps / float(step)
    duration_ms = max(40, int(round(1000.0 / wa_fps)))

    ffmpeg_exe = _get_ffmpeg()
    raw = b"".join(f.tobytes() for f in sampled)
    for q in ["58", "38", "24"]:
        cmd = [
            ffmpeg_exe, "-y", "-f", "rawvideo", "-pix_fmt", "bgra",
            "-s", "512x512", "-r", f"{wa_fps:.2f}", "-i", "pipe:0",
            "-c:v", "libwebp_anim", "-pix_fmt", "yuva420p",
            "-lossless", "0", "-loop", "0", "-q:v", q, "-compression_level", "3", out_webp,
        ]
        try:
            res = subprocess.run(cmd, input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            if res.returncode == 0 and os.path.exists(out_webp) and 100 < os.path.getsize(out_webp) <= 495 * 1024:
                return True
        except Exception:
            pass

    pil_frames = [Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGRA2RGBA), "RGBA") for f in sampled]
    for q in [55, 35, 20]:
        try:
            pil_frames[0].save(
                out_webp, format="WEBP", save_all=True, append_images=pil_frames[1:],
                duration=duration_ms, loop=0, quality=q, method=2, minimize_size=True
            )
            if os.path.exists(out_webp) and os.path.getsize(out_webp) <= 495 * 1024:
                return True
        except Exception:
            pass

    # Último recurso (5-6 fps, calidad 40) para garantizar siempre <= 495 KB en WhatsApp
    sampled_low = pil_frames[::2] if len(pil_frames) > 2 else pil_frames
    try:
        sampled_low[0].save(
            out_webp, format="WEBP", save_all=True, append_images=sampled_low[1:],
            duration=duration_ms * 2, loop=0, quality=40, method=2, minimize_size=True
        )
        if os.path.exists(out_webp) and os.path.getsize(out_webp) <= 495 * 1024:
            return True
    except Exception:
        pass
    return os.path.exists(out_webp) and 0 < os.path.getsize(out_webp) <= 495 * 1024


def _encode_webp_static(frame_bgra, out_webp):
    """Exporta Sticker Estático oficial de WhatsApp/Telegram (.webp 512x512 RGBA <= 98 KB)."""
    pil_im = Image.fromarray(cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2RGBA), "RGBA")
    for q in [90, 75, 55, 40]:
        try:
            pil_im.save(out_webp, format="WEBP", quality=q, method=6)
            if os.path.exists(out_webp) and os.path.getsize(out_webp) <= 98 * 1024:
                return True
        except Exception:
            pass
    return os.path.exists(out_webp) and os.path.getsize(out_webp) > 0


_STUDIO_BG_512 = None


def _get_studio_bg_512():
    """Precalcula fondo degradado oscuro elegante (#1e293b centro -> #0f172a esquinas) para contraste alto en MP4."""
    global _STUDIO_BG_512
    if _STUDIO_BG_512 is None:
        yy, xx = np.mgrid[0:512, 0:512].astype(np.float32)
        dist = np.sqrt(((xx - 255.5) / 256.0) ** 2 + ((yy - 255.5) / 256.0) ** 2) / np.sqrt(2.0)
        t = np.clip(dist, 0.0, 1.0)[..., None]
        # #1e293b = BGR (59, 41, 30), #0f172a = BGR (42, 23, 15)
        c_center = np.array([59.0, 41.0, 30.0], dtype=np.float32)
        c_edge = np.array([42.0, 23.0, 15.0], dtype=np.float32)
        _STUDIO_BG_512 = c_center * (1.0 - t) + c_edge * t
    return _STUDIO_BG_512


def _bgra_on_studio_bg(bgra, frame_style="cutout"):
    a = bgra[..., 3:4].astype(np.float32) / 255.0
    bg = 255.0 if frame_style == "meme" else _get_studio_bg_512()
    return np.clip(bgra[..., :3].astype(np.float32) * a + bg * (1.0 - a), 0, 255).astype(np.uint8)


def _encode_mp4_with_audio(frames_bgra, audio_path, out_mp4, fps=STICKER_FPS, max_audio_sec=12.0, frame_style="cutout"):
    """
    Exporta Sticker + Audio unido en un solo archivo (.mp4 512x512 H.264 + AAC 192k),
    haciendo bucle fluido del movimiento hasta cubrir la duración del audio (hasta max_audio_sec).
    """
    ffmpeg_exe = _get_ffmpeg()
    _, _, _, audio_dur = extract_audio_envelope(audio_path, fps=fps, max_duration=max_audio_sec)
    target_dur = min(max_audio_sec, max(len(frames_bgra) / float(fps), audio_dur))
    total_frames = max(len(frames_bgra), int(round(target_dur * fps)))

    bgr_frames = [_bgra_on_studio_bg(f, frame_style=frame_style) for f in frames_bgra]
    # Bucle de ida o repetición suave de los frames del sticker
    stream_bytes = b"".join(bgr_frames[i % len(bgr_frames)].tobytes() for i in range(total_frames))

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "512x512", "-r", str(fps), "-i", "pipe:0",
        "-t", f"{target_dur:.3f}", "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-shortest", out_mp4,
    ]
    try:
        res = subprocess.run(cmd, input=stream_bytes, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        return res.returncode == 0 and os.path.exists(out_mp4)
    except Exception:
        return False


def _read_video_frames_bgra(video_path, max_frames=STICKER_MAX_FRAMES, frame_style="full", outline=True, top_text="", bottom_text=""):
    """Extrae frames de un video/GIF de entrada y los convierte al estilo sticker 512x512 BGRA."""
    cap = cv2.VideoCapture(video_path)
    frames = []
    while len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        H, W = frame.shape[:2]
        scale = min(468.0 / max(W, 1), 468.0 / max(H, 1))
        nw, nh = max(16, int(round(W * scale))), max(16, int(round(H * scale)))
        resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)

        canvas = np.zeros((512, 512, 4), dtype=np.uint8)
        ox, oy = (512 - nw) // 2, (512 - nh) // 2
        if frame_style == "circle":
            d = min(nw, nh)
            sq = cv2.resize(resized, (d, d), interpolation=cv2.INTER_LINEAR)
            circ = np.zeros((d, d), dtype=np.uint8)
            cv2.circle(circ, (d // 2, d // 2), d // 2 - 2, 255, -1)
            cx0, cy0 = (512 - d) // 2, (512 - d) // 2
            canvas[cy0:cy0 + d, cx0:cx0 + d, :3] = sq
            canvas[cy0:cy0 + d, cx0:cx0 + d, 3] = circ
        elif frame_style == "meme":
            canvas[:, :, :3] = 255
            canvas[:, :, 3] = 255
            canvas[oy:oy + nh, ox:ox + nw, :3] = resized
        else:
            rr = _rounded_rect_mask(nh, nw, radius=32)
            canvas[oy:oy + nh, ox:ox + nw, :3] = resized
            canvas[oy:oy + nh, ox:ox + nw, 3] = rr

        if outline and frame_style != "meme":
            canvas = add_sticker_outline(canvas, thickness=8, add_shadow=False)
        if top_text or bottom_text:
            canvas = draw_meme_text_rgba(canvas, top_text=top_text, bottom_text=bottom_text)
        frames.append(canvas)
    cap.release()
    return frames


def build_sticker_bundle(
    media_path,
    audio_path,
    out_dir,
    base_name,
    effect="beat_pop",
    frame_style="cutout",
    top_text="",
    bottom_text="",
    outline=True,
):
    """
    Construye el paquete completo de Sticker Profesional (Telegram + WhatsApp + MP4 con Audio):
      - Para imágenes: recorte / marco + texto meme + animación limpia sincronizada al audio
        (o Lip-Sync Neural real en la nube cuando effect == 'ai_talk').
      - Para videos/GIFs: recorte/marco redondeado + texto + sincronización con el audio.
    """
    os.makedirs(out_dir, exist_ok=True)
    out_webm = os.path.join(out_dir, f"{base_name}.webm")
    out_webp_anim = os.path.join(out_dir, f"{base_name}_anim.webp")
    out_webp_static = os.path.join(out_dir, f"{base_name}_static.webp")
    out_mp4 = os.path.join(out_dir, f"{base_name}_audio.mp4")

    result = {
        "ok": False,
        "webm": None,
        "webp_anim": None,
        "webp_static": None,
        "mp4": None,
        "used_ai_talk": False,
        "cutout_applied": False,
        "frame_style": frame_style,
        "effect": effect,
        "error": None,
    }

    is_video = str(media_path).lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif"))
    frames = []

    if is_video:
        frames = _read_video_frames_bgra(
            media_path,
            max_frames=STICKER_MAX_FRAMES,
            frame_style=frame_style if frame_style != "cutout" else "full",
            outline=outline,
            top_text=top_text,
            bottom_text=bottom_text,
        )
        if not frames:
            result["error"] = "No se pudieron leer frames del video."
            return result
    else:
        # 1) Si eligió Habla IA Neural (nube), intentar Wav2Lip / EchoMimic primero
        if effect == "ai_talk":
            ai_tmp = os.path.join(out_dir, f"{base_name}_aitalk_raw.mp4")
            if run_cloud_ai_lipsync(media_path, audio_path, ai_tmp, timeout_sec=35):
                frames = _read_video_frames_bgra(
                    ai_tmp,
                    max_frames=STICKER_MAX_FRAMES,
                    frame_style=frame_style if frame_style != "cutout" else "full",
                    outline=outline,
                    top_text=top_text,
                    bottom_text=bottom_text,
                )
                if frames:
                    result["used_ai_talk"] = True
                try:
                    os.remove(ai_tmp)
                except Exception:
                    pass
            if not frames:
                effect = "beat_pop"
                result["effect"] = "beat_pop"

        # 2) Flujo limpio de alta calidad (recorte universal + borde blanco + animación al audio)
        if not frames:
            base_bgra, meta = prepare_sticker_subject(media_path, frame_style=frame_style, outline=outline)
            if base_bgra is None:
                result["error"] = "No se pudo abrir la imagen."
                return result
            result["cutout_applied"] = meta.get("cutout_applied", False)

            if top_text or bottom_text:
                base_bgra = draw_meme_text_rgba(base_bgra, top_text=top_text, bottom_text=bottom_text)

            energy, onset, start_sec, _ = extract_audio_envelope(audio_path, fps=STICKER_FPS)
            end_idx = min(len(energy), int(round(start_sec * STICKER_FPS)) + STICKER_MAX_FRAMES)
            start_idx = max(0, end_idx - STICKER_MAX_FRAMES) if end_idx == len(energy) else int(round(start_sec * STICKER_FPS))
            e_win = energy[start_idx:end_idx]
            on_win = onset[start_idx:end_idx]

            if len(e_win) < 45:
                pad_n = 45 - len(e_win)
                e_win = np.pad(e_win, (0, pad_n))
                on_win = np.pad(on_win, (0, pad_n))

            nf = len(e_win)
            border_mode = (255, 255, 255, 255) if frame_style == "meme" else (0, 0, 0, 0)
            for i in range(nf):
                progress = i / float(max(1, nf - 1))
                t_sec = i / float(STICKER_FPS)
                frames.append(_animate_frame_clean(base_bgra, effect, e_win[i], on_win[i], t_sec, progress, border_mode))

    if not frames:
        result["error"] = "Sin frames generados."
        return result

    if _encode_webm_alpha(frames, out_webm, fps=STICKER_FPS):
        result["webm"] = out_webm
    if _encode_webp_anim(frames, out_webp_anim, fps=STICKER_FPS):
        result["webp_anim"] = out_webp_anim
    if _encode_webp_static(frames[min(len(frames) - 1, len(frames) // 3)], out_webp_static):
        result["webp_static"] = out_webp_static
    if _encode_mp4_with_audio(frames, audio_path, out_mp4, fps=STICKER_FPS, frame_style=frame_style):
        result["mp4"] = out_mp4

    result["ok"] = bool(result["webm"] or result["webp_anim"] or result["webp_static"] or result["mp4"])
    return result
