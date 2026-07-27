from pathlib import Path

from math_im_book.storage.user_profile import default_user_profile_path


def test_default_user_profile_path_is_repo_relative_when_cwd_changes(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    path = default_user_profile_path()

    assert path == Path(__file__).resolve().parents[2] / "data/config/USER.md"
