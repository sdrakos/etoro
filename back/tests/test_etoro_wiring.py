def test_aggregated_router_exposes_settings():
    from routers.etoro import router
    paths = {r.path for r in router.routes}
    assert "/etoro/credentials" in paths
