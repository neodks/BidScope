"""
BidScope Configuration Module
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 기본 디렉터리 경로
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

# 캐시 및 리포트 디렉터리
CACHE_DIR = BASE_DIR / ".cache"
ITEMS_CACHE_DIR = CACHE_DIR / "items"
QUERIES_CACHE_DIR = CACHE_DIR / "queries"
REPORTS_DIR = BASE_DIR / "reports"

# 디렉터리 자동 생성
ITEMS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
QUERIES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# API 인증키 및 모델 설정
DATA_GO_KR_API_KEY = os.getenv("DATA_GO_KR_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# 캠코 온비드 공공데이터 오픈API 엔드포인트
# 공매물건목록조회 서비스
ONBID_LIST_API_URL = "http://apis.data.go.kr/B900001/kamcoPbctCltrList/getKamcoPbctCltrList"
# 온비드 압류재산 물건 상세/권리명세
ONBID_DETAIL_API_URL = "http://apis.data.go.kr/B900001/kamcoPbctCltrInfo/getKamcoPbctCltrInfo"

# 말소기준권리 대상 권리 유형 목록
# 압류, 가압류, 저당, 근저당, 담보가등기, 경매개시결정, 공매개시결정
EXTINGUISHMENT_BASE_RIGHTS = [
    "압류",
    "가압류",
    "근저당",
    "근저당권",
    "저당",
    "저당권",
    "담보가등기",
    "경매개시결정",
    "공매개시결정",
    "강제경매개시결정",
    "임의경매개시결정",
]
