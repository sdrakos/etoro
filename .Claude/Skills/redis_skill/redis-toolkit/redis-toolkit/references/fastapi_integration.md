# FastAPI Integration Guide

Complete guide for integrating redis_toolkit with FastAPI applications.

## Basic Setup

### Dependencies Installation

```python
# dependencies.py
from redis_toolkit import (
    RedisConnectionManager,
    RedisCache,
    RateLimiter,
    DistributedLock,
    QueueManager
)
from fastapi import Depends, HTTPException
import os

# Singleton instances
_redis_manager: RedisConnectionManager = None
_cache: RedisCache = None
_limiter: RateLimiter = None
_lock: DistributedLock = None
_queue_manager: QueueManager = None

def get_redis_manager() -> RedisConnectionManager:
    """Get Redis connection manager (singleton)"""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisConnectionManager.from_env()
    return _redis_manager

def get_cache(manager: RedisConnectionManager = Depends(get_redis_manager)) -> RedisCache:
    """Get Redis cache instance"""
    global _cache
    if _cache is None:
        _cache = RedisCache(manager, prefix=os.environ.get("APP_NAME", "myapp"))
    return _cache

def get_rate_limiter(manager: RedisConnectionManager = Depends(get_redis_manager)) -> RateLimiter:
    """Get rate limiter instance"""
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(manager)
    return _limiter

def get_distributed_lock(manager: RedisConnectionManager = Depends(get_redis_manager)) -> DistributedLock:
    """Get distributed lock instance"""
    global _lock
    if _lock is None:
        _lock = DistributedLock(manager)
    return _lock

def get_queue_manager(manager: RedisConnectionManager = Depends(get_redis_manager)) -> QueueManager:
    """Get queue manager instance"""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager(manager)
        # Register default queues
        _queue_manager.register_queue("default", timeout="10m", result_ttl=3600)
        _queue_manager.register_queue("high-priority", timeout="5m", result_ttl=1800)
        _queue_manager.register_queue("low-priority", timeout="30m", result_ttl=7200)
    return _queue_manager
```

