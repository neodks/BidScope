"""
Unit tests for BidScope Cache Manager
"""

import cache_manager


def test_cache_item_save_and_get(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_manager, "ITEMS_CACHE_DIR", tmp_path / "items")

    item_id = "2025-99999-001"
    sample_data = {"item_id": item_id, "name": "캐시 테스트 아파트", "price": 500000000}

    # 캐시 저장
    saved_file = cache_manager.save_item_cache(item_id, sample_data)
    assert saved_file.exists()

    # 캐시 조회
    cached = cache_manager.get_item_cache(item_id)
    assert cached is not None
    assert cached["item_id"] == item_id
    assert cached["name"] == "캐시 테스트 아파트"


def test_cache_search_save_and_get(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_manager, "QUERIES_CACHE_DIR", tmp_path / "queries")

    query = {"region": "서울특별시 영등포구", "type": "아파트", "page": 1}
    sample_result = {"total_count": 1, "items": [{"item_id": "2025-001"}]}

    # 검색 캐시 저장
    saved_file = cache_manager.save_search_cache(query, sample_result)
    assert saved_file.exists()

    # 검색 캐시 조회
    cached = cache_manager.get_search_cache(query)
    assert cached is not None
    assert cached["total_count"] == 1
    assert cached["items"][0]["item_id"] == "2025-001"
