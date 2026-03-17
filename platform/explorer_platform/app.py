"""FastAPI application — Agent Explorer platform backend."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from explorer_platform import config
from explorer_platform.auth import router as auth_router
from explorer_platform.db import init_db
from explorer_platform.deps import set_conn
from explorer_platform.explore import router as explore_router
from explorer_platform.idle import check_idle_vms
from explorer_platform.onboard import router as onboard_router
from explorer_platform.proxy import router as proxy_router
from explorer_platform.tiers import router as tier_router


async def _idle_loop():
    """Check for idle VMs every 15 minutes and suspend them."""
    while True:
        await asyncio.sleep(900)
        try:
            await check_idle_vms()
        except Exception:
            pass  # log and continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.FERNET_KEY:
        raise RuntimeError("PLATFORM_FERNET_KEY not set")
    if not config.COOKIE_SECRET:
        raise RuntimeError("PLATFORM_COOKIE_SECRET not set")

    conn = init_db(config.DB_PATH)
    set_conn(conn)

    idle_task = asyncio.create_task(_idle_loop())
    yield
    idle_task.cancel()
    conn.close()


app = FastAPI(title="Agent Explorer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(onboard_router)
app.include_router(explore_router)
app.include_router(proxy_router)
app.include_router(tier_router)


def run():
    import uvicorn
    uvicorn.run(
        "explorer_platform.app:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
    )
