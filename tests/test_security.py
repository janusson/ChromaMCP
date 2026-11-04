"""W8.2 tests — the filesystem boundary.

The boundary is the property that a file-reading tool cannot be pointed outside
the root by a literal path **or** by a symlink; both are refused with the same
actionable error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chromamcp.errors import PathEscapeError
from chromamcp.security import (
    ENV_ALLOWED_ROOT,
    FilesystemPolicy,
    policy_from_env,
    resolve_path,
)


def test_a_path_inside_the_root_resolves(tmp_path: Path) -> None:
    target = tmp_path / "a.mzML"
    target.write_bytes(b"x")
    assert resolve_path(target, policy=FilesystemPolicy(tmp_path)) == target.resolve()


def test_the_root_itself_is_allowed(tmp_path: Path) -> None:
    assert (
        resolve_path(tmp_path, policy=FilesystemPolicy(tmp_path)) == tmp_path.resolve()
    )


def test_a_path_outside_the_root_is_refused(tmp_path: Path) -> None:
    policy = FilesystemPolicy(tmp_path / "allowed")
    with pytest.raises(PathEscapeError):
        resolve_path(tmp_path / "elsewhere" / "a.mzML", policy=policy)


def test_a_symlink_that_escapes_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.mzML"
    outside.write_bytes(b"x")
    link = root / "link.mzML"
    link.symlink_to(outside)
    with pytest.raises(PathEscapeError):
        resolve_path(link, policy=FilesystemPolicy(root))


def test_a_symlink_that_stays_inside_is_allowed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "real.mzML"
    target.write_bytes(b"x")
    link = root / "link.mzML"
    link.symlink_to(target)
    assert resolve_path(link, policy=FilesystemPolicy(root)) == target.resolve()


def test_the_env_var_names_the_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(ENV_ALLOWED_ROOT, str(tmp_path))
    assert policy_from_env().allowed_root == tmp_path.resolve()


def test_an_unset_or_blank_env_var_falls_back_to_the_working_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_ALLOWED_ROOT, raising=False)
    assert policy_from_env().allowed_root == Path.cwd().resolve()
    monkeypatch.setenv(ENV_ALLOWED_ROOT, "   ")
    assert policy_from_env().allowed_root == Path.cwd().resolve()
