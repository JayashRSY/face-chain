"""
face_encoder.py
Detects faces and returns encodings using dlib directly.
ARM64 / Apple Silicon safe:
  - Global threading lock — dlib is NOT thread-safe, one call at a time
  - Models pre-loaded in main thread before Flask starts
  - upsample=0 to avoid memory crash on ARM64
  - Image forced to RGB, EXIF-corrected, capped at 640px
"""

import io
import threading
import dlib
import numpy as np
from PIL import Image, ImageOps
from pathlib import Path

_MODELS_DIR = (
    Path(__file__).parent.parent
    / "venv/lib/python3.11/site-packages/face_recognition_models/models"
)

# ── Global lock — only one dlib call at a time ────────────────
_dlib_lock = threading.Lock()

_detector  = None
_predictor = None
_encoder   = None
_cnn_det   = None


def load_models():
    """
    Call this once from the main thread before starting Flask.
    Pre-loading in the main thread avoids ARM64 thread-init crashes.
    """
    global _detector, _predictor, _encoder, _cnn_det
    if _detector is not None:
        return
    print("[FaceEncoder] Loading dlib models (main thread)...")
    _detector  = dlib.get_frontal_face_detector()
    _predictor = dlib.shape_predictor(
        str(_MODELS_DIR / "shape_predictor_68_face_landmarks.dat")
    )
    _encoder = dlib.face_recognition_model_v1(
        str(_MODELS_DIR / "dlib_face_recognition_resnet_model_v1.dat")
    )
    _cnn_det = dlib.cnn_face_detection_model_v1(
        str(_MODELS_DIR / "mmod_human_face_detector.dat")
    )
    print("[FaceEncoder] All models loaded.")


def _safe_load(image_path: str) -> np.ndarray:
    """
    Load image safely for dlib on ARM64 Mac.
    Capped at 640px — smaller images are more stable with dlib on Apple Silicon.
    """
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        if max(img.size) > 640:
            img.thumbnail((640, 640), Image.LANCZOS)
        arr = np.array(img, dtype=np.uint8)
        return np.ascontiguousarray(arr)


def encode_face(image_path: str) -> np.ndarray:
    """
    Detect face and return 128-dim encoding.
    Thread-safe via global lock.
    """
    load_models()
    image = _safe_load(image_path)

    with _dlib_lock:
        detections = _detector(image, 0)

        if len(detections) == 0:
            print("[FaceEncoder] HOG missed — trying CNN detector...")
            cnn_dets = _cnn_det(image, 0)
            if len(cnn_dets) == 0:
                raise ValueError(f"No face detected in: {image_path}")
            detections = [d.rect for d in cnn_dets]

        print(f"[FaceEncoder] Detected {len(detections)} face(s). Using first.")
        shape    = _predictor(image, detections[0])
        encoding = np.array(_encoder.compute_face_descriptor(image, shape))

    return encoding


def get_face_crop_bytes(image_path: str) -> bytes:
    """Returns cropped face region as JPEG bytes. Thread-safe."""
    load_models()
    image = _safe_load(image_path)

    with _dlib_lock:
        detections = _detector(image, 0)

    if len(detections) == 0:
        raise ValueError("No face detected for cropping.")

    d   = detections[0]
    pad = 40
    pil = Image.fromarray(image)
    w, h = pil.size
    crop = pil.crop((
        max(0, d.left()   - pad),
        max(0, d.top()    - pad),
        min(w, d.right()  + pad),
        min(h, d.bottom() + pad),
    ))
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=95)
    return buf.getvalue()
