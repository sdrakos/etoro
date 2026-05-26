from fastapi import APIRouter, Depends
from typing import Optional

from config import get_client
from utils import safe_call, take, to_dict

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("/index")
def filings_index(
    ticker: Optional[str] = None,
    cik: Optional[str] = None,
    form_type: Optional[str] = None,
    filing_date_gte: Optional[str] = None,
    filing_date_lte: Optional[str] = None,
    limit: int = 100,
    client=Depends(get_client),
):
    params = {k: v for k, v in {
        "ticker": ticker, "cik": cik, "form_type": form_type,
        "filing_date.gte": filing_date_gte, "filing_date.lte": filing_date_lte,
    }.items() if v}
    it = safe_call(client.list_filings_index, **params, limit=1000)
    return take(it, limit)


@router.get("/10k/{ticker}")
def ten_k_sections(ticker: str, limit: int = 20, client=Depends(get_client)):
    it = safe_call(client.list_10k_sections, ticker=ticker, limit=100)
    return take(it, limit)


@router.get("/8k/{ticker}")
def eight_k_text(ticker: str, limit: int = 50, client=Depends(get_client)):
    it = safe_call(client.list_8k_text, ticker=ticker, limit=200)
    return take(it, limit)


@router.get("/13f")
def thirteen_f(
    cik: Optional[str] = None,
    ticker: Optional[str] = None,
    limit: int = 100,
    client=Depends(get_client),
):
    params = {k: v for k, v in {"cik": cik, "ticker": ticker}.items() if v}
    it = safe_call(client.list_13f_filings, **params, limit=1000)
    return take(it, limit)


@router.get("/risk-factors/{ticker}")
def risk_factors(ticker: str, limit: int = 100, client=Depends(get_client)):
    it = safe_call(client.list_risk_factors, ticker=ticker, limit=1000)
    return take(it, limit)


@router.get("/risk-categories")
def risk_categories(client=Depends(get_client)):
    return to_dict(safe_call(client.get_risk_categories))


@router.get("/form-3")
def form_3(
    cik: Optional[str] = None,
    ticker: Optional[str] = None,
    limit: int = 100,
    client=Depends(get_client),
):
    params = {k: v for k, v in {"cik": cik, "ticker": ticker}.items() if v}
    it = safe_call(client.list_form_3, **params, limit=1000)
    return take(it, limit)


@router.get("/form-4")
def form_4(
    cik: Optional[str] = None,
    ticker: Optional[str] = None,
    filing_date_gte: Optional[str] = None,
    filing_date_lte: Optional[str] = None,
    limit: int = 100,
    client=Depends(get_client),
):
    params = {k: v for k, v in {
        "cik": cik, "ticker": ticker,
        "filing_date.gte": filing_date_gte, "filing_date.lte": filing_date_lte,
    }.items() if v}
    it = safe_call(client.list_form_4, **params, limit=1000)
    return take(it, limit)
