from __future__ import annotations

import hashlib

import pytest

from utils import release_assets


def test_whisper_asset_verifier_accepts_only_the_pinned_bytes(monkeypatch, tmp_path):
    model_dir = tmp_path / "tiny"
    model_dir.mkdir()
    payload = b"immutable-model"
    (model_dir / "model.bin").write_bytes(payload)
    monkeypatch.setattr(
        release_assets,
        "WHISPER_MODEL_ASSETS",
        {
            "tiny": {
                "repo_id": "example/model",
                "revision": "a" * 40,
                "files": {"model.bin": hashlib.sha256(payload).hexdigest()},
            }
        },
    )

    report = release_assets.verify_whisper_model_assets(tmp_path)

    assert report["verified"] is True
    assert report["models"]["tiny"]["revision"] == "a" * 40

    (model_dir / "model.bin").write_bytes(b"mutated")
    with pytest.raises(ValueError, match="Whisper release asset verification failed"):
        release_assets.verify_whisper_model_assets(tmp_path)
