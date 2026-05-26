---
name: redis-toolkit
description: Production-grade Redis utilities for Python - Connection management, caching, rate limiting, distributed locking, background jobs, and session management for scalable applications.
---

# Redis Toolkit Skill

**Author:** Dr. Stefanos Drakos  
**Package:** https://github.com/sdrakos/redis_toolkit  
**Version:** 1.0  
**Python:** 3.9+

Production-grade Redis utilities for Python applications - Connection management, caching, rate limiting, distributed locking, background job processing, and session management.

## When to Use This Skill

Use this skill when building Python applications that need:
- **Caching**: Reduce database/API calls with Redis caching
- **Rate Limiting**: Protect APIs from abuse with sliding window rate limiting
- **Distributed Locking**: Prevent race conditions in concurrent operations
- **Background Jobs**: Process tasks asynchronously with RQ queues
- **Session Management**: Store conversation history for AI agents (OpenAI Agent SDK)
- **Vector Stores**: Manage OpenAI vector stores with Redis caching
- **Horizontal Scaling**: Share state across multiple servers

## Overview

The `redis_toolkit` package provides 7 main components:

1. **RedisConnectionManager** - Dual connection pools (text/binary modes)
2. **RedisCache** - Key-value caching with TTL and JSON serialization
3. **RateLimiter** - Sliding window rate limiting using sorted sets
4. **DistributedLock** - Context manager-based distributed locks
5. **QueueManager** - RQ-based job queuing with dynamic queue registration
6. **VectorStoreManager** - OpenAI Vector Store operations with caching
7. **AgentSessionManager** - Redis-based session persistence for AI agents

## Installation

```bash
# From GitHub
pip install git+https://github.com/sdrakos/redis_toolkit.git

# Or add to requirements.txt
redis_toolkit @ git+https://github.com/sdrakos/redis_toolkit.git

# Dependencies
pip install redis rq pydantic openai
```

## Quick Start

### Basic Setup

```python
from redis_toolkit import RedisConnectionManager

# From environment variables
redis_manager = RedisConnectionManager.from_env()

# Or explicit configuration
from redis_toolkit import RedisConfig

config = RedisConfig(
    host="localhost",
    port=6379,
    password=None,
    db=0,
    max_connections=50
)
redis_manager = RedisConnectionManager(config)
```

### Environment Variables

```bash
# .env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

## Core Components

### 1. Connection Manager

Manages Redis connections with dual connection pools:

```python
from redis_toolkit import RedisConnectionManager

manager = RedisConnectionManager.from_env()

# Get clients
cache_client = manager.get_cache_client()  # decode_responses=True (text/JSON)
queue_client = manager.get_queue_client()  # decode_responses=False (RQ binary)
```

**Features:**
- Dual connection pools optimized for different use cases
- Automatic connection pooling (default: 50 connections)
- Graceful degradation on connection errors
- Health check methods

### 2. Caching Layer

Simple caching with automatic JSON serialization:

```python
from redis_toolkit import RedisCache

cache = RedisCache(manager, prefix="myapp")

# Basic operations
cache.set("user:123", {"name": "John", "email": "john@example.com"}, ttl=300)
user = cache.get("user:123")  # Returns dict
cache.delete("user:123")
exists = cache.exists("user:123")

# Batch operations
cache.set_many({
    "user:1": {"name": "Alice"},
    "user:2": {"name": "Bob"}
}, ttl=600)

users = cache.get_many(["user:1", "user:2"])
cache.delete_many(["user:1", "user:2"])
```

**Use cases:**
- API response caching
- Database query results
- Computed values (expensive operations)
- User session data
- Configuration settings

### 3. Rate Limiter

Sliding window rate limiting using Redis sorted sets:

```python
from redis_toolkit import RateLimiter

limiter = RateLimiter(manager)

# Check rate limit
allowed, remaining = limiter.check(
    key="api:user:123",
    limit=100,    # max requests
    window=60,    # time window in seconds
    cost=1        # cost of this request
)

