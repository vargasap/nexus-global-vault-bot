import os
import subprocess
import numpy as np
import cv2
import imageio_ffmpeg
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "face_landmarker.task")

# MediaPipe 468/478 Face Mesh key landmark indices
UPPER_LIP_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
LOWER_LIP_OUTER = [291, 375, 321, 405, 314, 17, 84, 181, 91, 146, 61]
UPPER_LIP_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
LOWER_LIP_INNER = [308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78]

LEFT_EYEBROW = [70, 63, 105, 66, 107]
RIGHT_EYEBROW = [336, 296, 334, 293, 300]

LEFT_EYE_UPPER = [159, 158, 157, 160, 161]
LEFT_EYE_LOWER = [145, 144, 153, 154, 163]
RIGHT_EYE_UPPER = [386, 385, 384, 387, 388]
RIGHT_EYE_LOWER = [374, 373, 380, 381, 390]

CHIN_IDX = 152
NOSE_TIP_IDX = 1
MOUTH_LEFT_IDX = 61
MOUTH_RIGHT_IDX = 291
UPPER_LIP_CENTER = 13
LOWER_LIP_CENTER = 14

_LANDMARKER = None


def _get_landmarker():
    global _LANDMARKER
    if _LANDMARKER is None and os.path.exists(MODEL_PATH):
        base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=3,
            min_face_detection_confidence=0.18,
            min_face_presence_confidence=0.18,
        )
        _LANDMARKER = mp_vision.FaceLandmarker.create_from_options(options)
    return _LANDMARKER


