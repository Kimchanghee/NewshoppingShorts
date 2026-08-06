from pathlib import Path

from utils import user_paths


def test_redirected_desktop_is_preferred(monkeypatch, tmp_path):
    desktop = tmp_path / "OneDrive" / "Desktop"
    desktop.mkdir(parents=True)
    monkeypatch.setattr(user_paths, "_windows_desktop_from_registry", lambda: desktop)
    monkeypatch.setattr(user_paths.Path, "home", classmethod(lambda cls: tmp_path))

    assert user_paths.default_output_directory() == desktop
    assert not (desktop / ".ssmaker_write_test").exists()


def test_writable_user_videos_fallback_avoids_current_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(user_paths, "desktop_directory", lambda: None)
    monkeypatch.setattr(user_paths.Path, "home", classmethod(lambda cls: tmp_path))

    result = user_paths.default_output_directory()

    assert result == tmp_path / "Videos" / "SSMaker"
    assert result.is_dir()


def test_unwritable_candidate_falls_back(monkeypatch, tmp_path):
    blocked = tmp_path / "blocked"
    fallback = tmp_path / "Videos" / "SSMaker"
    monkeypatch.setattr(user_paths, "desktop_directory", lambda: blocked)
    monkeypatch.setattr(user_paths.Path, "home", classmethod(lambda cls: tmp_path))

    original_mkdir = Path.mkdir

    def selective_mkdir(path, *args, **kwargs):
        if path == blocked:
            raise PermissionError("read-only package path")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", selective_mkdir)

    assert user_paths.default_output_directory() == fallback