if not allowed:
    raise Exception(f"Rate limit exceeded. Retry in {remaining} seconds")

# Different costs per operation
limiter.check("api:user:123", limit=100, window=60, cost=5)  # Heavy operation
limiter.check("api:user:123", limit=100, window=60, cost=1)  # Light operation
```

**Use cases:**
- API endpoint protection
- Per-user rate limiting
- Tiered rate limits (Basic/Pro/Enterprise)
- Cost-based rate limiting (different weights per operation)

### 4. Distributed Lock

Prevent concurrent operations with distributed locks:

```python
from redis_toolkit import DistributedLock

lock = DistributedLock(manager)

# Context manager (auto-release)
with lock.acquire("resource:invoice:123", timeout=300):
    # Only one process can execute this block
    process_invoice()

# Check if locked
if lock.is_locked("resource:invoice:123"):
    print("Resource is locked by another process")

# Force release (admin/debugging)
lock.force_release("resource:invoice:123")
```

**Use cases:**
- Prevent duplicate payment processing
- Protect critical sections
- Ensure single execution of scheduled jobs
- Database migration locks
- File processing locks

### 5. Queue Manager

Dynamic RQ queue management for background jobs:

```python
from redis_toolkit import QueueManager

qm = QueueManager(manager)

# Register queues with different timeouts
qm.register_queue("emails", timeout="10m", result_ttl=3600)
qm.register_queue("reports", timeout="30m", result_ttl=7200)
qm.register_queue("critical", timeout="2m", result_ttl=1800)

# Enqueue jobs
job_id = qm.enqueue("emails", send_email, recipient="user@example.com")

# Check job status
status = qm.get_job_status(job_id)  # queued, started, finished, failed

# Get queue statistics
stats = qm.get_queue_stats("emails")
# Returns: {"queued": 5, "started": 2, "finished": 45, "failed": 1}

# Get specific queue
queue = qm.get_queue("emails")
```

**Worker setup:**
```python
# worker.py
from rq import Worker
from redis_toolkit import RedisConnectionManager, QueueManager

redis_manager = RedisConnectionManager.from_env()
qm = QueueManager(redis_manager)

worker = Worker(
    queues=[
        qm.get_queue("critical"),
        qm.get_queue("emails"),
        qm.get_queue("reports")
    ],
    connection=redis_manager.get_queue_client()
)

if __name__ == "__main__":
    worker.work()
```

**Use cases:**
- Email sending
- Report generation
- Image processing
- Webhook processing
- Data exports
- Scheduled tasks

### 6. Vector Store Manager

OpenAI Vector Store operations with Redis caching:

```python
from redis_toolkit import VectorStoreManager

vsm = VectorStoreManager(
    openai_api_key="sk-...",
    redis_manager=redis_manager,
    storage_limit_mb=50.0  # Optional storage limit
)

# Create/get vector store (cached for 5 minutes)
vs = vsm.get_or_create_vector_store(
    application="myapp",
    org_id="org123",
    name="Knowledge Base"
)

# Upload single file (background job)
job_id = vsm.upload_file(
    application="myapp",
    org_id="org123",
    filename="document.pdf",
    file_content=pdf_bytes,
    use_queue=True
)

# Monitor upload status
status = vsm.get_upload_status(job_id)
print(f"Status: {status['status']}")  # queued, started, finished, failed

# Batch upload
files_data = [
    {"filename": "doc1.pdf", "content": bytes1},
    {"filename": "doc2.pdf", "content": bytes2}
]
job_id = vsm.upload_multiple_files("myapp", "org123", files_data)

# List files
files = vsm.list_files("myapp", "org123", status="active")

# Delete file
vsm.delete_file("myapp", "org123", file_id)

