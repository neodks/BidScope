"""
BidScope Cache Manager
JSON file-based local caching engine for API requests.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from config import ITEMS_CACHE_DIR, QUERIES_CACHE_DIR


def _hash_query_params(params: Dict[str, Any]) -> str:
    """검색 파라미터 딕셔너리를 키 정렬 후 SHA256 해시값 생성"""
    sorted_items = sorted((str(k), str(v)) for k, v in params.items() if v is not None)
    serialized = json.dumps(sorted_items, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def get_item_cache_path(item_id: str) -> Path:
    """물건관리번호 기반 캐시 파일 경로 반환 (특수문자 정규화)"""
    safe_id = item_id.replace("/", "_").replace("\\", "_").replace(" ", "")
    return ITEMS_CACHE_DIR / f"{safe_id}.json"


def get_search_cache_path(query_params: Dict[str, Any]) -> Path:
    """검색 쿼리 파라미터 기반 캐시 파일 경로 반환"""
    query_hash = _hash_query_params(query_params)
    return QUERIES_CACHE_DIR / f"search_{query_hash}.json"


def get_item_cache(item_id: str) -> Optional[Dict[str, Any]]:
    """물건 단건 캐시 조회. 파일 존재 시 파싱된 딕셔너리 반환, 없으면 None"""
    path = get_item_cache_path(item_id)
    if path.exists() and path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_item_cache(item_id: str, data: Dict[str, Any]) -> Path:
    """물건 단건 API 응답 데이터를 로컬 JSON 캐시로 저장"""
    path = get_item_cache_path(item_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def get_search_cache(query_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """조건 검색 결과 캐시 조회"""
    path = get_search_cache_path(query_params)
    if path.exists() and path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_search_cache(query_params: Dict[str, Any], data: Dict[str, Any]) -> Path:
    """조건 검색 결과를 로컬 JSON 캐시로 저장"""
    path = get_search_cache_path(query_params)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
