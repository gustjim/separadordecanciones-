# Separador Musical

Aplicación web local para separar la voz y los instrumentos de archivos musicales utilizando inteligencia artificial (Demucs HTDemucs de Meta AI Research).

## Características

- Separación en 2 pistas: voz + instrumental
- Separación en 4 pistas: voz, batería, bajo, otros instrumentos
- Interfaz web moderna y responsiva
- Mezclador sincronizado para escuchar todas las pistas simultáneamente
- Controles individuales de volumen y silencio por pista
- Descarga individual y masiva (ZIP) de pistas
- Soporte para MP3, WAV, FLAC, M4A, AAC, OGG
- Conversión WAV → MP3 opcional vía FFmpeg

## Requisitos

- Python 3.10+
- Node.js 18+
- FFmpeg
- Demucs (`pip install demucs`)
- ~2 GB de espacio en disco (modelos de Demucs + PyTorch)

## Instalación en macOS

```bash
# Opción 1: Script automático
chmod +x scripts/setup-macos.sh
./scripts/setup-macos.sh

# Opción 2: Manual
brew install python@3.11 node ffmpeg
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install demucs
cd ../frontend
npm install
```

## Instalación en Linux

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip nodejs npm ffmpeg

cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install demucs

cd ../frontend
npm install
```

## Instalación en Windows

1. Instalar Python 3.11+ desde [python.org](https://python.org)
2. Instalar Node.js desde [nodejs.org](https://nodejs.org)
3. Instalar FFmpeg y agregarlo al PATH
4. Ejecutar:
```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install demucs

cd ..\frontend
npm install
```

## Ejecución

### Opción 1: Script combinado
```bash
chmod +x scripts/start-dev.sh
./scripts/start-dev.sh
```

### Opción 2: Manual (dos terminales)

Terminal 1 - Backend:
```bash
cd backend
source .venv/bin/activate
python run.py
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

Abrir http://localhost:5173 en el navegador.

## Verificar que funciona

### FFmpeg
```bash
ffmpeg -version
# Debe mostrar la versión instalada
```

### Demucs
```bash
python -m demucs --help
# Debe mostrar la ayuda de Demucs
```

### Salud del servidor
```bash
curl http://localhost:8000/api/health
# Debe retornar: {"status":"ok",...}
```

## Arquitectura

```
separador-musical/
├── frontend/          # Vite + JavaScript vanilla
│   ├── index.html
│   ├── src/
│   │   ├── main.js        # Orquestación UI
│   │   ├── api.js          # Cliente HTTP + SSE
│   │   ├── audio-player.js # Gestión de reproductores
│   │   ├── mixer.js        # Mezclador sincronizado
│   │   └── styles.css      # Estilos responsivos
│   ├── package.json
│   └── vite.config.js
├── backend/           # FastAPI + Python
│   ├── app/
│   │   ├── main.py         # App FastAPI, CORS, lifespan
│   │   ├── config.py       # Configuración
│   │   ├── models.py       # Modelos Pydantic
│   │   ├── routes.py       # Endpoints REST
│   │   ├── jobs.py         # Gestión de trabajos
│   │   ├── separator.py    # Wrapper Demucs
│   │   ├── audio_utils.py  # FFmpeg utilities
│   │   ├── security.py     # Validación y sanitización
│   │   └── cleanup.py      # Limpieza de temporales
│   ├── tests/              # Pruebas automatizadas
│   ├── requirements.txt
│   └── run.py
├── scripts/
│   ├── setup-macos.sh
│   ├── start-dev.sh
│   └── start-dev.command
├── docker-compose.yml
├── README.md
└── LICENSE
```

## API REST

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/health` | Estado del servidor y dependencias |
| POST | `/api/jobs` | Subir archivo y crear trabajo |
| GET | `/api/jobs/{id}` | Estado de un trabajo |
| GET | `/api/jobs/{id}/tracks` | Lista de pistas generadas |
| GET | `/api/jobs/{id}/tracks/{name}` | Descargar pista individual |
| GET | `/api/jobs/{id}/download-all` | Descargar todas las pistas (ZIP) |
| DELETE | `/api/jobs/{id}` | Eliminar trabajo y archivos |

## Estados de un trabajo

1. `recibido` - Archivo recibido
2. `validando_audio` - Validando formato
3. `preparando_audio` - Analizando audio
4. `separando_pistas` - Ejecutando Demucs
5. `convirtiendo_resultados` - Convirtiendo a MP3 (opcional)
6. `creando_zip` - Empaquetando descarga
7. `completado` - Listo
8. `error` - Error durante procesamiento

## Formatos

**Entrada:** MP3, WAV, FLAC, M4A, AAC, OGG
**Salida:** WAV (predeterminado) o MP3

## Limitaciones

- **Sin GPU:** La separación en CPU es significativamente más lenta (~1.5x la duración de la canción)
- **Archivos grandes:** Canciones de más de 10 minutos pueden tardar varios minutos en procesarse
- **Memoria:** Archivos muy largos pueden requerir segmentación (`--segment`)
- **FFmpeg/Demucs:** Sin estas dependencias la separación no funcionará (detectable vía `/api/health`)

## Solución de errores

### "FFmpeg no encontrado"
```bash
brew install ffmpeg    # macOS
sudo apt install ffmpeg  # Linux
```

### "Demucs no encontrado"
```bash
pip install demucs
```

### Error de memoria durante separación
Usar un modelo más pequeño o reducir el segmento:
```bash
demucs -n mdx_q --segment 7 song.mp3
```

### Python 3.9 o inferior
Demucs 4.x requiere Python 3.10+. Actualizar:
```bash
brew install python@3.11
```

## Cómo detener la aplicación

Presiona `Ctrl+C` en la terminal donde se ejecuta el script, o cierra ambas terminales.

## Eliminar archivos temporales

```bash
rm -rf backend/temp_uploads/* backend/temp_jobs/*
```

Los archivos se eliminan automáticamente después de 2 horas.

## Aviso

Solo procese archivos de audio propios o para los que tenga autorización. Esta aplicación no descarga contenido de YouTube, Spotify ni otras plataformas.

## Licencia

MIT License. El modelo Demucs está licenciado bajo MIT por Meta AI Research.
