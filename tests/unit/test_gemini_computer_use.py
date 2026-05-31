# -*- coding: utf-8 -*-
import asyncio

from core.sourcing.gemini_computer_use import build_gemini_computer_use_queries


def test_gemini_computer_use_fallback_without_client():
    result = asyncio.run(
        build_gemini_computer_use_queries(
            gemini_client=None,
            product_name="음식물 거름망 싱크대 거치대",
            keyword_cn="水槽过滤网 架",
            keyword_en="sink strainer holder",
            max_queries_each=4,
        )
    )
    assert isinstance(result, dict)
    assert result.get("aliexpress")
    assert result.get("1688")


def test_gemini_computer_use_uses_json_plan(monkeypatch):
    async def _fake_generate_content_text(_client, _prompt):
        return (
            '{'
            '"aliexpress_queries":["sink drain basket","triangle sink strainer"],'
            '"search_1688_queries":["水槽 沥水篮","水槽 过滤网 挂架"]'
            '}'
        )

    monkeypatch.setattr(
        "core.sourcing.gemini_computer_use.generate_content_text",
        _fake_generate_content_text,
    )

    result = asyncio.run(
        build_gemini_computer_use_queries(
            gemini_client=object(),
            product_name="싱크대 음식물 거름망",
            keyword_cn="水槽过滤网 架",
            keyword_en="sink strainer holder",
            max_queries_each=3,
        )
    )
    assert "sink drain basket" in result.get("aliexpress", [])
    assert "水槽 沥水篮" in result.get("1688", [])
    assert len(result.get("aliexpress", [])) <= 3
    assert len(result.get("1688", [])) <= 3


def test_gemini_computer_use_invalid_response_falls_back(monkeypatch):
    async def _fake_generate_content_text(_client, _prompt):
        return "not-json-response"

    monkeypatch.setattr(
        "core.sourcing.gemini_computer_use.generate_content_text",
        _fake_generate_content_text,
    )

    result = asyncio.run(
        build_gemini_computer_use_queries(
            gemini_client=object(),
            product_name="차량용 선풍기",
            keyword_cn="车载风扇",
            keyword_en="car fan",
            max_queries_each=4,
        )
    )
    assert result.get("aliexpress")
    assert result.get("1688")