### Main Application

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dependencies import (
    get_redis_manager,
    get_cache,
    get_rate_limiter,
    get_distributed_lock,
    get_queue_manager
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    # Startup
    logger.info("Starting application...")
    redis_manager = get_redis_manager()
    
    try:
        cache_client = redis_manager.get_cache_client()
        cache_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")

app = FastAPI(
    title="My API with Redis",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check(
    redis_manager = Depends(get_redis_manager)
):
    """Health check endpoint with Redis status"""
    try:
        cache_client = redis_manager.get_cache_client()
        cache_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "ok",
        "redis": redis_status
    }
```

## Rate Limiting

### Global Rate Limiting Dependency

```python
# dependencies.py (add this)
from typing import Annotated

async def rate_limit_global(
    request: Request,
    limiter: RateLimiter = Depends(get_rate_limiter)
):
    """Global rate limit: 100 requests per minute per IP"""
    ip = request.client.host
    
    allowed, remaining = limiter.check(
        key=f"global:{ip}",
        limit=100,
        window=60
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {remaining} seconds",
            headers={"Retry-After": str(remaining)}
        )

# Type alias for cleaner code
RateLimitDep = Annotated[None, Depends(rate_limit_global)]
```

### Per-User Rate Limiting

```python
# dependencies.py
async def rate_limit_per_user(
    user_id: str,  # From auth dependency
    limiter: RateLimiter = Depends(get_rate_limiter)
):
    """Per-user rate limit: 1000 requests per hour"""
    allowed, remaining = limiter.check(
        key=f"user:{user_id}",
        limit=1000,
        window=3600
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"User rate limit exceeded. Retry after {remaining} seconds",
            headers={"Retry-After": str(remaining)}
        )
```

### Usage in Endpoints

```python
# main.py
@app.get("/api/data")
async def get_data(
    _: RateLimitDep,  # Apply global rate limit
    cache: RedisCache = Depends(get_cache)
):
    """Endpoint with rate limiting"""
    # Check cache first
    cached_data = cache.get("data:list")
    if cached_data:
        return cached_data
    
    # Fetch data
    data = fetch_data_from_database()
    
    # Cache for 5 minutes
    cache.set("data:list", data, ttl=300)
    
    return data

@app.post("/api/users/{user_id}/action")
async def user_action(
    user_id: str,
    _global: RateLimitDep,
    limiter: RateLimiter = Depends(get_rate_limiter)
):
    """Endpoint with both global and per-user rate limiting"""
    # Additional per-user check
    await rate_limit_per_user(user_id, limiter)
    
    # Process action
    result = process_user_action(user_id)
    return {"success": True, "result": result}
```

### Tiered Rate Limiting

```python
# services/rate_limiting.py
from enum import Enum

class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class TieredRateLimiter:
    def __init__(self, redis_manager):
        self.limiter = RateLimiter(redis_manager)
        
        self.tier_limits = {
            SubscriptionTier.FREE: {"limit": 10, "window": 60},
            SubscriptionTier.BASIC: {"limit": 100, "window": 60},
            SubscriptionTier.PRO: {"limit": 1000, "window": 60},
            SubscriptionTier.ENTERPRISE: {"limit": 10000, "window": 60}
        }
    
    def check(self, user_id: str, tier: SubscriptionTier):
        """Check rate limit based on subscription tier"""
        limits = self.tier_limits[tier]
        
        allowed, remaining = self.limiter.check(
            key=f"tier:{tier.value}:user:{user_id}",
            **limits
        )
        
        return allowed, remaining, limits["limit"]

# Usage
@app.get("/api/premium-feature")
async def premium_feature(
    user_id: str,
    user_tier: SubscriptionTier,  # From auth/database
    redis_manager = Depends(get_redis_manager)
):
    """Endpoint with tiered rate limiting"""
    tier_limiter = TieredRateLimiter(redis_manager)
    allowed, remaining, limit = tier_limiter.check(user_id, user_tier)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Tier limit reached ({limit} req/min for {user_tier.value})",
            headers={"Retry-After": str(remaining)}
        )
    
    return {"data": "premium content"}
```

## Caching Patterns

### Simple Cache-Aside Pattern

```python
@app.get("/api/users/{user_id}")
async def get_user(
    user_id: str,
    cache: RedisCache = Depends(get_cache)
):
    """Get user with cache-aside pattern"""
    cache_key = f"user:{user_id}"
    
    # Check cache
    cached_user = cache.get(cache_key)
    if cached_user:
        return {"user": cached_user, "source": "cache"}
    
    # Cache miss - fetch from database
    user = fetch_user_from_database(user_id)
    
    if user is None:
        raise HTTPException(404, "User not found")
    
    # Cache for 1 hour
    cache.set(cache_key, user, ttl=3600)
    
    return {"user": user, "source": "database"}
```

### Cache with Write-Through

```python
@app.post("/api/users")
async def create_user(
    user_data: dict,
    cache: RedisCache = Depends(get_cache)
):
    """Create user with write-through caching"""
    # Write to database
    user = create_user_in_database(user_data)
    
    # Immediately write to cache
    cache_key = f"user:{user['id']}"
    cache.set(cache_key, user, ttl=3600)
    
    return {"user": user}

@app.put("/api/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: dict,
    cache: RedisCache = Depends(get_cache)
):
    """Update user with cache invalidation"""
    # Update database
    user = update_user_in_database(user_id, user_data)
    
    # Invalidate cache
    cache_key = f"user:{user_id}"
    cache.delete(cache_key)
    
    # Optionally: Update cache immediately (write-through)
    cache.set(cache_key, user, ttl=3600)
    
    return {"user": user}
```

### Multi-Level Caching

```python
from functools import lru_cache

# Level 1: In-memory cache (LRU)
@lru_cache(maxsize=100)
def get_config_from_memory(config_key: str):
    """Memory cache for config (fastest)"""
    return None  # Will be populated

