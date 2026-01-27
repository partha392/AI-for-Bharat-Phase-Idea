#!/usr/bin/env python3
"""
Bandwidth Optimizer Demo for Bharat Voice Assistant

This script demonstrates the bandwidth optimization features including:
- Voice data compression while maintaining clarity
- Dynamic quality adjustment based on connection speed
- Progressive loading with priority-based delivery

Usage:
    python examples/bandwidth_optimizer_demo.py
"""

import asyncio
import time
import json
from pathlib import Path

from bharat_voice_assistant.voice.bandwidth_optimizer import (
    BandwidthOptimizer,
    CompressionLevel,
    ContentPriority,
    BandwidthProfile
)
from bharat_voice_assistant.voice.connection_manager import (
    ConnectionQuality,
    ConnectionMetrics
)
from bharat_voice_assistant.core.logging import get_logger

logger = get_logger(__name__)


async def demo_voice_compression():
    """Demonstrate voice data compression with clarity preservation."""
    print("\n=== Voice Data Compression Demo ===")
    
    optimizer = BandwidthOptimizer()
    
    # Create sample audio data (simulated)
    sample_audio = b'\x00\x01' * 8000  # 16KB of sample data
    print(f"Original audio size: {len(sample_audio)} bytes")
    
    # Test different connection qualities
    connection_scenarios = [
        ("Excellent Connection", ConnectionQuality.EXCELLENT, 512.0, 50.0),
        ("Good Connection", ConnectionQuality.GOOD, 256.0, 100.0),
        ("Fair Connection", ConnectionQuality.FAIR, 128.0, 200.0),
        ("Poor Connection", ConnectionQuality.POOR, 64.0, 500.0),
        ("Critical Connection", ConnectionQuality.CRITICAL, 32.0, 1000.0)
    ]
    
    for scenario_name, quality, bandwidth, latency in connection_scenarios:
        print(f"\n--- {scenario_name} ---")
        
        # Create connection metrics
        metrics = ConnectionMetrics(
            bandwidth_kbps=bandwidth,
            latency_ms=latency,
            packet_loss_rate=0.01,
            jitter_ms=10.0,
            connection_stability=0.9,
            quality_level=quality,
            timestamp=time.time()
        )
        
        # Optimize voice data
        optimized_data, metadata = await optimizer.optimize_voice_data(
            sample_audio,
            metrics,
            priority=ContentPriority.HIGH,
            preserve_clarity=True
        )
        
        print(f"  Bandwidth: {bandwidth} kbps")
        print(f"  Compressed size: {len(optimized_data)} bytes")
        print(f"  Compression ratio: {metadata['compression_ratio']:.2f}x")
        print(f"  Compression level: {metadata['compression_level']}")
        print(f"  Processing time: {metadata['processing_time_ms']}ms")


async def demo_dynamic_quality_adjustment():
    """Demonstrate dynamic quality adjustment based on changing conditions."""
    print("\n=== Dynamic Quality Adjustment Demo ===")
    
    optimizer = BandwidthOptimizer()
    stream_id = "demo_stream_001"
    
    # Simulate changing network conditions
    network_conditions = [
        (256.0, 100.0, ConnectionQuality.GOOD),
        (128.0, 200.0, ConnectionQuality.FAIR),
        (64.0, 400.0, ConnectionQuality.POOR),
        (32.0, 800.0, ConnectionQuality.CRITICAL),
        (96.0, 300.0, ConnectionQuality.FAIR),  # Recovery
        (192.0, 150.0, ConnectionQuality.GOOD)   # Improvement
    ]
    
    print("Simulating changing network conditions...")
    
    for i, (bandwidth, latency, quality) in enumerate(network_conditions):
        print(f"\n--- Time {i+1}: Network Change ---")
        
        # Create current metrics
        current_metrics = ConnectionMetrics(
            bandwidth_kbps=bandwidth,
            latency_ms=latency,
            packet_loss_rate=0.02,
            jitter_ms=15.0,
            connection_stability=0.8,
            quality_level=quality,
            timestamp=time.time()
        )
        
        # Get dynamic quality adjustment
        recommended_compression = await optimizer.adjust_quality_dynamically(
            stream_id,
            current_metrics,
            performance_feedback={
                "user_satisfaction": 0.7,
                "audio_quality": 0.6,
                "loading_time_ok": True
            }
        )
        
        print(f"  Bandwidth: {bandwidth} kbps")
        print(f"  Latency: {latency} ms")
        print(f"  Quality: {quality.value}")
        print(f"  Recommended compression: {recommended_compression.value}")
        
        # Small delay to simulate real-time monitoring
        await asyncio.sleep(0.5)
    
    # Show optimization statistics
    stats = optimizer.get_optimization_stats(stream_id)
    print(f"\n--- Stream Statistics ---")
    print(f"Stream ID: {stats['stream_id']}")
    print(f"Current compression: {stats['current_compression']}")
    print(f"Bandwidth history: {[f'{b:.1f}' for b in stats['bandwidth_history']]}")


