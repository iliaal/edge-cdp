"""PDF capture with screen-media + background-graphics defaults baked in."""
from __future__ import annotations

from pathlib import Path

from edge_cdp.browser import connect
from edge_cdp.config import Config

DEFAULT_VIEWPORT = (1280, 900)
DEFAULT_MARGIN = {"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"}


def capture_pdf(
    profile: str,
    url: str,
    out: str | Path,
    *,
    viewport: tuple[int, int] = DEFAULT_VIEWPORT,
    wait_seconds: float = 2.0,
    media: str = "screen",
    tall: bool = False,
    cfg: Config | None = None,
) -> Path:
    """Render a URL to PDF using the named profile.

    Defaults:
      - emulate_media('screen') so the site's @media print rules don't kick in
        (otherwise icons render as glyph boxes and multi-column layouts collapse)
      - print_background=True so background colors and images are preserved
      - viewport 1280x900 so responsive sites don't render mobile layout

    tall=True renders one page at body.scrollHeight (no pagination).
    """
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pw, browser, context, page = connect(profile, cfg=cfg)
    try:
        page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
        page.goto(url, wait_until="load")
        if wait_seconds > 0:
            page.wait_for_timeout(int(wait_seconds * 1000))
        page.emulate_media(media=media)

        if tall:
            height = page.evaluate("() => document.body.scrollHeight")
            page.pdf(
                path=str(out_path),
                print_background=True,
                width=f"{viewport[0]}px",
                height=f"{int(height)}px",
            )
        else:
            page.pdf(
                path=str(out_path),
                format="A4",
                print_background=True,
                margin=DEFAULT_MARGIN,
            )
        page.close()
        return out_path
    finally:
        pw.stop()