# Get statistics
status = vsm.get_vector_store_status("myapp", "org123")
print(f"Files: {status['file_count']}, Usage: {status['total_usage_mb']}MB")
```

**Features:**
- Vector store creation with caching (5-minute TTL)
- Single & batch file uploads
- Background job processing
- Storage limit enforcement
- File management (list, delete)
- Automatic cache invalidation

### 7. Agent Session Manager

Redis-based session persistence for OpenAI Agent SDK conversations:

```python
from redis_toolkit import AgentSessionManager, AgentExecutor

# Create session manager
session_mgr = AgentSessionManager(
    redis_manager,
    application="myapp",
    default_ttl=14400,  # 4 hours
    max_history=50      # max messages per session
)

# Low-level session management
session_mgr.update_session("user_123", [
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"}
])

history = session_mgr.get_session("user_123")
print(f"Session has {len(history)} messages")

# High-level agent execution
executor = AgentExecutor(
    session_mgr,
    openai_api_key="sk-..."
)

agent_config = {
    "name": "Support Agent",
    "instructions": "You are a helpful support agent...",
    "model": "gpt-4o-mini",
    "temperature": 0.0
}

result = await executor.execute(
    session_id="user_123",
    user_input="What's my order status?",
    agent_config=agent_config,
    detect_language=True
)

print(f"Response: {result['response']}")
print(f"Language: {result['language']}")
```

**Features:**
- Conversation history with TTL (default: 4 hours)
- Multi-session support (per user/phone/email)
- Automatic expiration and cleanup
- History size limiting
- Language detection
- Retry logic with exponential backoff
- 10-50x faster than file-based storage

## Advanced Patterns

See reference documentation for:
- **FastAPI Integration** - Complete FastAPI examples with all components
- **Multi-Level Caching** - Memory → Redis → Database/API strategies
- **Tiered Rate Limiting** - Different limits based on subscription plans
- **Lock Patterns** - With retry, deadlock prevention
- **Priority Queues** - Critical → High → Normal → Low
- **Webhook Processing** - Fast response with background processing
- **Testing Patterns** - Mocking Redis for unit tests
- **Monitoring** - Queue stats, cache hit rates, active locks
- **Graceful Degradation** - Handling Redis unavailability

## Performance Characteristics

### Caching
- **Cache Hit:** ~1-5ms (vs 50-200ms database/API call)
- **Cache Miss:** Original latency + ~2ms Redis overhead
- **Typical Hit Rate:** 80-95% (well-designed cache)

### Rate Limiting
- **Check Latency:** ~2-3ms
- **Memory:** ~100 bytes per key per window
- **Accuracy:** Sliding window (exact)

### Distributed Locking
- **Acquire Lock:** ~2-5ms
- **Check Lock:** ~1-2ms
- **Release Lock:** ~1-2ms

### Queue Processing
- **Enqueue:** ~2-5ms (non-blocking)
- **Processing:** Depends on job (async)
- **Throughput:** 1000+ jobs/second (per worker)

## Best Practices

### 1. Connection Management
```python
# ✅ Good: Single manager instance (reuse connections)
redis_manager = RedisConnectionManager.from_env()
cache = RedisCache(redis_manager, prefix="app")

# ❌ Bad: Creating new connections everywhere
def my_function():
    manager = RedisConnectionManager.from_env()  # Don't do this!
```

### 2. Cache Key Design
```python
# ✅ Good: Hierarchical, descriptive keys
cache.set("user:123:profile", data, ttl=300)
cache.set("product:456:inventory", data, ttl=60)

