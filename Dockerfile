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
    && rm -rf /var/lib/apt/lists/*

ENV DEMUCS_ENABLED="false"

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN python -c "from spleeter.separator import Separator; s = Separator('spleeter:2stems'); print('spleeter OK')"

RUN echo '#!/bin/sh\nexec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000
CMD ["/bin/sh", "/app/start.sh"]