# Level 2: Redis cache
async def get_config_from_redis(config_key: str, cache: RedisCache):
    """Redis cache (fast)"""
    return cache.get(f"config:{config_key}")

# Level 3: Database (slowest)
async def get_config_from_database(config_key: str):
    """Database (authoritative source)"""
    return fetch_config_from_db(config_key)

@app.get("/api/config/{config_key}")
async def get_config(
    config_key: str,
    cache: RedisCache = Depends(get_cache)
):
    """Multi-level cache: Memory → Redis → Database"""
    
    # Level 1: Memory
    config = get_config_from_memory(config_key)
    if config:
        return {"config": config, "source": "memory"}
    
    # Level 2: Redis
    config = await get_config_from_redis(config_key, cache)
    if config:
        # Populate memory cache
        get_config_from_memory.__wrapped__(config_key, config)
        return {"config": config, "source": "redis"}
    
    # Level 3: Database
    config = await get_config_from_database(config_key)
    if config:
        # Populate Redis cache (24 hours for config)
        cache.set(f"config:{config_key}", config, ttl=86400)
        return {"config": config, "source": "database"}
    
    raise HTTPException(404, "Config not found")
```

## Distributed Locking

### Prevent Duplicate Processing

```python
@app.post("/api/orders/{order_id}/process")
async def process_order(
    order_id: str,
    lock: DistributedLock = Depends(get_distributed_lock)
):
    """Process order with distributed lock"""
    lock_key = f"order:process:{order_id}"
    
    # Try to acquire lock (30 second timeout)
    with lock.acquire(lock_key, timeout=30):
        # Check if already processed
        order = get_order_from_database(order_id)
        if order["status"] == "processed":
            return {"message": "Order already processed"}
        
        # Process order (only one instance will execute this)
        result = process_order_payment(order_id)
        update_order_status(order_id, "processed")
        
        return {"message": "Order processed", "result": result}
```

### Lock with Retry

```python
import asyncio

async def process_with_retry(
    order_id: str,
    lock: DistributedLock,
    max_retries: int = 3
):
    """Process with lock retry logic"""
    lock_key = f"order:process:{order_id}"
    
    for attempt in range(max_retries):
        try:
            with lock.acquire(lock_key, timeout=5, blocking=False):
                # Process
                return process_order_payment(order_id)
        except Exception:
            if attempt < max_retries - 1:
                # Wait with exponential backoff
                await asyncio.sleep(2 ** attempt)
            else:
                raise HTTPException(
                    503,
                    "Resource is locked, please retry later"
                )

@app.post("/api/orders/{order_id}/process-retry")
async def process_order_with_retry(
    order_id: str,
    lock: DistributedLock = Depends(get_distributed_lock)
):
    """Process order with retry logic"""
    result = await process_with_retry(order_id, lock)
    return {"result": result}
```

## Background Job Processing

### Enqueue Jobs

```python
# tasks.py
"""Background tasks"""
import logging

logger = logging.getLogger(__name__)

def send_email(recipient: str, subject: str, body: str):
    """Send email (runs in background worker)"""
    logger.info(f"Sending email to {recipient}: {subject}")
    # Send email logic here
    time.sleep(2)  # Simulate email sending
    logger.info(f"Email sent to {recipient}")

def generate_report(user_id: str, report_type: str):
    """Generate report (runs in background worker)"""
    logger.info(f"Generating {report_type} report for user {user_id}")
    # Generate report logic here
    time.sleep(10)  # Simulate long-running task
    logger.info(f"Report generated for user {user_id}")
    return f"report_{user_id}_{report_type}.pdf"

def process_upload(file_id: str, file_path: str):
    """Process uploaded file (runs in background worker)"""
    logger.info(f"Processing file {file_id}")
    # Process file logic here
    time.sleep(5)
    logger.info(f"File {file_id} processed")
```

### Endpoints with Background Jobs

```python
# main.py
from tasks import send_email, generate_report, process_upload

