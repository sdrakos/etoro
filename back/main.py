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

app = FastAPI(
    title="Massive Market Data API",
    description="Wrapper over Massive.com (Polygon.io rebrand) — stocks, options, indices, crypto, forex, economy, filings, news.",
    version="1.0.0",
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


@app.get("/", tags=["health"])
def root():
    return {
        "service": "massive-api",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "categories": ["stocks", "options", "indices", "crypto", "forex", "economy", "news", "filings", "reference"],
    }


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
