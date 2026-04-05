import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import jobs, search, analysis
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="104 人選自動搜尋與評分排序系統",
    description="依據公司 JD 定期搜尋 104 人力銀行人才資料庫，並以 Scorecard 評分排序",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(jobs.router)
app.include_router(search.router)
app.include_router(analysis.router)


@app.get("/")
def root():
    return {
        "name": "104 Candidate Search System",
        "version": "0.2.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
