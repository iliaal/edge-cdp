"""edge-cdp CLI."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from edge_cdp.capture import capture_pdf
from edge_cdp.config import (
    Config,
    add_profile,
    config_path,
    load_config,
    remove_profile,
    save_config,
)
from edge_cdp.launcher import ensure_running, version_info


def _parse_viewport(text: str) -> tuple[int, int]:
    try:
        w, h = text.lower().split("x", 1)
        return int(w), int(h)
    except (ValueError, AttributeError) as exc:
        raise argparse.ArgumentTypeError(
            f"viewport must be WxH (e.g. 1280x900), got {text!r}"
        ) from exc


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config()
    if not cfg.profiles:
        print("No profiles configured. See `edge-cdp profile add --help`.")
        return 0
    width = max(len(name) for name in cfg.profiles)
    for name, profile in sorted(cfg.profiles.items()):
        info = version_info(profile)
        if info is None:
            state = "dead"
            extra = ""
        else:
            state = "alive"
            extra = f"  {info.get('Browser', '?')}"
        purpose = f"  -- {profile.purpose}" if profile.purpose else ""
        print(f"{name:<{width}}  port {profile.port}  {state}{extra}{purpose}")
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    profile = ensure_running(args.profile)
    print(f"{profile.name}: ready on port {profile.port}")
    return 0


def cmd_shell(args: argparse.Namespace) -> int:
    cfg = load_config()
    profile = ensure_running(args.profile, cfg=cfg)
    if not args.command:
        print("error: no command given. Use: edge-cdp shell <profile> -- CMD ARGS", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env["CDP_URL"] = profile.cdp_url
    env["EDGE_PROFILE"] = profile.name
    return subprocess.call(args.command, env=env)


def cmd_profile_list(args: argparse.Namespace) -> int:
    cfg = load_config()
    if not cfg.profiles:
        print("No profiles configured.")
        return 0
    for name, p in sorted(cfg.profiles.items()):
        purpose = f"  -- {p.purpose}" if p.purpose else ""
        print(f"{name}  port={p.port}  browser={p.browser}  data_dir={p.data_dir}{purpose}")
    return 0


def cmd_profile_add(args: argparse.Namespace) -> int:
    cfg = load_config()
    profile = add_profile(
        cfg,
        args.name,
        port=args.port,
        data_dir=args.data_dir,
        browser=args.browser,
        purpose=args.purpose or "",
        bind_all=args.bind_all,
    )
    save_config(cfg)
    bind_note = " (LAN-exposed)" if profile.bind_all else " (localhost-only)"
    print(f"added profile {profile.name}: port {profile.port}{bind_note}, data_dir {profile.data_dir}")
    print(f"config: {config_path()}")
    return 0


def cmd_profile_remove(args: argparse.Namespace) -> int:
    cfg = load_config()
    remove_profile(cfg, args.name)
    save_config(cfg)
    print(f"removed profile {args.name}")
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:
    out = capture_pdf(
        profile=args.profile,
        url=args.url,
        out=args.out,
        viewport=args.viewport,
        wait_seconds=args.wait,
        media=args.media,
        tall=args.tall,
    )
    size = Path(out).stat().st_size
    print(f"wrote {out} ({size:,} bytes)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="edge-cdp")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="list profiles and show alive/dead per port")
    p_status.set_defaults(func=cmd_status)

    for verb in ("launch", "ensure"):
        p = sub.add_parser(verb, help="launch profile if not already running")
        p.add_argument("profile")
        p.set_defaults(func=cmd_launch)

    p_shell = sub.add_parser(
        "shell", help="run a command with CDP_URL and EDGE_PROFILE in the environment"
    )
    p_shell.add_argument("profile")
    p_shell.add_argument("command", nargs=argparse.REMAINDER, help="command to exec (after --)")
    p_shell.set_defaults(func=cmd_shell)

    p_profile = sub.add_parser("profile", help="manage profiles in the registry")
    profile_sub = p_profile.add_subparsers(dest="profile_cmd", required=True)

    p_pl = profile_sub.add_parser("list")
    p_pl.set_defaults(func=cmd_profile_list)

    p_pa = profile_sub.add_parser("add")
    p_pa.add_argument("name")
    p_pa.add_argument("--port", type=int, default=None, help="CDP port (auto-pick if omitted)")
    p_pa.add_argument("--data-dir", default=None, help="user-data-dir path (Windows form)")
    p_pa.add_argument("--browser", default="edge")
    p_pa.add_argument("--purpose", default=None)
    p_pa.add_argument(
        "--bind-all",
        action="store_true",
        help="bind CDP debug port to 0.0.0.0 (LAN-exposed). Default is 127.0.0.1.",
    )
    p_pa.set_defaults(func=cmd_profile_add)

    p_pr = profile_sub.add_parser("remove")
    p_pr.add_argument("name")
    p_pr.set_defaults(func=cmd_profile_remove)

    p_pdf = sub.add_parser("pdf", help="render a URL to PDF using the named profile")
    p_pdf.add_argument("profile")
    p_pdf.add_argument("url")
    p_pdf.add_argument("out")
    p_pdf.add_argument("--tall", action="store_true", help="single-page render at body.scrollHeight")
    p_pdf.add_argument("--viewport", type=_parse_viewport, default=(1280, 900), help="WxH (default 1280x900)")
    p_pdf.add_argument("--wait", type=float, default=2.0, help="extra seconds to wait after load")
    p_pdf.add_argument("--media", choices=["screen", "print"], default="screen")
    p_pdf.set_defaults(func=cmd_pdf)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (KeyError, ValueError, TimeoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
