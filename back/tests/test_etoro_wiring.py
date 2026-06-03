def test_aggregated_router_exposes_settings_core_and_proxy():
    from routers.etoro import router
    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/etoro/credentials" in paths          # settings
    assert "/etoro/search" in paths               # core
    assert "/etoro/orders" in paths               # core
    # proxy catch-all — FastAPI stores the path converter as {path:path}
    assert any("/etoro/api/{version}" in p for p in paths)
