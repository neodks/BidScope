# 📌 Project BidScope: 온비드 공매 분석 및 듀얼 리포트(Rule + LLM) 생성 CLI

한국자산관리공사(캠코) 온비드 공공데이터 오픈API를 연동하여 공매(압류재산 등) 물건의 권리명세 및 배분요구 데이터를 자동 수집·정제하고, 로컬 파일 캐싱을 적용한 후 **1차 결정론적 룰 엔진(대항력·인수금액)**과 **2차 정밀 LLM 리스크 분석(명도·특수권리)**을 결합한 Markdown(.md) 듀얼 리포트를 생성하는 고성능 CLI 도구입니다.

---

## 🚀 주요 핵심 기능

1. **Zero PDF/OCR Dependency & 정형 데이터 분석**
   - 온비드 공공데이터 API를 직접 연동하여 스캔 문서 OCR 파싱 오류 및 토큰 낭비 제거
2. **Smart Local Caching (.cache/)**
   - 검색 조건 해시 및 물건관리번호 기반 로컬 파일 캐싱
   - API 트래픽 한도 절약 및 초고속 재분석 지원
3. **1차: 결정론적 권리분석 룰 엔진 (Rule Engine, 환각 0%)**
   - 말소기준권리(최초 압류/근저당 등) 일자 자동 산출
   - 주택임대차보호법 기준 임차인 대항력 판정 (전입 익일 0시 vs 말소기준일자)
   - 배분요구 적법 여부 체크 (배분요구종기일 이내 신청 여부)
   - 낙찰자 인수 예상 보증금 및 실질 취득 원가(최저가 + 인수액) 산출
4. **2차: 정밀 LLM 리스크 분석기 (LLM Engine - `--llm`)**
   - 비고란 비정형 텍스트 및 감정평가 요약 해석
   - 유치권 / 법정지상권 신고 문구 감지 및 리스크 평가
   - **온비드 공매 특화 명도 리스크**: 법원 경매와 달리 온비드 공매는 **인도명령 제도 부재** $\rightarrow$ 합의 불발 시 명도소송(4~6개월) 필수성 경고
   - 공용 관리비 체납 추정 리스크 (최근 3년 공용부분 승계 판례 반영)
   - 현장 임장 필수 체크리스트 생성
5. **Markdown 듀얼 리포터 & 콘솔 요약 (Reporter)**
   - `reports/BidScope_{물건관리번호}.md` 규격화된 리포트 자동 생성
   - 터미널 콘솔 요약 표(`tabulate`) 출력

---

## 📂 프로젝트 구조

```text
BidScope/
├── .env                       # API 인증키 (DATA_GO_KR_API_KEY, OPENAI_API_KEY 등)
├── .env.example               # 환경변수 예시 템플릿
├── requirements.txt           # 필수 패키지 목록
├── pyproject.toml             # pytest 설정
├── config.py                  # API 엔드포인트 URL, 디렉터리 경로, 기본 상수
├── models.py                  # Pydantic 기반 정형 데이터 스키마 정의
├── cache_manager.py           # 로컬 JSON 캐싱 및 파일 기반 조회/저장 엔진
├── api_client.py              # 온비드 오픈API 통신 및 시뮬레이션 데이터셋
├── rule_engine.py             # 1차 권리분석: 말소기준권리, 대항력 판정, 인수액 산출
├── llm_engine.py              # 2차 정밀분석: 비정형 텍스트 해석 및 명도 리스크 진단
├── reporter.py                # 1차 + 2차 분석 결과를 규격화된 Markdown으로 조립
├── cli.py                     # CLI 인자 파서 및 프로그램 메인 엔트리포인트
├── tests/                     # 단위 및 통합 테스트 슈트
│   ├── test_rule_engine.py
│   ├── test_cache_manager.py
│   └── test_reporter.py
├── .cache/                    # 로컬 원본 API 데이터 캐시 저장소
│   ├── items/                 # {물건관리번호}.json
│   └── queries/               # search_{쿼리해시}.json
└── reports/                   # 최종 생성된 Markdown 리포트 저장 폴더
```

---

## 🛠️ 설치 및 설정 (uv 기반)

### 1. 프로젝트 동기화 및 의존성 설치
```bash
# 가상환경 생성 및 의존성 동기화
uv sync --extra dev
```

### 2. 환경 변수 설정 (`.env`)
`.env` 파일에 API 키를 설정합니다:
```bash
# 공공데이터포털(data.go.kr) 디코딩 인증키
DATA_GO_KR_API_KEY=your_key_here

# OpenAI API 인증키 (옵션: --llm 사용 시 필요)
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4o-mini
```
*※ `OPENAI_API_KEY`가 없더라도 규칙 기반의 정밀 휴리스틱 리스크 분석으로 안전하게 전환(Fallback)되어 리포트가 정상 생성됩니다.*

---

## 💻 CLI 실행 가이드

`uv run bidscope` 또는 `python cli.py` 명령어로 실행할 수 있습니다.

### 1. 조건별 공매 물건 검색 (`search`)
```bash
# 기본 검색 (영등포구 아파트)
uv run bidscope search --region "서울특별시 영등포구" --type "아파트"

# 기간 지정 검색
uv run bidscope search --region "서울특별시 영등포구" --start-date "2026-10-01" --end-date "2026-10-31" --type "아파트"

# 캐시 무시하고 최신 데이터 재조회
uv run bidscope search --region "서울특별시 영등포구" --type "아파트" --refresh
```

### 2. 단건 권리분석 및 리포트 생성 (`analyze`)
```bash
# 1차 룰 엔진 분석 리포트 생성
uv run bidscope analyze --id "2025-10482-001"

# LLM 정밀 리스크 코멘터리가 포함된 듀얼 리포트 생성
uv run bidscope analyze --id "2025-10482-001" --llm

# 캐시 무시하고 최신 데이터 재호출 후 분석
uv run bidscope analyze --id "2025-10482-001" --llm --refresh
```

### 3. 테스트 실행
```bash
uv run pytest -v
```

