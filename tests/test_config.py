import getpass
import os
from pathlib import Path

import pytest

from edge_cdp.config import (
    Browser,
    Config,
    Profile,
    add_profile,
    load_config,
    remove_profile,
    save_config,
)


@pytest.fixture
def tmp_cfg_path(tmp_path: Path) -> Path:
    p = tmp_path / "profiles.toml"
    p.write_text(
        r"""
[browsers.edge]
exe = "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"

[profiles.work]
port = 9229
data_dir = 'C:\Users\someone\edge-work'
browser = "edge"
purpose = "test fixture"
""",
        encoding="utf-8",
    )
    return p


def test_load_config_reads_browsers_and_profiles(tmp_cfg_path: Path) -> None:
    cfg = load_config(tmp_cfg_path)
    assert "edge" in cfg.browsers
    assert cfg.browsers["edge"].exe.endswith("msedge.exe")
    assert "work" in cfg.profiles
    profile = cfg.profiles["work"]
    assert profile.port == 9229
    assert profile.cdp_url == "http://localhost:9229"
    assert profile.purpose == "test fixture"


def test_round_trip(tmp_path: Path, tmp_cfg_path: Path) -> None:
    cfg = load_config(tmp_cfg_path)
    out = tmp_path / "out.toml"
    save_config(cfg, out)
    reloaded = load_config(out)
    assert reloaded.profiles["work"].port == 9229
    assert reloaded.profiles["work"].data_dir == cfg.profiles["work"].data_dir
    assert reloaded.browsers["edge"].exe == cfg.browsers["edge"].exe


def test_add_profile_auto_picks_next_port(tmp_cfg_path: Path) -> None:
    cfg = load_config(tmp_cfg_path)
    cfg.profiles["other"] = Profile(
        name="other",
        port=9225,
        data_dir=r"C:\Users\someone\edge-other",
    )
    new = add_profile(cfg, "newproj", purpose="testing")
    expected_user = os.environ.get("WIN_USER") or getpass.getuser()
    assert new.port == 9226
    assert new.data_dir == rf"C:\Users\{expected_user}\edge-newproj"
    assert cfg.profiles["newproj"].port == 9226


def test_add_profile_honors_win_user_env(tmp_cfg_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = load_config(tmp_cfg_path)
    monkeypatch.setenv("WIN_USER", "alice")
    new = add_profile(cfg, "alpha")
    assert new.data_dir == r"C:\Users\alice\edge-alpha"


def test_add_profile_rejects_duplicate_name(tmp_cfg_path: Path) -> None:
    cfg = load_config(tmp_cfg_path)
    with pytest.raises(ValueError, match="already exists"):
        add_profile(cfg, "work")


def test_add_profile_rejects_duplicate_port(tmp_cfg_path: Path) -> None:
    cfg = load_config(tmp_cfg_path)
    with pytest.raises(ValueError, match="already used"):
        add_profile(cfg, "newproj", port=9229)


def test_add_profile_unknown_browser(tmp_cfg_path: Path) -> None:
    cfg = load_config(tmp_cfg_path)
    with pytest.raises(ValueError, match="unknown browser"):
        add_profile(cfg, "newproj", browser="firefox")


def test_remove_profile(tmp_cfg_path: Path) -> None:
    cfg = load_config(tmp_cfg_path)
    remove_profile(cfg, "work")
    assert "work" not in cfg.profiles
    with pytest.raises(KeyError):
        remove_profile(cfg, "work")


def test_get_profile_unknown_lists_known(tmp_cfg_path: Path) -> None:
    cfg = load_config(tmp_cfg_path)
    with pytest.raises(KeyError, match="work"):
        cfg.get_profile("nonexistent")


def test_next_free_port_skips_used(tmp_cfg_path: Path) -> None:
    cfg = Config()
    cfg.profiles["a"] = Profile(name="a", port=9225, data_dir="x")
    cfg.profiles["b"] = Profile(name="b", port=9226, data_dir="y")
    assert cfg.next_free_port() == 9227


def test_save_writes_purpose_only_when_set(tmp_path: Path) -> None:
    cfg = Config()
    cfg.browsers["edge"] = Browser(name="edge", exe="/x")
    cfg.profiles["a"] = Profile(name="a", port=9225, data_dir=r"C:\x", purpose="")
    cfg.profiles["b"] = Profile(name="b", port=9226, data_dir=r"C:\y", purpose="thing")
    out = tmp_path / "out.toml"
    save_config(cfg, out)
    text = out.read_text()
    assert 'purpose = "thing"' in text
    a_block = text.split("[profiles.a]")[1].split("[profiles.b]")[0]
    assert "purpose" not in a_block


def test_bind_all_defaults_false_and_round_trips(tmp_path: Path) -> None:
    cfg = Config()
    cfg.browsers["edge"] = Browser(name="edge", exe="/x")
    cfg.profiles["safe"] = Profile(name="safe", port=9225, data_dir=r"C:\a")
    cfg.profiles["lan"] = Profile(name="lan", port=9226, data_dir=r"C:\b", bind_all=True)
    assert cfg.profiles["safe"].bind_all is False
    out = tmp_path / "out.toml"
    save_config(cfg, out)
    text = out.read_text()
    safe_block = text.split("[profiles.safe]")[1].split("[profiles.lan]")[0]
    assert "bind_all" not in safe_block
    lan_block = text.split("[profiles.lan]")[1]
    assert "bind_all = true" in lan_block
    reloaded = load_config(out)
    assert reloaded.profiles["safe"].bind_all is False
    assert reloaded.profiles["lan"].bind_all is True
