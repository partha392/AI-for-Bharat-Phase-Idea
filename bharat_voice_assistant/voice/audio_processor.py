"""
Audio processing module for the Bharat Voice Assistant.

This module handles audio quality assessment, enhancement, compression,
and format conversion for voice data processing.
"""

import io
import numpy as np
from typing import Dict, Any, Optional, Tuple, Union
import asyncio
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import scipy.signal
from scipy.io import wavfile

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import AudioProcessingError

logger = get_logger(__name__)


class AudioProcessor:
    """
    Handles audio processing operations including quality assessment,
    enhancement, compression, and format conversion.
    """
    
    def __init__(self):
        """Initialize the audio processor with configuration settings."""
        self.sample_rate = 16000  # Standard sample rate for speech recognition
        self.channels = 1  # Mono audio for voice processing
        self.bit_depth = 16  # 16-bit audio
        
        # Quality thresholds
        self.min_quality_score = 0.3
        self.good_quality_score = 0.7
        
        # Noise reduction parameters
        self.noise_gate_threshold = -40  # dB
        self.noise_reduction_factor = 0.5
        
        logger.info("AudioProcessor initialized")
    
    async def assess_audio_quality(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Assess the quality of audio data.
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Dictionary containing quality metrics and assessment
        """
        try:
            # Convert bytes to AudioSegment
            audio = AudioSegment.from_raw(
                io.BytesIO(audio_data),
                sample_width=2,  # 16-bit
                frame_rate=self.sample_rate,
                channels=self.channels
            )
            
            # Calculate quality metrics
            quality_metrics = await self._calculate_quality_metrics(audio)
            
            # Determine overall quality score
            overall_score = self._calculate_overall_quality_score(quality_metrics)
            
            # Classify quality level
            if overall_score >= self.good_quality_score:
                quality_level = "good"
            elif overall_score >= self.min_quality_score:
                quality_level = "acceptable"
            else:
                quality_level = "poor"
            
            assessment = {
                "overall_score": overall_score,
                "quality_level": quality_level,
                "metrics": quality_metrics,
                "recommendations": self._generate_quality_recommendations(quality_metrics)
            }
            
            logger.debug(f"Audio quality assessment: {quality_level} (score: {overall_score:.2f})")
            return assessment
            
        except Exception as e:
            logger.error(f"Error assessing audio quality: {e}")
            raise AudioProcessingError(
                "Failed to assess audio quality",
                error_code="AUDIO_QUALITY_ASSESSMENT_FAILED",
                context={"error": str(e)}
            )
    
    async def enhance_audio(self, audio_data: bytes, quality_assessment: Dict[str, Any]) -> bytes:
        """
        Enhance audio quality based on assessment results.
        
        Args:
            audio_data: Raw audio bytes
            quality_assessment: Quality assessment results
            
        Returns:
            Enhanced audio bytes
        """
        try:
            # Convert bytes to AudioSegment
            audio = AudioSegment.from_raw(
                io.BytesIO(audio_data),
                sample_width=2,
                frame_rate=self.sample_rate,
                channels=self.channels
            )
            
            enhanced_audio = audio
            metrics = quality_assessment.get("metrics", {})
            
            # Apply noise reduction if needed
            if metrics.get("noise_level", 0) > 0.3:
                enhanced_audio = await self._apply_noise_reduction(enhanced_audio)
            
            # Normalize volume if needed
            if metrics.get("volume_level", 0) < 0.5:
                enhanced_audio = normalize(enhanced_audio)
            
            # Apply dynamic range compression for better clarity
            if metrics.get("dynamic_range", 1.0) > 0.8:
                enhanced_audio = compress_dynamic_range(enhanced_audio)
            
            # Apply high-pass filter to remove low-frequency noise
            if metrics.get("low_freq_noise", 0) > 0.2:
                enhanced_audio = await self._apply_high_pass_filter(enhanced_audio)
            
            # Convert back to bytes
            enhanced_bytes = enhanced_audio.raw_data
            
            logger.debug("Audio enhancement completed")
            return enhanced_bytes
            
        except Exception as e:
            logger.error(f"Error enhancing audio: {e}")
            raise AudioProcessingError(
                "Failed to enhance audio",
                error_code="AUDIO_ENHANCEMENT_FAILED",
                context={"error": str(e)}
            )
    
    async def compress_audio(self, audio_data: bytes, target_bitrate: int = None) -> bytes:
        """
        Compress audio for bandwidth optimization.
        
        Args:
            audio_data: Raw audio bytes
            target_bitrate: Target bitrate in kbps (defaults to config setting)
            
        Returns:
            Compressed audio bytes
        """
        try:
            if target_bitrate is None:
                target_bitrate = config.network.voice_compression_quality
            
            # Convert bytes to AudioSegment
            audio = AudioSegment.from_raw(
                io.BytesIO(audio_data),
                sample_width=2,
                frame_rate=self.sample_rate,
                channels=self.channels
            )
            
            # Export with compression
            compressed_buffer = io.BytesIO()
            audio.export(
                compressed_buffer,
                format="mp3",
                bitrate=f"{target_bitrate}k",
                parameters=["-ac", "1", "-ar", str(self.sample_rate)]
            )
            
            compressed_data = compressed_buffer.getvalue()
            
            # Calculate compression ratio
            original_size = len(audio_data)
            compressed_size = len(compressed_data)
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1
            
            logger.debug(f"Audio compressed: {original_size} -> {compressed_size} bytes "
                        f"(ratio: {compression_ratio:.2f}x)")
            
            return compressed_data
            
        except Exception as e:
            logger.error(f"Error compressing audio: {e}")
            raise AudioProcessingError(
                "Failed to compress audio",
                error_code="AUDIO_COMPRESSION_FAILED",
                context={"error": str(e)}
            )
    
    async def convert_format(self, audio_data: bytes, source_format: str, 
                           target_format: str) -> bytes:
        """
        Convert audio between different formats.
        
        Args:
            audio_data: Raw audio bytes
            source_format: Source audio format (e.g., 'wav', 'mp3')
            target_format: Target audio format (e.g., 'wav', 'mp3')
            
        Returns:
            Converted audio bytes
        """
        try:
            # Load audio from bytes
            if source_format.lower() == 'raw':
                audio = AudioSegment.from_raw(
                    io.BytesIO(audio_data),
                    sample_width=2,
                    frame_rate=self.sample_rate,
                    channels=self.channels
                )
            else:
                audio = AudioSegment.from_file(io.BytesIO(audio_data), format=source_format)
            
            # Ensure consistent parameters
            audio = audio.set_frame_rate(self.sample_rate)
            audio = audio.set_channels(self.channels)
            audio = audio.set_sample_width(2)  # 16-bit
            
            # Convert to target format
            output_buffer = io.BytesIO()
            
            if target_format.lower() == 'raw':
                converted_data = audio.raw_data
            else:
                audio.export(output_buffer, format=target_format)
                converted_data = output_buffer.getvalue()
            
            logger.debug(f"Audio converted from {source_format} to {target_format}")
            return converted_data
            
        except Exception as e:
            logger.error(f"Error converting audio format: {e}")
            raise AudioProcessingError(
                "Failed to convert audio format",
                error_code="AUDIO_FORMAT_CONVERSION_FAILED",
                context={
                    "source_format": source_format,
                    "target_format": target_format,
                    "error": str(e)
                }
            )
    
    async def _calculate_quality_metrics(self, audio: AudioSegment) -> Dict[str, float]:
        """Calculate various audio quality metrics."""
        try:
            # Convert to numpy array for analysis
            samples = np.array(audio.get_array_of_samples())
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
                samples = samples.mean(axis=1)  # Convert to mono
            
            # Normalize samples
            samples = samples.astype(np.float32) / 32768.0
            
            # Calculate metrics
            metrics = {}
            
            # Volume level (RMS)
            rms = np.sqrt(np.mean(samples ** 2))
            metrics["volume_level"] = min(rms * 10, 1.0)  # Scale to 0-1
            
            # Signal-to-noise ratio estimation
            # Use spectral analysis to estimate noise floor
            freqs, psd = scipy.signal.welch(samples, fs=self.sample_rate)
            
            # Estimate noise level (energy in high frequencies relative to total)
            high_freq_mask = freqs > 4000  # Above 4kHz
            speech_freq_mask = (freqs >= 300) & (freqs <= 3400)  # Speech range
            
            high_freq_energy = np.sum(psd[high_freq_mask])
            speech_energy = np.sum(psd[speech_freq_mask])
            total_energy = np.sum(psd)
            
            if total_energy > 0:
                metrics["noise_level"] = min(high_freq_energy / total_energy, 1.0)
                metrics["speech_energy_ratio"] = min(speech_energy / total_energy, 1.0)
            else:
                metrics["noise_level"] = 1.0
                metrics["speech_energy_ratio"] = 0.0
            
            # Dynamic range
            if len(samples) > 0:
                dynamic_range = (np.max(samples) - np.min(samples)) / 2.0
                metrics["dynamic_range"] = min(dynamic_range, 1.0)
            else:
                metrics["dynamic_range"] = 0.0
            
            # Low frequency noise (below 100Hz)
            low_freq_mask = freqs < 100
            low_freq_energy = np.sum(psd[low_freq_mask])
            metrics["low_freq_noise"] = min(low_freq_energy / total_energy, 1.0) if total_energy > 0 else 0.0
            
            # Clipping detection
            clipping_threshold = 0.95
            clipped_samples = np.sum(np.abs(samples) > clipping_threshold)
            metrics["clipping_ratio"] = clipped_samples / len(samples) if len(samples) > 0 else 0.0
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating quality metrics: {e}")
            # Return default metrics on error
            return {
                "volume_level": 0.5,
                "noise_level": 0.5,
                "speech_energy_ratio": 0.5,
                "dynamic_range": 0.5,
                "low_freq_noise": 0.3,
                "clipping_ratio": 0.0
            }
    
    def _calculate_overall_quality_score(self, metrics: Dict[str, float]) -> float:
        """Calculate overall quality score from individual metrics."""
        # Weighted scoring
        weights = {
            "volume_level": 0.2,
            "noise_level": -0.3,  # Negative because higher noise is worse
            "speech_energy_ratio": 0.3,
            "dynamic_range": 0.1,
            "low_freq_noise": -0.1,  # Negative because noise is bad
            "clipping_ratio": -0.2   # Negative because clipping is bad
        }
        
        score = 0.5  # Base score
        
        for metric, weight in weights.items():
            if metric in metrics:
                score += weight * metrics[metric]
        
        # Clamp to 0-1 range
        return max(0.0, min(1.0, score))
    
    def _generate_quality_recommendations(self, metrics: Dict[str, float]) -> list:
        """Generate recommendations based on quality metrics."""
        recommendations = []
        
        if metrics.get("volume_level", 0) < 0.3:
            recommendations.append("Increase microphone volume or speak closer to the microphone")
        
        if metrics.get("noise_level", 0) > 0.4:
            recommendations.append("Reduce background noise or use a quieter environment")
        
        if metrics.get("clipping_ratio", 0) > 0.05:
            recommendations.append("Reduce microphone gain to prevent audio clipping")
        
        if metrics.get("low_freq_noise", 0) > 0.3:
            recommendations.append("Use a microphone with better low-frequency noise rejection")
        
        if metrics.get("speech_energy_ratio", 0) < 0.4:
            recommendations.append("Ensure clear speech in the 300-3400Hz frequency range")
        
        return recommendations
    
    async def _apply_noise_reduction(self, audio: AudioSegment) -> AudioSegment:
        """Apply noise reduction to audio."""
        try:
            # Simple noise gate implementation
            # Convert to numpy for processing
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0  # Normalize
            
            # Calculate RMS in sliding windows
            window_size = int(0.02 * self.sample_rate)  # 20ms windows
            rms_values = []
            
            for i in range(0, len(samples) - window_size, window_size // 2):
                window = samples[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                rms_values.append(rms)
            
            # Estimate noise floor
            noise_floor = np.percentile(rms_values, 20) if rms_values else 0.01
            
            # Apply noise gate
            gate_threshold = noise_floor * 2
            
            processed_samples = samples.copy()
            for i in range(0, len(samples) - window_size, window_size // 2):
                window = samples[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                
                if rms < gate_threshold:
                    # Reduce amplitude in noisy regions
                    processed_samples[i:i + window_size] *= self.noise_reduction_factor
            
            # Convert back to AudioSegment
            processed_samples = (processed_samples * 32767).astype(np.int16)
            processed_audio = AudioSegment(
                processed_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            
            return processed_audio
            
        except Exception as e:
            logger.warning(f"Noise reduction failed, returning original audio: {e}")
            return audio
    
    async def _apply_high_pass_filter(self, audio: AudioSegment) -> AudioSegment:
        """Apply high-pass filter to remove low-frequency noise."""
        try:
            # Convert to numpy for processing
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # Design high-pass filter (cutoff at 80Hz)
            nyquist = self.sample_rate / 2
            cutoff = 80 / nyquist
            
            # Use a simple high-pass filter
            b, a = scipy.signal.butter(2, cutoff, btype='high')
            filtered_samples = scipy.signal.filtfilt(b, a, samples)
            
            # Convert back to AudioSegment
            filtered_samples = filtered_samples.astype(np.int16)
            filtered_audio = AudioSegment(
                filtered_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            
            return filtered_audio
            
        except Exception as e:
            logger.warning(f"High-pass filtering failed, returning original audio: {e}")
            return audio