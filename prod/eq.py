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

        # Paramètres de réverbération
        self.reverb_amount = 0.0  # 0.0 à 1.0
        self.reverb_type = 'room'  # 'room', 'hall', 'cathedral'
        self.reverb_damping = 0.5  # 0.0 à 1.0
        
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
        
    def reset(self, file_path, sample_rate=44100):
        self.file_path = file_path
        self.sample_rate = sample_rate
        self.smooth_factor = 0.5
        
        # Les 8 bandes
        self.band_centers = np.array([62, 125, 250, 500, 1000, 2000, 4000, 8000])
        self.band_labels = ['62', '125', '250', '500', '1k', '2k', '4k', '8k']
        self.n_bands = len(self.band_centers)
        self.gains = np.zeros(self.n_bands)

        # Paramètres de réverbération
        self.reverb_amount = 0.0  # 0.0 à 1.0
        self.reverb_type = 'room'  # 'room', 'hall', 'cathedral'
        self.reverb_damping = 0.5  # 0.0 à 1.0
        
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

    def apply_reverb(self, audio_block):
        """Applique la réverbération au bloc audio"""
        if self.reverb_amount == 0:
            return audio_block
        
        # Choisir le type de réverbération
        if self.reverb_type == 'room':
            delays = [1200, 2500, 3800, 5200]
            amps = [0.5, 0.3, 0.15, 0.08]
        elif self.reverb_type == 'hall':
            delays = [3000, 6000, 9000, 12000, 16000]
            amps = [0.6, 0.4, 0.25, 0.12, 0.06]
        elif self.reverb_type == 'cathedral':
            delays = [5000, 10000, 15000, 20000, 30000]
            amps = [0.5, 0.35, 0.2, 0.1, 0.05]
        else:
            delays = [2000, 4000, 6000]
            amps = [0.4, 0.2, 0.1]
        
        # Damping (absorption des aigus)
        damping_factor = 1.0 - self.reverb_damping * 0.8
        
        max_delay = max(delays)
        output = np.zeros(len(audio_block) + max_delay)
        output[:len(audio_block)] = audio_block
        
        for delay, amp in zip(delays, amps):
            delayed = audio_block * self.reverb_amount * amp
            
            # Filtre passe-bas pour le damping
            if self.reverb_damping > 0:
                # Filtre simple : lissage exponentiel
                filtered = np.zeros_like(delayed)
                prev = 0
                for j in range(len(delayed)):
                    filtered[j] = delayed[j] * (1 - damping_factor) + prev * damping_factor
                    prev = filtered[j]
                delayed = filtered
            
            output[delay:delay + len(audio_block)] += delayed
        
        output = output[:len(audio_block)]
        
        # Normalisation
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * 0.95
        
        return output
    
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

        # 2. Réverbération (NOUVEAU)
        #audio_with_reverb = self.apply_reverb(audio_equalized)
        
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
