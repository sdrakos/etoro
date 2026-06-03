def test_aggregated_router_exposes_all_subrouters():
    from routers.etoro import router
    paths = {r.path for r in router.routes}
    assert "/etoro/credentials" in paths
    assert "/etoro/market-data/search" in paths
    assert "/etoro/trading/info/demo/portfolio" in paths
    assert "/etoro/watchlists" in paths
    assert "/etoro/sub-portfolios" in paths
