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
    && rm -rf /var/lib/apt/lists/*

ENV DEMUCS_ENABLED="false"
ENV USE_TORCH=0
ENV OMP_NUM_THREADS=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/models && \
    curl -fSL -o /app/models/UVR_MDXNET_KARA.onnx \
    "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR_MDXNET_KARA.onnx" && \
    echo "Model: $(du -h /app/models/UVR_MDXNET_KARA.onnx | cut -f1)"

COPY backend/ ./
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN echo '#!/bin/sh\nexec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000
CMD ["/bin/sh", "/app/start.sh"]
