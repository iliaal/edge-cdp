"""Playwright connect_over_cdp helper that auto-launches profiles."""
from __future__ import annotations

from edge_cdp.config import Config, load_config
from edge_cdp.launcher import ensure_running


def connect(profile_name: str, cfg: Config | None = None, new_page: bool = True):
    """Open a Playwright connection to the named profile.

    Returns (playwright, browser, context, page). page is None when new_page=False.
    Caller is responsible for pw.stop() (or use as a context: pw, browser, ctx, page = connect(...);
    try: ... finally: pw.stop()).
    """
    from playwright.sync_api import sync_playwright

    if cfg is None:
        cfg = load_config()
    profile = ensure_running(profile_name, cfg=cfg)
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(profile.cdp_url)
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page() if new_page else None
    return pw, browser, context, page
