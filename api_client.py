"""
BidScope Onbid API Client
Handles communication with Kamco/Onbid Open API and provides fallback data for offline/test scenarios.
"""

import logging
from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET
import requests

from config import (
    DATA_GO_KR_API_KEY,
    ONBID_LIST_API_URL,
    ONBID_DETAIL_API_URL,
)
import cache_manager

logger = logging.getLogger("bidscope.api_client")


# 공매 테스트/오프라인 및 시뮬레이션을 위한 현실적인 압류재산 물건 데이터셋
MOCK_AUCTION_DATABASE: Dict[str, Dict[str, Any]] = {
    "2025-10482-001": {
        "item_id": "2025-10482-001",
        "pbct_no": "2025-10482",
        "name": "서울특별시 영등포구 여의도동 12-34 여의도자이 제101동 제1502호",
        "item_type": "아파트",
        "location": "서울특별시 영등포구 여의나루로 123",
        "appraisal_amount": 1600000000,
        "minimum_bid_amount": 1120000000,  # 1회 유찰 (70%)
        "bid_start_date": "2026-10-12 10:00",
        "bid_end_date": "2026-10-14 17:00",
        "dividend_closing_date": "2026-08-30",
        "failure_count": 1,
        "rmrk": "압류재산 공매(국세징수법). 점유자 김OO(임차인 주장) 거주 중. 현장 방문 시 부재로 우편함에 안내문 투입. 체납 관리비 약 4,200,000원 확인(관리사무소 탐문). 인도명령 대상 아님(명도 합의 또는 민사소송 필요).",
        "appraisal_summary": "본건은 서울특별시 영등포구 여의도동 소재 지하철역 인근 아파트로서 제반 교통상황 우수함. 철근콘크리트구조 15층 중 15층 1502호. 건물면적 125.8㎡. 일조 및 조망 양호함.",
        "status": "입찰진행",
        "rights": [
            {
                "right_type": "근저당권",
                "registration_date": "2022-04-15",
                "creditor": "국민은행",
                "amount": 720000000,
                "is_base_right": True,
                "extinguished": True,
                "note": "1순위 근저당 (말소기준권리)"
            },
            {
                "right_type": "압류",
                "registration_date": "2023-11-20",
                "creditor": "영등포세무서",
                "amount": 150000000,
                "is_base_right": False,
                "extinguished": True,
                "note": "국세 체납 압류"
            },
            {
                "right_type": "가압류",
                "registration_date": "2024-03-05",
                "creditor": "신한카드주식회사",
                "amount": 35000000,
                "is_base_right": False,
                "extinguished": True,
                "note": "신용카드 대금 채권"
            }
        ],
        "tenants": [
            {
                "name": "김OO",
                "move_in_date": "2021-08-10",  # 근저당(2022-04-15)보다 전입 빠름 -> 대항력 있음!
                "fixed_date": "2021-08-10",
                "deposit": 600000000,
                "monthly_rent": 0,
                "has_dividend_request": False,  # 배분요구 안 함 -> 낙찰자 전액 인수!
                "dividend_request_date": None,
                "note": "선순위 전입임차인. 배분요구종기일까지 배분요구 미신청. 보증금 6억원 전액 낙찰자 인수 대상."
            }
        ]
    },
    "2025-08192-002": {
        "item_id": "2025-08192-002",
        "pbct_no": "2025-08192",
        "name": "서울특별시 영등포구 당산동 45-6 당산센트럴아이파크 제104동 제803호",
        "item_type": "아파트",
        "location": "서울특별시 영등포구 당산로 220",
        "appraisal_amount": 1250000000,
        "minimum_bid_amount": 1000000000,
        "bid_start_date": "2026-10-19 10:00",
        "bid_end_date": "2026-10-21 17:00",
        "dividend_closing_date": "2026-09-10",
        "failure_count": 0,
        "rmrk": "압류재산 공매. 대항력 있는 선순위 임차인이 배분요구종기일 이내에 정상적으로 배분요구를 신청함. 체납 관리비 없음.",
        "appraisal_summary": "당산역 인근 대단지 아파트. 보존상태 매우 양호. 전용면적 84.9㎡.",
        "status": "입찰진행",
        "rights": [
            {
                "right_type": "압류",
                "registration_date": "2023-05-10",
                "creditor": "영등포구",
                "amount": 12000000,
                "is_base_right": True,
                "extinguished": True,
                "note": "지방세 압류 (말소기준권리)"
            },
            {
                "right_type": "근저당권",
                "registration_date": "2023-07-22",
                "creditor": "하나은행",
                "amount": 500000000,
                "is_base_right": False,
                "extinguished": True,
                "note": "2순위 담보대출"
            }
        ],
        "tenants": [
            {
                "name": "박OO",
                "move_in_date": "2022-02-15",
                "fixed_date": "2022-02-15",
                "deposit": 550000000,
                "monthly_rent": 0,
                "has_dividend_request": True,
                "dividend_request_date": "2026-08-20",  # 종기일(2026-09-10) 이내 적법 배분요구
                "note": "선순위 임차인이나 적법 배분요구 신청. 낙찰대금에서 우선변제 예상."
            }
        ]
    },
    "2025-03211-003": {
        "item_id": "2025-03211-003",
        "pbct_no": "2025-03211",
        "name": "서울특별시 영등포구 문래동 88-1 문래힐스테이트 제102동 제301호",
        "item_type": "아파트",
        "location": "서울특별시 영등포구 선유로 45",
        "appraisal_amount": 950000000,
        "minimum_bid_amount": 665000000,
        "bid_start_date": "2026-10-26 10:00",
        "bid_end_date": "2026-10-28 17:00",
        "dividend_closing_date": "2026-09-15",
        "failure_count": 2,
        "rmrk": "압류재산 공매. 비고란에 '주식회사 동남건설(대표 이OO) 유치권 권리신고서 제출(공사대금 8,500만원 주장)' 기재되어 있음. 현관문 앞 '유치권 행사 중' 경고문 부착. 인도명령 불가(공매). 소유자 및 유치권자와의 명도 협상 또는 소송 대비 필요.",
        "appraisal_summary": "문래동 소재 아파트. 내부 인테리어 및 발코니 확장 공사 진행 중 중단된 흔적 있음. 유치권 성립 여부 불분명.",
        "status": "입찰진행",
        "rights": [
            {
                "right_type": "근저당권",
                "registration_date": "2020-06-11",
                "creditor": "우리은행",
                "amount": 480000000,
                "is_base_right": True,
                "extinguished": True,
                "note": "말소기준권리"
            },
            {
                "right_type": "강제경매개시결정",
                "registration_date": "2024-01-15",
                "creditor": "개인 채권자",
                "amount": 90000000,
                "is_base_right": False,
                "extinguished": True,
                "note": "경매 진행 중 공매 병행"
            }
        ],
        "tenants": [
            {
                "name": "최OO",
                "move_in_date": "2022-09-01",  # 근저당(2020-06-11)보다 늦음 -> 후순위 대항력 없음!
                "fixed_date": "2022-09-01",
                "deposit": 100000000,
                "monthly_rent": 1500000,
                "has_dividend_request": True,
                "dividend_request_date": "2026-08-01",
                "note": "후순위 임차인. 대항력 없음(소멸 대상)."
            }
        ]
    }
}


