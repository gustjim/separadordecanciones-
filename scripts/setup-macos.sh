#!/bin/bash
set -e

echo "========================================="
echo "  Separador Musical - Instalación macOS"
echo "========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "[1/7] Verificando Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "  Homebrew no encontrado. Instalando..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "  Homebrew encontrado: $(brew --version | head -1)"
fi

echo ""
echo "[2/7] Verificando Python..."
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1)
    echo "  $PY_VERSION"
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -lt 10 ]; then
        echo "  Python >= 3.10 requerido para Demucs. Instalando..."
        brew install python@3.11
    fi
else
    echo "  Python no encontrado. Instalando..."
    brew install python@3.11
fi

echo ""
echo "[3/7] Verificando Node.js..."
if ! command -v node &> /dev/null; then
    echo "  Node.js no encontrado. Instalando..."
    brew install node
else
    echo "  Node.js encontrado: $(node --version)"
fi

echo ""
echo "[4/7] Verificando FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "  FFmpeg no encontrado. Instalando..."
    brew install ffmpeg
else
    echo "  FFmpeg encontrado: $(ffmpeg -version 2>&1 | head -1)"
fi

echo ""
echo "[5/7] Creando entorno virtual e instalando dependencias Python..."
cd "$PROJECT_DIR/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pytest httpx --quiet
echo "  Dependencias Python instaladas."

echo ""
echo "[6/7] Instalando Demucs (puede tardar varios minutos)..."
pip install demucs --quiet
echo "  Demucs instalado."

echo ""
echo "[7/7] Instalando dependencias del frontend..."
cd "$PROJECT_DIR/frontend"
npm install
echo "  Dependencias del frontend instaladas."

echo ""
echo "========================================="
echo "  ¡Instalación completada!"
echo "========================================="
echo ""
echo "Para iniciar la aplicación:"
echo "  cd $PROJECT_DIR/scripts"
echo "  ./start-dev.sh"
echo ""
echo "O ejecuta directamente:"
echo "  Backend:  cd backend && source .venv/bin/activate && python run.py"
echo "  Frontend: cd frontend && npm run dev"
