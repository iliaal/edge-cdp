"""PDF capture with screen-media + background-graphics defaults baked in."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from edge_cdp.browser import connect
from edge_cdp.config import Config

DEFAULT_VIEWPORT = (1280, 900)
DEFAULT_MARGIN = {"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"}
STAMP_MARGIN_TOP = {"top": "18mm", "right": "10mm", "bottom": "12mm", "left": "10mm"}
STAMP_MARGIN_BOTTOM = {"top": "12mm", "right": "10mm", "bottom": "18mm", "left": "10mm"}

EMPTY_TEMPLATE = "<div></div>"

StampPosition = Literal["top", "bottom"]


def _stamp_template(url: str, retrieved: str) -> str:
    u = html.escape(url, quote=True)
    t = html.escape(retrieved, quote=True)
    return (
        '<div style="font-size:8px; color:#666; width:100%; '
        'padding:0 10mm; font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif; '
        'display:flex; justify-content:space-between; gap:10mm;">'
        f'<span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:55%;">{u}</span>'
        f'<span style="white-space:nowrap;">Retrieved {t}</span>'
        '<span style="white-space:nowrap;"><span class="pageNumber"></span>/<span class="totalPages"></span></span>'
        "</div>"
    )


def capture_pdf(
    profile: str,
    url: str,
    out: str | Path,
    *,
    viewport: tuple[int, int] = DEFAULT_VIEWPORT,
    wait_seconds: float = 2.0,
    media: str = "screen",
    tall: bool = False,
    stamp: StampPosition | None = None,
    cfg: Config | None = None,
) -> Path:
    """Render a URL to PDF using the named profile.

    Defaults:
      - emulate_media('screen') so the site's @media print rules don't kick in
        (otherwise icons render as glyph boxes and multi-column layouts collapse)
      - print_background=True so background colors and images are preserved
      - viewport 1280x900 so responsive sites don't render mobile layout

    tall=True renders one page at body.scrollHeight (no pagination).
    stamp="top" or "bottom" adds a header or footer with the captured URL,
    UTC retrieval timestamp, and page numbers. In tall mode the height is
    padded so the stamp has room without clipping content.
    """
    if stamp not in (None, "top", "bottom"):
        raise ValueError(f"stamp must be None, 'top', or 'bottom', got {stamp!r}")

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stamp_kwargs: dict = {}
    margin = DEFAULT_MARGIN
    if stamp is not None:
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        template = _stamp_template(url, retrieved)
        if stamp == "top":
            stamp_kwargs = {
                "display_header_footer": True,
                "header_template": template,
                "footer_template": EMPTY_TEMPLATE,
            }
            margin = STAMP_MARGIN_TOP
        else:
            stamp_kwargs = {
                "display_header_footer": True,
                "header_template": EMPTY_TEMPLATE,
                "footer_template": template,
            }
            margin = STAMP_MARGIN_BOTTOM

    pw, browser, context, page = connect(profile, cfg=cfg)
    try:
        page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
        page.goto(url, wait_until="load")
        if wait_seconds > 0:
            page.wait_for_timeout(int(wait_seconds * 1000))
        page.emulate_media(media=media)

        if tall:
            height = page.evaluate("() => document.body.scrollHeight")
            # 18mm at 96dpi ~= 68px; pad so the stamp doesn't clip content.
            stamp_pad = 80 if stamp is not None else 0
            page.pdf(
                path=str(out_path),
                print_background=True,
                width=f"{viewport[0]}px",
                height=f"{int(height) + stamp_pad}px",
                margin=margin,
                **stamp_kwargs,
            )
        else:
            page.pdf(
                path=str(out_path),
                format="A4",
                print_background=True,
                margin=margin,
                **stamp_kwargs,
            )
        page.close()
        return out_path
    finally:
        pw.stop()
