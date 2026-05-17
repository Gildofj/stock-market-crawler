from kombu.exceptions import OperationalError as KombuOperationalError
from redis.exceptions import RedisError
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from crawler.services.request_manager import RequestManager

request_manager = RequestManager()

_TRANSIENT_ERRORS = (
    OperationalError,
    SQLAlchemyError,
    RedisError,
    KombuOperationalError,
    ConnectionError,
    TimeoutError,
)
