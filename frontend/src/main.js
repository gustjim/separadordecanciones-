import { checkHealth, createJob, createJobFromUrl, getTrackDownloadUrl, getDownloadAllUrl, pollJobStatus } from './api.js';
import { AudioPlayerManager } from './audio-player.js';
import { Mixer } from './mixer.js';

const STEP_ORDER = [
  { key: 'recibido', label: 'Archivo recibido' },
  { key: 'validando_audio', label: 'Validando audio' },
  { key: 'preparando_audio', label: 'Preparando audio' },
  { key: 'separando_pistas', label: 'Separando pistas' },
  { key: 'convirtiendo_resultados', label: 'Convirtiendo resultados' },
  { key: 'creando_zip', label: 'Creando archivo ZIP' },
  { key: 'completado', label: 'Proceso completado' },
];

const STEM_LABELS = {
  vocals: 'Voz',
  drums: 'Bateria',
  bass: 'Bajo',
  piano: 'Piano',
  other: 'Otros instrumentos',
  no_vocals: 'Instrumental',
  accompaniment: 'Instrumental',
};

let currentFile = null;
let currentJobId = null;
let stopPolling = null;
let currentObjectURL = null;
let currentMode = 'file';
const playerManager = new AudioPlayerManager();
let mixer = null;

const dom = {
  dropZone: document.getElementById('drop-zone'),
  fileInput: document.getElementById('file-input'),
  uploadSection: document.getElementById('upload-section'),
  fileInfo: document.getElementById('file-info'),
  fileName: document.getElementById('file-name'),
  fileDetails: document.getElementById('file-details'),
  removeFile: document.getElementById('remove-file'),
  originalPlayer: document.getElementById('original-player'),
  optionsSection: document.getElementById('options-section'),
  modeSelect: document.getElementById('mode-select'),
  formatSelect: document.getElementById('format-select'),
  separateBtn: document.getElementById('separate-btn'),
  progressSection: document.getElementById('progress-section'),
  progressMessage: document.getElementById('progress-message'),
  progressSteps: document.getElementById('progress-steps'),
  errorSection: document.getElementById('error-section'),
  errorMessage: document.getElementById('error-message'),
  retryBtn: document.getElementById('retry-btn'),
  resultsSection: document.getElementById('results-section'),
  tracksContainer: document.getElementById('tracks-container'),
  downloadAllBtn: document.getElementById('download-all-btn'),
  newSongBtn: document.getElementById('new-song-btn'),
  healthBanner: document.getElementById('health-banner'),
  healthText: document.getElementById('health-text'),
  mixerControls: document.getElementById('mixer-controls'),
  urlInput: document.getElementById('url-input'),
  urlSubmitBtn: document.getElementById('url-submit-btn'),
  urlError: document.getElementById('url-error'),
};

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

async function checkServerHealth() {
  try {
    const health = await checkHealth();
    const missing = [];
    if (!health.ffmpeg_available) missing.push('FFmpeg');
    if (!health.demucs_available) missing.push('Demucs');

    if (missing.length > 0) {
      dom.healthBanner.style.display = 'block';
      dom.healthBanner.className = 'health-banner warning';
      dom.healthText.textContent = `Dependencias faltantes: ${missing.join(', ')}. La separacion no funcionara sin ellas.`;
    } else {
      dom.healthBanner.style.display = 'block';
      dom.healthBanner.className = 'health-banner';
      const urlStatus = health.ytdlp_available ? '' : ' (URLs no disponibles - falta yt-dlp)';
      const spleeterStatus = health.spleeter_available ? '' : ' (5 pistas no disponible - falta spleeter)';
      dom.healthText.textContent = `Servidor activo. Python ${health.python_version}. Espacio disponible: ${health.disk_space_mb.toFixed(0)} MB${urlStatus}${spleeterStatus}`;
      if (health.url_download_enabled === false) {
        const urlSection = document.querySelector('.url-divider');
        const urlInputGroup = document.querySelector('.url-input-group');
        if (urlSection) urlSection.style.display = 'none';
        if (urlInputGroup) urlInputGroup.style.display = 'none';
      }
    }
  } catch {
    dom.healthBanner.style.display = 'block';
    dom.healthBanner.className = 'health-banner error';
    dom.healthText.textContent = 'No se pudo conectar con el servidor backend. Asegúrese de que está ejecutándose en el puerto 8000.';
  }
}

