"""eToro agent sub-portfolios (copy-trading sub-accounts) + user tokens."""
from fastapi import APIRouter, Body, Depends

from etoro_api.client import EtoroClient
from etoro_api.deps import get_etoro_client

router = APIRouter(prefix="/etoro/sub-portfolios", tags=["etoro:agent-portfolios"])


@router.get("")
def list_sub_portfolios(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/sub-portfolios")


@router.post("")
def create_sub_portfolio(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/sub-portfolios", json=body)


@router.delete("/{sub_portfolio_id}")
def delete_sub_portfolio(sub_portfolio_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/sub-portfolios/{sub_portfolio_id}")


@router.post("/{sub_portfolio_id}/user-tokens")
def create_user_token(sub_portfolio_id: str, body: dict = Body(...),
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", f"/sub-portfolios/{sub_portfolio_id}/user-tokens", json=body)


@router.patch("/{sub_portfolio_id}/user-tokens/{user_token_id}")
def update_user_token(sub_portfolio_id: str, user_token_id: str, body: dict = Body(...),
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request(
        "PATCH", f"/sub-portfolios/{sub_portfolio_id}/user-tokens/{user_token_id}", json=body)


@router.delete("/{sub_portfolio_id}/user-tokens/{user_token_id}")
def delete_user_token(sub_portfolio_id: str, user_token_id: str,
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request(
        "DELETE", f"/sub-portfolios/{sub_portfolio_id}/user-tokens/{user_token_id}")
