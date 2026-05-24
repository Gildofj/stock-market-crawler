"""Background task functions split by domain.

Tasks live in per-domain modules but are re-exported here so that
``from crawler.tasks import crawl_ticker_task`` keeps working for callers
(scripts/, tests/, api/routers/tasks.py). Each function is an async
coroutine invoked over HTTP by Cloud Tasks via the worker's ``/_tasks/*``
endpoints.
"""

from crawler.tasks.lake_news import crawl_news_task
from crawler.tasks.lake_ri import crawl_ri_task
from crawler.tasks.macro import crawl_macro_data_task
from crawler.tasks.ticker import crawl_ticker_task

__all__ = [
    "crawl_ticker_task",
    "crawl_macro_data_task",
    "crawl_news_task",
    "crawl_ri_task",
]