function showSection(section) {
  [dom.uploadSection, dom.fileInfo, dom.optionsSection, dom.progressSection, dom.errorSection, dom.resultsSection].forEach(s => {
    s.style.display = 'none';
  });
  if (section) section.style.display = 'block';
}

function handleFileSelect(file) {
  if (!file) return;
  currentFile = file;

  dom.fileName.textContent = file.name;
  const sizeStr = formatSize(file.size);
  dom.fileDetails.textContent = `${sizeStr}`;

  if (currentObjectURL) URL.revokeObjectURL(currentObjectURL);
  currentObjectURL = URL.createObjectURL(file);
  dom.originalPlayer.src = currentObjectURL;

  dom.originalPlayer.onloadedmetadata = () => {
    const duration = formatDuration(dom.originalPlayer.duration);
    dom.fileDetails.textContent = `${sizeStr} · ${duration}`;
  };

  showSection(dom.fileInfo);
  dom.fileInfo.style.display = 'block';
  dom.optionsSection.style.display = 'block';
  dom.uploadSection.style.display = 'none';
}

function resetUI() {
  currentFile = null;
  currentJobId = null;
  currentMode = 'file';
  if (stopPolling) stopPolling();
  stopPolling = null;
  if (currentObjectURL) { URL.revokeObjectURL(currentObjectURL); currentObjectURL = null; }
  dom.originalPlayer.src = '';
  dom.tracksContainer.innerHTML = '';
  dom.progressSteps.innerHTML = '';
  dom.mixerControls.style.display = 'none';
  dom.urlInput.value = '';
  dom.urlError.style.display = 'none';
  showSection(dom.uploadSection);
  dom.uploadSection.style.display = 'block';
  dom.optionsSection.style.display = 'block';
}

function renderProgressSteps(status) {
  const currentIdx = STEP_ORDER.findIndex(s => s.key === status);
  dom.progressSteps.innerHTML = STEP_ORDER.map((step, i) => {
    let cls = 'progress-step';
    if (i < currentIdx) cls += ' done';
    else if (i === currentIdx) cls += ' active';
    return `<div class="${cls}"><span class="progress-step-dot"></span>${step.label}</div>`;
  }).join('');
}

function renderResults(jobData) {
  showSection(dom.resultsSection);
  dom.resultsSection.style.display = 'block';
  dom.tracksContainer.innerHTML = '';

  const audioElements = [];

  for (const track of jobData.tracks) {
    const card = document.createElement('div');
    const labelKey = track.name.replace('minus_', '');
    card.className = `track-card track-label-${labelKey}`;
    card.dataset.trackName = track.name;

    const displayName = STEM_LABELS[track.name] || track.name;
    const downloadUrl = getTrackDownloadUrl(currentJobId, track.name);

    card.innerHTML = `
      <div class="track-header">
        <span class="track-name">${displayName}</span>
        <span class="track-meta">${formatDuration(track.duration_seconds)} · ${formatSize(track.size_bytes)}</span>
      </div>
      <audio class="track-player" controls preload="metadata"></audio>
      <div class="track-controls">
        <div class="volume-control">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
          </svg>
          <input type="range" class="volume-slider" min="0" max="1" step="0.01" value="1" data-track="${track.name}" />
        </div>
        <button class="btn-download" data-url="${downloadUrl}" data-filename="${track.filename}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Descargar
        </button>
      </div>
    `;

    dom.tracksContainer.appendChild(card);

    const audio = card.querySelector('audio');
    audio.src = downloadUrl;
    audioElements.push(audio);

    audio.addEventListener('loadedmetadata', () => {
      const meta = card.querySelector('.track-meta');
      meta.textContent = `${formatDuration(audio.duration)} · ${formatSize(track.size_bytes)}`;
    });

    const slider = card.querySelector('.volume-slider');
    slider.addEventListener('input', (e) => {
      audio.volume = parseFloat(e.target.value);
    });

    const dlBtn = card.querySelector('.btn-download');
    dlBtn.addEventListener('click', () => {
      const a = document.createElement('a');
      a.href = dlBtn.dataset.url;
      a.download = dlBtn.dataset.filename;
      a.click();
    });
  }

  if (audioElements.length > 1) {
    dom.mixerControls.style.display = 'block';
    if (!mixer) mixer = new Mixer(playerManager);
    mixer.setTracks(audioElements);
  }
}

