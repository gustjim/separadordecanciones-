FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    pkg-config \
    curl \
    unzip \
    && curl -fsSL https://deno.land/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir "numpy<2"
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir "numpy<2"
RUN pip install --no-cache-dir --no-deps spleeter==2.1.0 "librosa>=0.10.0" && pip install --no-cache-dir "numpy<2"
RUN pip install --no-cache-dir demucs && pip install --no-cache-dir "numpy<2"

COPY backend/ ./
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN python -c "import demucs; print('demucs OK')" && python -c "import spleeter; print('spleeter OK')"
ENV TORCH_HOME=/app/.cache/torch
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p /app/.cache/torch/hub/checkpoints /app/.cache/huggingface
RUN python -c "
import os
os.environ['HF_HOME'] = '/app/.cache/huggingface'
os.environ['TORCH_HOME'] = '/app/.cache/torch'
from demucs.pretrained import get_model
model = get_model('htdemucs')
print('htdemucs model pre-downloaded OK:', model.name)
" 2>&1

RUN echo '#!/bin/sh\nexec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000
CMD ["/bin/sh", "/app/start.sh"]
