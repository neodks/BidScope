"""
BidScope Rule Engine
Deterministic rights analysis, opposing tenant verification, and takeover calculation.
"""

from datetime import datetime, timedelta
import re
from typing import Optional, List, Tuple
from config import EXTINGUISHMENT_BASE_RIGHTS
from models import AuctionItem, RightItem, Tenant, RuleAnalysisResult


def parse_date(date_str: Optional[str]) -> Optional[datetime.date]:
    """다양한 날짜 문자열(YYYY-MM-DD, YYYYMMDD, YYYY.MM.DD)을 datetime.date 객체로 변환"""
    if not date_str:
        return None

    cleaned = re.sub(r"[^\d]", "", str(date_str).strip())
    if len(cleaned) == 8:
        try:
            return datetime.strptime(cleaned, "%Y%m%d").date()
        except ValueError:
            return None
    elif len(cleaned) >= 8:
        # 시간 정보 등이 포함된 경우 앞 8자리 파싱
        try:
            return datetime.strptime(cleaned[:8], "%Y%m%d").date()
        except ValueError:
            return None
    return None


def format_date(d: Optional[datetime.date]) -> Optional[str]:
    """date 객체를 YYYY-MM-DD 포맷 문자열로 변환"""
    return d.strftime("%Y-%m-%d") if d else None