async function startSeparation() {
  if (!currentFile) return;

  showSection(dom.progressSection);
  dom.progressSection.style.display = 'block';
  dom.separateBtn.disabled = true;

  renderProgressSteps('recibido');
  dom.progressMessage.textContent = 'Subiendo archivo...';

  try {
    const job = await createJob(
      currentFile,
      dom.modeSelect.value,
      dom.formatSelect.value
    );

    currentJobId = job.job_id;
    renderProgressSteps(job.status);
    dom.progressMessage.textContent = job.progress_message;

    stopPolling = pollJobStatus(currentJobId, (data) => {
      renderProgressSteps(data.status);
      dom.progressMessage.textContent = data.progress_message;

      if (data.status === 'completado') {
        dom.progressMessage.textContent = 'Proceso completado. Cargando resultados...';
        setTimeout(() => renderResults(data), 500);
        dom.separateBtn.disabled = false;
      }

      if (data.status === 'error') {
        showSection(dom.errorSection);
        dom.errorSection.style.display = 'block';
        dom.errorMessage.textContent = data.error_message || 'Error desconocido durante el procesamiento.';
        dom.separateBtn.disabled = false;
      }
    });

  } catch (err) {
    showSection(dom.errorSection);
    dom.errorSection.style.display = 'block';
    dom.errorMessage.textContent = err.message;
    dom.separateBtn.disabled = false;
  }
}

async function startSeparationFromUrl() {
  const url = dom.urlInput.value.trim();
  if (!url) return;

  dom.urlError.style.display = 'none';
  dom.urlSubmitBtn.disabled = true;

  showSection(dom.progressSection);
  dom.progressSection.style.display = 'block';

  renderProgressSteps('recibido');
  dom.progressMessage.textContent = 'Descargando audio desde la URL...';

  try {
    const job = await createJobFromUrl(
      url,
      dom.modeSelect.value,
      dom.formatSelect.value
    );

    currentJobId = job.job_id;
    currentMode = 'url';
    renderProgressSteps(job.status);
    dom.progressMessage.textContent = job.progress_message;

    stopPolling = pollJobStatus(currentJobId, (data) => {
      renderProgressSteps(data.status);
      dom.progressMessage.textContent = data.progress_message;

      if (data.status === 'completado') {
        dom.progressMessage.textContent = 'Proceso completado. Cargando resultados...';
        setTimeout(() => renderResults(data), 500);
        dom.urlSubmitBtn.disabled = false;
      }

      if (data.status === 'error') {
        showSection(dom.errorSection);
        dom.errorSection.style.display = 'block';
        dom.errorMessage.textContent = data.error_message || 'Error desconocido durante el procesamiento.';
        dom.urlSubmitBtn.disabled = false;
      }
    });

  } catch (err) {
    showSection(dom.errorSection);
    dom.errorSection.style.display = 'block';
    dom.errorMessage.textContent = err.message;
    dom.urlSubmitBtn.disabled = false;
  }
}

dom.dropZone.addEventListener('click', () => dom.fileInput.click());

dom.dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dom.dropZone.classList.add('drag-over');
});

dom.dropZone.addEventListener('dragleave', () => {
  dom.dropZone.classList.remove('drag-over');
});

dom.dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dom.dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

dom.fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) handleFileSelect(file);
});

dom.removeFile.addEventListener('click', () => {
  currentFile = null;
  dom.originalPlayer.src = '';
  showSection(dom.uploadSection);
  dom.uploadSection.style.display = 'block';
  dom.fileInput.value = '';
});

dom.separateBtn.addEventListener('click', startSeparation);

dom.urlSubmitBtn.addEventListener('click', startSeparationFromUrl);

dom.urlInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') startSeparationFromUrl();
});

dom.retryBtn.addEventListener('click', () => {
  showSection(dom.uploadSection);
  dom.uploadSection.style.display = 'block';
  dom.urlInput.value = '';
  dom.urlError.style.display = 'none';
  if (currentFile) {
    dom.optionsSection.style.display = 'block';
  }
});

dom.downloadAllBtn.addEventListener('click', () => {
  if (!currentJobId) return;
  const a = document.createElement('a');
  a.href = getDownloadAllUrl(currentJobId);
  a.download = 'pistas.zip';
  a.click();
});

dom.newSongBtn.addEventListener('click', resetUI);

checkServerHealth();
dom.optionsSection.style.display = 'block';
