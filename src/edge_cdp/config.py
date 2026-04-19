"""Profile registry stored as TOML at ~/.config/edge-cdp/profiles.toml."""
from __future__ import annotations

import getpass
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_BASE_PORT = 9225


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "edge-cdp"


def config_path() -> Path:
    return config_dir() / "profiles.toml"


def example_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "profiles.example.toml"


@dataclass
class Browser:
    name: str
    exe: str


@dataclass
class Profile:
    name: str
    port: int
    data_dir: str
    browser: str = "edge"
    purpose: str = ""
    bind_all: bool = False

    @property
    def cdp_url(self) -> str:
        return f"http://localhost:{self.port}"


@dataclass
class Config:
    browsers: dict[str, Browser] = field(default_factory=dict)
    profiles: dict[str, Profile] = field(default_factory=dict)

    def get_profile(self, name: str) -> Profile:
        if name not in self.profiles:
            known = ", ".join(sorted(self.profiles)) or "(none)"
            raise KeyError(f"unknown profile {name!r}. Known: {known}")
        return self.profiles[name]

    def get_browser(self, name: str) -> Browser:
        if name not in self.browsers:
            raise KeyError(f"unknown browser {name!r}")
        return self.browsers[name]

    def next_free_port(self, base: int = DEFAULT_BASE_PORT) -> int:
        used = {p.port for p in self.profiles.values()}
        port = base
        while port in used:
            port += 1
        return port


def _ensure_config_exists() -> None:
    path = config_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    src = example_path()
    if src.exists():
        shutil.copy(src, path)
    else:
        path.write_text("[browsers]\n[profiles]\n", encoding="utf-8")


def load_config(path: Path | None = None) -> Config:
    if path is None:
        _ensure_config_exists()
        path = config_path()
    with path.open("rb") as f:
        data = tomllib.load(f)
    cfg = Config()
    for name, body in (data.get("browsers") or {}).items():
        cfg.browsers[name] = Browser(name=name, exe=body["exe"])
    for name, body in (data.get("profiles") or {}).items():
        cfg.profiles[name] = Profile(
            name=name,
            port=int(body["port"]),
            data_dir=body["data_dir"],
            browser=body.get("browser", "edge"),
            purpose=body.get("purpose", ""),
            bind_all=bool(body.get("bind_all", False)),
        )
    return cfg


def save_config(cfg: Config, path: Path | None = None) -> None:
    if path is None:
        path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for name, b in cfg.browsers.items():
        lines.append(f"[browsers.{name}]")
        lines.append(f'exe = "{b.exe}"')
        lines.append("")
    for name, p in cfg.profiles.items():
        lines.append(f"[profiles.{name}]")
        lines.append(f"port = {p.port}")
        lines.append(f"data_dir = '{p.data_dir}'")
        lines.append(f'browser = "{p.browser}"')
        if p.purpose:
            lines.append(f'purpose = "{p.purpose}"')
        if p.bind_all:
            lines.append("bind_all = true")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def add_profile(
    cfg: Config,
    name: str,
    *,
    port: int | None = None,
    data_dir: str | None = None,
    browser: str = "edge",
    purpose: str = "",
    bind_all: bool = False,
) -> Profile:
    if name in cfg.profiles:
        raise ValueError(f"profile {name!r} already exists")
    if browser not in cfg.browsers:
        raise ValueError(
            f"unknown browser {browser!r}. Known: {', '.join(sorted(cfg.browsers))}"
        )
    if port is None:
        port = cfg.next_free_port()
    if any(p.port == port for p in cfg.profiles.values()):
        raise ValueError(f"port {port} already used by another profile")
    if data_dir is None:
        win_user = os.environ.get("WIN_USER") or getpass.getuser()
        data_dir = rf"C:\Users\{win_user}\edge-{name}"
    profile = Profile(
        name=name,
        port=port,
        data_dir=data_dir,
        browser=browser,
        purpose=purpose,
        bind_all=bind_all,
    )
    cfg.profiles[name] = profile
    return profile


def remove_profile(cfg: Config, name: str) -> None:
    if name not in cfg.profiles:
        raise KeyError(f"unknown profile {name!r}")
    del cfg.profiles[name]
