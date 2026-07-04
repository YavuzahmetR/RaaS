"""Phase 1 verification: make ONE real call through the configured provider and
print the answer, token usage, computed cost and latency.

    python -m app.providers.smoke_test

Requires a real API key in .env. There is no mock fallback by design — the whole
value of this project is real measurements, so a missing key fails loudly.
"""

from __future__ import annotations

import asyncio

from app.providers.base import user
from app.providers.factory import get_provider


async def _run() -> int:
    provider = get_provider()
    print(f"Provider : {provider.name} | model: {provider.model}")
    resp = await provider.generate(
        [user("Reply with exactly this sentence: RaaS smoke test OK.")],
        temperature=0.0,
        max_tokens=32,
    )
    print("-" * 60)
    print(f"Answer   : {resp.text.strip()}")
    print(
        f"Tokens   : prompt={resp.usage.prompt_tokens} "
        f"completion={resp.usage.completion_tokens} total={resp.usage.total_tokens}"
    )
    print(f"Cost     : ${resp.cost_usd:.6f}")
    print(f"Latency  : {resp.latency_ms:.0f} ms")
    print("-" * 60)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
