from redis.asyncio import Redis
from fastapi import HTTPException
from apps.api.config import settings


def _parse(spec: str) -> tuple[int,int]:
    try:
        count_s, unit = spec.split('/',1)
        count=int(count_s)
    except Exception:
        return 20,60
    seconds={'second':1,'minute':60,'hour':3600}.get(unit.rstrip('s'),60)
    return count,seconds


async def enforce_rate_limit(subject: str, scope: str='ask') -> None:
    limit, window=_parse(settings.rate_limit_ask)
    redis=Redis.from_url(settings.redis_url,decode_responses=True)
    key=f"ratelimit:{scope}:{subject}"
    try:
        current=await redis.incr(key)
        if current == 1:
            await redis.expire(key,window)
        if current > limit:
            ttl=await redis.ttl(key)
            raise HTTPException(429,detail=f"Rate limit exceeded. Retry in {max(ttl,1)} seconds.",headers={"Retry-After":str(max(ttl,1))})
    finally:
        await redis.aclose()
