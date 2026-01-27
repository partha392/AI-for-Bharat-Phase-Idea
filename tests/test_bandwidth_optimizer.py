"""
Unit tests for the BandwidthOptimizer class.

Tests voice data compression, dynamic quality adjustment,
and progressive loading functionality.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

from bharat_voice_assistant.voice.bandwidth_optimizer import (
    BandwidthOptimizer,
    CompressionLevel,
    ContentPriority,
    CompressionSettings,
    ProgressiveChunk,
    BandwidthProfile
)
from bharat_voice_assistant.voice.connection_manager import (
    ConnectionQuality,
    ConnectionMetrics
)
from bharat_voice_assistant.core.exceptions import BandwidthError


class TestBandwidthOptimizer:
    """Test cases for BandwidthOptimizer."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a BandwidthOptimizer instance for testing."""
        return BandwidthOptimizer()
    
    @pytest.fixture
    def sample_audio_data(self):
        """Create sample audio data for testing."""
        return b'\x00\x01' * 8000  # 16KB of sample data
    
    @pytest.fixture
    def excellent_connection_metrics(self):
        """Create excellent connection metrics."""
        return ConnectionMetrics(
            bandwidth_kbps=512.0,
            latency_ms=50.0,
            packet_loss_rate=0.01,
            jitter_ms=5.0,
            connection_stability=0.95,
            quality_level=ConnectionQuality.EXCELLENT,
            timestamp=time.time()
        )
    
    @pytest.fixture
    def poor_connection_metrics(self):
        """Create poor connection metrics."""
        return ConnectionMetrics(
            bandwidth_kbps=32.0,
            latency_ms=800.0,
            packet_loss_rate=0.08,
            jitter_ms=80.0,
            connection_stability=0.4,
            quality_level=ConnectionQuality.POOR,
            timestamp=time.time()
        )
    
    def test_initialization(self, optimizer):
        """Test BandwidthOptimizer initialization."""
        assert optimizer is not None
        assert len(optimizer.compression_profiles) == 5
        assert CompressionLevel.NONE in optimizer.compression_profiles
        assert CompressionLevel.MAXIMUM in optimizer.compression_profiles
        assert optimizer.clarity_threshold == 0.7
        assert optimizer.compression_efficiency_threshold == 2.0
    
    def test_compression_profiles(self, optimizer):
        """Test compression profile configuration."""
        profiles = optimizer.compression_profiles
        
        # Test NONE compression
        none_profile = profiles[CompressionLevel.NONE]
        assert none_profile.target_bitrate == 128
        assert none_profile.quality_factor == 1.0
        
        # Test MAXIMUM compression
        max_profile = profiles[CompressionLevel.MAXIMUM]
        assert max_profile.target_bitrate == 16
        assert max_profile.quality_factor == 0.6
        assert max_profile.sample_rate == 8000
        
        # Test compression levels are ordered correctly
        bitrates = [profiles[level].target_bitrate for level in CompressionLevel]
        assert bitrates == sorted(bitrates, reverse=True)
    
    @pytest.mark.asyncio
    async def test_create_bandwidth_profile(self, optimizer, excellent_connection_metrics):
        """Test bandwidth profile creation."""
        profile = await optimizer._create_bandwidth_profile(excellent_connection_metrics)
        
        assert isinstance(profile, BandwidthProfile)
        assert profile.connection_quality == ConnectionQuality.EXCELLENT
        assert profile.available_bandwidth_kbps == 512.0
        assert profile.latency_ms == 50.0
        assert profile.recommended_compression == CompressionLevel.NONE
        assert profile.max_chunk_size_kb == 64
        assert not profile.progressive_loading_enabled  # High bandwidth
    
    @pytest.mark.asyncio
    async def test_create_bandwidth_profile_poor_connection(self, optimizer, poor_connection_metrics):
        """Test bandwidth profile creation for poor connection."""
        profile = await optimizer._create_bandwidth_profile(poor_connection_metrics)
        
        assert profile.connection_quality == ConnectionQuality.POOR
        assert profile.available_bandwidth_kbps == 32.0
        assert profile.recommended_compression == CompressionLevel.HIGH
        assert profile.max_chunk_size_kb == 8
        assert profile.progressive_loading_enabled  # Low bandwidth
    
    @pytest.mark.asyncio
    async def test_determine_compression_level_priority(self, optimizer):
        """Test compression level determination based on priority."""
        # Create a bandwidth profile with medium compression
        profile = BandwidthProfile(
            connection_quality=ConnectionQuality.FAIR,
            available_bandwidth_kbps=128.0,
            latency_ms=200.0,
            packet_loss_rate=0.02,
            stability_score=0.8,
            recommended_compression=CompressionLevel.MEDIUM,
            max_chunk_size_kb=16,
            progressive_loading_enabled=True
        )
        
        # Test critical priority gets better quality
        critical_level = await optimizer._determine_compression_level(
            profile, ContentPriority.CRITICAL, True
        )
        assert critical_level in [CompressionLevel.MEDIUM, CompressionLevel.LOW]
        
        # Test low priority gets higher compression
        low_level = await optimizer._determine_compression_level(
            profile, ContentPriority.LOW, True
        )
        # Should be same or higher compression than base
        assert low_level.value in [CompressionLevel.MEDIUM.value, CompressionLevel.HIGH.value]
    
    @pytest.mark.asyncio
    @patch('bharat_voice_assistant.voice.bandwidth_optimizer.AudioSegment')
    async def test_compress_with_clarity_preservation(self, mock_audio_segment, optimizer, sample_audio_data):
        """Test audio compression with clarity preservation."""
        # Mock AudioSegment behavior
        mock_audio = Mock()
        mock_audio.export = Mock()
        mock_audio_segment.from_raw.return_value = mock_audio
        
        # Mock the enhance_for_compression method
        optimizer._enhance_for_compression = AsyncMock(return_value=mock_audio)
        
        # Test compression
        compressed_data, compression_info = await optimizer._compress_with_clarity_preservation(
            sample_audio_data, CompressionLevel.MEDIUM
        )
        
        assert compression_info["compression_applied"] is True
        assert compression_info["target_bitrate"] == 64
        assert compression_info["format"] == "mp3"
    
    @pytest.mark.asyncio
    async def test_compress_with_clarity_preservation_no_compression(self, optimizer, sample_audio_data):
        """Test compression with NONE level."""
        compressed_data, compression_info = await optimizer._compress_with_clarity_preservation(
            sample_audio_data, CompressionLevel.NONE
        )
        
        assert compressed_data == sample_audio_data
        assert compression_info["compression_applied"] is False
    
    @pytest.mark.asyncio
    @patch('bharat_voice_assistant.voice.bandwidth_optimizer.AudioSegment')
    async def test_enhance_for_compression(self, mock_audio_segment, optimizer):
        """Test audio enhancement before compression."""
        # Mock AudioSegment
        mock_audio = Mock()
        mock_audio.frame_rate = 16000
        mock_audio.channels = 1
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_channels.return_value = mock_audio
        
        settings = CompressionSettings(
            level=CompressionLevel.MEDIUM,
            target_bitrate=64,
            sample_rate=16000,
            channels=1,
            format="mp3",
            quality_factor=0.8
        )
        
        enhanced = await optimizer._enhance_for_compression(mock_audio, settings)
        
        # Should return the mock audio object
        assert enhanced == mock_audio
    
    @pytest.mark.asyncio
    async def test_assess_audio_clarity_error_handling(self, optimizer):
        """Test audio clarity assessment error handling."""
        # Test with invalid data that will cause an error
        clarity_score = await optimizer._assess_audio_clarity(b"invalid", b"invalid")
        
        # Should return neutral score on error
        assert clarity_score == 0.5
    
    def test_get_lower_compression_level(self, optimizer):
        """Test getting lower compression level."""
        # Test normal case
        lower = optimizer._get_lower_compression_level(CompressionLevel.HIGH)
        assert lower == CompressionLevel.MEDIUM
        
        # Test lowest level
        lower = optimizer._get_lower_compression_level(CompressionLevel.NONE)
        assert lower == CompressionLevel.NONE
    
    def test_get_priority_weight(self, optimizer):
        """Test priority weight calculation."""
        assert optimizer._get_priority_weight(ContentPriority.CRITICAL) == 5
        assert optimizer._get_priority_weight(ContentPriority.HIGH) == 4
        assert optimizer._get_priority_weight(ContentPriority.MEDIUM) == 3
        assert optimizer._get_priority_weight(ContentPriority.LOW) == 2
        assert optimizer._get_priority_weight(ContentPriority.BACKGROUND) == 1
    
    @pytest.mark.asyncio
    async def test_optimize_voice_data_excellent_connection(self, optimizer, sample_audio_data, excellent_connection_metrics):
        """Test voice data optimization with excellent connection."""
        with patch.object(optimizer, '_compress_with_clarity_preservation') as mock_compress:
            mock_compress.return_value = (sample_audio_data, {"compression_applied": False})
            
            optimized_data, metadata = await optimizer.optimize_voice_data(
                sample_audio_data,
                excellent_connection_metrics,
                ContentPriority.MEDIUM,
                preserve_clarity=True
            )
            
            assert optimized_data == sample_audio_data
            assert metadata["original_size"] == len(sample_audio_data)
            assert metadata["compression_ratio"] == 1.0
            assert metadata["priority"] == ContentPriority.MEDIUM.value
    
    @pytest.mark.asyncio
    async def test_optimize_voice_data_poor_connection(self, optimizer, sample_audio_data, poor_connection_metrics):
        """Test voice data optimization with poor connection."""
        compressed_data = b"compressed_data"
        
        with patch.object(optimizer, '_compress_with_clarity_preservation') as mock_compress:
            with patch.object(optimizer, '_assess_audio_clarity') as mock_clarity:
                mock_compress.return_value = (compressed_data, {"compression_applied": True})
                mock_clarity.return_value = 0.8  # Good clarity
                
                optimized_data, metadata = await optimizer.optimize_voice_data(
                    sample_audio_data,
                    poor_connection_metrics,
                    ContentPriority.HIGH,
                    preserve_clarity=True
                )
                
                assert optimized_data == compressed_data
                assert metadata["original_size"] == len(sample_audio_data)
                assert metadata["compressed_size"] == len(compressed_data)
                assert metadata["priority"] == ContentPriority.HIGH.value
    
    @pytest.mark.asyncio
    async def test_optimize_voice_data_clarity_retry(self, optimizer, sample_audio_data, poor_connection_metrics):
        """Test voice data optimization with clarity retry."""
        compressed_data_1 = b"highly_compressed"
        compressed_data_2 = b"less_compressed_data"
        
        with patch.object(optimizer, '_compress_with_clarity_preservation') as mock_compress:
            with patch.object(optimizer, '_assess_audio_clarity') as mock_clarity:
                with patch.object(optimizer, '_get_lower_compression_level') as mock_lower:
                    # First compression has poor clarity
                    mock_clarity.return_value = 0.5  # Below threshold
                    mock_compress.side_effect = [
                        (compressed_data_1, {"compression_applied": True}),
                        (compressed_data_2, {"compression_applied": True})
                    ]
                    mock_lower.return_value = CompressionLevel.MEDIUM
                    
                    optimized_data, metadata = await optimizer.optimize_voice_data(
                        sample_audio_data,
                        poor_connection_metrics,
                        ContentPriority.HIGH,
                        preserve_clarity=True
                    )
                    
                    # Should have called compression twice
                    assert mock_compress.call_count == 2
                    assert optimized_data == compressed_data_2
    
    @pytest.mark.asyncio
    async def test_create_progressive_chunks_disabled(self, optimizer, sample_audio_data):
        """Test progressive chunk creation when disabled."""
        profile = BandwidthProfile(
            connection_quality=ConnectionQuality.EXCELLENT,
            available_bandwidth_kbps=512.0,
            latency_ms=50.0,
            packet_loss_rate=0.01,
            stability_score=0.95,
            recommended_compression=CompressionLevel.NONE,
            max_chunk_size_kb=64,
            progressive_loading_enabled=False
        )
        
        chunks = await optimizer.create_progressive_chunks(
            sample_audio_data, profile, ContentPriority.MEDIUM
        )
        
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "single"
        assert chunks[0].data == sample_audio_data
        assert chunks[0].total_chunks == 1
    
    @pytest.mark.asyncio
    async def test_create_progressive_chunks_enabled(self, optimizer, sample_audio_data):
        """Test progressive chunk creation when enabled."""
        profile = BandwidthProfile(
            connection_quality=ConnectionQuality.POOR,
            available_bandwidth_kbps=32.0,
            latency_ms=800.0,
            packet_loss_rate=0.08,
            stability_score=0.4,
            recommended_compression=CompressionLevel.HIGH,
            max_chunk_size_kb=8,
            progressive_loading_enabled=True
        )
        
        chunks = await optimizer.create_progressive_chunks(
            sample_audio_data, profile, ContentPriority.HIGH
        )
        
        assert len(chunks) > 1
        assert all(chunk.size_bytes <= 8 * 1024 for chunk in chunks)  # Max 8KB chunks
        assert all(chunk.priority == ContentPriority.HIGH for chunk in chunks)
        assert chunks[0].total_chunks == len(chunks)
        
        # Check sequence numbers
        sequence_numbers = [chunk.sequence_number for chunk in chunks]
        assert sequence_numbers == list(range(len(chunks)))
    
    @pytest.mark.asyncio
    async def test_create_progressive_chunks_priority_sorting(self, optimizer):
        """Test progressive chunk creation with priority sorting."""
        profile = BandwidthProfile(
            connection_quality=ConnectionQuality.FAIR,
            available_bandwidth_kbps=128.0,
            latency_ms=200.0,
            packet_loss_rate=0.02,
            stability_score=0.8,
            recommended_compression=CompressionLevel.MEDIUM,
            max_chunk_size_kb=16,
            progressive_loading_enabled=True
        )
        
        # Test with critical priority
        critical_chunks = await optimizer.create_progressive_chunks(
            b"critical_data" * 100, profile, ContentPriority.CRITICAL
        )
        
        # Test with background priority
        background_chunks = await optimizer.create_progressive_chunks(
            b"background_data" * 100, profile, ContentPriority.BACKGROUND
        )
        
        # Critical chunks should have higher priority weight
        critical_weight = optimizer._get_priority_weight(critical_chunks[0].priority)
        background_weight = optimizer._get_priority_weight(background_chunks[0].priority)
        assert critical_weight > background_weight
    
    @pytest.mark.asyncio
    async def test_adjust_quality_dynamically(self, optimizer, excellent_connection_metrics):
        """Test dynamic quality adjustment."""
        stream_id = "test_stream"
        
        compression_level = await optimizer.adjust_quality_dynamically(
            stream_id,
            excellent_connection_metrics,
            performance_feedback={
                "user_satisfaction": 0.8,
                "audio_quality": 0.9,
                "loading_time_ok": True
            }
        )
        
        assert isinstance(compression_level, CompressionLevel)
        assert stream_id in optimizer.active_streams
        assert stream_id in optimizer.bandwidth_history
        assert stream_id in optimizer.quality_metrics
        
        # Check stored data
        stream_info = optimizer.active_streams[stream_id]
        assert stream_info["compression_level"] == compression_level
        assert "bandwidth_profile" in stream_info
        assert "bandwidth_trend" in stream_info
    
    @pytest.mark.asyncio
    async def test_calculate_bandwidth_trend(self, optimizer):
        """Test bandwidth trend calculation."""
        stream_id = "trend_test"
        
        # Test with insufficient history
        trend = await optimizer._calculate_bandwidth_trend(stream_id)
        assert trend == "stable"
        
        # Add bandwidth history
        optimizer.bandwidth_history[stream_id] = [100, 120, 140, 160, 180]
        
        # Test improving trend
        trend = await optimizer._calculate_bandwidth_trend(stream_id)
        assert trend == "improving"
        
        # Test degrading trend
        optimizer.bandwidth_history[stream_id] = [200, 180, 160, 140, 120]
        trend = await optimizer._calculate_bandwidth_trend(stream_id)
        assert trend == "degrading"
        
        # Test stable trend
        optimizer.bandwidth_history[stream_id] = [150, 148, 152, 149, 151]
        trend = await optimizer._calculate_bandwidth_trend(stream_id)
        assert trend == "stable"
    
    @pytest.mark.asyncio
    async def test_incorporate_performance_feedback(self, optimizer):
        """Test performance feedback incorporation."""
        stream_id = "feedback_test"
        feedback = {
            "user_satisfaction": 0.7,
            "audio_quality": 0.6,
            "loading_time_ok": False
        }
        
        await optimizer._incorporate_performance_feedback(stream_id, feedback)
        
        assert stream_id in optimizer.quality_metrics
        metrics = optimizer.quality_metrics[stream_id]
        assert metrics["user_satisfaction"] == 0.7
        assert metrics["audio_quality_rating"] == 0.6
        assert metrics["loading_time_acceptable"] is False
        assert "last_feedback_time" in metrics
    
    @pytest.mark.asyncio
    async def test_determine_adaptive_compression_level(self, optimizer):
        """Test adaptive compression level determination."""
        profile = BandwidthProfile(
            connection_quality=ConnectionQuality.FAIR,
            available_bandwidth_kbps=128.0,
            latency_ms=200.0,
            packet_loss_rate=0.02,
            stability_score=0.8,
            recommended_compression=CompressionLevel.MEDIUM,
            max_chunk_size_kb=16,
            progressive_loading_enabled=True
        )
        
        stream_id = "adaptive_test"
        
        # Test with improving trend
        level = await optimizer._determine_adaptive_compression_level(
            profile, "improving", stream_id
        )
        assert level == CompressionLevel.LOW  # Should reduce compression
        
        # Test with degrading trend
        level = await optimizer._determine_adaptive_compression_level(
            profile, "degrading", stream_id
        )
        assert level == CompressionLevel.HIGH  # Should increase compression
        
        # Test with poor quality feedback
        optimizer.quality_metrics[stream_id] = {"audio_quality_rating": 0.2}
        level = await optimizer._determine_adaptive_compression_level(
            profile, "stable", stream_id
        )
        assert level == CompressionLevel.LOW  # Should improve quality
    
    def test_get_optimization_stats_single_stream(self, optimizer):
        """Test optimization statistics for single stream."""
        stream_id = "stats_test"
        
        # Add test data
        optimizer.active_streams[stream_id] = {
            "compression_level": CompressionLevel.MEDIUM,
            "bandwidth_profile": Mock(),
            "last_update": time.time(),
            "bandwidth_trend": "stable"
        }
        optimizer.bandwidth_history[stream_id] = [100, 120, 110]
        optimizer.quality_metrics[stream_id] = {"user_satisfaction": 0.8}
        
        stats = optimizer.get_optimization_stats(stream_id)
        
        assert stats["stream_id"] == stream_id
        assert stats["active_streams"] == 1
        assert stats["current_compression"] == CompressionLevel.MEDIUM.value
        assert stats["bandwidth_history"] == [100, 120, 110]
        assert stats["quality_metrics"]["user_satisfaction"] == 0.8
    
    def test_get_optimization_stats_all_streams(self, optimizer):
        """Test optimization statistics for all streams."""
        # Add test data for multiple streams
        optimizer.active_streams["stream1"] = {"compression_level": CompressionLevel.LOW}
        optimizer.active_streams["stream2"] = {"compression_level": CompressionLevel.HIGH}
        optimizer.bandwidth_history["stream1"] = [200, 220]
        optimizer.bandwidth_history["stream2"] = [50, 60]
        
        stats = optimizer.get_optimization_stats()
        
        assert stats["total_active_streams"] == 2
        assert "stream1" in stats["compression_levels"]
        assert "stream2" in stats["compression_levels"]
        assert stats["compression_levels"]["stream1"] == CompressionLevel.LOW.value
        assert stats["compression_levels"]["stream2"] == CompressionLevel.HIGH.value
        assert stats["average_bandwidth"] > 0
    
    @pytest.mark.asyncio
    async def test_optimize_voice_data_error_handling(self, optimizer, sample_audio_data, excellent_connection_metrics):
        """Test error handling in voice data optimization."""
        with patch.object(optimizer, '_create_bandwidth_profile') as mock_profile:
            mock_profile.side_effect = Exception("Profile creation failed")
            
            with pytest.raises(BandwidthError) as exc_info:
                await optimizer.optimize_voice_data(
                    sample_audio_data,
                    excellent_connection_metrics
                )
            
            assert exc_info.value.error_code == "OPTIMIZATION_FAILED"
    
    @pytest.mark.asyncio
    async def test_create_progressive_chunks_error_handling(self, optimizer, sample_audio_data):
        """Test error handling in progressive chunk creation."""
        # Create invalid profile that will cause errors
        invalid_profile = Mock()
        invalid_profile.progressive_loading_enabled = True
        invalid_profile.max_chunk_size_kb = None  # Invalid value
        
        with pytest.raises(BandwidthError) as exc_info:
            await optimizer.create_progressive_chunks(
                sample_audio_data, invalid_profile
            )
        
        assert exc_info.value.error_code == "CHUNKING_FAILED"


