const API_BASE = '/api';

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('No se pudo verificar el estado del servidor');
  return res.json();
}

export async function createJob(file, mode, outputFormat) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('mode', mode);
  formData.append('output_format', outputFormat);

  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Error al subir el archivo');
  }
  return data;
}

export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error('No se pudo obtener el estado del trabajo');
  return res.json();
}

export async function getJobTracks(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/tracks`);
  if (!res.ok) throw new Error('No se pudieron obtener las pistas');
  return res.json();
}

export function getTrackDownloadUrl(jobId, trackName) {
  return `${API_BASE}/jobs/${jobId}/tracks/${trackName}`;
}

export function getDownloadAllUrl(jobId) {
  return `${API_BASE}/jobs/${jobId}/download-all`;
}

export async function deleteJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' });
  return res.ok;
}

export async function createJobFromUrl(url, mode, outputFormat) {
  const formData = new FormData();
  formData.append('url', url);
  formData.append('mode', mode);
  formData.append('output_format', outputFormat);

  const res = await fetch(`${API_BASE}/jobs/url`, {
    method: 'POST',
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Error al procesar la URL');
  }
  return data;
}

export function pollJobStatus(jobId, onUpdate, interval = 1500) {
  let active = true;

  const poll = async () => {
    if (!active) return;
    try {
      const data = await getJobStatus(jobId);
      onUpdate(data);
      if (data.status !== 'error' && data.status !== 'completado') {
        setTimeout(poll, interval);
      }
    } catch {
      if (active) setTimeout(poll, interval * 2);
    }
  };

  poll();
  return () => { active = false; };
}
