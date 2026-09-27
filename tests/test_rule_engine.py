"""
Unit tests for BidScope Rule Engine
"""

from models import AuctionItem, RightItem, Tenant
from rule_engine import RuleEngine, parse_date


def test_parse_date():
    assert str(parse_date("2022-04-15")) == "2022-04-15"
    assert str(parse_date("20220415")) == "2022-04-15"
    assert str(parse_date("2022.04.15")) == "2022-04-15"
    assert parse_date(None) is None
    assert parse_date("") is None


def test_opposing_tenant_no_dividend_request_full_takeover():
    """
    선순위 임차인: 전입 2021-08-10 (효력 2021-08-11 00:00)
    말소기준권리: 근저당 2022-04-15
    배분요구 미신청 -> 보증금 전액(6억원) 낙찰자 인수
    """
    item = AuctionItem(
        item_id="TEST-001",
        name="테스트 아파트",
        location="서울 영등포구",
        appraisal_amount=1600000000,
        minimum_bid_amount=1120000000,
        dividend_closing_date="2026-08-30",
        rights=[
            RightItem(
                right_type="근저당권",
                registration_date="2022-04-15",
                creditor="국민은행",
                amount=700000000,
            ),
            RightItem(
                right_type="압류",
                registration_date="2023-01-10",
                creditor="영등포세무서",
                amount=50000000,
            ),
        ],
        tenants=[
            Tenant(
                name="김선순위",
                move_in_date="2021-08-10",
                fixed_date="2021-08-10",
                deposit=600000000,
                has_dividend_request=False,
            )
        ],
    )

    result = RuleEngine.analyze(item)

    assert result.base_date == "2022-04-15"
    assert result.base_right is not None
    assert result.base_right.right_type == "근저당권"
    assert result.has_opposing_tenant is True
    assert result.total_takeover_deposit == 600000000
    assert result.effective_acquisition_cost == 1120000000 + 600000000
    assert result.opposing_tenants[0].is_opposing is True
    assert result.opposing_tenants[0].estimated_takeover_amount == 600000000


def test_subordinate_tenant_extinguished():
    """
    후순위 임차인: 전입 2023-05-01 (효력 2023-05-02)
    말소기준권리: 근저당 2022-04-15
    -> 대항력 없음, 인수액 0원 (소멸)
    """
    item = AuctionItem(
        item_id="TEST-002",
        name="후순위 테스트",
        location="서울 영등포구",
        appraisal_amount=500000000,
        minimum_bid_amount=400000000,
        rights=[
            RightItem(
                right_type="근저당권",
                registration_date="2022-04-15",
                amount=300000000,
            )
        ],
        tenants=[
            Tenant(
                name="이후순위",
                move_in_date="2023-05-01",
                deposit=200000000,
                has_dividend_request=True,
                dividend_request_date="2026-01-01",
            )
        ],
    )

    result = RuleEngine.analyze(item)

    assert result.has_opposing_tenant is False
    assert result.total_takeover_deposit == 0
    assert result.effective_acquisition_cost == 400000000
    assert item.tenants[0].is_opposing is False
    assert item.tenants[0].estimated_takeover_amount == 0


def test_opposing_tenant_valid_dividend_request():
    """
    선순위 임차인: 전입 2021-01-01
    말소기준권리: 압류 2022-01-01
    배분요구종기일: 2026-05-01
    배분요구 신청일: 2026-04-01 (종기일 이내 적법)
    최저가: 5억원, 보증금: 3억원 -> 전액 배분 수령 예상으로 인수액 0원
    """
    item = AuctionItem(
        item_id="TEST-003",
        name="배분신청 테스트",
        location="서울 영등포구",
        appraisal_amount=600000000,
        minimum_bid_amount=500000000,
        dividend_closing_date="2026-05-01",
        rights=[
            RightItem(
                right_type="압류",
                registration_date="2022-01-01",
                amount=50000000,
            )
        ],
        tenants=[
            Tenant(
                name="박적법",
                move_in_date="2021-01-01",
                fixed_date="2021-01-01",
                deposit=300000000,
                has_dividend_request=True,
                dividend_request_date="2026-04-01",
            )
        ],
    )

    result = RuleEngine.analyze(item)

    assert result.has_opposing_tenant is True
    assert item.tenants[0].is_valid_dividend_request is True
    assert result.total_takeover_deposit == 0
    assert result.effective_acquisition_cost == 500000000