async def demo_progressive_loading():
    """Demonstrate progressive loading with priority-based delivery."""
    print("\n=== Progressive Loading Demo ===")
    
    optimizer = BandwidthOptimizer()
    
    # Create different types of content with priorities
    content_types = [
        ("Critical System Response", b"Critical response data" * 100, ContentPriority.CRITICAL),
        ("Important Information", b"Important info data" * 200, ContentPriority.HIGH),
        ("Standard Response", b"Standard response data" * 300, ContentPriority.MEDIUM),
        ("Optional Content", b"Optional content data" * 150, ContentPriority.LOW),
        ("Background Data", b"Background data" * 50, ContentPriority.BACKGROUND)
    ]
    
    # Test with poor connection requiring progressive loading
    poor_connection_metrics = ConnectionMetrics(
        bandwidth_kbps=48.0,
        latency_ms=600.0,
        packet_loss_rate=0.05,
        jitter_ms=50.0,
        connection_stability=0.6,
        quality_level=ConnectionQuality.POOR,
        timestamp=time.time()
    )
    
    bandwidth_profile = await optimizer._create_bandwidth_profile(poor_connection_metrics)
    
    print(f"Connection Profile:")
    print(f"  Bandwidth: {bandwidth_profile.available_bandwidth_kbps} kbps")
    print(f"  Max chunk size: {bandwidth_profile.max_chunk_size_kb} KB")
    print(f"  Progressive loading: {bandwidth_profile.progressive_loading_enabled}")
    
    for content_name, content_data, priority in content_types:
        print(f"\n--- {content_name} ({priority.value}) ---")
        print(f"  Original size: {len(content_data)} bytes")
        
        # Create progressive chunks
        chunks = await optimizer.create_progressive_chunks(
            content_data,
            bandwidth_profile,
            priority,
            metadata={"content_type": content_name}
        )
        
        print(f"  Created {len(chunks)} chunks")
        
        # Show chunk details
        for chunk in chunks[:3]:  # Show first 3 chunks
            print(f"    Chunk {chunk.sequence_number}: {chunk.size_bytes} bytes "
                  f"(priority: {chunk.priority.value})")
        
        if len(chunks) > 3:
            print(f"    ... and {len(chunks) - 3} more chunks")


async def demo_bandwidth_optimization_scenarios():
    """Demonstrate optimization for different rural connectivity scenarios."""
    print("\n=== Rural Connectivity Scenarios Demo ===")
    
    optimizer = BandwidthOptimizer()
    
    # Rural connectivity scenarios common in India
    scenarios = [
        {
            "name": "Remote Village - 2G Connection",
            "bandwidth_kbps": 16.0,
            "latency_ms": 1200.0,
            "packet_loss": 0.08,
            "stability": 0.4,
            "quality": ConnectionQuality.CRITICAL
        },
        {
            "name": "Semi-Urban - Slow 3G",
            "bandwidth_kbps": 64.0,
            "latency_ms": 400.0,
            "packet_loss": 0.03,
            "stability": 0.7,
            "quality": ConnectionQuality.POOR
        },
        {
            "name": "District Town - 3G",
            "bandwidth_kbps": 128.0,
            "latency_ms": 200.0,
            "packet_loss": 0.02,
            "stability": 0.8,
            "quality": ConnectionQuality.FAIR
        },
        {
            "name": "Urban Area - 4G",
            "bandwidth_kbps": 512.0,
            "latency_ms": 80.0,
            "packet_loss": 0.01,
            "stability": 0.95,
            "quality": ConnectionQuality.EXCELLENT
        }
    ]
    
    # Sample government scheme information (typical use case)
    scheme_info_audio = b"Government scheme information audio data" * 200  # ~7KB
    
    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")
        
        # Create connection metrics
        metrics = ConnectionMetrics(
            bandwidth_kbps=scenario['bandwidth_kbps'],
            latency_ms=scenario['latency_ms'],
            packet_loss_rate=scenario['packet_loss'],
            jitter_ms=scenario['latency_ms'] * 0.1,
            connection_stability=scenario['stability'],
            quality_level=scenario['quality'],
            timestamp=time.time()
        )
        
        # Optimize for this scenario
        optimized_data, metadata = await optimizer.optimize_voice_data(
            scheme_info_audio,
            metrics,
            priority=ContentPriority.HIGH,  # Government info is high priority
            preserve_clarity=True
        )
        
        # Create progressive chunks
        bandwidth_profile = await optimizer._create_bandwidth_profile(metrics)
        chunks = await optimizer.create_progressive_chunks(
            optimized_data,
            bandwidth_profile,
            ContentPriority.HIGH
        )
        
        # Calculate estimated delivery time
        total_size_kb = len(optimized_data) / 1024
        estimated_time_seconds = (total_size_kb * 8) / scenario['bandwidth_kbps']
        
        print(f"  Connection: {scenario['bandwidth_kbps']} kbps, "
              f"{scenario['latency_ms']} ms latency")
        print(f"  Original size: {len(scheme_info_audio)} bytes")
        print(f"  Optimized size: {len(optimized_data)} bytes "
              f"({metadata['compression_ratio']:.1f}x compression)")
        print(f"  Compression level: {metadata['compression_level']}")
        print(f"  Progressive chunks: {len(chunks)}")
        print(f"  Estimated delivery time: {estimated_time_seconds:.1f} seconds")
        
        # Show suitability for rural users
        if estimated_time_seconds <= 5:
            suitability = "Excellent"
        elif estimated_time_seconds <= 10:
            suitability = "Good"
        elif estimated_time_seconds <= 20:
            suitability = "Acceptable"
        else:
            suitability = "Poor"
        
        print(f"  Rural user experience: {suitability}")


