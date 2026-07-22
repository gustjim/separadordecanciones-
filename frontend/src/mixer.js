export class Mixer {
  constructor(playerManager, jobId) {
    this.playerManager = playerManager;
    this.jobId = jobId;
    this.isPlaying = false;
    this.isPaused = false;
    this.tracks = [];
    this.rafId = null;
    this.isDragging = false;

    this.playAllBtn = document.getElementById('mixer-play-all');
    this.pauseAllBtn = document.getElementById('mixer-pause-all');
    this.stopAllBtn = document.getElementById('mixer-stop-all');
    this.timeDisplay = document.getElementById('mixer-time');
    this.durationDisplay = document.getElementById('mixer-duration');
    this.progressBar = document.getElementById('mixer-progress-bar');
    this.progressFill = document.getElementById('mixer-progress-fill');

    this.playAllBtn.addEventListener('click', () => this.playAll());
    this.pauseAllBtn.addEventListener('click', () => this.pauseAll());
    this.stopAllBtn.addEventListener('click', () => this.stopAll());

    this.progressBar.addEventListener('click', (e) => this.seekFromEvent(e));
    this.progressBar.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.seekFromEvent(e);
      e.preventDefault();
    });
    document.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      this.seekFromEvent(e);
    });
    document.addEventListener('mouseup', () => { this.isDragging = false; });

    this.progressBar.addEventListener('touchstart', (e) => {
      this.isDragging = true;
      this.seekFromEvent(e.touches[0]);
      e.preventDefault();
    }, { passive: false });
    document.addEventListener('touchmove', (e) => {
      if (!this.isDragging) return;
      e.preventDefault();
      this.seekFromEvent(e.touches[0]);
    }, { passive: false });
    document.addEventListener('touchend', () => { this.isDragging = false; });
  }

  setTracks(audioElements) {
    this.tracks = audioElements;
    if (audioElements.length > 0) {
      const duration = audioElements[0].duration || 0;
      this.durationDisplay.textContent = this.formatTime(duration);
    }
  }

  playAll() {
    if (this.tracks.length === 0) return;

    let maxTime = 0;
    for (const audio of this.tracks) {
      if (audio.currentTime > maxTime) maxTime = audio.currentTime;
    }

    for (const audio of this.tracks) {
      if (audio.currentTime < maxTime) {
        audio.currentTime = maxTime;
      }
      audio.play().catch(() => {});
    }

    this.isPlaying = true;
    this.isPaused = false;
    this.playAllBtn.style.display = 'none';
    this.pauseAllBtn.style.display = 'inline-flex';
    this.startProgressUpdate();
  }

  pauseAll() {
    for (const audio of this.tracks) {
      audio.pause();
    }
    this.isPlaying = false;
    this.isPaused = true;
    this.playAllBtn.style.display = 'inline-flex';
    this.pauseAllBtn.style.display = 'none';
    this.stopProgressUpdate();
  }

  stopAll() {
    for (const audio of this.tracks) {
      audio.pause();
      audio.currentTime = 0;
    }
    this.isPlaying = false;
    this.isPaused = false;
    this.playAllBtn.style.display = 'inline-flex';
    this.pauseAllBtn.style.display = 'none';
    this.progressFill.style.width = '0%';
    this.timeDisplay.textContent = '0:00';
    this.stopProgressUpdate();
  }

  seekFromEvent(event) {
    if (this.tracks.length === 0) return;
    const rect = this.progressBar.getBoundingClientRect();
    const clientX = event.clientX || 0;
    let ratio = (clientX - rect.left) / rect.width;
    ratio = Math.max(0, Math.min(1, ratio));
    const duration = this.tracks[0].duration || 0;
    const seekTime = ratio * duration;

    for (const audio of this.tracks) {
      audio.currentTime = Math.min(seekTime, audio.duration || 0);
    }

    this.progressFill.style.width = `${ratio * 100}%`;
    this.timeDisplay.textContent = this.formatTime(seekTime);
  }

  startProgressUpdate() {
    this.stopProgressUpdate();
    const update = () => {
      if (!this.isPlaying) return;
      const currentTime = this.tracks[0]?.currentTime || 0;
      const duration = this.tracks[0]?.duration || 1;
      const progress = (currentTime / duration) * 100;

      this.progressFill.style.width = `${progress}%`;
      this.timeDisplay.textContent = this.formatTime(currentTime);
      this.durationDisplay.textContent = this.formatTime(duration);

      if (currentTime >= duration - 0.1) {
        this.stopAll();
        return;
      }

      this.rafId = requestAnimationFrame(update);
    };
    this.rafId = requestAnimationFrame(update);
  }

  stopProgressUpdate() {
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }
}
