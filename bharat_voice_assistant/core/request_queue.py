"""
Request queue management module for the Bharat Voice Assistant.

This module implements request queuing for intermittent connectivity,
allowing the system to queue requests when network is unavailable and
process them when connection is restored.

Implements Requirement 5.4: Queue requests and process them when connection is restored.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import QueueError, NetworkError

logger = get_logger(__name__)


class RequestStatus(Enum):
    """Status of queued requests."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RequestPriority(Enum):
    """Priority levels for queued requests."""
    CRITICAL = 1    # Emergency requests
    HIGH = 2        # Important user actions
    MEDIUM = 3      # Standard requests
    LOW = 4         # Background tasks
    BULK = 5        # Batch operations


@dataclass
class QueuedRequest:
    """Represents a queued request."""
    request_id: str
    user_id: str
    request_type: str
    endpoint: str
    method: str
    payload: Dict[str, Any]
    headers: Dict[str, str]
    priority: RequestPriority
    status: RequestStatus
    created_at: float
    scheduled_at: Optional[float] = None
    max_retries: int = 3
    retry_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = None
    expires_at: Optional[float] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.expires_at is None:
            # Default expiration: 24 hours
            self.expires_at = self.created_at + (24 * 3600)
    
    def is_expired(self) -> bool:
        """Check if the request has expired."""
        return time.time() > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if the request can be retried."""
        return (self.retry_count < self.max_retries and 
                self.status in [RequestStatus.PENDING, RequestStatus.FAILED] and
                not self.is_expired())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "request_type": self.request_type,
            "endpoint": self.endpoint,
            "method": self.method,
            "payload": self.payload,
            "headers": self.headers,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "scheduled_at": self.scheduled_at,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "metadata": self.metadata,
            "expires_at": self.expires_at
        }


@dataclass
class QueueStats:
    """Queue performance statistics."""
    total_queued: int = 0
    pending_requests: int = 0
    processing_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    expired_requests: int = 0
    success_rate: float = 0.0
    average_processing_time: float = 0.0
    
    def update_success_rate(self):
        """Update success rate calculation."""
        total_processed = self.completed_requests + self.failed_requests
        if total_processed > 0:
            self.success_rate = self.completed_requests / total_processed
        else:
            self.success_rate = 0.0


class RequestQueue:
    """
    Manages request queuing for intermittent connectivity.
    
    Implements Requirement 5.4: Queue requests and process them when connection is restored.
    """
    
    def __init__(self, queue_dir: str = "queue", 
                 max_queue_size: int = 10000,
                 processing_interval: int = 5):
        """
        Initialize the request queue.
        
        Args:
            queue_dir: Directory for persistent queue storage
            max_queue_size: Maximum number of queued requests
            processing_interval: Interval between processing attempts (seconds)
        """
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(exist_ok=True)
        self.max_queue_size = max_queue_size
        self.processing_interval = processing_interval
        
        # Queue storage
        self.db_path = self.queue_dir / "request_queue.db"
        self._init_database()
        
        # In-memory queue for fast access
        self.memory_queue: Dict[str, QueuedRequest] = {}
        
        # Statistics
        self.stats = QueueStats()
        
        # Background processing
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Request processors (callbacks for different request types)
        self.processors: Dict[str, Callable] = {}
        
        # Network connectivity checker
        self.connectivity_checker: Optional[Callable] = None
        
        logger.info("RequestQueue initialized")
    
    async def start(self):
        """Start the request queue background processing."""
        # Load existing requests from database
        await self._load_from_database()
        
        # Start background processing task
        self._processing_task = asyncio.create_task(self._process_queue())
        
        logger.info("RequestQueue started")
    
    async def stop(self):
        """Stop the request queue and persist pending requests."""
        self._shutdown_event.set()
        
        if self._processing_task:
            self._processing_task.cancel()
        
        # Persist memory queue to database
        await self._persist_to_database()
        
        logger.info("RequestQueue stopped")
    
    def register_processor(self, request_type: str, processor: Callable):
        """
        Register a processor function for a request type.
        
        Args:
            request_type: Type of request to process
            processor: Async function to process the request
        """
        self.processors[request_type] = processor
        logger.info(f"Registered processor for request type: {request_type}")
    
    def set_connectivity_checker(self, checker: Callable):
        """
        Set a function to check network connectivity.
        
        Args:
            checker: Async function that returns True if connected
        """
        self.connectivity_checker = checker
        logger.info("Connectivity checker registered")
    
    async def enqueue(self, user_id: str, request_type: str, endpoint: str,
                     method: str = "POST", payload: Dict[str, Any] = None,
                     headers: Dict[str, str] = None, 
                     priority: RequestPriority = RequestPriority.MEDIUM,
                     max_retries: int = 3, expires_in_hours: int = 24,
                     metadata: Dict[str, Any] = None) -> str:
        """
        Enqueue a request for processing.
        
        Args:
            user_id: User identifier
            request_type: Type of request
            endpoint: API endpoint
            method: HTTP method
            payload: Request payload
            headers: Request headers
            priority: Request priority
            max_retries: Maximum retry attempts
            expires_in_hours: Hours until request expires
            metadata: Additional metadata
            
        Returns:
            Request ID
        """
        try:
            # Check queue size limit
            if len(self.memory_queue) >= self.max_queue_size:
                # Remove expired requests to make space
                await self._cleanup_expired_requests()
                
                if len(self.memory_queue) >= self.max_queue_size:
                    raise QueueError(
                        "Queue is full",
                        error_code="QUEUE_FULL",
                        context={"queue_size": len(self.memory_queue)}
                    )
            
            # Create request
            request_id = str(uuid.uuid4())
            current_time = time.time()
            
            queued_request = QueuedRequest(
                request_id=request_id,
                user_id=user_id,
                request_type=request_type,
                endpoint=endpoint,
                method=method,
                payload=payload or {},
                headers=headers or {},
                priority=priority,
                status=RequestStatus.PENDING,
                created_at=current_time,
                max_retries=max_retries,
                metadata=metadata or {},
                expires_at=current_time + (expires_in_hours * 3600)
            )
            
            # Store in memory queue
            self.memory_queue[request_id] = queued_request
            
            # Persist to database
            await self._save_request_to_db(queued_request)
            
            # Update statistics
            self.stats.total_queued += 1
            self.stats.pending_requests += 1
            
            logger.info(f"Request queued: {request_id} ({request_type})")
            return request_id
            
        except Exception as e:
            logger.error(f"Error enqueuing request: {e}")
            raise QueueError(
                "Failed to enqueue request",
                error_code="ENQUEUE_FAILED",
                context={"error": str(e)}
            )
    
    async def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a queued request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Request status information or None if not found
        """
        try:
            if request_id in self.memory_queue:
                request = self.memory_queue[request_id]
                return {
                    "request_id": request_id,
                    "status": request.status.value,
                    "created_at": request.created_at,
                    "retry_count": request.retry_count,
                    "max_retries": request.max_retries,
                    "last_error": request.last_error,
                    "expires_at": request.expires_at,
                    "is_expired": request.is_expired()
                }
            
            # Check database if not in memory
            return await self._get_request_status_from_db(request_id)
            
        except Exception as e:
            logger.error(f"Error getting request status: {e}")
            return None
    
    async def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a queued request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            True if cancelled successfully
        """
        try:
            if request_id in self.memory_queue:
                request = self.memory_queue[request_id]
                if request.status in [RequestStatus.PENDING, RequestStatus.FAILED]:
                    request.status = RequestStatus.CANCELLED
                    await self._update_request_in_db(request)
                    
                    # Update statistics
                    if request.status == RequestStatus.PENDING:
                        self.stats.pending_requests -= 1
                    
                    logger.info(f"Request cancelled: {request_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling request: {e}")
            return False
    
    async def get_queue_stats(self) -> QueueStats:
        """Get queue statistics."""
        # Update current counts
        self.stats.pending_requests = sum(
            1 for req in self.memory_queue.values()
            if req.status == RequestStatus.PENDING
        )
        self.stats.processing_requests = sum(
            1 for req in self.memory_queue.values()
            if req.status == RequestStatus.PROCESSING
        )
        
        self.stats.update_success_rate()
        return self.stats
    
    async def get_user_requests(self, user_id: str, 
                              status: Optional[RequestStatus] = None) -> List[Dict[str, Any]]:
        """
        Get requests for a specific user.
        
        Args:
            user_id: User identifier
            status: Optional status filter
            
        Returns:
            List of user requests
        """
        try:
            user_requests = []
            
            for request in self.memory_queue.values():
                if request.user_id == user_id:
                    if status is None or request.status == status:
                        user_requests.append({
                            "request_id": request.request_id,
                            "request_type": request.request_type,
                            "status": request.status.value,
                            "created_at": request.created_at,
                            "retry_count": request.retry_count,
                            "last_error": request.last_error
                        })
            
            return user_requests
            
        except Exception as e:
            logger.error(f"Error getting user requests: {e}")
            return []
    
    async def retry_failed_requests(self, user_id: Optional[str] = None) -> int:
        """
        Retry failed requests.
        
        Args:
            user_id: Optional user ID to filter requests
            
        Returns:
            Number of requests marked for retry
        """
        try:
            retry_count = 0
            
            for request in self.memory_queue.values():
                if (request.status == RequestStatus.FAILED and 
                    request.can_retry() and
                    (user_id is None or request.user_id == user_id)):
                    
                    request.status = RequestStatus.PENDING
                    await self._update_request_in_db(request)
                    retry_count += 1
            
            logger.info(f"Marked {retry_count} requests for retry")
            return retry_count
            
        except Exception as e:
            logger.error(f"Error retrying failed requests: {e}")
            return 0
    
    def _init_database(self):
        """Initialize SQLite database for persistent queue storage."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS queued_requests (
                        request_id TEXT PRIMARY KEY,
                        user_id TEXT,
                        request_type TEXT,
                        endpoint TEXT,
                        method TEXT,
                        payload TEXT,
                        headers TEXT,
                        priority INTEGER,
                        status TEXT,
                        created_at REAL,
                        scheduled_at REAL,
                        max_retries INTEGER,
                        retry_count INTEGER,
                        last_error TEXT,
                        metadata TEXT,
                        expires_at REAL
                    )
                """)
                
                # Create indexes for performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_id ON queued_requests(user_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status ON queued_requests(status)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_priority ON queued_requests(priority)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON queued_requests(created_at)
                """)
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error initializing queue database: {e}")
    
    async def _load_from_database(self):
        """Load existing requests from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM queued_requests 
                    WHERE status IN ('pending', 'processing', 'failed')
                    AND expires_at > ?
                    ORDER BY priority, created_at
                """, (time.time(),))
                
                for row in cursor.fetchall():
                    request = self._row_to_request(row)
                    self.memory_queue[request.request_id] = request
                
                logger.info(f"Loaded {len(self.memory_queue)} requests from database")
                
        except Exception as e:
            logger.error(f"Error loading requests from database: {e}")
    
    async def _save_request_to_db(self, request: QueuedRequest):
        """Save request to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO queued_requests VALUES 
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    request.request_id, request.user_id, request.request_type,
                    request.endpoint, request.method, json.dumps(request.payload),
                    json.dumps(request.headers), request.priority.value,
                    request.status.value, request.created_at, request.scheduled_at,
                    request.max_retries, request.retry_count, request.last_error,
                    json.dumps(request.metadata), request.expires_at
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error saving request to database: {e}")
    
    async def _update_request_in_db(self, request: QueuedRequest):
        """Update request in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE queued_requests SET
                    status = ?, retry_count = ?, last_error = ?, scheduled_at = ?
                    WHERE request_id = ?
                """, (
                    request.status.value, request.retry_count, request.last_error,
                    request.scheduled_at, request.request_id
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error updating request in database: {e}")
    
    async def _get_request_status_from_db(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get request status from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT status, created_at, retry_count, max_retries, 
                           last_error, expires_at FROM queued_requests 
                    WHERE request_id = ?
                """, (request_id,))
                row = cursor.fetchone()
                
                if row:
                    status, created_at, retry_count, max_retries, last_error, expires_at = row
                    return {
                        "request_id": request_id,
                        "status": status,
                        "created_at": created_at,
                        "retry_count": retry_count,
                        "max_retries": max_retries,
                        "last_error": last_error,
                        "expires_at": expires_at,
                        "is_expired": time.time() > expires_at
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting request status from database: {e}")
            return None
    
    def _row_to_request(self, row) -> QueuedRequest:
        """Convert database row to QueuedRequest object."""
        (request_id, user_id, request_type, endpoint, method, payload_json,
         headers_json, priority, status, created_at, scheduled_at, max_retries,
         retry_count, last_error, metadata_json, expires_at) = row
        
        return QueuedRequest(
            request_id=request_id,
            user_id=user_id,
            request_type=request_type,
            endpoint=endpoint,
            method=method,
            payload=json.loads(payload_json),
            headers=json.loads(headers_json),
            priority=RequestPriority(priority),
            status=RequestStatus(status),
            created_at=created_at,
            scheduled_at=scheduled_at,
            max_retries=max_retries,
            retry_count=retry_count,
            last_error=last_error,
            metadata=json.loads(metadata_json),
            expires_at=expires_at
        )
    
    async def _persist_to_database(self):
        """Persist memory queue to database."""
        try:
            for request in self.memory_queue.values():
                await self._save_request_to_db(request)
            logger.info("Memory queue persisted to database")
        except Exception as e:
            logger.error(f"Error persisting queue to database: {e}")
    
    async def _process_queue(self):
        """Background task to process queued requests."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.processing_interval)
                
                # Check connectivity if checker is available
                if self.connectivity_checker:
                    is_connected = await self.connectivity_checker()
                    if not is_connected:
                        logger.debug("No connectivity, skipping queue processing")
                        continue
                
                # Get pending requests sorted by priority
                pending_requests = [
                    req for req in self.memory_queue.values()
                    if req.status == RequestStatus.PENDING and not req.is_expired()
                ]
                
                # Sort by priority and creation time
                pending_requests.sort(key=lambda x: (x.priority.value, x.created_at))
                
                # Process requests
                for request in pending_requests[:10]:  # Process up to 10 at a time
                    await self._process_request(request)
                
                # Cleanup expired requests
                await self._cleanup_expired_requests()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processing: {e}")
    
    async def _process_request(self, request: QueuedRequest):
        """Process a single queued request."""
        try:
            # Mark as processing
            request.status = RequestStatus.PROCESSING
            self.stats.processing_requests += 1
            self.stats.pending_requests -= 1
            await self._update_request_in_db(request)
            
            # Get processor for request type
            processor = self.processors.get(request.request_type)
            if not processor:
                raise QueueError(f"No processor registered for type: {request.request_type}")
            
            # Process the request
            start_time = time.time()
            result = await processor(request)
            processing_time = time.time() - start_time
            
            # Mark as completed
            request.status = RequestStatus.COMPLETED
            self.stats.processing_requests -= 1
            self.stats.completed_requests += 1
            
            # Update average processing time
            if self.stats.completed_requests == 1:
                self.stats.average_processing_time = processing_time
            else:
                self.stats.average_processing_time = (
                    (self.stats.average_processing_time * (self.stats.completed_requests - 1) + 
                     processing_time) / self.stats.completed_requests
                )
            
            await self._update_request_in_db(request)
            
            logger.info(f"Request processed successfully: {request.request_id}")
            
        except Exception as e:
            # Mark as failed
            request.status = RequestStatus.FAILED
            request.retry_count += 1
            request.last_error = str(e)
            self.stats.processing_requests -= 1
            
            if request.can_retry():
                # Schedule for retry with exponential backoff
                backoff_seconds = min(300, 2 ** request.retry_count * 10)  # Max 5 minutes
                request.scheduled_at = time.time() + backoff_seconds
                request.status = RequestStatus.PENDING
                self.stats.pending_requests += 1
                logger.warning(f"Request failed, will retry: {request.request_id} (attempt {request.retry_count})")
            else:
                self.stats.failed_requests += 1
                logger.error(f"Request failed permanently: {request.request_id} - {e}")
            
            await self._update_request_in_db(request)
    
    async def _cleanup_expired_requests(self):
        """Remove expired requests from queue."""
        try:
            expired_requests = []
            current_time = time.time()
            
            for request_id, request in self.memory_queue.items():
                if request.is_expired():
                    expired_requests.append(request_id)
            
            for request_id in expired_requests:
                request = self.memory_queue[request_id]
                request.status = RequestStatus.EXPIRED
                await self._update_request_in_db(request)
                del self.memory_queue[request_id]
                
                # Update statistics
                if request.status == RequestStatus.PENDING:
                    self.stats.pending_requests -= 1
                elif request.status == RequestStatus.PROCESSING:
                    self.stats.processing_requests -= 1
                
                self.stats.expired_requests += 1
            
            if expired_requests:
                logger.info(f"Cleaned up {len(expired_requests)} expired requests")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired requests: {e}")


# Global request queue instance
request_queue = RequestQueue()