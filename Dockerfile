FROM python:3.11-slim

# ── System deps for dlib / cmake ──────────────────────────────
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────
WORKDIR /app

# ── Install Python deps ───────────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install dlib==19.24.6
RUN pip install git+https://github.com/ageitgey/face_recognition_models
RUN pip install -r requirements.txt

# ── Copy project ──────────────────────────────────────────────
COPY . .

# ── Create uploads dir ────────────────────────────────────────
RUN mkdir -p uploads

# ── Expose port ───────────────────────────────────────────────
EXPOSE 7860

# ── Start ─────────────────────────────────────────────────────
CMD ["python", "app.py"]
