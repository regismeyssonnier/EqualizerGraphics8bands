import numpy as np
import matplotlib.pyplot as plt
import sounddevice as sd
from threading import Lock
import time
import os
import subprocess
import tempfile
from scipy.io import wavfile

class EqualizerAudio:
    def __init__(self, file_path, sample_rate=44100):
        self.file_path = file_path
        self.sample_rate = sample_rate
        self.smooth_factor = 0.5
        
        # Les 8 bandes
        self.band_centers = np.array([62, 125, 250, 500, 1000, 2000, 4000, 8000])
        self.band_labels = ['62', '125', '250', '500', '1k', '2k', '4k', '8k']
        self.n_bands = len(self.band_centers)
        self.gains = np.zeros(self.n_bands)
        
        # Chargement du fichier
        self.audio_data, self.sample_rate_original = self.load_audio(file_path)
        print(f"✅ Fichier chargé : {file_path}")
        print(f"   Durée : {len(self.audio_data) / self.sample_rate_original:.2f} secondes")
        print(f"   Fréquence d'échantillonnage : {self.sample_rate_original} Hz")
        
        # Si stéréo, on prend le premier canal
        if len(self.audio_data.shape) > 1:
            self.audio_data_mono = self.audio_data[:, 0]
        else:
            self.audio_data_mono = self.audio_data
        
        # Normalisation
        max_val = np.max(np.abs(self.audio_data_mono))
        if max_val > 0:
            self.audio_data_mono = self.audio_data_mono / max_val * 0.95
        print(f"   Niveau max du signal : {20 * np.log10(max_val + 1e-12):.1f} dB")
        
        # Paramètres d'analyse
        self.buffer_size = 4096
        self.hop_size = 2048
        self.position = 0
        self.running = False
        self.paused = False
        self.smoothed_amplitudes = np.zeros(self.n_bands)
        self.lock = Lock()
        
        # Pour la lecture audio
        self.stream = None
        self.volume = 0.8
        
        # Filtres pour l'égalisation en temps réel
        self.filters = self.create_filters()
        
    def create_filters(self):
        """Crée des filtres passe-bande pour chaque fréquence"""
        filters = []
        for center in self.band_centers:
            # Filtre simple : coefficient pour une approximation rapide
            filters.append(1.0)
        return filters
    
    def load_audio(self, file_path):
        """Charge un fichier audio"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(file_path)
            samples = np.array(audio.get_array_of_samples())
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            samples = samples.astype(np.float32) / 32768.0
            return samples, audio.frame_rate
        except ImportError:
            print("⚠️ pydub non installé, utilisation de ffmpeg...")
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
            
            cmd = [
                'ffmpeg', '-i', file_path,
                '-ar', str(self.sample_rate),
                '-ac', '1',
                '-f', 'wav',
                '-y',
                tmp_path
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            sample_rate, data = wavfile.read(tmp_path)
            os.unlink(tmp_path)
            
            if data.dtype == np.int16:
                data = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32:
                data = data.astype(np.float32) / 2147483648.0
            else:
                data = data.astype(np.float32)
            
            return data, sample_rate
            
        except FileNotFoundError:
            raise RuntimeError("❌ ffmpeg n'est pas installé !")
    
    def apply_gain_to_audio(self, audio_block):
        """
        Applique les gains au bloc audio en temps réel
        C'est le coeur de l'égaliseur !
        """
        if len(audio_block) == 0 or np.all(self.gains == 0):
            return audio_block
        
        # FFT du bloc
        fft = np.fft.rfft(audio_block)
        freqs = np.fft.rfftfreq(len(audio_block), 1/self.sample_rate_original)
        
        # Application des gains par bande
        for i, center in enumerate(self.band_centers):
            # Bande d'une octave
            ratio = 2.0 ** (1.0/2.0)
            f_min = center / ratio
            f_max = center * ratio
            
            # Trouver les fréquences dans cette bande
            mask = (freqs >= f_min) & (freqs <= f_max)
            
            # Conversion dB → facteur linéaire
            gain_factor = 10 ** (self.gains[i] / 20)
            
            # Appliquer le gain
            fft[mask] *= gain_factor
        
        # Retour au domaine temporel
        audio_equalized = np.fft.irfft(fft)
        
        # Ajuster la longueur (peut varier légèrement)
        if len(audio_equalized) > len(audio_block):
            audio_equalized = audio_equalized[:len(audio_block)]
        elif len(audio_equalized) < len(audio_block):
            audio_equalized = np.pad(audio_equalized, (0, len(audio_block) - len(audio_equalized)))
        
        return audio_equalized
    
    def fft_to_bands(self, audio_segment):
        """Analyse le segment pour l'affichage (sans appliquer les gains)"""
        if len(audio_segment) == 0:
            return np.zeros(self.n_bands)
        
        window = np.hanning(len(audio_segment))
        audio_windowed = audio_segment * window
        
        fft_data = np.fft.rfft(audio_windowed)
        fft_freqs = np.fft.rfftfreq(len(audio_windowed), 1/self.sample_rate_original)
        
        power = np.abs(fft_data) ** 2
        power_db = 10 * np.log10(power + 1e-12)
        power_db = power_db - 10 * np.log10(len(audio_segment))
        
        band_amplitudes = []
        for center in self.band_centers:
            ratio = 2.0 ** (1.0/2.0)
            f_min = center / ratio
            f_max = center * ratio
            mask = (fft_freqs >= f_min) & (fft_freqs <= f_max)
            
            if np.any(mask):
                band_amp = np.mean(power_db[mask])
            else:
                band_amp = -80.0
            
            # Afficher le gain appliqué (pour le visuel)
            band_idx = np.where(self.band_centers == center)[0][0]
            band_amp += self.gains[band_idx]
            
            band_amplitudes.append(band_amp)
        
        return np.array(band_amplitudes)
    
    def smooth(self, new_amplitudes):
        self.smoothed_amplitudes = (
            self.smoothed_amplitudes * 0.5 + 
            new_amplitudes * 0.5
        )
        return self.smoothed_amplitudes
    
    def audio_callback(self, outdata, frames, time, status):
        """Callback audio avec égalisation EN TEMPS REEL"""
        if self.paused or not self.running:
            outdata.fill(0)
            return
        
        start = self.position
        end = start + frames
        
        if end >= len(self.audio_data_mono):
            remaining = len(self.audio_data_mono) - start
            if remaining > 0:
                segment = self.audio_data_mono[start:len(self.audio_data_mono)] * self.volume
                # === APPLICATION DES GAINS SUR LE SON ===
                segment_eq = self.apply_gain_to_audio(segment)
                outdata[:remaining, 0] = segment_eq
                outdata[remaining:, 0] = 0
            else:
                outdata.fill(0)
            self.position = 0
            return
        
        segment = self.audio_data_mono[start:end] * self.volume
        
        # === APPLICATION DES GAINS SUR LE SON ===
        segment_eq = self.apply_gain_to_audio(segment)
        
        if len(segment_eq) < frames:
            outdata[:len(segment_eq), 0] = segment_eq
            outdata[len(segment_eq):, 0] = 0
        else:
            outdata[:, 0] = segment_eq
        
        self.position = end
        
        # Analyse pour l'affichage (UNIQUEMENT visuel)
        if self.position % self.hop_size < frames:
            analysis_start = max(0, self.position - self.buffer_size)
            analysis_segment = self.audio_data_mono[analysis_start:self.position]
            if len(analysis_segment) < self.buffer_size:
                analysis_segment = np.pad(analysis_segment, (0, self.buffer_size - len(analysis_segment)))
            else:
                analysis_segment = analysis_segment[-self.buffer_size:]
            
            # On analyse le son ORIGINAL (sans les gains) pour l'affichage
            # MAIS on ajoute les gains visuellement pour voir l'effet
            amplitudes = self.fft_to_bands(analysis_segment)
            with self.lock:
                self.smoothed_amplitudes = self.smooth(amplitudes)
    
    def get_amplitudes(self):
        with self.lock:
            return self.smoothed_amplitudes.copy()
    
    def set_gain(self, band_idx, value):
        with self.lock:
            self.gains[band_idx] = np.clip(value, -60, 60)
            print(f"🔊 Gain {self.band_labels[band_idx]} = {self.gains[band_idx]:+.1f} dB")
    
    def start_playback(self):
        self.running = True
        self.paused = False
        self.position = 0
        
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate_original,
            channels=1,
            callback=self.audio_callback,
            blocksize=1024
        )
        self.stream.start()
        print("🔊 Lecture en cours...")
        print("   🔹 Glissez les barres pour modifier le son")
        print("   🔹 Molette souris pour le volume")
        print("   🔹 Cliquez 'Pause' pour arrêter/reprendre")
    
    def stop_playback(self):
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        print("⏹️ Lecture arrêtée")
    
    def toggle_pause(self):
        self.paused = not self.paused
        print("⏸️ Pause" if self.paused else "▶️ Reprise")
    
    def apply_equalization(self, output_path=None):
        """Exporte le fichier avec les gains appliqués"""
        print("\n🎵 Exportation du fichier égalisé...")
        print(f"   Gains appliqués : {self.gains.round(1)} dB")
        
        audio = self.audio_data_mono.copy()
        block_size = 8192
        hop_size = 4096
        output = np.zeros(len(audio))
        
        for start in range(0, len(audio), hop_size):
            end = min(start + block_size, len(audio))
            block = audio[start:end]
            
            if len(block) < block_size:
                block = np.pad(block, (0, block_size - len(block)))
            
            # Appliquer les gains
            fft = np.fft.rfft(block)
            freqs = np.fft.rfftfreq(len(block), 1/self.sample_rate_original)
            
            for i, center in enumerate(self.band_centers):
                ratio = 2.0 ** (1.0/2.0)
                f_min = center / ratio
                f_max = center * ratio
                mask = (freqs >= f_min) & (freqs <= f_max)
                gain_factor = 10 ** (self.gains[i] / 20)
                fft[mask] *= gain_factor
            
            block_eq = np.fft.irfft(fft)
            block_eq = block_eq[:min(block_size, end-start)]
            
            if start == 0:
                output[start:end] = block_eq
            else:
                overlap = min(hop_size, len(block_eq))
                output[start:start+overlap] += block_eq[:overlap] * 0.5
                if len(block_eq) > overlap:
                    output[start+overlap:end] = block_eq[overlap:]
        
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * 0.95
        
        if output_path is None:
            base, ext = os.path.splitext(self.file_path)
            output_path = f"{base}_equalized.wav"
        
        output_int16 = (output * 32767).astype(np.int16)
        wavfile.write(output_path, self.sample_rate_original, output_int16)
        print(f"✅ Fichier sauvegardé : {output_path}")
        return output_path


