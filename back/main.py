import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import (
    alternative,
    crypto,
    economy,
    filings,
    forex,
    indices,
    options,
    reference,
    screener,
    stocks,
)
from routers import etoro
from routers.screener import _refresh_once, CATALOG_REFRESH_S

@asynccontextmanager
async def lifespan(app: FastAPI):
    async def _loop():
        while True:
            try:
                await asyncio.to_thread(_refresh_once)
            except Exception:
                pass  # never let a refresh failure kill the loop
            await asyncio.sleep(CATALOG_REFRESH_S)
    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="Massive Market Data API",
    description="Wrapper over Massive.com (Polygon.io rebrand) — stocks, options, indices, crypto, forex, economy, filings, news.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
app.include_router(options.router)
app.include_router(indices.router)
app.include_router(crypto.router)
app.include_router(forex.router)
app.include_router(economy.router)
app.include_router(alternative.router)
app.include_router(filings.router)
app.include_router(reference.router)
app.include_router(screener.router)
app.include_router(etoro.router)


@app.get("/", tags=["health"])
def root():
    return {
        "service": "massive-api",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "categories": ["stocks", "options", "indices", "crypto", "forex", "economy", "news", "filings", "reference", "etoro"],
    }


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8765, reload=True)