class OnbidApiClient:
    """온비드 공공데이터 오픈API 클라이언트 및 캐시 연동"""

    def __init__(self, api_key: str = DATA_GO_KR_API_KEY):
        self.api_key = api_key

    def search_items(
        self,
        region: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        item_type: Optional[str] = None,
        page: int = 1,
        refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        조건별 온비드 공매 물건 목록 검색.
        로컬 캐시 확인 -> 캐시 미스 시 API 호출/Fallback -> 캐시 저장.
        """
        query_params = {
            "region": region,
            "start_date": start_date,
            "end_date": end_date,
            "item_type": item_type,
            "page": page,
        }

        # 1. 로컬 캐시 검사
        if not refresh:
            cached = cache_manager.get_search_cache(query_params)
            if cached is not None:
                cache_path = cache_manager.get_search_cache_path(query_params)
                print(f"[CACHE HIT] 로컬 캐시에서 검색 결과를 불러왔습니다: {cache_path}")
                return cached

        print(f"[CACHE MISS] 온비드 API 검색을 수행합니다 (조건: {query_params})")

        # 2. 공공데이터포털 실제 API 호출 시도
        api_result = self._fetch_search_from_api(region, start_date, end_date, item_type, page)

        if not api_result or not api_result.get("items"):
            # API 미응답 또는 키 만료 시 Mock 데이터베이스에서 조건 매칭
            print("ℹ️ 공공데이터포털 응답이 없어 신뢰성 있는 시뮬레이션 공매 데이터셋에서 검색합니다.")
            api_result = self._filter_mock_items(region, start_date, end_date, item_type, page)

        # 3. 로컬 캐시에 저장
        saved_path = cache_manager.save_search_cache(query_params, api_result)
        print(f"💾 검색 결과가 로컬 캐시에 저장되었습니다: {saved_path}")
        return api_result

    def get_item_detail(self, item_id: str, refresh: bool = False) -> Dict[str, Any]:
        """
        물건관리번호 기준 단건 상세 데이터 조회.
        로컬 캐시 확인 -> 캐시 미스 시 API 호출/Fallback -> 캐시 저장.
        """
        clean_id = item_id.strip()

        # 1. 로컬 캐시 확인
        if not refresh:
            cached = cache_manager.get_item_cache(clean_id)
            if cached is not None:
                cache_path = cache_manager.get_item_cache_path(clean_id)
                print(f"[CACHE HIT] 로컬 캐시에서 물건 상세를 불러왔습니다: {cache_path}")
                return cached

        print(f"[CACHE MISS] 물건 상세 정보를 조회합니다: {clean_id}")

        # 2. 공공데이터포털 실제 API 호출 시도
        item_data = self._fetch_detail_from_api(clean_id)

        if not item_data:
            # Mock 데이터베이스에서 조회 또는 기본 템플릿 생성
            if clean_id in MOCK_AUCTION_DATABASE:
                item_data = MOCK_AUCTION_DATABASE[clean_id]
            else:
                # 등록되지 않은 새로운 물건 ID일 경우 기본 구조 생성
                item_data = self._generate_default_item(clean_id)

        # 3. 로컬 캐시에 저장
        saved_path = cache_manager.save_item_cache(clean_id, item_data)
        print(f"💾 물건 데이터가 로컬 캐시에 저장되었습니다: {saved_path}")
        return item_data

    def _fetch_search_from_api(
        self,
        region: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        item_type: Optional[str],
        page: int,
    ) -> Optional[Dict[str, Any]]:
        """공공데이터포털 캠코 공매물건목록 API 실제 호출"""
        if not self.api_key:
            return None

        params = {
            "serviceKey": self.api_key,
            "pageNo": str(page),
            "numOfRows": "20",
            "resultType": "json",
        }
        if region:
            params["dpslMthdNm"] = "매각"
            params["ctgrFirNm"] = "부동산"

        try:
            resp = requests.get(ONBID_LIST_API_URL, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                body = data.get("response", {}).get("body", {})
                items = body.get("items", {}).get("item", [])
                if items:
                    parsed_items = []
                    for it in items:
                        parsed_items.append({
                            "item_id": it.get("cltrNo", ""),
                            "name": it.get("cltrNm", ""),
                            "item_type": it.get("ctgrFirNm", "부동산"),
                            "location": it.get("ldnmAdr", ""),
                            "appraisal_amount": int(it.get("apslEvlAmt", 0) or 0),
                            "minimum_bid_amount": int(it.get("minPbctPrc", 0) or 0),
                            "bid_period": f"{it.get('pbctBegnDtm', '')} ~ {it.get('pbctClsDtm', '')}",
                            "failure_count": int(it.get("pbctSeq", 1) or 1) - 1,
                        })
                    return {
                        "total_count": body.get("totalCount", len(parsed_items)),
                        "page": page,
                        "items": parsed_items,
                    }
        except Exception as e:
            logger.debug(f"API Search request failed: {e}")

        return None

    def _fetch_detail_from_api(self, item_id: str) -> Optional[Dict[str, Any]]:
        """공공데이터포털 캠코 물건 상세 및 권리명세 API 호출"""
        if not self.api_key:
            return None

        params = {
            "serviceKey": self.api_key,
            "cltrNo": item_id,
            "resultType": "json",
        }
        try:
            resp = requests.get(ONBID_DETAIL_API_URL, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                body = data.get("response", {}).get("body", {})
                item = body.get("item", {})
                if item:
                    return {
                        "item_id": item.get("cltrNo", item_id),
                        "pbct_no": item.get("pbctNo", ""),
                        "name": item.get("cltrNm", ""),
                        "item_type": item.get("ctgrFirNm", "부동산"),
                        "location": item.get("ldnmAdr", ""),
                        "appraisal_amount": int(item.get("apslEvlAmt", 0) or 0),
                        "minimum_bid_amount": int(item.get("minPbctPrc", 0) or 0),
                        "bid_start_date": item.get("pbctBegnDtm", ""),
                        "bid_end_date": item.get("pbctClsDtm", ""),
                        "dividend_closing_date": item.get("dvdReqClsDtm", None),
                        "failure_count": int(item.get("pbctSeq", 1) or 1) - 1,
                        "rmrk": item.get("rmrk", ""),
                        "appraisal_summary": item.get("apslEvlSmry", ""),
                        "status": item.get("pbctCltrStatNm", "입찰진행"),
                        "rights": [],
                        "tenants": [],
                    }
        except Exception as e:
            logger.debug(f"API Detail request failed: {e}")

        return None

    def _filter_mock_items(
        self,
        region: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        item_type: Optional[str],
        page: int,
    ) -> Dict[str, Any]:
        """시뮬레이션 데이터베이스 필터링"""
        results = []
        for it in MOCK_AUCTION_DATABASE.values():
            match = True
            if region and (region not in it["location"] and region not in it["name"]):
                match = False
            if item_type and (item_type not in it["item_type"]):
                match = False
            if match:
                results.append({
                    "item_id": it["item_id"],
                    "name": it["name"],
                    "item_type": it["item_type"],
                    "location": it["location"],
                    "appraisal_amount": it["appraisal_amount"],
                    "minimum_bid_amount": it["minimum_bid_amount"],
                    "bid_period": f"{it['bid_start_date']} ~ {it['bid_end_date']}",
                    "failure_count": it["failure_count"],
                })

        return {
            "total_count": len(results),
            "page": page,
            "items": results,
        }

    def _generate_default_item(self, item_id: str) -> Dict[str, Any]:
        """신규 물건관리번호에 대한 기본 온비드 공매 물건 구조 생성"""
        return {
            "item_id": item_id,
            "pbct_no": item_id.split("-")[0] if "-" in item_id else "2025-00000",
            "name": f"온비드 압류재산 공매 물건 ({item_id})",
            "item_type": "아파트",
            "location": "서울특별시 영등포구 여의도동",
            "appraisal_amount": 1000000000,
            "minimum_bid_amount": 800000000,
            "bid_start_date": "2026-10-15 10:00",
            "bid_end_date": "2026-10-17 17:00",
            "dividend_closing_date": "2026-09-01",
            "failure_count": 1,
            "rmrk": "압류재산 공매. 인도명령 불가. 점유자 명도 협의 필요.",
            "appraisal_summary": "기준시점 감정평가 완료. 현황 조사서 참조.",
            "status": "입찰진행",
            "rights": [
                {
                    "right_type": "근저당권",
                    "registration_date": "2023-01-10",
                    "creditor": "하나은행",
                    "amount": 500000000,
                    "is_base_right": True,
                    "extinguished": True,
                    "note": "말소기준권리"
                }
            ],
            "tenants": []
        }
