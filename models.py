"""
BidScope Data Models (Pydantic based)
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class RightItem(BaseModel):
    """등기부상 권리 항목"""
    right_type: str = Field(description="권리 종류 (예: 압류, 가압류, 근저당권, 전세권 등)")
    registration_date: str = Field(description="접수일자 (YYYY-MM-DD)")
    creditor: str = Field(default="", description="권리자/채권자 (예: 국민은행, 역삼세무서 등)")
    amount: int = Field(default=0, description="채권금액 또는 설정최고액 (원)")
    is_base_right: bool = Field(default=False, description="말소기준권리 해당 여부")
    extinguished: bool = Field(default=True, description="낙찰 시 소멸 여부 (말소기준권리 포함 이후 권리는 소멸)")
    note: str = Field(default="", description="비고")


class Tenant(BaseModel):
    """임차인 / 점유자 정보"""
    name: str = Field(default="미상", description="임차인명 또는 점유자")
    move_in_date: Optional[str] = Field(default=None, description="전입신고일 (YYYY-MM-DD)")
    effective_date: Optional[str] = Field(default=None, description="대항력 효력발생일 (전입 익일 0시)")
    fixed_date: Optional[str] = Field(default=None, description="확정일자 (YYYY-MM-DD)")
    deposit: int = Field(default=0, description="임차 보증금 (원)")
    monthly_rent: int = Field(default=0, description="월세 (원)")
    has_dividend_request: bool = Field(default=False, description="배분요구 신청 여부")
    dividend_request_date: Optional[str] = Field(default=None, description="배분요구 신청일자 (YYYY-MM-DD)")
    is_valid_dividend_request: bool = Field(default=False, description="배분요구종기일 이내 적법 신청 여부")
    is_opposing: bool = Field(default=False, description="대항력 인정 여부 (선순위)")
    estimated_takeover_amount: int = Field(default=0, description="낙찰자 인수 예상 보증금 (원)")
    note: str = Field(default="", description="비고")


class AuctionItem(BaseModel):
    """온비드 공매 물건 상세 모델"""
    item_id: str = Field(description="물건관리번호 (예: 2025-10482-001)")
    pbct_no: str = Field(default="", description="공고번호")
    name: str = Field(description="물건명")
    item_type: str = Field(default="기타", description="용도 구분 (아파트, 다세대, 오피스텔 등)")
    location: str = Field(description="소재지 주소")
    appraisal_amount: int = Field(default=0, description="감정평가액 (원)")
    minimum_bid_amount: int = Field(default=0, description="최저입찰가 (원)")
    bid_start_date: str = Field(default="", description="입찰 시작일시")
    bid_end_date: str = Field(default="", description="입찰 마감일시")
    dividend_closing_date: Optional[str] = Field(default=None, description="배분요구종기일 (YYYY-MM-DD)")
    failure_count: int = Field(default=0, description="유찰 횟수")
    rmrk: str = Field(default="", description="공고 및 물건 비고란 텍스트")
    appraisal_summary: str = Field(default="", description="감정평가 요약 및 현황 텍스트")
    status: str = Field(default="입찰진행", description="진행 상태")
    rights: List[RightItem] = Field(default_factory=list, description="등기부 권리 목록")
    tenants: List[Tenant] = Field(default_factory=list, description="임차인 목록")


class RuleAnalysisResult(BaseModel):
    """1차 결정론적 권리분석 결과"""
    base_right: Optional[RightItem] = Field(default=None, description="말소기준권리 정보")
    base_date: Optional[str] = Field(default=None, description="말소기준일자 (YYYY-MM-DD)")
    has_opposing_tenant: bool = Field(default=False, description="대항력 있는 선순위 임차인 존재 여부")
    opposing_tenants: List[Tenant] = Field(default_factory=list, description="선순위 대항력 임차인 목록")
    total_deposit: int = Field(default=0, description="전체 임차보증금 합계")
    total_takeover_deposit: int = Field(default=0, description="낙찰자 인수 예상 보증금 총액 (원)")
    minimum_bid_price: int = Field(default=0, description="최저입찰가 (원)")
    effective_acquisition_cost: int = Field(default=0, description="실질 총 취득 원가 (최저가 + 인수 보증금)")
    acquisition_cost_ratio: float = Field(default=0.0, description="감정가 대비 실질 취득 원가 비율 (%)")
    analysis_notes: List[str] = Field(default_factory=list, description="권리분석 주요 판정 사유 및 주의사항")


class LLMAnalysisResult(BaseModel):
    """2차 정밀 LLM 리스크 분석 결과"""
    special_rights_commentary: str = Field(default="", description="특수 권리(유치권, 법정지상권, 분묘 등) 분석")
    building_risk: str = Field(default="", description="제시외 건물, 불법 증축 및 위반건축물 리스크")
    eviction_risk: str = Field(default="", description="공매 특화 명도 리스크 (인도명령 부재 및 명도소송 필수성)")
    unpaid_maintenance_fee_risk: str = Field(default="", description="공용 관리비 체납 추정 리스크")
    field_inspection_checklist: List[str] = Field(default_factory=list, description="현장 임장 필수 체크리스트")
    overall_risk_grade: str = Field(default="보통", description="종합 리스크 등급 (안전 / 보통 / 주의 / 고위험)")
    summary_opinion: str = Field(default="", description="종합 투자의견 요약")


class SearchResultItem(BaseModel):
    """조건 검색 결과 단건 항목"""
    item_id: str = Field(description="물건관리번호")
    name: str = Field(description="물건명")
    item_type: str = Field(description="용도")
    location: str = Field(description="소재지")
    appraisal_amount: int = Field(description="감정평가액 (원)")
    minimum_bid_amount: int = Field(description="최저입찰가 (원)")
    bid_period: str = Field(description="입찰 기간")
    failure_count: int = Field(default=0, description="유찰 횟수")
