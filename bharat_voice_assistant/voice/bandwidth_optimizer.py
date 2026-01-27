"""
Bandwidth optimization module for the Bharat Voice Assistant.

This module implements voice data compression while maintaining clarity,
dynamic quality adjustment based on connection speed, and progressive
loading with priority-based delivery for users in rural areas with
limited bandwidth.
"""

import asyncio
import time
import json
import io
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import BandwidthError
from bharat_voice_assistant.voice.connection_manager import ConnectionQuality, ConnectionMetrics

logger = get_logger(__name__)


class CompressionLevel(Enum):
    """Audio compression levels for different bandwidth conditions."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAXIMUM = "maximum"


class ContentPriority(Enum):
    """Content delivery priority levels."""
    CRITICAL = "critical"      # Essential system responses
    HIGH = "high"             # Important information
    MEDIUM = "medium"         # Standard responses
    LOW = "low"               # Optional content
    BACKGROUND = "background"  # Non-essential data


@dataclass
class CompressionSettings:
    """Settings for audio compression."""
    level: CompressionLevel
    target_bitrate: int  # kbps
    sample_rate: int     # Hz
    channels: int        # 1 for mono, 2 for stereo
    format: str          # mp3, ogg, etc.
    quality_factor: float  # 0.0 to 1.0


@dataclass
class ProgressiveChunk:
    """A chunk of data for progressive loading."""
    chunk_id: str
    data: bytes
    priority: ContentPriority
    size_bytes: int
    sequence_number: int
    total_chunks: int
    metadata: Dict[str, Any]
    timestamp: float


@dataclass
class BandwidthProfile:
    """Profile for bandwidth optimization decisions."""
    connection_quality: ConnectionQuality
    available_bandwidth_kbps: float
    latency_ms: float
    packet_loss_rate: float
    stability_score: float  # 0.0 to 1.0
    recommended_compression: CompressionLevel
    max_chunk_size_kb: int
    progressive_loading_enabled: bool


class BandwidthOptimizer:
    """
    Optimizes voice data transmission for low-bandwidth connections.
    
    Implements Requirements 5.1 and 5.2:
    - Voice data compression while maintaining clarity
    - Dynamic quality adjustment based on connection speed
    """
    
    def __init__(self):
        """Initialize the bandwidth optimizer."""
        self.compression_profiles = self._initialize_compression_profiles()
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.bandwidth_history: Dict[str, List[float]] = {}
        self.quality_metrics: Dict[str, Dict[str, float]] = {}
        
        # Progressive loading settings
        self.max_chunk_size_kb = 32  # Maximum chunk size in KB
        self.min_chunk_size_kb = 4   # Minimum chunk size in KB
        self.chunk_timeout_seconds = 10
        
        # Quality thresholds
        self.clarity_threshold = 0.7  # Minimum acceptable clarity score
        self.compression_efficiency_threshold = 2.0  # Minimum compression ratio
        
        logger.info("BandwidthOptimizer initialized")
    
    def _initialize_compression_profiles(self) -> Dict[CompressionLevel, CompressionSettings]:
        """Initialize compression profiles for different bandwidth conditions."""
        return {
            CompressionLevel.NONE: CompressionSettings(
                level=CompressionLevel.NONE,
                target_bitrate=128,
                sample_rate=22050,
                channels=1,
                format="mp3",
                quality_factor=1.0
            ),
            CompressionLevel.LOW: CompressionSettings(
                level=CompressionLevel.LOW,
                target_bitrate=96,
                sample_rate=16000,
                channels=1,
                format="mp3",
                quality_factor=0.9
            ),
            CompressionLevel.MEDIUM: CompressionSettings(
                level=CompressionLevel.MEDIUM,
                target_bitrate=64,
                sample_rate=16000,
                channels=1,
                format="mp3",
                quality_factor=0.8
            ),
            CompressionLevel.HIGH: CompressionSettings(
                level=CompressionLevel.HIGH,
                target_bitrate=32,
                sample_rate=12000,
                channels=1,
                format="mp3",
                quality_factor=0.7
            ),
            CompressionLevel.MAXIMUM: CompressionSettings(
                level=CompressionLevel.MAXIMUM,
                target_bitrate=16,
                sample_rate=8000,
                channels=1,
                format="mp3",
                quality_factor=0.6
            )
        }
    
    async def optimize_voice_data(self, audio_data: bytes, 
                                connection_metrics: ConnectionMetrics,
                                priority: ContentPriority = ContentPriority.MEDIUM,
                                preserve_clarity: bool = True) -> Tuple[bytes, Dict[str, Any]]:
        """
        Optimize voice data for transmission based on connection quality.
        
        Args:
            audio_data: Raw audio data to optimize
            connection_metrics: Current connection quality metrics
            priority: Content priority level
            preserve_clarity: Whether to prioritize clarity over compression
            
        Returns:
            Tuple of (optimized_audio_data, optimization_metadata)
        """
        try:
            start_time = time.time()
            
            # Create bandwidth profile
            bandwidth_profile = await self._create_bandwidth_profile(connection_metrics)
            
            # Determine compression level
            compression_level = await self._determine_compression_level(
                bandwidth_profile, priority, preserve_clarity
            )
            
            # Apply compression while maintaining clarity
            compressed_data, compression_info = await self._compress_with_clarity_preservation(
                audio_data, compression_level
            )
            
            # Validate clarity if required
            if preserve_clarity:
                clarity_score = await self._assess_audio_clarity(compressed_data, audio_data)
                if clarity_score < self.clarity_threshold:
                    logger.warning(f"Clarity score {clarity_score:.2f} below threshold, "
                                 f"reducing compression")
                    # Retry with lower compression
                    lower_compression = self._get_lower_compression_level(compression_level)
                    compressed_data, compression_info = await self._compress_with_clarity_preservation(
                        audio_data, lower_compression
                    )
            
            processing_time = time.time() - start_time
            
            # Prepare optimization metadata
            optimization_metadata = {
                "original_size": len(audio_data),
                "compressed_size": len(compressed_data),
                "compression_ratio": len(audio_data) / len(compressed_data) if compressed_data else 1.0,
                "compression_level": compression_level.value,
                "bandwidth_profile": asdict(bandwidth_profile),
                "clarity_preserved": preserve_clarity,
                "processing_time_ms": int(processing_time * 1000),
                "priority": priority.value,
                **compression_info
            }
            
            logger.debug(f"Voice data optimized: {len(audio_data)} -> {len(compressed_data)} bytes "
                        f"({compression_level.value} compression)")
            
            return compressed_data, optimization_metadata
            
        except Exception as e:
            logger.error(f"Voice data optimization failed: {e}")
            raise BandwidthError(
                "Failed to optimize voice data",
                error_code="OPTIMIZATION_FAILED",
                context={"error": str(e)}
            )
    
    async def create_progressive_chunks(self, data: bytes, 
                                      bandwidth_profile: BandwidthProfile,
                                      priority: ContentPriority = ContentPriority.MEDIUM,
                                      metadata: Dict[str, Any] = None) -> List[ProgressiveChunk]:
        """
        Create progressive loading chunks based on bandwidth profile.
        
        Args:
            data: Data to chunk
            bandwidth_profile: Current bandwidth profile
            priority: Content priority
            metadata: Additional metadata
            
        Returns:
            List of progressive chunks ordered by priority
        """
        try:
            if not bandwidth_profile.progressive_loading_enabled:
                # Return single chunk if progressive loading is disabled
                return [ProgressiveChunk(
                    chunk_id="single",
                    data=data,
                    priority=priority,
                    size_bytes=len(data),
                    sequence_number=0,
                    total_chunks=1,
                    metadata=metadata or {},
                    timestamp=time.time()
                )]
            
            # Determine optimal chunk size based on bandwidth
            chunk_size_kb = min(
                bandwidth_profile.max_chunk_size_kb,
                max(self.min_chunk_size_kb, int(bandwidth_profile.available_bandwidth_kbps / 8))
            )
            chunk_size_bytes = chunk_size_kb * 1024
            
            # Create chunks
            chunks = []
            total_chunks = (len(data) + chunk_size_bytes - 1) // chunk_size_bytes
            
            for i in range(total_chunks):
                start_idx = i * chunk_size_bytes
                end_idx = min(start_idx + chunk_size_bytes, len(data))
                chunk_data = data[start_idx:end_idx]
                
                chunk = ProgressiveChunk(
                    chunk_id=f"chunk_{i}",
                    data=chunk_data,
                    priority=priority,
                    size_bytes=len(chunk_data),
                    sequence_number=i,
                    total_chunks=total_chunks,
                    metadata=metadata or {},
                    timestamp=time.time()
                )
                chunks.append(chunk)
            
            # Sort chunks by priority (critical content first)
            chunks.sort(key=lambda x: self._get_priority_weight(x.priority), reverse=True)
            
            logger.debug(f"Created {len(chunks)} progressive chunks "
                        f"(chunk size: {chunk_size_kb}KB)")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to create progressive chunks: {e}")
            raise BandwidthError(
                "Failed to create progressive chunks",
                error_code="CHUNKING_FAILED",
                context={"error": str(e)}
            )
    
    async def adjust_quality_dynamically(self, stream_id: str,
                                       current_metrics: ConnectionMetrics,
                                       performance_feedback: Dict[str, Any] = None) -> CompressionLevel:
        """
        Dynamically adjust quality based on real-time connection metrics.
        
        Args:
            stream_id: Unique stream identifier
            current_metrics: Current connection metrics
            performance_feedback: Optional performance feedback
            
        Returns:
            Recommended compression level
        """
        try:
            # Update bandwidth history
            if stream_id not in self.bandwidth_history:
                self.bandwidth_history[stream_id] = []
            
            self.bandwidth_history[stream_id].append(current_metrics.bandwidth_kbps)
            
            # Keep only recent history (last 10 measurements)
            if len(self.bandwidth_history[stream_id]) > 10:
                self.bandwidth_history[stream_id] = self.bandwidth_history[stream_id][-10:]
            
            # Calculate bandwidth trend
            bandwidth_trend = await self._calculate_bandwidth_trend(stream_id)
            
            # Create updated bandwidth profile
            bandwidth_profile = await self._create_bandwidth_profile(current_metrics)
            
            # Adjust compression based on trend and performance
            if performance_feedback:
                await self._incorporate_performance_feedback(
                    stream_id, performance_feedback
                )
            
            # Determine new compression level
            new_compression_level = await self._determine_adaptive_compression_level(
                bandwidth_profile, bandwidth_trend, stream_id
            )
            
            # Update active stream info
            self.active_streams[stream_id] = {
                "compression_level": new_compression_level,
                "bandwidth_profile": bandwidth_profile,
                "last_update": time.time(),
                "bandwidth_trend": bandwidth_trend
            }
            
            logger.debug(f"Dynamic quality adjustment for stream {stream_id}: "
                        f"{new_compression_level.value}")
            
            return new_compression_level
            
        except Exception as e:
            logger.error(f"Dynamic quality adjustment failed: {e}")
            # Return safe default
            return CompressionLevel.MEDIUM
    
    async def _create_bandwidth_profile(self, metrics: ConnectionMetrics) -> BandwidthProfile:
        """Create bandwidth profile from connection metrics."""
        # Map connection quality to compression level
        compression_mapping = {
            ConnectionQuality.EXCELLENT: CompressionLevel.NONE,
            ConnectionQuality.GOOD: CompressionLevel.LOW,
            ConnectionQuality.FAIR: CompressionLevel.MEDIUM,
            ConnectionQuality.POOR: CompressionLevel.HIGH,
            ConnectionQuality.CRITICAL: CompressionLevel.MAXIMUM
        }
        
        # Determine max chunk size based on bandwidth
        if metrics.bandwidth_kbps >= 256:
            max_chunk_size = 64
        elif metrics.bandwidth_kbps >= 128:
            max_chunk_size = 32
        elif metrics.bandwidth_kbps >= 64:
            max_chunk_size = 16
        else:
            max_chunk_size = 8
        
        return BandwidthProfile(
            connection_quality=metrics.quality_level,
            available_bandwidth_kbps=metrics.bandwidth_kbps,
            latency_ms=metrics.latency_ms,
            packet_loss_rate=metrics.packet_loss_rate,
            stability_score=metrics.connection_stability,
            recommended_compression=compression_mapping.get(
                metrics.quality_level, CompressionLevel.MEDIUM
            ),
            max_chunk_size_kb=max_chunk_size,
            progressive_loading_enabled=metrics.bandwidth_kbps < config.network.high_quality_threshold
        )
    
    async def _determine_compression_level(self, bandwidth_profile: BandwidthProfile,
                                         priority: ContentPriority,
                                         preserve_clarity: bool) -> CompressionLevel:
        """Determine optimal compression level."""
        base_compression = bandwidth_profile.recommended_compression
        
        # Adjust based on priority
        if priority == ContentPriority.CRITICAL:
            # Critical content gets better quality
            if base_compression == CompressionLevel.MAXIMUM:
                return CompressionLevel.HIGH
            elif base_compression == CompressionLevel.HIGH:
                return CompressionLevel.MEDIUM
        elif priority == ContentPriority.LOW or priority == ContentPriority.BACKGROUND:
            # Low priority content can use higher compression
            if base_compression == CompressionLevel.NONE:
                return CompressionLevel.LOW
            elif base_compression == CompressionLevel.LOW:
                return CompressionLevel.MEDIUM
        
        # Adjust based on clarity preservation requirement
        if preserve_clarity and base_compression == CompressionLevel.MAXIMUM:
            return CompressionLevel.HIGH
        
        return base_compression
    
    async def _compress_with_clarity_preservation(self, audio_data: bytes,
                                                compression_level: CompressionLevel) -> Tuple[bytes, Dict[str, Any]]:
        """Compress audio while preserving clarity."""
        try:
            if compression_level == CompressionLevel.NONE:
                return audio_data, {"compression_applied": False}
            
            # Get compression settings
            settings = self.compression_profiles[compression_level]
            
            # Convert to AudioSegment for processing
            audio = AudioSegment.from_raw(
                io.BytesIO(audio_data),
                sample_width=2,  # 16-bit
                frame_rate=16000,  # Assume 16kHz input
                channels=1
            )
            
            # Apply clarity-preserving preprocessing
            enhanced_audio = await self._enhance_for_compression(audio, settings)
            
            # Apply compression
            compressed_buffer = io.BytesIO()
            enhanced_audio.export(
                compressed_buffer,
                format=settings.format,
                bitrate=f"{settings.target_bitrate}k",
                parameters=[
                    "-ac", str(settings.channels),
                    "-ar", str(settings.sample_rate),
                    "-q:a", str(int((1.0 - settings.quality_factor) * 9))  # Quality scale 0-9
                ]
            )
            
            compressed_data = compressed_buffer.getvalue()
            
            compression_info = {
                "compression_applied": True,
                "target_bitrate": settings.target_bitrate,
                "sample_rate": settings.sample_rate,
                "format": settings.format,
                "quality_factor": settings.quality_factor
            }
            
            return compressed_data, compression_info
            
        except Exception as e:
            logger.warning(f"Compression failed, returning original: {e}")
            return audio_data, {"compression_applied": False, "error": str(e)}
    
    async def _enhance_for_compression(self, audio: AudioSegment,
                                     settings: CompressionSettings) -> AudioSegment:
        """Enhance audio before compression to preserve clarity."""
        try:
            enhanced = audio
            
            # Normalize volume to prevent clipping
            enhanced = normalize(enhanced)
            
            # Apply gentle dynamic range compression to improve clarity
            if settings.quality_factor < 0.8:
                enhanced = compress_dynamic_range(enhanced, threshold=-20.0, ratio=2.0)
            
            # Resample if needed
            if enhanced.frame_rate != settings.sample_rate:
                enhanced = enhanced.set_frame_rate(settings.sample_rate)
            
            # Ensure mono if required
            if settings.channels == 1 and enhanced.channels > 1:
                enhanced = enhanced.set_channels(1)
            
            return enhanced
            
        except Exception as e:
            logger.warning(f"Audio enhancement failed: {e}")
            return audio
    
    async def _assess_audio_clarity(self, compressed_data: bytes, 
                                  original_data: bytes) -> float:
        """Assess audio clarity after compression."""
        try:
            # Simple clarity assessment based on spectral analysis
            # Convert both to numpy arrays for analysis
            compressed_audio = AudioSegment.from_mp3(io.BytesIO(compressed_data))
            original_audio = AudioSegment.from_raw(
                io.BytesIO(original_data),
                sample_width=2,
                frame_rate=16000,
                channels=1
            )
            
            # Convert to same format for comparison
            compressed_samples = np.array(compressed_audio.get_array_of_samples(), dtype=np.float32)
            original_samples = np.array(original_audio.get_array_of_samples(), dtype=np.float32)
            
            # Normalize
            compressed_samples = compressed_samples / np.max(np.abs(compressed_samples))
            original_samples = original_samples / np.max(np.abs(original_samples))
            
            # Calculate correlation as clarity metric
            if len(compressed_samples) == len(original_samples):
                correlation = np.corrcoef(compressed_samples, original_samples)[0, 1]
                clarity_score = max(0.0, correlation)
            else:
                # If lengths differ, use energy preservation as metric
                compressed_energy = np.mean(compressed_samples ** 2)
                original_energy = np.mean(original_samples ** 2)
                clarity_score = min(1.0, compressed_energy / original_energy) if original_energy > 0 else 0.0
            
            return clarity_score
            
        except Exception as e:
            logger.warning(f"Clarity assessment failed: {e}")
            return 0.5  # Return neutral score on error
    
    def _get_lower_compression_level(self, current_level: CompressionLevel) -> CompressionLevel:
        """Get a lower compression level for better quality."""
        level_order = [
            CompressionLevel.NONE,
            CompressionLevel.LOW,
            CompressionLevel.MEDIUM,
            CompressionLevel.HIGH,
            CompressionLevel.MAXIMUM
        ]
        
        try:
            current_index = level_order.index(current_level)
            if current_index > 0:
                return level_order[current_index - 1]
        except ValueError:
            pass
        
        return current_level
    
    def _get_priority_weight(self, priority: ContentPriority) -> int:
        """Get numeric weight for priority sorting."""
        weights = {
            ContentPriority.CRITICAL: 5,
            ContentPriority.HIGH: 4,
            ContentPriority.MEDIUM: 3,
            ContentPriority.LOW: 2,
            ContentPriority.BACKGROUND: 1
        }
        return weights.get(priority, 3)
    
    async def _calculate_bandwidth_trend(self, stream_id: str) -> str:
        """Calculate bandwidth trend for a stream."""
        if stream_id not in self.bandwidth_history or len(self.bandwidth_history[stream_id]) < 3:
            return "stable"
        
        history = self.bandwidth_history[stream_id]
        recent_avg = np.mean(history[-3:])
        older_avg = np.mean(history[:-3]) if len(history) > 3 else recent_avg
        
        if recent_avg > older_avg * 1.2:
            return "improving"
        elif recent_avg < older_avg * 0.8:
            return "degrading"
        else:
            return "stable"
    
    async def _incorporate_performance_feedback(self, stream_id: str,
                                              feedback: Dict[str, Any]):
        """Incorporate performance feedback into optimization decisions."""
        if stream_id not in self.quality_metrics:
            self.quality_metrics[stream_id] = {}
        
        # Update quality metrics
        self.quality_metrics[stream_id].update({
            "user_satisfaction": feedback.get("user_satisfaction", 0.5),
            "audio_quality_rating": feedback.get("audio_quality", 0.5),
            "loading_time_acceptable": feedback.get("loading_time_ok", True),
            "last_feedback_time": time.time()
        })
    
    async def _determine_adaptive_compression_level(self, bandwidth_profile: BandwidthProfile,
                                                  bandwidth_trend: str,
                                                  stream_id: str) -> CompressionLevel:
        """Determine compression level with adaptive adjustments."""
        base_level = bandwidth_profile.recommended_compression
        
        # Adjust based on trend
        if bandwidth_trend == "improving":
            # Bandwidth is improving, can reduce compression
            base_level = self._get_lower_compression_level(base_level)
        elif bandwidth_trend == "degrading":
            # Bandwidth is degrading, increase compression
            level_order = [
                CompressionLevel.NONE,
                CompressionLevel.LOW,
                CompressionLevel.MEDIUM,
                CompressionLevel.HIGH,
                CompressionLevel.MAXIMUM
            ]
            try:
                current_index = level_order.index(base_level)
                if current_index < len(level_order) - 1:
                    base_level = level_order[current_index + 1]
            except ValueError:
                pass
        
        # Adjust based on quality metrics if available
        if stream_id in self.quality_metrics:
            metrics = self.quality_metrics[stream_id]
            if metrics.get("audio_quality_rating", 0.5) < 0.3:
                # User reports poor quality, reduce compression
                base_level = self._get_lower_compression_level(base_level)
        
        return base_level
    
    def get_optimization_stats(self, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """Get optimization statistics."""
        if stream_id and stream_id in self.active_streams:
            return {
                "stream_id": stream_id,
                "active_streams": 1,
                "current_compression": self.active_streams[stream_id]["compression_level"].value,
                "bandwidth_history": self.bandwidth_history.get(stream_id, []),
                "quality_metrics": self.quality_metrics.get(stream_id, {})
            }
        else:
            return {
                "total_active_streams": len(self.active_streams),
                "compression_levels": {
                    stream_id: info["compression_level"].value
                    for stream_id, info in self.active_streams.items()
                },
                "average_bandwidth": np.mean([
                    np.mean(history) for history in self.bandwidth_history.values()
                    if history
                ]) if self.bandwidth_history else 0.0
            }