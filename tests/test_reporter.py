"""
Unit tests for BidScope Reporter
"""

from models import AuctionItem, RightItem, Tenant, LLMAnalysisResult
from rule_engine import RuleEngine
from reporter import Reporter


def test_markdown_report_generation(tmp_path, monkeypatch):
    monkeypatch.setattr("reporter.REPORTS_DIR", tmp_path)

    item = AuctionItem(
        item_id="2025-10482-001",
        name="여의도자이 제101동 제1502호",
        item_type="아파트",
        location="서울특별시 영등포구 여의나루로 123",
        appraisal_amount=1600000000,
        minimum_bid_amount=1120000000,
        dividend_closing_date="2026-08-30",
        rights=[
            RightItem(
                right_type="근저당권",
                registration_date="2022-04-15",
                creditor="국민은행",
                amount=720000000,
            )
        ],
        tenants=[
            Tenant(
                name="김선순위",
                move_in_date="2021-08-10",
                deposit=600000000,
                has_dividend_request=False,
            )
        ],
    )

    rule_result = RuleEngine.analyze(item)
    llm_result = LLMAnalysisResult(
        special_rights_commentary="유치권 성립 불명확",
        building_risk="정상 집합건물",
        eviction_risk="공매 인도명령 부재로 명도소송 필수",
        unpaid_maintenance_fee_risk="체납 관리비 420만원 확인",
        field_inspection_checklist=["관리사무소 방문", "전입세대 확인"],
        overall_risk_grade="고위험",
        summary_opinion="인수 보증금 6억원 고려 시 실질 취득 원가 상승 주의",
    )

    report_path = Reporter.generate_and_save_report(
        item=item,
        rule_result=rule_result,
        llm_result=llm_result,
        cache_source_path="/dummy/cache.json",
    )

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")

    assert "# 📋 BidScope 공매 권리분석 및 리스크 진단 듀얼 리포트" in content
    assert "여의도자이" in content
    assert "600,000,000원" in content  # 인수 보증금
    assert "1,720,000,000원" in content  # 실질 취득 원가 (11.2억 + 6억)
    assert "인도명령" in content
    assert "고위험" in content
