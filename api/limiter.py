import os

from pyrate_limiter import Duration, Limiter, Rate, RedisBucket, SingleBucketFactory
from redis.asyncio import from_url

# Configuração do Redis para o Rate Limiter
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Criação do Limiter
# Definimos taxas globais que podem ser usadas em diferentes rotas
# Exemplo: 10 requisições por minuto
rates = [Rate(10, Duration.MINUTE)]

# Factory que gerencia os buckets no Redis
# Nota: Em ambiente de desenvolvimento sem Redis, poderia usar InMemoryBucket
try:
    redis_connection = from_url(redis_url, encoding="utf8", decode_responses=True)
    bucket_factory = SingleBucketFactory(
        bucket_class=RedisBucket,
        bucket_kwargs={
            "redis": redis_connection,
            "bucket_name": "api-rate-limit",
        },
    )
    limiter = Limiter(bucket_factory)
except Exception:
    # Fallback para memória se o Redis falhar (evita crash da API)
    limiter = Limiter(rates)


def get_limiter():
    return limiter
