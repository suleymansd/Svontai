"""Redis leases cap tenant SSE connections across API replicas."""

from uuid import uuid4


ACQUIRE = """
local now = tonumber(redis.call('TIME')[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('ZADD', KEYS[1], now + 60, ARGV[1])
redis.call('EXPIRE', KEYS[1], 90)
return 1
"""
RENEW = """
local now = tonumber(redis.call('TIME')[1])
local expires = redis.call('ZSCORE', KEYS[1], ARGV[1])
if not expires or tonumber(expires) <= now then return 0 end
redis.call('ZADD', KEYS[1], now + 60, ARGV[1])
redis.call('EXPIRE', KEYS[1], 90)
return 1
"""


class RealtimeLease:
    def __init__(self, client, tenant_id: str):
        self.client = client
        self.key = f"smartwa:sse-capacity:{tenant_id}"
        self.token = uuid4().hex

    async def acquire(self, limit: int) -> bool:
        return bool(await self.client.eval(ACQUIRE, 1, self.key, self.token, limit))

    async def renew(self) -> bool:
        return bool(await self.client.eval(RENEW, 1, self.key, self.token))

    async def release(self) -> None:
        await self.client.zrem(self.key, self.token)