# ❌ Bad: Flat, unclear keys
cache.set("u123", data, ttl=300)
cache.set("p456", data, ttl=60)
```

### 3. Cache TTL Strategy
```python
# Different TTLs for different data types
ttls = {
    "static_content": 86400,    # 24 hours
    "user_profile": 3600,       # 1 hour
    "api_response": 300,        # 5 minutes
    "real_time_data": 60        # 1 minute
}
```

### 4. Rate Limit Design
```python
# Use appropriate windows and limits
rate_limits = {
    "auth_attempts": {"limit": 5, "window": 300},      # 5 attempts per 5 minutes
    "api_calls": {"limit": 100, "window": 60},         # 100 calls per minute
    "downloads": {"limit": 10, "window": 3600},        # 10 downloads per hour
}
```

### 5. Lock Timeouts
```python
# Set appropriate timeouts based on operation
lock_timeouts = {
    "quick_update": 10,      # 10 seconds
    "payment": 60,           # 1 minute
    "report_generation": 300, # 5 minutes
}
```

### 6. Queue Priorities
```python
# Use different queues for different priorities
qm.register_queue("critical", timeout="2m")   # Payment processing
qm.register_queue("high", timeout="5m")       # Email sending
qm.register_queue("normal", timeout="10m")    # Report generation
qm.register_queue("low", timeout="30m")       # Data cleanup
```

### 7. Error Handling
```python
# Always handle Redis connection errors gracefully
try:
    cache.set("key", value, ttl=300)
except RedisConnectionError:
    logger.warning("Redis unavailable, bypassing cache")
    # Continue without cache
```

## Common Pitfalls to Avoid

❌ **Don't:** Cache everything blindly
✅ **Do:** Cache only frequently accessed, expensive-to-compute data

❌ **Don't:** Use same TTL for all data
✅ **Do:** Use appropriate TTLs based on data volatility

❌ **Don't:** Forget to invalidate cache on updates
✅ **Do:** Always invalidate related cache keys after data changes

❌ **Don't:** Use locks without timeouts
✅ **Do:** Always set appropriate timeouts to prevent deadlocks

❌ **Don't:** Block API responses with slow jobs
✅ **Do:** Use queues for long-running tasks

❌ **Don't:** Store large objects in Redis (>1MB)
✅ **Do:** Use Redis for small, frequently accessed data

❌ **Don't:** Use Redis as primary database
✅ **Do:** Use Redis as cache/queue/lock layer with proper database

## Resources

### Reference Documentation
- **fastapi_integration.md** - Complete FastAPI examples with all components
- **advanced_patterns.md** - Multi-level caching, tiered rate limiting, lock patterns
- **testing_guide.md** - Unit testing with Redis mocks
- **monitoring_observability.md** - Metrics, logging, debugging
- **deployment_guide.md** - Docker, Kubernetes, production setup
- **migration_guide.md** - Migrating from file-based/in-memory to Redis

### Examples
All examples are in the package repository:
- `examples/basic_usage.py` - All components demo
- `examples/fastapi_example.py` - FastAPI integration
- `examples/worker_example.py` - Background workers
- `examples/caching_patterns.py` - Advanced caching strategies
- `examples/vector_store_example.py` - Vector store operations
- `examples/agent_session_example.py` - Agent session management

## Troubleshooting

### Redis Connection Issues
```python
# Check if Redis is running
redis_manager = RedisConnectionManager.from_env()
try:
    client = redis_manager.get_cache_client()
    client.ping()
    print("✅ Redis is running")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
```

### Cache Not Working
```python
# Debug cache operations
cache.set("test_key", "test_value", ttl=60)
value = cache.get("test_key")
print(f"Cached value: {value}")

exists = cache.exists("test_key")
print(f"Key exists: {exists}")
```

### Rate Limiter Not Limiting
```python
# Verify rate limiter is checking correctly
for i in range(15):
    allowed, remaining = limiter.check("test:key", limit=10, window=60)
    print(f"Request {i+1}: allowed={allowed}, remaining={remaining}s")
```

### Queue Jobs Not Processing
```python
# Check worker is running
# Run: python worker.py

# Check queue stats
stats = qm.get_queue_stats("emails")
print(f"Queue stats: {stats}")

# Check job status
status = qm.get_job_status(job_id)
print(f"Job status: {status}")
```

## License

MIT License - Copyright (c) 2025 Dr. Stefanos Drakos

## Contributing

Package repository: https://github.com/sdrakos/redis_toolkit

This skill is maintained by the redis_toolkit package author.
