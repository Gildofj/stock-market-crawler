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
async def trigger_ri(request: Request, days_back: int = 30):
    _verify_task_auth(request)
    await crawl_ri_task(days_back)
    return {"status": "success", "task": "ri"}
