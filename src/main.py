import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.database import create_tables
from src.config.cache import cache_manager
from src.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    await cache_manager.initialize()
    await create_tables()
    yield

app = FastAPI(
    title="AI Email Subject Line Optimizer",
    description="Generate and A/B test email subject line variations using AI",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)