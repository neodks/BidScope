# 📌 Project BidScope: 온비드 공매 데이터 권리분석 & Markdown 듀얼 리포트 생성기 상세 설계서

## 1. 프로젝트 개요

* **프로젝트명:** BidScope (비드스코프)
* **목적:** 한국자산관리공사(캠코) 온비드 공공데이터 오픈API를 연동하여 공매(압류재산 등) 물건의 권리명세 및 배분요구 데이터를 자동 수집·정제하고, 로컬 파일 캐싱을 적용한 후 1차 결정론적 룰 엔진(대항력·인수금액)과 2차 정밀 LLM 리스크 분석을 결합한 Markdown(.md) 리포트를 생성하는 CLI 도구.
* **실행 환경:** Python 3.10 이상 기반 단일 실행 CLI (Command Line Interface).
* **핵심 설계 원칙:**
  1. **Zero PDF/OCR Dependency:** 정형 공공데이터 API를 100% 활용하여 스캔 문서 파싱 오류 및 API 토큰 비용 제거.
  2. **Smart Local Caching:** 조건 검색 결과 및 물건별 상세 JSON을 로컬 파일로 저장하여 API 트래픽 한도 보호 및 즉각적인 재사용 지원.
  3. **Dual Analysis Pipeline:** 날짜·금액 계산은 결정론적 룰 엔진(환각 0%)이 담당하고, 비고란 및 명도 리스크 등 비정형 해석은 LLM이 담당하는 하이브리드 구조.

---

## 2. 시스템 아키텍처 및 데이터 흐름

```text
[CLI 명령어 실행] (조건 검색 search / 단건 분석 analyze)
       │
       ▼
 [로컬 캐시 매니저 (Cache Manager)]
  ├─ 조건 해시 또는 물건번호 기반 .cache/ 내 JSON 파일 탐색
  ├─ [CACHE HIT]  ──> 로컬 JSON에서 즉시 파싱 (네트워크 미사용)
  └─ [CACHE MISS] ──> 공공데이터포털 온비드 API 호출 ──> .cache/에 JSON 저장 후 반환
       │
       ▼
 [1차: 결정론적 권리분석 룰 엔진 (Rule Engine)]
  ├─ 날짜 정규화(YYYY-MM-DD) 및 금액(원 단위) 캐스팅
  ├─ 말소기준권리(최초 압류/근저당 등) 일자 산출
  ├─ 임차인 대항력 판정 (전입 익일 0시 vs 말소기준권리)
  ├─ 배분요구 적법 여부 체크 (배분요구종기일 이내)
  └─ 낙찰자 인수 예상 보증금 및 실질 취득 원가 계산
       │
       ▼
 [2차: 정밀 LLM 리스크 분석기 (LLM Engine) - 옵션: --llm]
  ├─ 물건현황, 감정평가 요약, 비고란 텍스트 정제
  ├─ 1차 분석 결과와 함께 구조화 프롬프트(Structured Prompt) 주입
  └─ 특수 권리(유치권/지분 매각), 공매 인도명령 부재에 따른 명도 난이도, 임장 체크포인트 도출
       │
       ▼
 [Markdown 듀얼 리포터 (Reporter)]
  └─ reports/BidScope_{물건관리번호}.md 파일 생성 및 콘솔 요약 출력
```

---

## 3. 디렉터리 및 모듈 구조

