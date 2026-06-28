import json
import os
import sys
import time

import redis
import requests
from loguru import logger

QUEUE_KEY = "crawler:tasks"


def start_dispatcher():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    worker_api_url = os.getenv("WORKER_API_URL", "http://127.0.0.1:8000")
    api_key = os.getenv("API_KEY", "")

    logger.info(f"Worker Dispatcher starting. Listening on Redis queue '{QUEUE_KEY}'...")

    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Worker Dispatcher failed to connect to Redis: {e}")
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "X-Task-Queue": "redis-crawler-queue",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    while True:
        try:
            # blpop returns a tuple (queue_name, data) or None on timeout
            item = r.blpop(QUEUE_KEY, timeout=5)
            if not item:
                continue

            _, raw_data = item
            task = json.loads(raw_data)
            endpoint = task.get("endpoint")
            payload = task.get("payload", {})

            if not endpoint:
                continue

            target_url = f"{worker_api_url}{endpoint}"
            logger.info(f"Worker Dispatcher executing task for endpoint: {endpoint}")

            response = requests.post(target_url, json=payload, headers=headers, timeout=300)
            if response.status_code == 200:
                logger.success(f"Task completed successfully: {endpoint}")
            else:
                logger.error(
                    f"Task execution failed for {endpoint} "
                    f"status={response.status_code} body={response.text}"
                )

        except Exception as e:
            logger.error(f"Error in Worker Dispatcher loop: {e}")
            time.sleep(2)


if __name__ == "__main__":
    start_dispatcher()