@app.post("/api/contact")
async def contact_form(
    email: str,
    message: str,
    queue_manager: QueueManager = Depends(get_queue_manager)
):
    """Contact form with background email"""
    # Enqueue email job (non-blocking)
    job_id = queue_manager.enqueue(
        "default",
        send_email,
        recipient=email,
        subject="Contact Form Submission",
        body=message
    )
    
    return {
        "message": "Thank you! We'll get back to you soon.",
        "job_id": job_id
    }

@app.post("/api/reports/generate")
async def generate_user_report(
    user_id: str,
    report_type: str,
    queue_manager: QueueManager = Depends(get_queue_manager)
):
    """Generate report in background"""
    # Enqueue report generation (long-running task)
    job_id = queue_manager.enqueue(
        "low-priority",  # Use low-priority queue
        generate_report,
        user_id=user_id,
        report_type=report_type
    )
    
    return {
        "message": "Report generation started",
        "job_id": job_id,
        "status_url": f"/api/jobs/{job_id}/status"
    }

@app.get("/api/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    queue_manager: QueueManager = Depends(get_queue_manager)
):
    """Check job status"""
    status = queue_manager.get_job_status(job_id)
    
    return {
        "job_id": job_id,
        "status": status
    }
```

### Webhook Processing

```python
@app.post("/api/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    queue_manager: QueueManager = Depends(get_queue_manager)
):
    """Fast webhook handler with background processing"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    # Verify signature (fast)
    try:
        event = verify_stripe_webhook(payload, sig_header)
    except Exception:
        raise HTTPException(400, "Invalid signature")
    
    # Queue for background processing (very fast!)
    job_id = queue_manager.enqueue(
        "high-priority",
        process_stripe_event,
        event_id=event["id"],
        event_type=event["type"],
        data=event["data"]
    )
    
    # Return immediately (<50ms)
    return {"received": True, "job_id": job_id}

# tasks.py
def process_stripe_event(event_id: str, event_type: str, data: dict):
    """Process Stripe event (background worker)"""
    logger.info(f"Processing Stripe event: {event_type} ({event_id})")
    
    if event_type == "payment_intent.succeeded":
        update_payment_status(data["object"]["id"], "succeeded")
    elif event_type == "customer.subscription.updated":
        sync_subscription(data["object"]["id"])
    
    logger.info(f"Stripe event processed: {event_id}")
```

## Monitoring & Admin Endpoints

```python
@app.get("/api/admin/redis/stats")
async def get_redis_stats(
    redis_manager = Depends(get_redis_manager)
):
    """Get Redis statistics"""
    cache_client = redis_manager.get_cache_client()
    info = cache_client.info("stats")
    
    return {
        "keyspace_hits": info.get("keyspace_hits", 0),
        "keyspace_misses": info.get("keyspace_misses", 0),
        "hit_rate": info.get("keyspace_hits", 0) / 
                   (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1)),
        "connected_clients": info.get("connected_clients", 0),
        "used_memory_human": info.get("used_memory_human", "unknown")
    }

@app.get("/api/admin/queues/stats")
async def get_queue_stats(
    queue_manager: QueueManager = Depends(get_queue_manager)
):
    """Get statistics for all queues"""
    queues = ["default", "high-priority", "low-priority"]
    
    stats = {}
    for queue_name in queues:
        stats[queue_name] = queue_manager.get_queue_stats(queue_name)
    
    return stats

@app.get("/api/admin/locks/active")
async def get_active_locks(
    redis_manager = Depends(get_redis_manager)
):
    """Get all active locks"""
    cache_client = redis_manager.get_cache_client()
    
    # Get all lock keys
    lock_keys = cache_client.keys("lock:*")
    
    active_locks = []
    for key in lock_keys:
        ttl = cache_client.ttl(key)
        if ttl > 0:
            active_locks.append({
                "key": key.decode() if isinstance(key, bytes) else key,
                "ttl_seconds": ttl
            })
    
    return {"active_locks": active_locks, "count": len(active_locks)}
```

## Complete Example

See full working example in `references/complete_fastapi_example.py`
