"""
Ephemeral presence — who's connected right now.

Backed by Redis sets, NOT the database: presence is transient and must never touch
Postgres. Two sets per site:
  * presence:site:<id>:ops           — channel names of connected operators
  * presence:site:<id>:online_convs  — ids of conversations with a live visitor

Membership uses channel names / conversation ids so add/remove is idempotent and a
count is just SCARD.

Known limitation: an unclean process crash (operator/visitor never runs disconnect)
leaves a stale set member — a phantom "online". Acceptable for v1. A hardened version
would store per-member TTLs refreshed by a heartbeat and treat expiry as offline.
"""

import redis.asyncio as aioredis
from django.conf import settings

_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _ops_key(site_id) -> str:
    return f"presence:site:{site_id}:ops"


def _convs_key(site_id) -> str:
    return f"presence:site:{site_id}:online_convs"


async def operator_join(site_id, channel: str) -> tuple[int, bool]:
    """Returns (operator_count, became_online) where became_online is a 0->1 flip."""
    key = _ops_key(site_id)
    added = await _redis.sadd(key, channel)
    count = await _redis.scard(key)
    return count, (count == 1 and added == 1)


async def operator_leave(site_id, channel: str) -> tuple[int, bool]:
    """Returns (operator_count, became_offline) where became_offline is a 1->0 flip."""
    key = _ops_key(site_id)
    removed = await _redis.srem(key, channel)
    count = await _redis.scard(key)
    return count, (count == 0 and removed == 1)


async def is_operator_online(site_id) -> bool:
    return (await _redis.scard(_ops_key(site_id))) > 0


async def visitor_join(site_id, conversation_id) -> None:
    await _redis.sadd(_convs_key(site_id), str(conversation_id))


async def visitor_leave(site_id, conversation_id) -> None:
    await _redis.srem(_convs_key(site_id), str(conversation_id))


async def online_conversation_ids(site_id) -> set:
    members = await _redis.smembers(_convs_key(site_id))
    return {int(m) for m in members}
