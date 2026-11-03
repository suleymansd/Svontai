import asyncio
import os
from urllib.parse import urlparse
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.services.realtime_capacity import RealtimeLease


def test_lease_release_removes_only_its_owner():
    client = AsyncMock()
    first, second = RealtimeLease(client, "tenant"), RealtimeLease(client, "tenant")
    assert first.token != second.token and first.key == second.key
    asyncio.run(first.release())
    client.zrem.assert_awaited_once_with(first.key, first.token)


def test_redis_capacity_is_atomic_across_connections():
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("Requires disposable local Redis")
    parsed = urlparse(url)
    if parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.path != "/15":
        raise RuntimeError("Redis test requires local DB 15")
    async def run():
        import redis.asyncio as redis
        client = redis.Redis.from_url(url)
        tenant = f"test-{uuid4()}"
        leases = [RealtimeLease(client, tenant) for _ in range(50)]
        try:
            outcomes = await asyncio.gather(*(lease.acquire(4) for lease in leases))
            assert sum(outcomes) == 4
            active = [lease for lease, admitted in zip(leases, outcomes) if admitted]
            assert await active[0].renew()
            await active[0].release()
            assert not await active[0].renew()
            assert await RealtimeLease(client, tenant).acquire(4)
        finally:
            await client.delete(leases[0].key)
            await client.aclose()
    asyncio.run(run())
