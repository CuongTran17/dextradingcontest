from contextlib import asynccontextmanager
from typing import Any, Callable


def build_lifespan(*, init_db: Callable[[], None]):
    @asynccontextmanager
    async def lifespan(app: Any):
        del app
        init_db()
        yield

    return lifespan
