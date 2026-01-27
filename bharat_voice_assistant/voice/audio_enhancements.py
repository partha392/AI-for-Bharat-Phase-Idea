"""
Audio processing enhancements for the Bharat Voice Assistant.

This module provides advanced audio processing capabilities including:
- Advanced noise cancellation for background sound filtering
- Automatic volume and clarity adjustment for poor audio quality
- Response time optimization for 3-second target performance
- Speaking pace adaptation based on user preferences
- Real-time audio quality monitoring and adjustment
"""

import asyncio
import time
import numpy as np
from typing import Dict, Any, Optional, Tuple, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import scipy.signal
from scipy.fft import fft, ifft
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import io

from ..core.logging import get_logger
from ..core.exceptions import AudioProcessingError
from .audio_processor import AudioProcessor


logger = get_logger(__name__)


class NoiseType(Enum):
    """Types of background noise."""
    TRAFFIC = "traffic"
    CROWD = "crowd"
    WIND = "wind"
    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"
    GENERAL = "general"


class AudioQuality(Enum):
    """Audio quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    VERY_POOR = "very_poor"


@dataclass
class SpeakingPaceProfile:
    """Profile for user's speaking pace preferences."""
    words_per_minute: float = 120.0  # Normal speaking pace
    pause_duration: float = 0.5      # Seconds between phrases
    response_delay: float = 1.0      # Delay before responding
    clarity_preference: str = "normal"  # slow, normal, fast
    repetition_tolerance: int = 2    # How many times to repeat before slowing down


@dataclass
class AudioEnhancementConfig:
    """Configuration for audio enhancements."""
    noise_cancellation_enabled: bool = True
    auto_volume_adjustment: bool = True
    clarity_enhancement: bool = True
    response_time_optimization: bool = True
    speaking_pace_adaptation: bool = True
    target_response_time: float = 3.0  # seconds
    min_audio_quality: AudioQuality = AudioQuality.FAIR