def afficher_equaliseur_audio(file_path):
    """Affiche l'égaliseur avec lecture audio ET son modifié"""
    
    eq = EqualizerAudio(file_path)
    eq.start_playback()
    
    plt.ion()
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor('#0a0a0a')
    ax.set_facecolor('#1a1a1a')
    
    x = np.arange(eq.n_bands)
    width = 0.7
    
    bars = ax.bar(x, np.zeros(eq.n_bands), 
                  color='#0066ff', alpha=0.85, width=width,
                  edgecolor='white', linewidth=0.5)
    
    ax.set_ylim(-60, 60)
    ax.set_ylabel('Amplitude (dB)', color='white', fontsize=12)
    ax.axhline(y=0, color='white', alpha=0.3, linestyle='-', linewidth=1)
    
    for y in range(-60, 7, 6):
        ax.axhline(y=y, color='gray', alpha=0.1, linestyle='--', linewidth=0.5)
        if y % 12 == 0:
            ax.text(-0.8, y, f'{y}', color='gray', fontsize=7, ha='right', va='center')
    
    ax.set_xticks(x)
    ax.set_xticklabels(eq.band_labels, color='white', fontsize=12, fontweight='bold')
    ax.set_xlabel('Fréquence (Hz)', color='white', fontsize=12)
    ax.set_title(f'🎵 Égaliseur - {os.path.basename(file_path)}', 
                 color='white', fontsize=14, pad=20)
    
    ax.tick_params(axis='both', colors='white')
    for spine in ax.spines.values():
        spine.set_color('white')
        spine.set_alpha(0.3)
    
    gain_texts = []
    for i in range(eq.n_bands):
        txt = ax.text(i, -55, f'0 dB', 
                     color='white', fontsize=8, fontweight='bold',
                     ha='center', va='bottom')
        gain_texts.append(txt)
    
    info_text = ax.text(0.02, 0.95, '', transform=ax.transAxes, 
                        color='white', fontsize=11, fontweight='bold',
                        verticalalignment='top')
    
    pause_text = ax.text(0.98, 0.95, '⏸️ Pause', transform=ax.transAxes,
                         color='#ffcc00', fontsize=11, fontweight='bold',
                         verticalalignment='top', ha='right',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor='#ffcc00'))
    
    export_text = ax.text(0.98, 0.87, '💾 Exporter', transform=ax.transAxes,
                         color='#00ff00', fontsize=11, fontweight='bold',
                         verticalalignment='top', ha='right',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor='green'))
    
    volume_text = ax.text(0.02, 0.05, f'🔊 Volume: {int(eq.volume * 100)}%', transform=ax.transAxes,
                          color='white', fontsize=10,
                          verticalalignment='bottom')
    
    drag_data = {'index': None, 'start_y': None, 'start_gain': None}
    
    def on_press(event):
        if event.inaxes != ax:
            return
        
        if pause_text.contains(event)[0]:
            eq.toggle_pause()
            pause_text.set_text('▶️ Lecture' if eq.paused else '⏸️ Pause')
            fig.canvas.draw_idle()
            return
        
        if export_text.contains(event)[0]:
            eq.apply_equalization()
            return
        
        for i, bar in enumerate(bars):
            if bar.contains(event)[0]:
                drag_data['index'] = i
                drag_data['start_y'] = event.ydata
                drag_data['start_gain'] = eq.gains[i]
                bar.set_edgecolor('yellow')
                bar.set_linewidth(2)
                fig.canvas.draw_idle()
                break
    
    def on_motion(event):
        if drag_data['index'] is None or event.inaxes != ax:
            return
        delta_y = event.ydata - drag_data['start_y']
        new_gain = np.clip(drag_data['start_gain'] + delta_y, -60, 60)
        idx = drag_data['index']
        eq.set_gain(idx, new_gain)
        gain_texts[idx].set_text(f'{new_gain:+.1f} dB')
        y_pos = max(-55, new_gain - 2)
        gain_texts[idx].set_position((idx, y_pos))
        fig.canvas.draw_idle()
    
    def on_release(event):
        if drag_data['index'] is not None:
            bars[drag_data['index']].set_edgecolor('white')
            bars[drag_data['index']].set_linewidth(0.5)
            fig.canvas.draw_idle()
            drag_data['index'] = None
    
    def on_scroll(event):
        if event.inaxes != ax:
            return
        if event.button == 'up':
            eq.volume = min(1.5, eq.volume + 0.1)
        elif event.button == 'down':
            eq.volume = max(0.1, eq.volume - 0.1)
        volume_text.set_text(f'🔊 Volume: {int(eq.volume * 100)}%')
        fig.canvas.draw_idle()
    
    fig.canvas.mpl_connect('button_press_event', on_press)
    fig.canvas.mpl_connect('motion_notify_event', on_motion)
    fig.canvas.mpl_connect('button_release_event', on_release)
    fig.canvas.mpl_connect('scroll_event', on_scroll)
    
    fig.canvas.draw()
    fig.canvas.flush_events()
    
    try:
        while True:
            amplitudes = eq.get_amplitudes()
            amplitudes_clipped = np.clip(amplitudes, -60, 60)
            
            for i, (bar, amp) in enumerate(zip(bars, amplitudes_clipped)):
                if amp > 0:
                    color = '#ff0000'
                elif amp > -6:
                    color = '#ff4400'
                elif amp > -12:
                    color = '#ff8800'
                elif amp > -18:
                    color = '#ffcc00'
                elif amp > -24:
                    color = '#66ff66'
                elif amp > -30:
                    color = '#00ddff'
                elif amp > -40:
                    color = '#0099ff'
                elif amp > -50:
                    color = '#0066cc'
                else:
                    color = '#003366'
                
                bar.set_color(color)
                bar.set_height(amp)
            
            max_level = np.max(amplitudes_clipped)
            position_sec = eq.position / eq.sample_rate_original
            total_sec = len(eq.audio_data_mono) / eq.sample_rate_original
            gains_str = ' '.join([f'{g:+.1f}' for g in eq.gains])
            
            status = "⏸️ PAUSE" if eq.paused else "▶️ LECTURE"
            info_text.set_text(
                f'{status} | Peak: {max_level:.1f} dB\n'
                f'⏱️ {position_sec:.1f}s / {total_sec:.1f}s\n'
                f'Gains: {gains_str} dB'
            )
            
            fig.canvas.draw_idle()
            plt.pause(0.05)
            
    except KeyboardInterrupt:
        print("\nArrêt demandé...")
    finally:
        eq.stop_playback()
        plt.ioff()
        plt.close(fig)