class RuleEngine:
    """결정론적 1차 권리분석 룰 엔진 (환각 0%)"""

    @classmethod
    def analyze(cls, item: AuctionItem) -> RuleAnalysisResult:
        """온비드 공매 물건에 대해 결정론적 권리분석 수행"""
        notes: List[str] = []

        # 1. 말소기준권리(Base Right) 도출
        base_right, base_date = cls._find_extinguishment_base_right(item.rights)
        if base_right and base_date:
            notes.append(
                f"말소기준권리: {base_right.registration_date} 설정된 [{base_right.right_type}] "
                f"(채권자: {base_right.creditor or '미상'}, 채권액: {base_right.amount:,}원)"
            )
        else:
            notes.append("등기부상 말소기준권리(근저당/압류/가압류 등)가 존재하지 않습니다.")

        # 2. 등기부 권리별 소멸/인수 여부 판정
        for r in item.rights:
            r_date = parse_date(r.registration_date)
            if not base_date:
                r.extinguished = False
            elif r.is_base_right or (r_date and r_date >= base_date):
                r.extinguished = True
            else:
                # 말소기준권리보다 빠른 선순위 권리
                r.extinguished = False
                notes.append(f"⚠️ 선순위 등기권리 존재: {r.registration_date} [{r.right_type}] 낙찰자 인수 가능성 검토 필요.")

        # 3. 임차인 대항력 및 인수 보증금 판정
        dividend_closing = parse_date(item.dividend_closing_date)
        opposing_tenants: List[Tenant] = []
        total_deposit = 0
        total_takeover = 0

        for t in item.tenants:
            total_deposit += t.deposit
            move_in = parse_date(t.move_in_date)

            if move_in:
                # 대항력 효력 발생 시점: 전입신고 익일(다음날) 0시
                effective_date = move_in + timedelta(days=1)
                t.effective_date = format_date(effective_date)

                # 대항력 판정: effective_date <= base_date 이면 선순위 대항력 보유
                if base_date is None or effective_date <= base_date:
                    t.is_opposing = True
                    opposing_tenants.append(t)
                else:
                    t.is_opposing = False
            else:
                t.is_opposing = False

            # 배분요구 적법성 판정
            req_date = parse_date(t.dividend_request_date)
            if t.has_dividend_request and req_date and dividend_closing:
                if req_date <= dividend_closing:
                    t.is_valid_dividend_request = True
                else:
                    t.is_valid_dividend_request = False
                    notes.append(
                        f"⚠️ 임차인 [{t.name}]의 배분요구일({t.dividend_request_date})이 "
                        f"배분요구종기일({item.dividend_closing_date})을 도과하여 무효입니다."
                    )
            elif t.has_dividend_request and not dividend_closing:
                t.is_valid_dividend_request = True
            else:
                t.is_valid_dividend_request = False

            # 인수 예상 보증금 계산
            if t.is_opposing:
                if not t.has_dividend_request or not t.is_valid_dividend_request:
                    # Case 1: 선순위 대항력 임차인이 배분요구를 하지 않았거나 기한을 넘긴 경우 -> 보증금 전액 인수
                    t.estimated_takeover_amount = t.deposit
                    total_takeover += t.deposit
                    notes.append(
                        f"🚨 선순위 대항력 임차인 [{t.name}] 배분요구 미신청 -> "
                        f"보증금 전액({t.deposit:,}원) 낙찰자 전액 인수 대상!"
                    )
                else:
                    # Case 2: 선순위 대항력 임차인이 적법하게 배분요구를 한 경우
                    # 최저입찰가 기준 배분 시뮬레이션
                    # 임차인이 우선변제권(확정일자)을 갖추었을 때 최저가에서 수령 가능액 산출
                    estimated_payout = min(item.minimum_bid_amount, t.deposit)
                    unpaid_balance = max(0, t.deposit - estimated_payout)
                    t.estimated_takeover_amount = unpaid_balance
                    total_takeover += unpaid_balance

                    if unpaid_balance > 0:
                        notes.append(
                            f"⚠️ 선순위 임차인 [{t.name}] 최저입찰가 낙찰 시 미배분 보증금 "
                            f"{unpaid_balance:,}원 낙찰자 인수 예상."
                        )
                    else:
                        notes.append(
                            f"✅ 선순위 임차인 [{t.name}] 적법 배분요구 완료. "
                            f"최저입찰가 이상 낙찰 시 전액 배분 예상 (인수액 0원)."
                        )
            else:
                # 후순위 임차인 -> 소멸 (인수액 없음)
                t.estimated_takeover_amount = 0
                if t.deposit > 0:
                    notes.append(
                        f"임차인 [{t.name}](보증금 {t.deposit:,}원)은 말소기준권리보다 후순위로 "
                        f"대항력이 없어 낙찰자 인수 책임이 소멸됩니다."
                    )

        # 4. 실질 취득 원가 계산
        effective_cost = item.minimum_bid_amount + total_takeover
        ratio = 0.0
        if item.appraisal_amount > 0:
            ratio = round((effective_cost / item.appraisal_amount) * 100, 1)

        notes.append(
            f"💰 실질 취득 원가: {effective_cost:,}원 (최저가 {item.minimum_bid_amount:,}원 + "
            f"인수 보증금 {total_takeover:,}원, 감정가 대비 {ratio}%)"
        )

        return RuleAnalysisResult(
            base_right=base_right,
            base_date=format_date(base_date),
            has_opposing_tenant=len(opposing_tenants) > 0,
            opposing_tenants=opposing_tenants,
            total_deposit=total_deposit,
            total_takeover_deposit=total_takeover,
            minimum_bid_price=item.minimum_bid_amount,
            effective_acquisition_cost=effective_cost,
            acquisition_cost_ratio=ratio,
            analysis_notes=notes,
        )

    @classmethod
    def _find_extinguishment_base_right(
        cls, rights: List[RightItem]
    ) -> Tuple[Optional[RightItem], Optional[datetime.date]]:
        """등기부 권리 목록 중 접수일자가 가장 빠른 말소기준권리 탐색"""
        candidates: List[Tuple[datetime.date, RightItem]] = []

        for r in rights:
            # 권리 유형 검사 (압류, 가압류, 근저당, 저당, 담보가등기, 경매개시결정 등)
            is_match = any(base_type in r.right_type for base_type in EXTINGUISHMENT_BASE_RIGHTS)
            if is_match:
                d = parse_date(r.registration_date)
                if d:
                    candidates.append((d, r))

        if not candidates:
            return None, None

        # 접수일자 오름차순 정렬 (가장 빠른 날짜)
        candidates.sort(key=lambda x: x[0])
        base_date, base_item = candidates[0]
        base_item.is_base_right = True

        return base_item, base_date