class AdvancedNoiseCancellation:
    """Advanced noise cancellation system."""
    
    def __init__(self):
        """Initialize noise cancellation system."""
        self.logger = get_logger(__name__)
        self._noise_profiles = self._load_noise_profiles()
        self._adaptive_filter_coeffs = None
        self._noise_estimation_window = 0.5  # seconds
    
    def _load_noise_profiles(self) -> Dict[NoiseType, Dict[str, Any]]:
        """Load noise profiles for different types of background noise."""
        return {
            NoiseType.TRAFFIC: {
                "frequency_range": (50, 2000),
                "dominant_frequencies": [100, 200, 400, 800],
                "spectral_shape": "low_pass",
                "temporal_pattern": "continuous"
            },
            NoiseType.CROWD: {
                "frequency_range": (200, 4000),
                "dominant_frequencies": [500, 1000, 2000],
                "spectral_shape": "broad_band",
                "temporal_pattern": "variable"
            },
            NoiseType.WIND: {
                "frequency_range": (20, 500),
                "dominant_frequencies": [50, 100, 200],
                "spectral_shape": "low_pass",
                "temporal_pattern": "fluctuating"
            },
            NoiseType.ELECTRICAL: {
                "frequency_range": (50, 1000),
                "dominant_frequencies": [50, 100, 150, 200],  # Harmonics of 50Hz
                "spectral_shape": "harmonic",
                "temporal_pattern": "continuous"
            },
            NoiseType.MECHANICAL: {
                "frequency_range": (100, 3000),
                "dominant_frequencies": [200, 400, 800, 1600],
                "spectral_shape": "harmonic",
                "temporal_pattern": "periodic"
            },
            NoiseType.GENERAL: {
                "frequency_range": (50, 4000),
                "dominant_frequencies": [100, 500, 1000, 2000],
                "spectral_shape": "broad_band",
                "temporal_pattern": "variable"
            }
        }
    
    async def cancel_noise(
        self, 
        audio_data: bytes, 
        sample_rate: int = 16000
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Apply advanced noise cancellation to audio data.
        
        Args:
            audio_data: Raw audio bytes
            sample_rate: Audio sample rate
            
        Returns:
            Tuple of (processed_audio_bytes, processing_info)
        """
        try:
            # Convert to numpy array
            audio = AudioSegment.from_raw(
                io.BytesIO(audio_data),
                sample_width=2,
                frame_rate=sample_rate,
                channels=1
            )
            
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0  # Normalize to [-1, 1]
            
            # Detect noise type
            noise_type = await self._detect_noise_type(samples, sample_rate)
            
            # Apply appropriate noise cancellation
            if noise_type == NoiseType.ELECTRICAL:
                processed_samples = await self._cancel_electrical_noise(samples, sample_rate)
            elif noise_type == NoiseType.WIND:
                processed_samples = await self._cancel_wind_noise(samples, sample_rate)
            elif noise_type == NoiseType.TRAFFIC:
                processed_samples = await self._cancel_traffic_noise(samples, sample_rate)
            else:
                processed_samples = await self._cancel_general_noise(samples, sample_rate)
            
            # Apply spectral subtraction for additional noise reduction
            processed_samples = await self._spectral_subtraction(processed_samples, sample_rate)
            
            # Convert back to bytes
            processed_samples = np.clip(processed_samples, -1.0, 1.0)
            processed_samples = (processed_samples * 32767).astype(np.int16)
            
            processed_audio = AudioSegment(
                processed_samples.tobytes(),
                frame_rate=sample_rate,
                sample_width=2,
                channels=1
            )
            
            processing_info = {
                "noise_type_detected": noise_type.value,
                "noise_reduction_applied": True,
                "processing_time": time.time()  # Would be calculated properly
            }
            
            return processed_audio.raw_data, processing_info
            
        except Exception as e:
            self.logger.error(f"Failed to cancel noise: {e}")
            return audio_data, {"error": str(e)}
    
    async def _detect_noise_type(self, samples: np.ndarray, sample_rate: int) -> NoiseType:
        """Detect the type of background noise."""
        try:
            # Compute power spectral density
            freqs, psd = scipy.signal.welch(samples, fs=sample_rate, nperseg=1024)
            
            # Analyze spectral characteristics
            low_freq_power = np.sum(psd[freqs < 200])
            mid_freq_power = np.sum(psd[(freqs >= 200) & (freqs < 2000)])
            high_freq_power = np.sum(psd[freqs >= 2000])
            total_power = np.sum(psd)
            
            # Check for electrical noise (50Hz harmonics)
            electrical_freqs = [50, 100, 150, 200, 250]
            electrical_power = 0
            for freq in electrical_freqs:
                freq_idx = np.argmin(np.abs(freqs - freq))
                electrical_power += psd[freq_idx]
            
            # Decision logic
            if electrical_power / total_power > 0.3:
                return NoiseType.ELECTRICAL
            elif low_freq_power / total_power > 0.6:
                return NoiseType.WIND if low_freq_power / total_power > 0.8 else NoiseType.TRAFFIC
            elif mid_freq_power / total_power > 0.5:
                return NoiseType.CROWD
            else:
                return NoiseType.GENERAL
                
        except Exception as e:
            self.logger.warning(f"Failed to detect noise type: {e}")
            return NoiseType.GENERAL
    
    async def _cancel_electrical_noise(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """Cancel electrical noise (50Hz and harmonics)."""
        try:
            # Design notch filters for 50Hz and harmonics
            processed = samples.copy()
            
            for freq in [50, 100, 150, 200]:
                if freq < sample_rate / 2:  # Ensure frequency is below Nyquist
                    # Design notch filter
                    Q = 30  # Quality factor
                    w0 = freq / (sample_rate / 2)  # Normalized frequency
                    b, a = scipy.signal.iirnotch(w0, Q)
                    processed = scipy.signal.filtfilt(b, a, processed)
            
            return processed
            
        except Exception as e:
            self.logger.warning(f"Failed to cancel electrical noise: {e}")
            return samples
    
    async def _cancel_wind_noise(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """Cancel wind noise using high-pass filtering."""
        try:
            # Design high-pass filter to remove low-frequency wind noise
            cutoff = 100  # Hz
            nyquist = sample_rate / 2
            normalized_cutoff = cutoff / nyquist
            
            b, a = scipy.signal.butter(4, normalized_cutoff, btype='high')
            processed = scipy.signal.filtfilt(b, a, samples)
            
            return processed
            
        except Exception as e:
            self.logger.warning(f"Failed to cancel wind noise: {e}")
            return samples
    
    async def _cancel_traffic_noise(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """Cancel traffic noise using adaptive filtering."""
        try:
            # Apply band-stop filter for typical traffic frequencies
            low_cutoff = 50
            high_cutoff = 1000
            nyquist = sample_rate / 2
            
            low_norm = low_cutoff / nyquist
            high_norm = high_cutoff / nyquist
            
            b, a = scipy.signal.butter(2, [low_norm, high_norm], btype='bandstop')
            processed = scipy.signal.filtfilt(b, a, samples)
            
            # Apply additional smoothing
            window_size = int(0.01 * sample_rate)  # 10ms window
            processed = scipy.signal.savgol_filter(processed, window_size | 1, 3)
            
            return processed
            
        except Exception as e:
            self.logger.warning(f"Failed to cancel traffic noise: {e}")
            return samples
    
    async def _cancel_general_noise(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply general noise cancellation using Wiener filtering."""
        try:
            # Estimate noise using initial silence or low-energy regions
            window_size = int(0.02 * sample_rate)  # 20ms windows
            energy_threshold = 0.01
            
            # Find low-energy regions (likely noise)
            noise_samples = []
            for i in range(0, len(samples) - window_size, window_size):
                window = samples[i:i + window_size]
                energy = np.mean(window ** 2)
                if energy < energy_threshold:
                    noise_samples.extend(window)
            
            if len(noise_samples) > window_size:
                # Estimate noise spectrum
                noise_fft = fft(noise_samples[:len(noise_samples) // window_size * window_size])
                noise_power = np.abs(noise_fft) ** 2
                
                # Apply Wiener filter
                signal_fft = fft(samples)
                signal_power = np.abs(signal_fft) ** 2
                
                # Wiener filter coefficient
                wiener_coeff = signal_power / (signal_power + noise_power[:len(signal_power)])
                
                # Apply filter
                filtered_fft = signal_fft * wiener_coeff
                processed = np.real(ifft(filtered_fft))
                
                return processed
            
            return samples
            
        except Exception as e:
            self.logger.warning(f"Failed to apply general noise cancellation: {e}")
            return samples
    
    async def _spectral_subtraction(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply spectral subtraction for additional noise reduction."""
        try:
            # Parameters for spectral subtraction
            frame_size = int(0.025 * sample_rate)  # 25ms frames
            hop_size = frame_size // 2
            alpha = 2.0  # Over-subtraction factor
            beta = 0.01  # Spectral floor factor
            
            # Pad signal
            padded_samples = np.pad(samples, (frame_size // 2, frame_size // 2), mode='reflect')
            
            # Process in frames
            processed_frames = []
            
            for i in range(0, len(padded_samples) - frame_size, hop_size):
                frame = padded_samples[i:i + frame_size]
                
                # Apply window
                windowed_frame = frame * np.hanning(frame_size)
                
                # FFT
                frame_fft = fft(windowed_frame)
                magnitude = np.abs(frame_fft)
                phase = np.angle(frame_fft)
                
                # Estimate noise (use first few frames as noise estimate)
                if i == 0:
                    noise_magnitude = magnitude.copy()
                
                # Spectral subtraction
                enhanced_magnitude = magnitude - alpha * noise_magnitude
                
                # Apply spectral floor
                enhanced_magnitude = np.maximum(enhanced_magnitude, beta * magnitude)
                
                # Reconstruct signal
                enhanced_fft = enhanced_magnitude * np.exp(1j * phase)
                enhanced_frame = np.real(ifft(enhanced_fft))
                
                processed_frames.append(enhanced_frame)
            
            # Overlap-add reconstruction
            if processed_frames:
                output_length = len(samples)
                processed = np.zeros(output_length + frame_size)
                
                for i, frame in enumerate(processed_frames):
                    start_idx = i * hop_size
                    processed[start_idx:start_idx + frame_size] += frame
                
                return processed[:output_length]
            
            return samples
            
        except Exception as e:
            self.logger.warning(f"Failed to apply spectral subtraction: {e}")
            return samples


class AutoVolumeClarity:
    """Automatic volume and clarity adjustment system."""
    
    def __init__(self):
        """Initialize auto volume and clarity system."""
        self.logger = get_logger(__name__)
        self.target_rms = 0.3  # Target RMS level
        self.target_peak = 0.8  # Target peak level
    
    async def adjust_volume_clarity(
        self, 
        audio_data: bytes, 
        sample_rate: int = 16000
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Automatically adjust volume and clarity of audio.
        
        Args:
            audio_data: Raw audio bytes
            sample_rate: Audio sample rate
            
        Returns:
            Tuple of (processed_audio_bytes, adjustment_info)
        """
        try:
            # Convert to AudioSegment
            audio = AudioSegment.from_raw(
                io.BytesIO(audio_data),
                sample_width=2,
                frame_rate=sample_rate,
                channels=1
            )
            
            # Analyze current audio characteristics
            analysis = await self._analyze_audio_characteristics(audio)
            
            # Apply volume adjustment
            if analysis["needs_volume_adjustment"]:
                audio = await self._adjust_volume(audio, analysis)
            
            # Apply clarity enhancement
            if analysis["needs_clarity_enhancement"]:
                audio = await self._enhance_clarity(audio, analysis)
            
            # Apply dynamic range compression
            if analysis["needs_compression"]:
                audio = await self._apply_compression(audio, analysis)
            
            adjustment_info = {
                "volume_adjusted": analysis["needs_volume_adjustment"],
                "clarity_enhanced": analysis["needs_clarity_enhancement"],
                "compression_applied": analysis["needs_compression"],
                "original_rms": analysis["rms_level"],
                "original_peak": analysis["peak_level"],
                "final_rms": self._calculate_rms(audio),
                "final_peak": self._calculate_peak(audio)
            }
            
            return audio.raw_data, adjustment_info
            
        except Exception as e:
            self.logger.error(f"Failed to adjust volume and clarity: {e}")
            return audio_data, {"error": str(e)}
    
    async def _analyze_audio_characteristics(self, audio: AudioSegment) -> Dict[str, Any]:
        """Analyze audio characteristics to determine needed adjustments."""
        try:
            # Calculate audio metrics
            rms_level = self._calculate_rms(audio)
            peak_level = self._calculate_peak(audio)
            dynamic_range = self._calculate_dynamic_range(audio)
            spectral_centroid = self._calculate_spectral_centroid(audio)
            
            # Determine needed adjustments
            needs_volume_adjustment = (
                rms_level < self.target_rms * 0.5 or 
                rms_level > self.target_rms * 1.5 or
                peak_level > self.target_peak
            )
            
            needs_clarity_enhancement = (
                spectral_centroid < 1000 or  # Too much low-frequency content
                dynamic_range < 0.2  # Too compressed
            )
            
            needs_compression = dynamic_range > 0.8  # Too much dynamic range
            
            return {
                "rms_level": rms_level,
                "peak_level": peak_level,
                "dynamic_range": dynamic_range,
                "spectral_centroid": spectral_centroid,
                "needs_volume_adjustment": needs_volume_adjustment,
                "needs_clarity_enhancement": needs_clarity_enhancement,
                "needs_compression": needs_compression
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze audio characteristics: {e}")
            return {
                "rms_level": 0.3,
                "peak_level": 0.8,
                "dynamic_range": 0.5,
                "spectral_centroid": 1500,
                "needs_volume_adjustment": False,
                "needs_clarity_enhancement": False,
                "needs_compression": False
            }
    
    def _calculate_rms(self, audio: AudioSegment) -> float:
        """Calculate RMS level of audio."""
        try:
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0
            return np.sqrt(np.mean(samples ** 2))
        except Exception:
            return 0.3
    
    def _calculate_peak(self, audio: AudioSegment) -> float:
        """Calculate peak level of audio."""
        try:
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0
            return np.max(np.abs(samples))
        except Exception:
            return 0.8
    
    def _calculate_dynamic_range(self, audio: AudioSegment) -> float:
        """Calculate dynamic range of audio."""
        try:
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0
            
            # Calculate percentiles
            p95 = np.percentile(np.abs(samples), 95)
            p5 = np.percentile(np.abs(samples), 5)
            
            return (p95 - p5) / p95 if p95 > 0 else 0.5
        except Exception:
            return 0.5
    
    def _calculate_spectral_centroid(self, audio: AudioSegment) -> float:
        """Calculate spectral centroid of audio."""
        try:
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # Compute FFT
            fft_result = np.abs(fft(samples))
            freqs = np.fft.fftfreq(len(samples), 1/audio.frame_rate)
            
            # Calculate spectral centroid
            magnitude_sum = np.sum(fft_result)
            if magnitude_sum > 0:
                centroid = np.sum(freqs[:len(freqs)//2] * fft_result[:len(freqs)//2]) / np.sum(fft_result[:len(freqs)//2])
                return abs(centroid)
            
            return 1500  # Default value
            
        except Exception:
            return 1500
    
    async def _adjust_volume(self, audio: AudioSegment, analysis: Dict[str, Any]) -> AudioSegment:
        """Adjust volume to target level."""
        try:
            current_rms = analysis["rms_level"]
            
            if current_rms > 0:
                # Calculate gain needed
                gain_db = 20 * np.log10(self.target_rms / current_rms)
                
                # Limit gain to prevent distortion
                gain_db = np.clip(gain_db, -20, 20)
                
                # Apply gain
                adjusted_audio = audio + gain_db
                
                return adjusted_audio
            
            return audio
            
        except Exception as e:
            self.logger.warning(f"Failed to adjust volume: {e}")
            return audio
    
    async def _enhance_clarity(self, audio: AudioSegment, analysis: Dict[str, Any]) -> AudioSegment:
        """Enhance audio clarity."""
        try:
            # Apply high-frequency emphasis for clarity
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # Design high-frequency emphasis filter
            nyquist = audio.frame_rate / 2
            high_freq = 2000 / nyquist  # Emphasize frequencies above 2kHz
            
            # Simple high-frequency boost
            b, a = scipy.signal.butter(2, high_freq, btype='high')
            emphasized_samples = scipy.signal.filtfilt(b, a, samples)
            
            # Mix with original (subtle enhancement)
            enhanced_samples = 0.7 * samples + 0.3 * emphasized_samples
            
            # Convert back to AudioSegment
            enhanced_samples = enhanced_samples.astype(np.int16)
            enhanced_audio = AudioSegment(
                enhanced_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            
            return enhanced_audio
            
        except Exception as e:
            self.logger.warning(f"Failed to enhance clarity: {e}")
            return audio
    
    async def _apply_compression(self, audio: AudioSegment, analysis: Dict[str, Any]) -> AudioSegment:
        """Apply dynamic range compression."""
        try:
            # Use pydub's built-in compression
            compressed_audio = compress_dynamic_range(
                audio,
                threshold=-20.0,  # dB
                ratio=4.0,        # 4:1 compression ratio
                attack=5.0,       # ms
                release=50.0      # ms
            )
            
            return compressed_audio
            
        except Exception as e:
            self.logger.warning(f"Failed to apply compression: {e}")
            return audio


class ResponseTimeOptimizer:
    """Optimizes response time for 3-second target."""
    
    def __init__(self, target_response_time: float = 3.0):
        """Initialize response time optimizer."""
        self.logger = get_logger(__name__)
        self.target_response_time = target_response_time
        self._processing_times: List[float] = []
        self._max_history = 100
    
    async def optimize_processing(
        self, 
        audio_data: bytes, 
        processing_functions: List[Callable]
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Optimize audio processing to meet response time target.
        
        Args:
            audio_data: Raw audio bytes
            processing_functions: List of processing functions to apply
            
        Returns:
            Tuple of (processed_audio_bytes, timing_info)
        """
        try:
            start_time = time.time()
            
            # Determine processing strategy based on available time
            strategy = await self._determine_processing_strategy()
            
            processed_audio = audio_data
            applied_functions = []
            
            for func in processing_functions:
                # Check remaining time
                elapsed = time.time() - start_time
                remaining_time = self.target_response_time - elapsed
                
                if remaining_time > 0.5:  # Need at least 0.5s for processing
                    try:
                        if strategy == "fast":
                            # Apply fast processing
                            processed_audio = await self._apply_fast_processing(processed_audio, func)
                        elif strategy == "balanced":
                            # Apply balanced processing
                            processed_audio = await func(processed_audio)
                        else:
                            # Apply full processing
                            processed_audio = await func(processed_audio)
                        
                        applied_functions.append(func.__name__)
                        
                    except Exception as e:
                        self.logger.warning(f"Processing function {func.__name__} failed: {e}")
                        continue
                else:
                    # Skip remaining functions to meet time target
                    break
            
            total_time = time.time() - start_time
            self._update_processing_times(total_time)
            
            timing_info = {
                "total_processing_time": total_time,
                "target_response_time": self.target_response_time,
                "strategy_used": strategy,
                "functions_applied": applied_functions,
                "functions_skipped": len(processing_functions) - len(applied_functions),
                "time_budget_met": total_time <= self.target_response_time
            }
            
            return processed_audio, timing_info
            
        except Exception as e:
            self.logger.error(f"Failed to optimize processing: {e}")
            return audio_data, {"error": str(e)}
    
    async def _determine_processing_strategy(self) -> str:
        """Determine processing strategy based on historical performance."""
        try:
            if not self._processing_times:
                return "balanced"
            
            avg_time = np.mean(self._processing_times[-10:])  # Last 10 measurements
            
            if avg_time > self.target_response_time * 1.2:
                return "fast"
            elif avg_time > self.target_response_time * 0.8:
                return "balanced"
            else:
                return "full"
                
        except Exception:
            return "balanced"
    
    async def _apply_fast_processing(self, audio_data: bytes, func: Callable) -> bytes:
        """Apply fast processing with reduced quality for speed."""
        try:
            # Create a timeout for the function
            return await asyncio.wait_for(func(audio_data), timeout=0.5)
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Processing function timed out, returning original audio")
            return audio_data
        except Exception as e:
            self.logger.warning(f"Fast processing failed: {e}")
            return audio_data
    
    def _update_processing_times(self, processing_time: float):
        """Update processing time history."""
        self._processing_times.append(processing_time)
        if len(self._processing_times) > self._max_history:
            self._processing_times.pop(0)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        try:
            if not self._processing_times:
                return {"no_data": True}
            
            return {
                "average_processing_time": np.mean(self._processing_times),
                "median_processing_time": np.median(self._processing_times),
                "max_processing_time": np.max(self._processing_times),
                "min_processing_time": np.min(self._processing_times),
                "target_response_time": self.target_response_time,
                "success_rate": np.mean([t <= self.target_response_time for t in self._processing_times]),
                "total_measurements": len(self._processing_times)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get performance stats: {e}")
            return {"error": str(e)}


class SpeakingPaceAdapter:
    """Adapts response pacing based on user speaking patterns."""
    
    def __init__(self):
        """Initialize speaking pace adapter."""
        self.logger = get_logger(__name__)
        self._user_profiles: Dict[str, SpeakingPaceProfile] = {}
    
    async def analyze_speaking_pace(
        self, 
        user_id: str,
        audio_data: bytes, 
        transcript: str,
        sample_rate: int = 16000
    ) -> SpeakingPaceProfile:
        """
        Analyze user's speaking pace and update their profile.
        
        Args:
            user_id: Unique user identifier
            audio_data: Raw audio bytes
            transcript: Transcribed text
            sample_rate: Audio sample rate
            
        Returns:
            Updated speaking pace profile
        """
        try:
            # Calculate speaking metrics
            audio_duration = len(audio_data) / (sample_rate * 2)  # 2 bytes per sample
            word_count = len(transcript.split())
            
            if audio_duration > 0 and word_count > 0:
                words_per_minute = (word_count / audio_duration) * 60
                
                # Detect pauses
                pause_duration = await self._detect_pause_patterns(audio_data, sample_rate)
                
                # Get or create user profile
                if user_id not in self._user_profiles:
                    self._user_profiles[user_id] = SpeakingPaceProfile()
                
                profile = self._user_profiles[user_id]
                
                # Update profile with exponential moving average
                alpha = 0.3  # Learning rate
                profile.words_per_minute = (
                    alpha * words_per_minute + 
                    (1 - alpha) * profile.words_per_minute
                )
                profile.pause_duration = (
                    alpha * pause_duration + 
                    (1 - alpha) * profile.pause_duration
                )
                
                # Determine clarity preference
                if words_per_minute < 80:
                    profile.clarity_preference = "slow"
                    profile.response_delay = 1.5
                elif words_per_minute > 160:
                    profile.clarity_preference = "fast"
                    profile.response_delay = 0.5
                else:
                    profile.clarity_preference = "normal"
                    profile.response_delay = 1.0
                
                self.logger.debug(f"Updated speaking pace profile for user {user_id}: "
                                f"{words_per_minute:.1f} WPM, {pause_duration:.2f}s pauses")
                
                return profile
            
            # Return default profile if analysis fails
            return self._user_profiles.get(user_id, SpeakingPaceProfile())
            
        except Exception as e:
            self.logger.error(f"Failed to analyze speaking pace: {e}")
            return SpeakingPaceProfile()
    
    async def _detect_pause_patterns(self, audio_data: bytes, sample_rate: int) -> float:
        """Detect pause patterns in audio."""
        try:
            # Convert to numpy array
            audio = AudioSegment.from_raw(
                io.BytesIO(audio_data),
                sample_width=2,
                frame_rate=sample_rate,
                channels=1
            )
            
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0
            
            # Detect silence/pause regions
            window_size = int(0.1 * sample_rate)  # 100ms windows
            silence_threshold = 0.01  # RMS threshold for silence
            
            pause_durations = []
            current_pause_length = 0
            
            for i in range(0, len(samples) - window_size, window_size // 2):
                window = samples[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                
                if rms < silence_threshold:
                    current_pause_length += window_size / (2 * sample_rate)
                else:
                    if current_pause_length > 0.2:  # Pauses longer than 200ms
                        pause_durations.append(current_pause_length)
                    current_pause_length = 0
            
            # Return average pause duration
            return np.mean(pause_durations) if pause_durations else 0.5
            
        except Exception as e:
            self.logger.warning(f"Failed to detect pause patterns: {e}")
            return 0.5
    
    def get_response_timing(self, user_id: str) -> Dict[str, float]:
        """Get recommended response timing for a user."""
        try:
            profile = self._user_profiles.get(user_id, SpeakingPaceProfile())
            
            return {
                "response_delay": profile.response_delay,
                "speech_rate": self._calculate_speech_rate(profile),
                "pause_duration": profile.pause_duration,
                "words_per_minute": profile.words_per_minute
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get response timing: {e}")
            return {
                "response_delay": 1.0,
                "speech_rate": 1.0,
                "pause_duration": 0.5,
                "words_per_minute": 120.0
            }
    
    def _calculate_speech_rate(self, profile: SpeakingPaceProfile) -> float:
        """Calculate recommended speech rate multiplier."""
        try:
            if profile.clarity_preference == "slow":
                return 0.8  # 20% slower
            elif profile.clarity_preference == "fast":
                return 1.2  # 20% faster
            else:
                return 1.0  # Normal speed
                
        except Exception:
            return 1.0


class AudioEnhancementSystem:
    """Main audio enhancement system that coordinates all enhancements."""
    
    def __init__(self, config: AudioEnhancementConfig = None):
        """Initialize audio enhancement system."""
        self.logger = get_logger(__name__)
        self.config = config or AudioEnhancementConfig()
        
        # Initialize subsystems
        self.noise_cancellation = AdvancedNoiseCancellation()
        self.volume_clarity = AutoVolumeClarity()
        self.response_optimizer = ResponseTimeOptimizer(self.config.target_response_time)
        self.pace_adapter = SpeakingPaceAdapter()
        
        # Base audio processor
        self.base_processor = AudioProcessor()
    
    async def enhance_audio(
        self, 
        user_id: str,
        audio_data: bytes, 
        transcript: Optional[str] = None,
        sample_rate: int = 16000
    ) -> Dict[str, Any]:
        """
        Apply comprehensive audio enhancements.
        
        Args:
            user_id: Unique user identifier
            audio_data: Raw audio bytes
            transcript: Transcribed text (optional)
            sample_rate: Audio sample rate
            
        Returns:
            Dictionary containing enhanced audio and processing information
        """
        try:
            start_time = time.time()
            
            # Assess initial audio quality
            quality_assessment = await self.base_processor.assess_audio_quality(audio_data)
            
            # Prepare processing functions based on configuration
            processing_functions = []
            
            if self.config.noise_cancellation_enabled:
                processing_functions.append(
                    lambda data: self.noise_cancellation.cancel_noise(data, sample_rate)
                )
            
            if self.config.auto_volume_adjustment:
                processing_functions.append(
                    lambda data: self.volume_clarity.adjust_volume_clarity(data, sample_rate)
                )
            
            # Apply optimized processing
            if self.config.response_time_optimization:
                enhanced_audio, timing_info = await self.response_optimizer.optimize_processing(
                    audio_data, processing_functions
                )
            else:
                # Apply all enhancements without time constraints
                enhanced_audio = audio_data
                for func in processing_functions:
                    try:
                        result = await func(enhanced_audio)
                        if isinstance(result, tuple):
                            enhanced_audio = result[0]
                        else:
                            enhanced_audio = result
                    except Exception as e:
                        self.logger.warning(f"Enhancement function failed: {e}")
                
                timing_info = {"total_processing_time": time.time() - start_time}
            
            # Analyze speaking pace if transcript is available
            pace_profile = None
            if transcript and self.config.speaking_pace_adaptation:
                pace_profile = await self.pace_adapter.analyze_speaking_pace(
                    user_id, audio_data, transcript, sample_rate
                )
            
            # Final quality assessment
            final_quality = await self.base_processor.assess_audio_quality(enhanced_audio)
            
            # Prepare response
            enhancement_result = {
                "enhanced_audio": enhanced_audio,
                "original_quality": quality_assessment,
                "final_quality": final_quality,
                "timing_info": timing_info,
                "pace_profile": pace_profile.__dict__ if pace_profile else None,
                "enhancements_applied": {
                    "noise_cancellation": self.config.noise_cancellation_enabled,
                    "volume_adjustment": self.config.auto_volume_adjustment,
                    "clarity_enhancement": self.config.clarity_enhancement,
                    "response_optimization": self.config.response_time_optimization,
                    "pace_adaptation": self.config.speaking_pace_adaptation
                },
                "processing_time": time.time() - start_time,
                "quality_improvement": (
                    final_quality["overall_score"] - quality_assessment["overall_score"]
                )
            }
            
            self.logger.info(f"Audio enhancement completed in {enhancement_result['processing_time']:.3f}s")
            
            return enhancement_result
            
        except Exception as e:
            self.logger.error(f"Failed to enhance audio: {e}")
            return {
                "enhanced_audio": audio_data,
                "error": str(e),
                "processing_time": time.time() - start_time
            }
    
    def get_user_response_timing(self, user_id: str) -> Dict[str, float]:
        """Get recommended response timing for a user."""
        return self.pace_adapter.get_response_timing(user_id)
    
    def get_system_performance(self) -> Dict[str, Any]:
        """Get system performance statistics."""
        try:
            return {
                "response_optimizer": self.response_optimizer.get_performance_stats(),
                "config": {
                    "target_response_time": self.config.target_response_time,
                    "noise_cancellation_enabled": self.config.noise_cancellation_enabled,
                    "auto_volume_adjustment": self.config.auto_volume_adjustment,
                    "clarity_enhancement": self.config.clarity_enhancement,
                    "response_time_optimization": self.config.response_time_optimization,
                    "speaking_pace_adaptation": self.config.speaking_pace_adaptation
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get system performance: {e}")
            return {"error": str(e)}