import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import routers
from app.services.scheduler import start_scheduler, catchup_if_needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    asyncio.create_task(catchup_if_needed())
    yield


app = FastAPI(title="Cumbre — 基金智投跟投平台", lifespan=lifespan, docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in routers:
    app.include_router(router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "cumbre"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
