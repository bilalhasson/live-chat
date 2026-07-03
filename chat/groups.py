"""
Redis channel-layer group names.

conv_<id>            — one per conversation (the visitor + any operators viewing it)
site_<id>_operators  — one per site (every connected operator dashboard)
"""


def conversation_group(conversation_id) -> str:
    return f"conv_{conversation_id}"


def site_operators_group(site_id) -> str:
    return f"site_{site_id}_operators"
