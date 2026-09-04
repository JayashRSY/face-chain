"""
face_encoder.py
Detects faces and returns encodings using dlib directly.
Points to model files by path — avoids the broken face_recognition_models
pkg_resources import that fails on Python 3.11+.
"""

import io
import dlib
import numpy as np
from PIL import Image
from pathlib import Path

# ── Locate model files directly ───────────────────────────────
_MODELS_DIR = (
    Path(__file__).parent.parent
    / "venv/lib/python3.11/site-packages/face_recognition_models/models"
)

DETECTOR = dlib.get_frontal_face_detector()

PREDICTOR = dlib.shape_predictor(
    str(_MODELS_DIR / "shape_predictor_68_face_landmarks.dat")
)

ENCODER = dlib.face_recognition_model_v1(
    str(_MODELS_DIR / "dlib_face_recognition_resnet_model_v1.dat")
)


def _load_image(image_path: str) -> np.ndarray:
    img = Image.open(image_path).convert("RGB")
    return np.array(img)


def encode_face(image_path: str) -> np.ndarray:
    """
    Load image, detect faces with dlib, return 128-dim encoding of first face.
    Raises ValueError if no face is detected.
    """
    image      = _load_image(image_path)
    detections = DETECTOR(image, 1)

    if len(detections) == 0:
        raise ValueError(f"No face detected in: {image_path}")

    print(f"[FaceEncoder] Detected {len(detections)} face(s). Using first.")
    shape    = PREDICTOR(image, detections[0])
    encoding = np.array(ENCODER.compute_face_descriptor(image, shape))
    return encoding


def get_face_crop_bytes(image_path: str) -> bytes:
    """
    Returns the cropped face region as JPEG bytes.
    Used for reverse image search upload.
    """
    image      = _load_image(image_path)
    detections = DETECTOR(image, 1)

    if len(detections) == 0:
        raise ValueError("No face detected for cropping.")

    d   = detections[0]
    pad = 50
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