```text
BidScope/
├── .env                       # API 인증키 (DATA_GO_KR_API_KEY, OPENAI_API_KEY 등)
├── pyproject.toml             # uv 패키지 설정 및 프로젝트 종속성 정의
├── requirements.txt           # requests, python-dotenv, pydantic, openai, tabulate, pytest
├── cli.py                     # CLI 인자 파서 및 프로그램 메인 엔트리포인트
├── config.py                  # API 엔드포인트 URL, 디렉터리 경로, 기본 상수
│
├── cache_manager.py           # 로컬 JSON 캐싱 및 파일 기반 조회/저장 엔진
├── api_client.py              # 온비드 오픈API 통신 (목록 조회 및 상세 권리명세)
├── models.py                  # Pydantic 기반 정형 데이터 스키마 정의
│
├── rule_engine.py             # 1차 권리분석: 말소기준권리, 대항력 판정, 인수액 산출
├── llm_engine.py              # 2차 정밀분석: 비정형 텍스트 해석 및 명도 리스크 진단
├── reporter.py                # 1차 + 2차 분석 결과를 규격화된 Markdown으로 조립
│
├── tests/                     # 단위 및 통합 테스트 슈트
│   ├── test_rule_engine.py
│   ├── test_cache_manager.py
│   └── test_reporter.py
│
├── .cache/                    # 로컬 원본 API 데이터 캐시 저장소 (.gitignore 대상)
│   ├── items/                 # {물건관리번호}.json (물건별 권리명세 상세 원본)
│   └── queries/               # search_{쿼리해시}.json (조건별 검색 결과 목록)
└── reports/                   # 최종 생성된 Markdown 리포트 저장 폴더
```

---

## 4. CLI 인터페이스 상세 설계

`argparse` 기반으로 동작하며, 2가지 하위 커맨드(`search`, `analyze`)를 제공합니다.

### 1) 조건별 검색 및 캐싱 모드 (`search`)
조건에 맞는 공매 물건 목록을 조회하고, 검색 결과를 콘솔 표로 표시하는 동시에 로컬 캐시에 저장합니다.

* **실행 예시:**
  ```bash
  python cli.py search --region "서울특별시 영등포구" --start-date "2026-10-01" --end-date "2026-10-31" --type "아파트"
  ```
* **옵션 설명:**
  * `--region`: 시/군/구 단위 지역명
  * `--start-date` / `--end-date`: 입찰 시작 및 마감 기간 (YYYY-MM-DD)
  * `--type`: 용도 구분 (아파트, 다세대, 오피스텔 등)
  * `--page`: 페이지 번호 (기본값: 1)
  * `--refresh`: 캐시 무시하고 최신 데이터 조회

### 2) 단건 분석 및 리포트 생성 모드 (`analyze`)
물건관리번호를 입력받아 `캐시 검사` $\rightarrow$ `분석 수행` $\rightarrow$ `.md` 파일을 생성합니다.

* **1차 룰 엔진 분석 리포트만 생성 (로컬 캐시 자동 활용):**
  ```bash
  python cli.py analyze --id "2025-10482-001"
  ```
* **LLM 정밀 코멘터리가 포함된 듀얼 리포트 생성:**
  ```bash
  python cli.py analyze --id "2025-10482-001" --llm
  ```
* **캐시를 무시하고 API를 재호출하여 최신화한 뒤 분석:**
  ```bash
  python cli.py analyze --id "2025-10482-001" --refresh
  ```

---

## 5. 핵심 모듈별 세부 개발 명세

### 1) `cache_manager.py` (파일 기반 캐시 엔진)
* **저장 규칙:**
  * 단건 상세: `.cache/items/{물건관리번호}.json`
  * 조건 검색: 검색 파라미터 딕셔너리를 정렬 후 해싱하여 `.cache/queries/search_{hash}.json`으로 저장.
* **핵심 함수:**
  * `get_item_cache(item_id: str) -> dict | None`: 파일 존재 시 JSON 역직렬화 반환.
  * `save_item_cache(item_id: str, data: dict) -> Path`: API 응답을 JSON 들여쓰기 포맷으로 로컬 저장.
  * `get_search_cache(query_params: dict) -> dict | None`
  * `save_search_cache(query_params: dict, data: dict) -> Path`

### 2) `api_client.py` (온비드 공공데이터 연동)
* `requests` 모듈을 사용하여 공공데이터포털 온비드 엔드포인트 호출.
* **필수 연동 오퍼레이션:**
  * 캠코 공매물건목록조회 서비스: 지역코드, 일자, 용도별 목록 수집.
  * 캠코 온비드물건정보 서비스: 기본 정보(`getKamcoPbctCltrList`) 및 권리명세/배분요구 상세 호출.
  * `.env`의 `DATA_GO_KR_API_KEY` (Decoding 키)를 활용하여 쿼리 스트링 구성.
