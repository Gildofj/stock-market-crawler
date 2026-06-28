import json
import os
from typing import Any

import redis
from loguru import logger

from core.config import settings


class RedisTaskQueueService:
    QUEUE_KEY = "crawler:tasks"

    def __init__(self):
        redis_url = os.getenv("REDIS_URL") or settings.REDIS_URL or "redis://localhost:6379/0"
        try:
            self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning(f"Could not initialize Redis client for queue: {e}")
            self.client = None

    def enqueue_task(self, endpoint: str, payload: dict[str, Any] | None = None) -> bool:
        """Enqueue a task to the native Redis queue. Returns True if successfully enqueued."""
        if not self.client:
            logger.error("Redis queue client not configured. Task NOT enqueued.")
            return False

        task_data = {
            "endpoint": endpoint,
            "payload": payload or {},
        }

        try:
            self.client.rpush(self.QUEUE_KEY, json.dumps(task_data))
            logger.debug(f"Enqueued task to Redis: {endpoint}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue task to Redis ({endpoint}): {e}")
            return False