async def demo_clarity_preservation():
    """Demonstrate clarity preservation during compression."""
    print("\n=== Clarity Preservation Demo ===")
    
    optimizer = BandwidthOptimizer()
    
    # Test with different compression levels
    sample_audio = b'\x00\x01\x02\x03' * 4000  # 16KB sample
    
    # Poor connection requiring high compression
    poor_metrics = ConnectionMetrics(
        bandwidth_kbps=32.0,
        latency_ms=800.0,
        packet_loss_rate=0.06,
        jitter_ms=80.0,
        connection_stability=0.5,
        quality_level=ConnectionQuality.CRITICAL,
        timestamp=time.time()
    )
    
    print("Testing clarity preservation with high compression...")
    
    # Test with clarity preservation enabled
    print("\n--- With Clarity Preservation ---")
    optimized_with_clarity, metadata_with = await optimizer.optimize_voice_data(
        sample_audio,
        poor_metrics,
        priority=ContentPriority.HIGH,
        preserve_clarity=True
    )
    
    print(f"  Compression ratio: {metadata_with['compression_ratio']:.2f}x")
    print(f"  Compression level: {metadata_with['compression_level']}")
    print(f"  Clarity preserved: {metadata_with['clarity_preserved']}")
    
    # Test without clarity preservation
    print("\n--- Without Clarity Preservation ---")
    optimized_without_clarity, metadata_without = await optimizer.optimize_voice_data(
        sample_audio,
        poor_metrics,
        priority=ContentPriority.HIGH,
        preserve_clarity=False
    )
    
    print(f"  Compression ratio: {metadata_without['compression_ratio']:.2f}x")
    print(f"  Compression level: {metadata_without['compression_level']}")
    print(f"  Clarity preserved: {metadata_without['clarity_preserved']}")
    
    # Compare results
    print(f"\n--- Comparison ---")
    print(f"  Size difference: {len(optimized_with_clarity) - len(optimized_without_clarity)} bytes")
    print(f"  Clarity preservation trades {metadata_without['compression_ratio'] - metadata_with['compression_ratio']:.2f}x compression for better quality")


async def main():
    """Run all bandwidth optimizer demonstrations."""
    print("Bharat Voice Assistant - Bandwidth Optimizer Demo")
    print("=" * 50)
    
    try:
        await demo_voice_compression()
        await demo_dynamic_quality_adjustment()
        await demo_progressive_loading()
        await demo_bandwidth_optimization_scenarios()
        await demo_clarity_preservation()
        
        print("\n" + "=" * 50)
        print("Bandwidth Optimizer Demo completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✓ Voice data compression while maintaining clarity")
        print("✓ Dynamic quality adjustment based on connection speed")
        print("✓ Progressive loading with priority-based delivery")
        print("✓ Rural connectivity scenario optimization")
        print("✓ Clarity preservation mechanisms")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\nDemo failed with error: {e}")


if __name__ == "__main__":
    asyncio.run(main())