* **시뮬레이션/오프라인 지원:**
  * API 서버 점검 또는 키 미발급 환경에서도 안정적인 분석 검증이 가능하도록 현실적인 온비드 압류재산 공매 데이터셋 내장.

### 3) `rule_engine.py` (1차 결정론적 권리분석기)
* **말소기준권리(기준일자) 도출 로직:**
  * 등기상 압류, 가압류, 근저당, 저당, 담보가등기, 경매/공매개시결정 등기 중 가장 접수일자가 빠른 일자를 `base_date`로 확정.
* **임차인 대항력 판정 로직:**
  * 전입신고일 익일 0시 기준: `effective_date = move_in_date + 1 day`
  * **판정식:**
    * `effective_date <= base_date`: 대항력 있음 (선순위)
    * `effective_date > base_date`: 대항력 없음 (소멸 대상)
* **인수 보증금 계산 수식:**
  * 대항력이 있는 임차인이 배분요구종기일 이내에 배분요구를 하지 않은 경우: `인수액 = 보증금 전액`.
  * 대항력이 있는 임차인이 배분요구를 마친 경우: 예상 낙찰가 및 선순위 조세채권 공제 후 미배분 잔액을 인수액으로 산출.
* **실질 취득 원가:** `최저입찰가 + 인수 예상 보증금`.

### 4) `llm_engine.py` (2차 비정형 텍스트 & 특수 리스크 해석)
* **입력 컨텍스트:**
  * 룰 엔진 1차 분석 결과 요약 JSON
  * API 응답 원본의 비고란(`rmrk`), 감정평가 특이사항, 세부 현황 텍스트
* **프롬프트 평가 기준:**
  * 유치권/법정지상권 신고 문구 감지 및 성립 리스크 평가
  * 제시외 건물 및 미등기 증축 여부
  * **공매 특성 분석:** 법원 경매와 달리 온비드 압류재산 공매는 인도명령 제도가 없음 $\rightarrow$ 합의 실패 시 명도소송(4~6개월) 필수 여부 경고
  * 공용 관리비 체납 추정 리스크 및 현장 조사 가이드라인 제시

### 5) `reporter.py` (Markdown 통합 빌더)
* 룰 엔진의 수식 결과 표와 LLM 에이전트의 텍스트 코멘터리를 결합.
* 파이썬 f-string을 활용해 외부 템플릿 의존성 없이 표준 마크다운 규격으로 파일 쓰기(`reports/BidScope_{id}.md`).
* 터미널 콘솔 요약 표(`tabulate`) 시각화 출력.

---

## 6. 최종 출력 Markdown 리포트 레이아웃

리포트 생성 시 아래와 같은 섹션 구조로 `.md` 파일이 작성됩니다.

1. **헤더 메타데이터:** 물건관리번호, 소재지, 감정평가액, 최저입찰가, 분석엔진 버전, 데이터 캐시 소스 경로.
2. **Ⅰ. [1차] 결정론적 권리분석 (Rule Engine):**
   * 권리 및 대항력 판정 요약 표 (말소기준권리, 선순위 임차인 정보, 배분요구 여부, 낙찰자 인수 보증금)
   * 실질 총 취득비용 시뮬레이션 (최저가 + 인수 보증금 = 실질 취득 원가)
3. **Ⅱ. [2차] 정밀 리스크 & 명도 분석 (LLM Engine):**
   * 특수 권리 및 법적 코멘터리 (유치권, 불법 증축, 위반건축물 이행강제금 소지 등)
   * 명도 난이도 평가 (점유 상태 및 공매 인도명령 부재에 따른 명도소송 기간 리스크)
   * 현장 임장 체크리스트 (관리비 체납 확인, 전입세대 열람 크로스체크 등)
4. **푸터:** 법적 면책 고지 (Disclaimer)

---

## 7. 주요 의존성 및 패키지 (`requirements.txt` / `pyproject.toml`)

```text
requests>=2.31.0
python-dotenv>=1.0.0
pydantic>=2.0.0
tabulate>=0.9.0
openai>=1.0.0
pytest>=8.0.0
```
