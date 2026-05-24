from fastapi import APIRouter, HTTPException, Request

from crawler.tasks.lake_news import crawl_news_task
from crawler.tasks.lake_ri import crawl_ri_task
from crawler.tasks.macro import crawl_macro_data_task
from crawler.tasks.ticker import crawl_ticker_task

router = APIRouter(prefix="/_tasks", tags=["Internal Tasks"])


def _verify_task_auth(request: Request) -> None:
    """
    Verify that the request comes from Google Cloud Tasks or is authenticated.
    In Cloud Run, Cloud Tasks attaches an OIDC token or a specific header.
    For simplicity in this implementation, we check for 'X-CloudTasks-QueueName'
    or a fallback admin API KEY if triggered manually.
    """
    # Se for acionado pelo Cloud Tasks internamente no GCP, ele injeta esse header
    if request.headers.get("X-CloudTasks-QueueName"):
        return

    # Se for acionado por outro meio (ex: curl local), verifica a API_KEY do admin
    import os

    expected_api_key = os.getenv("API_KEY")
    auth_header = request.headers.get("Authorization", "")

    if expected_api_key and auth_header == f"Bearer {expected_api_key}":
        return

    raise HTTPException(status_code=401, detail="Unauthorized task invocation")


@router.post("/macro-data")
async def trigger_macro_data(request: Request):
    _verify_task_auth(request)
    await crawl_macro_data_task()
    return {"status": "success", "task": "macro-data"}


@router.post("/ticker/{symbol}")
async def trigger_ticker(symbol: str, request: Request):
    _verify_task_auth(request)
    await crawl_ticker_task(symbol)
    return {"status": "success", "task": "ticker", "symbol": symbol}


@router.post("/news")
async def trigger_news(request: Request):
    _verify_task_auth(request)
    await crawl_news_task()
    return {"status": "success", "task": "news"}


@router.post("/ri")
async def trigger_ri(
    request: Request,
    days_back: int | None = None,
    year: int | None = None,
):
    _verify_task_auth(request)
    persisted = await crawl_ri_task(days_back=days_back, year=year)
    mode = "year" if year is not None else ("days_back" if days_back is not None else "incremental")
    return {
        "status": "success",
        "task": "ri",
        "mode": mode,
        "days_back": days_back,
        "year": year,
        "persisted": persisted,
    }


@router.post("/enqueue-daily")
async def enqueue_daily(request: Request):
    """
    Enqueues the daily batch of tasks (Macro + all active tickers).
    This runs entirely inside Cloud Run so it inherits the correct IAM permissions.
    """
    _verify_task_auth(request)

    from loguru import logger

    from core.services.cloud_tasks_service import CloudTasksService
    from crawler.services.ticker_service import TickerService

    tasks_service = CloudTasksService()
    ticker_service = TickerService()

    logger.info("Discovering active tickers...")
    all_tickers = ticker_service.get_all_tickers()

    if not all_tickers:
        return {"status": "error", "detail": "No tickers found to enqueue."}

    logger.info("Enqueuing macro data task...")
    enqueued = 1 if tasks_service.enqueue_task("/_tasks/macro-data") else 0

    logger.info(f"Enqueuing {len(all_tickers)} ticker tasks...")
    for index, symbol in enumerate(all_tickers, start=1):
        if tasks_service.enqueue_task(f"/_tasks/ticker/{symbol}"):
            enqueued += 1
        if index % 50 == 0:
            logger.info(
                f"Processed {index}/{len(all_tickers)} tickers ({enqueued} enqueued so far)..."
            )

    attempted = len(all_tickers) + 1
    if enqueued == 0:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cloud Tasks not configured — no tasks were enqueued. "
                "Check GCP_PROJECT_ID/CLOUD_RUN_URL on the Cloud Run service."
            ),
        )

    return {"status": "success", "enqueued": enqueued, "attempted": attempted}