def extract_audio_features(audio_path, fps=25, max_duration=15.0):
    """
    Decodes audio to mono 16kHz PCM and computes per-frame:
    - energy: normalized loudness [0..1] (mouth openness)
    - brightness: zero-crossing rate [0..1] (vowel width: E/I wide vs O/U round)
    - emphasis: positive onset energy [0..1] (eyebrow raise & head nod)
    - duration: float seconds
    """
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    sr = 16000
    cmd = [
        ffmpeg_exe, "-y", "-i", audio_path,
        "-t", str(max_duration),
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ac", "1", "-ar", str(sr),
        "pipe:1"
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
    raw = res.stdout
    if not raw or len(raw) < 320:
        n_frames = int(fps * 3.0)
        return np.zeros(n_frames), np.zeros(n_frames), np.zeros(n_frames), 3.0

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    duration = len(samples) / float(sr)
    n_frames = max(1, int(round(duration * fps)))
    hop = max(1, int(sr / fps))

    energy = np.zeros(n_frames, dtype=np.float32)
    brightness = np.zeros(n_frames, dtype=np.float32)

    for i in range(n_frames):
        start = i * hop
        end = min(len(samples), start + hop * 2)
        chunk = samples[start:end]
        if len(chunk) < 4:
            continue
        rms = float(np.sqrt(np.mean(chunk * chunk)))
        energy[i] = rms
        # Zero-crossing rate estimates spectral brightness (consonants / E-I vs O-U)
        zcr = float(np.mean(np.abs(np.diff(np.sign(chunk))))) * 0.5
        brightness[i] = zcr

    # Adaptive normalization using 95th percentile so loud peaks don't crush speech
    p95 = float(np.percentile(energy, 95)) if np.max(energy) > 0 else 1.0
    if p95 < 1e-4:
        p95 = float(np.max(energy)) + 1e-5
    energy = np.clip(energy / p95, 0.0, 1.15)
    # Soft noise gate so silence closes mouth cleanly
    energy = np.where(energy < 0.08, 0.0, (energy - 0.08) / 0.92)
    energy = np.clip(energy, 0.0, 1.0)

    # Smooth attack (fast) and release (moderate) for natural lip movement
    smooth_e = np.zeros_like(energy)
    for i in range(n_frames):
        prev = smooth_e[i - 1] if i > 0 else 0.0
        alpha = 0.72 if energy[i] > prev else 0.42
        smooth_e[i] = prev + alpha * (energy[i] - prev)

    # Brightness normalization
    b95 = float(np.percentile(brightness, 95)) if np.max(brightness) > 0 else 1.0
    brightness = np.clip(brightness / (b95 + 1e-5), 0.0, 1.0)
    smooth_b = np.convolve(brightness, np.ones(3) / 3.0, mode="same")

    # Emphasis (onset / sudden loudness increase -> eyebrow raise & head nod)
    diff_e = np.maximum(0.0, np.diff(smooth_e, prepend=0.0))
    emphasis = np.clip(diff_e * 3.5 + smooth_e * 0.45, 0.0, 1.0)
    smooth_emp = np.zeros_like(emphasis)
    for i in range(n_frames):
        prev = smooth_emp[i - 1] if i > 0 else 0.0
        alpha = 0.55 if emphasis[i] > prev else 0.20
        smooth_emp[i] = prev + alpha * (emphasis[i] - prev)

    return smooth_e, smooth_b, smooth_emp, duration


def prepare_canvas_512(image_path):
    """Loads image and centers it onto a 512x512 white letterbox canvas (BGR)."""
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = min(512.0 / w, 512.0 / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.full((512, 512, 3), 255, dtype=np.uint8)
    ox = (512 - nw) // 2
    oy = (512 - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return canvas


def detect_primary_face(canvas_bgr):
    """
    Detects facial landmarks on the 512x512 canvas with multi-scale crop fallback
    so even wide shots / small faces (e.g. a person standing in a room) are detected.
    Returns Nx2 float32 pixel array in 512x512 coordinates, or None.
    """
    landmarker = _get_landmarker()
    if landmarker is None:
        return None
    rgb = cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2RGB)

    # Candidate regions (x0, y0, x1, y1) normalized in [0..1]
    regions = [
        (0.0, 0.0, 1.0, 1.0),     # Full image (portraits / close-ups)
        (0.20, 0.15, 0.80, 0.75), # Center-upper crop
        (0.20, 0.35, 0.80, 0.95), # Center-lower crop
        (0.0, 0.15, 0.60, 0.75),  # Left-mid crop
        (0.40, 0.15, 1.0, 0.75),  # Right-mid crop
    ]

    for (rx0, ry0, rx1, ry1) in regions:
        x0, y0 = int(rx0 * 512), int(ry0 * 512)
        x1, y1 = int(rx1 * 512), int(ry1 * 512)
        if rx0 == 0.0 and ry0 == 0.0 and rx1 == 1.0 and ry1 == 1.0:
            patch = rgb
        else:
            sub = rgb[y0:y1, x0:x1]
            patch = cv2.resize(sub, (512, 512), interpolation=cv2.INTER_CUBIC)

        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=patch)
        result = landmarker.detect(mp_img)
        if result.face_landmarks:
            best_pts = None
            best_area = -1.0
            pw = float(x1 - x0)
            ph = float(y1 - y0)
            for face_lm in result.face_landmarks:
                pts = np.array(
                    [[x0 + lm.x * pw, y0 + lm.y * ph] for lm in face_lm],
                    dtype=np.float32
                )
                area = (pts[:, 0].max() - pts[:, 0].min()) * (pts[:, 1].max() - pts[:, 1].min())
                if area > best_area:
                    best_area = area
                    best_pts = pts
            if best_pts is not None:
                return best_pts
    return None


def _gaussian_warp_field(grid_x, grid_y, cx, cy, dx, dy, rx, ry):
    """Returns backward-mapping displacement (-dx, -dy) weighted by an elliptical Gaussian."""
    dist2 = ((grid_x - cx) / (rx + 1e-5)) ** 2 + ((grid_y - cy) / (ry + 1e-5)) ** 2
    w = np.exp(-dist2 * 1.5).astype(np.float32)
    return -dx * w, -dy * w


def render_talking_frame(base_bgr, pts, mouth_open, vowel_wide, emphasis, blink, t_sec, grid_x, grid_y, base_map_x, base_map_y):
    """
    Applies real audio-driven facial animation to base_bgr:
    - Jaw & lower lip drop + dark mouth interior (true lip-sync)
    - Upper lip & mouth corner stretch (vowel shapes)
    - Eyebrow raises on emphasis
    - Periodic natural eye blinks
    - Subtle audio-driven head nod & tilt
    """
    face_w = float(pts[:, 0].max() - pts[:, 0].min())
    face_h = float(pts[:, 1].max() - pts[:, 1].min())
    if face_w < 18 or face_h < 18:
        return base_bgr.copy()

    # Work on a 128x128 displacement grid for speed, then upscale to 512x512
    disp_x = np.zeros_like(grid_x)
    disp_y = np.zeros_like(grid_y)

    # 1. Mouth & Jaw Lip-Sync
    mouth_l = pts[MOUTH_LEFT_IDX]
    mouth_r = pts[MOUTH_RIGHT_IDX]
    mouth_w = float(np.linalg.norm(mouth_r - mouth_l))
    upper_c = pts[UPPER_LIP_CENTER]
    lower_c = pts[LOWER_LIP_CENTER]
    chin = pts[CHIN_IDX]
    mouth_center = 0.5 * (upper_c + lower_c)

    # Jaw drop amount scaled to face height
    jaw_drop = float(mouth_open) * face_h * 0.135
    upper_lift = float(mouth_open) * face_h * 0.022
    corner_stretch = (float(vowel_wide) - 0.42) * float(mouth_open) * mouth_w * 0.22

    # Drop lower lip & chin
    if jaw_drop > 0.3:
        lx, ly = _gaussian_warp_field(
            grid_x, grid_y,
            lower_c[0], lower_c[1] + face_h * 0.04,
            0.0, jaw_drop,
            mouth_w * 0.72, face_h * 0.22
        )
        disp_x += lx
        disp_y += ly

        # Chin follows slightly softer
        cx2, cy2 = _gaussian_warp_field(
            grid_x, grid_y,
            chin[0], chin[1],
            0.0, jaw_drop * 0.75,
            face_w * 0.36, face_h * 0.18
        )
        disp_x += cx2
        disp_y += cy2

        # Upper lip lifts subtly
        ux, uy = _gaussian_warp_field(
            grid_x, grid_y,
            upper_c[0], upper_c[1],
            0.0, -upper_lift,
            mouth_w * 0.55, face_h * 0.09
        )
        disp_x += ux
        disp_y += uy

        # Mouth corners widen (smile/E/I) or narrow (O/U)
        if abs(corner_stretch) > 0.2:
            ml_x, ml_y = _gaussian_warp_field(
                grid_x, grid_y,
                mouth_l[0], mouth_l[1],
                -corner_stretch, -corner_stretch * 0.2,
                mouth_w * 0.35, face_h * 0.12
            )
            mr_x, mr_y = _gaussian_warp_field(
                grid_x, grid_y,
                mouth_r[0], mouth_r[1],
                corner_stretch, -corner_stretch * 0.2,
                mouth_w * 0.35, face_h * 0.12
            )
            disp_x += ml_x + mr_x
            disp_y += ml_y + mr_y

    # 2. Eyebrow raises on vocal emphasis
    brow_lift = float(emphasis) * face_h * 0.045
    if brow_lift > 0.2:
        lb_center = np.mean(pts[LEFT_EYEBROW], axis=0)
        rb_center = np.mean(pts[RIGHT_EYEBROW], axis=0)
        bx1, by1 = _gaussian_warp_field(grid_x, grid_y, lb_center[0], lb_center[1], 0.0, -brow_lift, face_w * 0.20, face_h * 0.09)
        bx2, by2 = _gaussian_warp_field(grid_x, grid_y, rb_center[0], rb_center[1], 0.0, -brow_lift, face_w * 0.20, face_h * 0.09)
        disp_x += bx1 + bx2
        disp_y += by1 + by2

    # 3. Natural eye blinks
    if blink > 0.05:
        le_u = np.mean(pts[LEFT_EYE_UPPER], axis=0)
        le_l = np.mean(pts[LEFT_EYE_LOWER], axis=0)
        re_u = np.mean(pts[RIGHT_EYE_UPPER], axis=0)
        re_l = np.mean(pts[RIGHT_EYE_LOWER], axis=0)
        le_drop = max(2.0, float(le_l[1] - le_u[1])) * float(blink) * 1.15
        re_drop = max(2.0, float(re_l[1] - re_u[1])) * float(blink) * 1.15
        ex1, ey1 = _gaussian_warp_field(grid_x, grid_y, le_u[0], le_u[1], 0.0, le_drop, face_w * 0.13, face_h * 0.06)
        ex2, ey2 = _gaussian_warp_field(grid_x, grid_y, re_u[0], re_u[1], 0.0, re_drop, face_w * 0.13, face_h * 0.06)
        disp_x += ex1 + ex2
        disp_y += ey1 + ey2

    # Upscale displacement field to 512x512 and remap
    dx_full = cv2.resize(disp_x, (512, 512), interpolation=cv2.INTER_LINEAR)
    dy_full = cv2.resize(disp_y, (512, 512), interpolation=cv2.INTER_LINEAR)
    warped = cv2.remap(
        base_bgr,
        base_map_x + dx_full,
        base_map_y + dy_full,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )

    # 4. Draw realistic dark mouth cavity inside opened lips so it looks truly speaking
    if mouth_open > 0.14:
        upper_poly = pts[UPPER_LIP_INNER].copy()
        lower_poly = pts[LOWER_LIP_INNER].copy()
        # Move inner lip polygons to match the warp
        upper_poly[:, 1] -= upper_lift * 0.85
        lower_poly[:, 1] += jaw_drop * 0.92
        mouth_poly = np.vstack([upper_poly, lower_poly]).astype(np.int32)

        mask = np.zeros((512, 512), dtype=np.float32)
        cv2.fillPoly(mask, [mouth_poly], 1.0)
        ksize = max(3, int(round(mouth_w * 0.12)) | 1)
        mask = cv2.GaussianBlur(mask, (ksize, ksize), 0)
        # Scale opacity with mouth openness
        alpha = np.clip(mask * min(0.88, float(mouth_open) * 1.15), 0.0, 0.88)[..., None]

        # Deep warm dark interior color (natural oral cavity tone, not harsh pure black)
        cavity_color = np.array([22, 18, 36], dtype=np.float32)
        warped = (warped.astype(np.float32) * (1.0 - alpha) + cavity_color * alpha).astype(np.uint8)

    # 5. Subtle audio-driven head gesture (nod + expressive lean/tilt synced to emphasis)
    nod_y = float(emphasis) * 4.5 - float(mouth_open) * 1.8
    tilt_deg = float(np.sin(t_sec * 3.1)) * (0.9 + float(emphasis) * 2.4)
    zoom = 1.0 + float(emphasis) * 0.032

    face_center = (float(pts[NOSE_TIP_IDX][0]), float(pts[NOSE_TIP_IDX][1]))
    M = cv2.getRotationMatrix2D(face_center, tilt_deg, zoom)
    M[1, 2] += nod_y
    out = cv2.warpAffine(warped, M, (512, 512), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return out


def render_audio_reactive_fallback(base_bgr, mouth_open, emphasis, t_sec):
    """
    For non-human memes (cats, cartoons, objects):
    Squash-and-stretch + expressive tilt driven directly by actual audio energy & peaks.
    """
    scale_x = 1.0 + float(mouth_open) * 0.055 - float(emphasis) * 0.02
    scale_y = 1.0 - float(mouth_open) * 0.025 + float(emphasis) * 0.065
    tilt_deg = float(np.sin(t_sec * 4.2)) * (0.5 + float(emphasis) * 3.8)
    dy = -float(emphasis) * 10.0

    # Squash & stretch around center
    nw = max(64, int(round(512 * scale_x)))
    nh = max(64, int(round(512 * scale_y)))
    stretched = cv2.resize(base_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)

    canvas = np.full((512, 512, 3), 255, dtype=np.uint8)
    ox = (512 - nw) // 2
    oy = (512 - nh) // 2

    src_x0 = max(0, -ox)
    src_y0 = max(0, -oy)
    dst_x0 = max(0, ox)
    dst_y0 = max(0, oy)
    copy_w = min(nw - src_x0, 512 - dst_x0)
    copy_h = min(nh - src_y0, 512 - dst_y0)
    if copy_w > 0 and copy_h > 0:
        canvas[dst_y0:dst_y0 + copy_h, dst_x0:dst_x0 + copy_w] = stretched[src_y0:src_y0 + copy_h, src_x0:src_x0 + copy_w]

    M = cv2.getRotationMatrix2D((256.0, 256.0), tilt_deg, 1.0)
    M[1, 2] += dy
    return cv2.warpAffine(canvas, M, (512, 512), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


def generate_lipsync_sticker(image_path, audio_path, output_mp4, fps=25):
    """
    Main entry point: takes a static photo + audio file, detects face landmarks,
    and produces a 512x512 MP4 sticker where the character speaks/gestures in sync with the audio.
    Returns (ok: bool, face_detected: bool).
    """
    canvas = prepare_canvas_512(image_path)
    if canvas is None:
        return False, False

    energy, brightness, emphasis, duration = extract_audio_features(audio_path, fps=fps)
    n_frames = len(energy)
    pts = detect_primary_face(canvas)
    face_detected = pts is not None

    # Precompute grids once
    g_coords = np.linspace(0, 511, 128, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(g_coords, g_coords)
    full_coords = np.arange(512, dtype=np.float32)
    base_map_x, base_map_y = np.meshgrid(full_coords, full_coords)

    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "512x512",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-i", audio_path,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-shortest",
        output_mp4
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for i in range(n_frames):
            t_sec = i / float(fps)
            # Periodic natural blink every 2.4 seconds (duration ~0.16s)
            blink_phase = t_sec % 2.4
            if 1.10 <= blink_phase <= 1.26:
                blink = float(np.sin((blink_phase - 1.10) / 0.16 * np.pi))
            else:
                blink = 0.0

            if face_detected:
                frame = render_talking_frame(
                    canvas, pts,
                    energy[i], brightness[i], emphasis[i], blink, t_sec,
                    grid_x, grid_y, base_map_x, base_map_y
                )
            else:
                frame = render_audio_reactive_fallback(canvas, energy[i], emphasis[i], t_sec)

            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        proc.wait(timeout=30)
        ok = (proc.returncode == 0 and os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 1024)
        return ok, face_detected
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        return False, face_detected