class TestCompressionSettings:
    """Test cases for CompressionSettings dataclass."""
    
    def test_compression_settings_creation(self):
        """Test CompressionSettings creation."""
        settings = CompressionSettings(
            level=CompressionLevel.MEDIUM,
            target_bitrate=64,
            sample_rate=16000,
            channels=1,
            format="mp3",
            quality_factor=0.8
        )
        
        assert settings.level == CompressionLevel.MEDIUM
        assert settings.target_bitrate == 64
        assert settings.sample_rate == 16000
        assert settings.channels == 1
        assert settings.format == "mp3"
        assert settings.quality_factor == 0.8


class TestProgressiveChunk:
    """Test cases for ProgressiveChunk dataclass."""
    
    def test_progressive_chunk_creation(self):
        """Test ProgressiveChunk creation."""
        chunk = ProgressiveChunk(
            chunk_id="test_chunk",
            data=b"test_data",
            priority=ContentPriority.HIGH,
            size_bytes=9,
            sequence_number=0,
            total_chunks=3,
            metadata={"type": "audio"},
            timestamp=time.time()
        )
        
        assert chunk.chunk_id == "test_chunk"
        assert chunk.data == b"test_data"
        assert chunk.priority == ContentPriority.HIGH
        assert chunk.size_bytes == 9
        assert chunk.sequence_number == 0
        assert chunk.total_chunks == 3
        assert chunk.metadata["type"] == "audio"
        assert isinstance(chunk.timestamp, float)


class TestBandwidthProfile:
    """Test cases for BandwidthProfile dataclass."""
    
    def test_bandwidth_profile_creation(self):
        """Test BandwidthProfile creation."""
        profile = BandwidthProfile(
            connection_quality=ConnectionQuality.GOOD,
            available_bandwidth_kbps=256.0,
            latency_ms=100.0,
            packet_loss_rate=0.02,
            stability_score=0.8,
            recommended_compression=CompressionLevel.LOW,
            max_chunk_size_kb=32,
            progressive_loading_enabled=True
        )
        
        assert profile.connection_quality == ConnectionQuality.GOOD
        assert profile.available_bandwidth_kbps == 256.0
        assert profile.latency_ms == 100.0
        assert profile.packet_loss_rate == 0.02
        assert profile.stability_score == 0.8
        assert profile.recommended_compression == CompressionLevel.LOW
        assert profile.max_chunk_size_kb == 32
        assert profile.progressive_loading_enabled is True