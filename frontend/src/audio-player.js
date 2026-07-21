export class AudioPlayerManager {
  constructor() {
    this.players = new Map();
    this.mutedTracks = new Set();
  }

  registerPlayer(trackName, audioElement) {
    this.players.set(trackName, {
      element: audioElement,
      originalVolume: 1.0,
    });
  }

  unregisterPlayer(trackName) {
    this.players.delete(trackName);
    this.mutedTracks.delete(trackName);
  }

  setVolume(trackName, volume) {
    const player = this.players.get(trackName);
    if (player) {
      player.element.volume = volume;
      player.originalVolume = volume;
      if (volume > 0) this.mutedTracks.delete(trackName);
    }
  }

  toggleMute(trackName) {
    const player = this.players.get(trackName);
    if (!player) return false;

    if (this.mutedTracks.has(trackName)) {
      player.element.volume = player.originalVolume;
      this.mutedTracks.delete(trackName);
      return false;
    } else {
      this.mutedTracks.add(trackName);
      player.element.volume = 0;
      return true;
    }
  }

  isMuted(trackName) {
    return this.mutedTracks.has(trackName);
  }

  stopAll() {
    for (const [, player] of this.players) {
      player.element.pause();
      player.element.currentTime = 0;
    }
  }

  pauseAll() {
    for (const [, player] of this.players) {
      player.element.pause();
    }
  }
}
