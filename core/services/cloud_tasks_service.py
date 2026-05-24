import json
import os
from typing import Any

from google.cloud import tasks_v2
from loguru import logger

from core.config import settings


class CloudTasksService:
    def __init__(self):
        self.project = settings.GCP_PROJECT_ID
        self.location = os.getenv("CLOUD_TASKS_LOCATION", "us-central1")
        self.queue = os.getenv("CLOUD_TASKS_QUEUE", "crawler-queue")
        self.base_url = os.getenv("CLOUD_RUN_URL", "http://localhost:8000")
        # When set, talks to a local emulator (aertje/cloud-tasks-emulator) via
        # plaintext gRPC. The emulator does not validate OIDC, so tokens are
        # also skipped on the produced tasks.
        self.emulator_host = os.getenv("CLOUD_TASKS_EMULATOR_HOST")
        self.client = None

        if self.project:
            try:
                if self.emulator_host:
                    import grpc
                    from google.cloud.tasks_v2.services.cloud_tasks.transports import (
                        CloudTasksGrpcTransport,
                    )

                    channel = grpc.insecure_channel(self.emulator_host)
                    self.client = tasks_v2.CloudTasksClient(
                        transport=CloudTasksGrpcTransport(channel=channel)
                    )
                else:
                    self.client = tasks_v2.CloudTasksClient()
                self.parent = self.client.queue_path(self.project, self.location, self.queue)
            except Exception as e:
                logger.warning(f"Could not initialize CloudTasksClient: {e}")

    def enqueue_task(self, endpoint: str, payload: dict[str, Any] | None = None) -> None:
        """
        Enqueue a task to Cloud Tasks. If GCP_PROJECT_ID is not set,
        fallback to logging (or in a real local dev, a direct HTTP post).
        """
        url = f"{self.base_url}{endpoint}"

        if not self.client or not self.project:
            logger.info(f"[Local Fallback] Enqueuing task to {url} with payload {payload}")
            return

        task: dict[str, Any] = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-type": "application/json"},
            }
        }

        if not self.emulator_host:
            service_account_email = f"cloud-run-api-sa@{self.project}.iam.gserviceaccount.com"
            task["http_request"]["oidc_token"] = {
                "service_account_email": service_account_email,
                "audience": self.base_url,
            }

        if payload is not None:
            task["http_request"]["body"] = json.dumps(payload).encode()

        try:
            response = self.client.create_task(
                tasks_v2.CreateTaskRequest(
                    parent=self.parent,
                    task=task,
                )
            )
            logger.debug(f"Created task {response.name}")
        except Exception as e:
            logger.error(f"Failed to create Cloud Task: {e}")
            raise
