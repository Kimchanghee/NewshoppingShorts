# -*- coding: utf-8 -*-
"""Guard against uploading encoding-corrupted (?????) titles."""

from managers.youtube_manager import _text_looks_corrupted


def test_detects_question_mark_runs():
    assert _text_looks_corrupted("????? ??? ?? ??? ???")
    assert _text_looks_corrupted("?? ??? ??? ???? ??")
    assert _text_looks_corrupted("제품 �� 손상")  # replacement char


def test_allows_clean_titles():
    assert not _text_looks_corrupted("에어컨 틀기 전 10초 쿨링템, 미니냉풍기 체감")
    assert not _text_looks_corrupted("이거 진짜 좋아요?")  # single legit question mark
    assert not _text_looks_corrupted("모기랑 전쟁하는 밤엔 포충기부터 체크")
    assert not _text_looks_corrupted("")


def test_single_question_mark_ok():
    assert not _text_looks_corrupted("써보니 왜 다들 추천하는지 알겠네?")
