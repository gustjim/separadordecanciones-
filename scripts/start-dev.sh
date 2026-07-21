#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

echo "Iniciando Separador Musical..."
echo ""

echo "[1/2] Iniciando backend (puerto 8000)..."
cd "$PROJECT_DIR/backend"
source .venv/bin/activate
python run.py &
BACKEND_PID=$!

echo "[2/2] Iniciando frontend (puerto 5173)..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================="
echo "  Separador Musical activo"
echo "========================================="
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo ""
echo "  Presiona Ctrl+C para detener"
echo "========================================="

cleanup() {
    echo ""
    echo "Deteniendo servidores..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo "Servidores detenidos."
}

trap cleanup EXIT INT TERM

wait
