"""eToro social endpoints: feeds, watchlists, curated lists, recommendations,
copiers, and user-info / analytics."""
from typing import Optional
from fastapi import APIRouter, Body, Depends

from etoro_api.client import EtoroClient, drop_none
from etoro_api.deps import get_etoro_client

router = APIRouter(prefix="/etoro", tags=["etoro:social"])


# ---------------- Feeds ----------------

@router.get("/feeds/instrument/{market_id}")
def feed_instrument(market_id: str, requesterUserId: Optional[int] = None,
                    take: Optional[int] = None, offset: Optional[int] = None,
                    client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/feeds/instrument/{market_id}", params=drop_none({
        "requesterUserId": requesterUserId, "take": take, "offset": offset}))


@router.get("/feeds/user/{user_id}")
def feed_user(user_id: int, requesterUserId: Optional[int] = None,
              take: Optional[int] = None, offset: Optional[int] = None,
              client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/feeds/user/{user_id}", params=drop_none({
        "requesterUserId": requesterUserId, "take": take, "offset": offset}))


@router.post("/feeds/post")
def feed_post(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/feeds/post", json=body)


# ---------------- Watchlists ----------------

@router.get("/watchlists")
def list_watchlists(itemsPerPageForSingle: Optional[int] = None,
                    ensureBuiltinWatchlists: Optional[bool] = None,
                    addRelatedAssets: Optional[bool] = None,
                    client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/watchlists", params=drop_none({
        "itemsPerPageForSingle": itemsPerPageForSingle,
        "ensureBuiltinWatchlists": ensureBuiltinWatchlists,
        "addRelatedAssets": addRelatedAssets}))


@router.get("/watchlists/{watchlist_id}")
def get_watchlist(watchlist_id: str, pageNumber: Optional[int] = None,
                  itemsPerPage: Optional[int] = None,
                  client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/watchlists/{watchlist_id}", params=drop_none({
        "pageNumber": pageNumber, "itemsPerPage": itemsPerPage}))


@router.post("/watchlists")
def create_watchlist(name: str, type: Optional[str] = None,
                     dynamicQuery: Optional[str] = None,
                     client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/watchlists", params=drop_none({
        "name": name, "type": type, "dynamicQuery": dynamicQuery}))


@router.put("/watchlists/{watchlist_id}")
def rename_watchlist(watchlist_id: str, newName: str,
                     client: EtoroClient = Depends(get_etoro_client)):
    return client.request("PUT", f"/watchlists/{watchlist_id}", params={"newName": newName})


@router.delete("/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/watchlists/{watchlist_id}")


@router.post("/watchlists/{watchlist_id}/items")
def add_watchlist_items(watchlist_id: str, body: list = Body(...),
                        client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", f"/watchlists/{watchlist_id}/items", json=body)


@router.put("/watchlists/{watchlist_id}/items")
def update_watchlist_items(watchlist_id: str, body: list = Body(...),
                           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("PUT", f"/watchlists/{watchlist_id}/items", json=body)


@router.delete("/watchlists/{watchlist_id}/items")
def delete_watchlist_items(watchlist_id: str, body: list = Body(...),
                           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/watchlists/{watchlist_id}/items", json=body)


@router.get("/watchlists/public/{user_id}")
def public_watchlists(user_id: int, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/watchlists/public/{user_id}")


@router.get("/watchlists/public/{user_id}/{watchlist_id}")
def public_watchlist(user_id: int, watchlist_id: str,
                     client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/watchlists/public/{user_id}/{watchlist_id}")


# ---------------- Curated lists & recommendations ----------------

@router.get("/curated-lists")
def curated_lists(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/curated-lists")


@router.get("/market-recommendations/{items_count}")
def market_recommendations(items_count: int,
                           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/market-recommendations/{items_count}")


# ---------------- Popular investors ----------------

@router.get("/pi-data/copiers")
def copiers(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/pi-data/copiers")


# ---------------- User info & analytics ----------------

@router.get("/user-info/people")
def people(usernames: Optional[str] = None, cidList: Optional[str] = None,
           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/user-info/people", params=drop_none({
        "usernames": usernames, "cidList": cidList}))


@router.get("/user-info/people/search")
def people_search(period: str, page: Optional[int] = None, pageSize: Optional[int] = None,
                  sort: Optional[str] = None, popularInvestor: Optional[bool] = None,
                  client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/user-info/people/search", params=drop_none({
        "period": period, "page": page, "pageSize": pageSize, "sort": sort,
        "popularInvestor": popularInvestor}))


@router.get("/user-info/people/{username}/gain")
def people_gain(username: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/user-info/people/{username}/gain")


@router.get("/user-info/people/{username}/daily-gain")
def people_daily_gain(username: str, minDate: str, maxDate: str, type: str,
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/user-info/people/{username}/daily-gain", params={
        "minDate": minDate, "maxDate": maxDate, "type": type})


@router.get("/user-info/people/{username}/portfolio/live")
def people_portfolio_live(username: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/user-info/people/{username}/portfolio/live")


@router.get("/user-info/people/{username}/tradeinfo")
def people_tradeinfo(username: str, period: str,
                     client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/user-info/people/{username}/tradeinfo",
                          params={"period": period})
