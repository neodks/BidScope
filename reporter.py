"""
BidScope Reporter Module
Assembles Rule Engine and LLM Engine outputs into standardized Markdown reports and console summaries.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from tabulate import tabulate

from config import REPORTS_DIR
from models import AuctionItem, RuleAnalysisResult, LLMAnalysisResult


class Reporter:
    """Markdown 듀얼 리포트 생성 및 터미널 콘솔 출력기"""

    @classmethod
    def generate_and_save_report(
        cls,
        item: AuctionItem,
        rule_result: RuleAnalysisResult,
        llm_result: Optional[LLMAnalysisResult] = None,
        cache_source_path: Optional[str] = None,
    ) -> Path:
        """최종 마크다운 듀얼 리포트를 생성하고 디스크에 저장"""
        md_content = cls.build_markdown(item, rule_result, llm_result, cache_source_path)

        safe_id = item.item_id.replace("/", "_").replace("\\", "_").replace(" ", "")
        output_file = REPORTS_DIR / f"BidScope_{safe_id}.md"

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        return output_file

    @classmethod
    def build_markdown(
        cls,
        item: AuctionItem,
        rule_result: RuleAnalysisResult,
        llm_result: Optional[LLMAnalysisResult] = None,
        cache_source_path: Optional[str] = None,
    ) -> str:
        """Markdown 문서 조립 (순수 f-string 기반)"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. 등기부 권리 내역 표
        rights_table_rows = []
        if item.rights:
            for r in item.rights:
                base_mark = "★말소기준" if r.is_base_right else ""
                exting_mark = "소멸" if r.extinguished else "인수 주의"
                rights_table_rows.append(
                    f"| {r.registration_date} | {r.right_type} {base_mark} | {r.creditor or '-'} | "
                    f"{r.amount:,}원 | {exting_mark} | {r.note or '-'} |"
                )
        else:
            rights_table_rows.append("| - | 등록된 등기 권리 없음 | - | - | - | - |")
        rights_table_md = "\n".join(rights_table_rows)

        # 2. 임차인 및 대항력 판정 표
        tenants_table_rows = []
        if item.tenants:
            for t in item.tenants:
                opposing_str = "⚠️ 대항력 있음 (선순위)" if t.is_opposing else "소멸 (후순위)"
                dividend_str = "신청 (적법)" if t.is_valid_dividend_request else ("신청 (종기일도과/무효)" if t.has_dividend_request else "미신청")
                tenants_table_rows.append(
                    f"| {t.name} | {t.move_in_date or '-'} | {t.effective_date or '-'} | {t.fixed_date or '-'} | "
                    f"{t.deposit:,}원 | {dividend_str} | {opposing_str} | **{t.estimated_takeover_amount:,}원** |"
                )
        else:
            tenants_table_rows.append("| - | 조사된 임차인 내역 없음 | - | - | - | - | - | 0원 |")
        tenants_table_md = "\n".join(tenants_table_rows)

        # 3. 1차 분석 노트
        notes_md = "\n".join([f"- {note}" for note in rule_result.analysis_notes])

        # 4. 2차 LLM 분석 섹션
        if llm_result:
            checklist_md = "\n".join([f"- [ ] {chk}" for chk in llm_result.field_inspection_checklist])
            llm_section = f"""
---

## Ⅱ. [2차] 정밀 리스크 & 명도 분석 (LLM Engine)

> **종합 리스크 등급:** `{llm_result.overall_risk_grade}`  
> **종합 투자의견:** {llm_result.summary_opinion}

### 1. 특수 권리 및 법적 코멘터리 (유치권 / 법정지상권)
{llm_result.special_rights_commentary}

### 2. 건물 및 현황 리스크 (제시외 건물 / 불법증축 / 위반건축물)
{llm_result.building_risk}

### 3. 공매 특화 명도 난이도 및 기간 평가
{llm_result.eviction_risk}

### 4. 공용 관리비 체납 추정 리스크
{llm_result.unpaid_maintenance_fee_risk}

### 5. 현장 임장 필수 체크리스트
{checklist_md}
"""
        else:
            llm_section = """
---

## Ⅱ. [2차] 정밀 리스크 & 명도 분석 (LLM Engine)

*💡 CLI 실행 시 `--llm` 옵션을 추가하면 비고란, 유치권 신고 문구, 공매 인도명령 부재에 따른 명도소송 기간 리스크 분석이 리포트에 추가됩니다.*
"""

        # 전체 마크다운 조립
        md = f"""# 📋 BidScope 공매 권리분석 및 리스크 진단 듀얼 리포트

> **분석일시:** {now_str}  
> **분석엔진 버전:** BidScope v1.0 (Rule Engine + LLM Hybrid)  
> **데이터 캐시 소스:** `{cache_source_path or "직접 호출 / 실시간"}`

---

## 📌 물건 기본 정보

| 항목 | 내용 |
| :--- | :--- |
| **물건관리번호** | `{item.item_id}` |
| **공고번호** | `{item.pbct_no or '-'}` |
| **물건명** | **{item.name}** |
| **용도 구분** | {item.item_type} |
| **소재지** | {item.location} |
| **감정평가액** | **{item.appraisal_amount:,}원** |
| **최저입찰가** | **{item.minimum_bid_amount:,}원** ({item.failure_count}회 유찰) |
| **입찰 기간** | {item.bid_start_date} ~ {item.bid_end_date} |
| **배분요구종기일** | {item.dividend_closing_date or "미지정 / 확인 필요"} |
| **진행 상태** | {item.status} |

### 📝 공고 비고란 및 현황 요약
```text
{item.rmrk or "(비고란 기재사항 없음)"}
```

---

## Ⅰ. [1차] 결정론적 권리분석 (Rule Engine)

### 1. 등기부상 권리 현황 및 말소기준권리
| 접수일자 | 권리종류 | 권리자 | 채권/설정액 | 소멸여부 | 비고 |
| :--- | :--- | :--- | :--- | :--- | :--- |
{rights_table_md}

* **말소기준권리:** {rule_result.base_date or "없음"} 설정된 `{rule_result.base_right.right_type if rule_result.base_right else "없음"}`

### 2. 임차인 대항력 판정 및 인수 보증금 분석
| 임차인 | 전입신고일 | 대항력효력일 | 확정일자 | 보증금 | 배분요구 | 대항력판정 | **낙찰자 인수예상액** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{tenants_table_md}

### 3. 실질 총 취득비용 시뮬레이션
| 항목 | 금액 | 계산식 / 비고 |
| :--- | :--- | :--- |
| **최저입찰가 (A)** | {rule_result.minimum_bid_price:,}원 | 현재 회차 입찰 최저가 |
| **낙찰자 인수 예상 보증금 (B)** | **{rule_result.total_takeover_deposit:,}원** | 선순위 대항력 임차인 미배분 보증금 합계 |
| **실질 총 취득 원가 (A + B)** | **{rule_result.effective_acquisition_cost:,}원** | **감정가 대비 {rule_result.acquisition_cost_ratio}% 수준** |

### 🔍 룰 엔진 핵심 판정 사항
{notes_md}
{llm_section}
---

## ⚖️ 법적 면책 고지 (Disclaimer)
1. 본 리포트는 공공데이터포털 캠코 온비드 API의 제공 정보와 입력된 데이터를 바탕으로 알고리즘 및 AI 분석에 의해 자동 생성된 참고자료입니다.
2. 온비드 압류재산 공매는 법원 경매와 달리 **'인도명령' 제도가 적용되지 않으므로**, 점유자 자진 인도 거부 시 명도소송(4~6개월)이 필요할 수 있습니다.
3. 실제 입찰 전 반드시 최신 등기사항전부증명서, 매각물건명세서, 주민센터 전입세대확인서, 현장 체납 관리비 등을 직접 열람·조사하여 최종 입찰 결정을 내리시기 바랍니다.
"""
        return md

    @classmethod
    def print_console_summary(
        cls,
        item: AuctionItem,
        rule_result: RuleAnalysisResult,
        llm_result: Optional[LLMAnalysisResult] = None,
        report_path: Optional[Path] = None,
    ) -> None:
        """터미널 콘솔에 한눈에 보기 쉬운 요약 표 출력"""
        print("\n" + "=" * 70)
        print(f"📊 [BidScope 권리분석 요약 리포트] {item.item_id}")
        print("=" * 70)
        print(f"📌 물건명 : {item.name}")
        print(f"📍 소재지 : {item.location} ({item.item_type})")
        print(f"📅 입찰기간 : {item.bid_start_date} ~ {item.bid_end_date} (유찰 {item.failure_count}회)")
        print("-" * 70)

        # 비용 시뮬레이션 표
        summary_data = [
            ["감정평가액", f"{item.appraisal_amount:,}원", "100.0%"],
            ["최저입찰가 (A)", f"{rule_result.minimum_bid_price:,}원", f"{round(rule_result.minimum_bid_price/item.appraisal_amount*100, 1) if item.appraisal_amount else 0}%"],
            ["낙찰자 인수 예상 보증금 (B)", f"{rule_result.total_takeover_deposit:,}원", "선순위 임차인"],
            ["실질 취득 원가 (A + B)", f"{rule_result.effective_acquisition_cost:,}원", f"감정가 대비 {rule_result.acquisition_cost_ratio}%"],
        ]
        print(tabulate(summary_data, headers=["구분", "금액", "비율 / 비고"], tablefmt="rounded_grid"))

        # 권리분석 핵심 진단
        print("\n[1차 룰 엔진 판정]")
        base_str = f"{rule_result.base_date} [{rule_result.base_right.right_type}]" if rule_result.base_right else "없음"
        print(f" • 말소기준권리 : {base_str}")
        if rule_result.has_opposing_tenant:
            print(f" • 선순위 임차인 : 🚨 대항력 보유 임차인 존재! (인수예상: {rule_result.total_takeover_deposit:,}원)")
        else:
            print(" • 선순위 임차인 : ✅ 대항력 있는 선순위 임차인 없음 (인수 보증금 0원)")

        if llm_result:
            print("\n[2차 LLM 정밀 리스크 진단]")
            print(f" • 종합 리스크 등급 : [{llm_result.overall_risk_grade}]")
            print(f" • 공매 명도 리스크 : {llm_result.eviction_risk[:120]}...")
            print(f" • 특수 권리 코멘트 : {llm_result.special_rights_commentary[:120]}...")

        if report_path:
            print("-" * 70)
            print(f"📄 상세 Markdown 리포트가 생성되었습니다:\n👉 {report_path.resolve()}")
        print("=" * 70 + "\n")