# --------------------------------------------------------------
# MAIN
# --------------------------------------------------------------

if __name__ == "__main__":
    # Recherche automatique de fichiers audio
    audio_files = []
    for f in os.listdir('.'):
        if f.endswith(('.wav', '.WAV', '.mp3', '.MP3', '.flac', '.FLAC', '.m4a', '.M4A')):
            audio_files.append(f)
    
    if not audio_files:
        print("❌ Aucun fichier audio trouvé.")
        print("\nGénération d'un fichier test...")
        
        sr = 44100
        duration = 10
        t = np.linspace(0, duration, int(sr * duration))
        signal = (
            0.5 * np.sin(2 * np.pi * 62 * t) +
            0.3 * np.sin(2 * np.pi * 250 * t) +
            0.4 * np.sin(2 * np.pi * 1000 * t) +
            0.2 * np.sin(2 * np.pi * 4000 * t)
        )
        signal = signal / np.max(np.abs(signal))
        wavfile.write('test_audio.wav', sr, (signal * 32767).astype(np.int16))
        print("✅ test_audio.wav créé !")
        audio_files = ['test_audio.wav']
    
    print("🎵 ÉGALISEUR AUDIO - TEMPS REEL")
    print("=" * 60)
    print("Fichiers disponibles :")
    for i, f in enumerate(audio_files):
        size = os.path.getsize(f) / (1024 * 1024)
        print(f"   {i+1}. {f} ({size:.1f} MB)")
    print("=" * 60)
    
    choice = input("Choisissez un fichier (numéro) : ")
    
    try:
        idx = int(choice) - 1
        file_path = audio_files[idx] if 0 <= idx < len(audio_files) else audio_files[0]
    except:
        file_path = audio_files[0]
    
    print(f"\n📁 Fichier : {file_path}")
    print("=" * 60)
    print("1. Mode interactif (LE SON CHANGE EN TEMPS REEL !)")
    print("2. Analyse rapide")
    print("3. Exporter le fichier égalisé")
    print("=" * 60)
    
    mode = input("Option (1-3) : ").strip()
    
    if mode == '1':
        afficher_equaliseur_audio(file_path)
    elif mode == '2':
        eq = EqualizerAudio(file_path)
        quick_analyze(eq)
    elif mode == '3':
        eq = EqualizerAudio(file_path)
        eq.set_gain(0, 3)
        eq.set_gain(1, 2)
        eq.set_gain(6, -2)
        eq.set_gain(7, -3)
        eq.apply_equalization()
    else:
        print("Option invalide")