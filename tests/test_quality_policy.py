import pytest
from app.models.domain import Track, QualityOption

def test_quality_policy_prefers_confirmed_320k():
    track = Track(
        id="t-1",
        album_id="a-1",
        provider="mock",
        title="Test Song",
        artists=["Artist 1"],
        qualities=[
            QualityOption(bitrate_kbps=128, format="mp3", download_url="http://test/128", is_confirmed_320k=False),
            QualityOption(bitrate_kbps=320, format="mp3", download_url="http://test/320", is_confirmed_320k=True)
        ]
    )
    # Default prefer 320k
    best = track.get_best_quality(prefer_320k=True, strict_320k=False)
    assert best is not None
    assert best.bitrate_kbps == 320
    assert best.is_confirmed_320k is True

def test_quality_policy_fallback_when_320k_unavailable():
    # Only 128 kbps available
    track = Track(
        id="t-2",
        album_id="a-1",
        provider="mock",
        title="Test Song 128 only",
        artists=["Artist 2"],
        qualities=[
            QualityOption(bitrate_kbps=128, format="mp3", download_url="http://test/128", is_confirmed_320k=False)
        ]
    )
    # Fallback allowed when strict_320k is False
    best = track.get_best_quality(prefer_320k=True, strict_320k=False)
    assert best is not None
    assert best.bitrate_kbps == 128

def test_quality_policy_strict_mode_skips_unconfirmed_320k():
    track = Track(
        id="t-3",
        album_id="a-1",
        provider="mock",
        title="Test Song Strict Rejection",
        artists=["Artist 3"],
        qualities=[
            QualityOption(bitrate_kbps=128, format="mp3", download_url="http://test/128", is_confirmed_320k=False)
        ]
    )
    # Strict mode active: must return None
    best = track.get_best_quality(prefer_320k=True, strict_320k=True)
    assert best is None

def test_quality_policy_unverified_bitrate_not_treated_as_confirmed():
    # A source claiming 320k without verified confirmation flag
    track = Track(
        id="t-4",
        album_id="a-1",
        provider="mock",
        title="Fake 320k",
        artists=["Artist 4"],
        qualities=[
            QualityOption(bitrate_kbps=320, format="mp3", download_url="http://test/fake320", is_confirmed_320k=False)
        ]
    )
    # Strict mode must reject it because is_confirmed_320k is False
    best = track.get_best_quality(prefer_320k=True, strict_320k=True)
    assert best is None
