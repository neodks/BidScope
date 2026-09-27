"""
BidScope LLM Engine
Performs deep qualitative risk analysis, eviction litigation assessment, and special rights commentary.
"""

import json
import logging
from typing import Optional, List
from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from models import AuctionItem, RuleAnalysisResult, LLMAnalysisResult

logger = logging.getLogger("bidscope.llm_engine")


LLM_SYSTEM_PROMPT = """당신은 대한민국 부동산 공매 및 경매 분야 최고 권위의 권리분석 및 리스크 진단 전문 법률 AI입니다.
온비드(한국자산관리공사 캠코) 압류재산 공매의 특수성을 깊이 있게 이해하고 있으며, 아래의 원칙에 따라 분석을 수행합니다.

[온비드 압류재산 공매의 핵심 특수성]
1. 인도명령 제도의 부재:
   - 법원 경매(민사집행법 제136조)와 달리, 온비드 공매(국세징수법 등)에는 '인도명령' 제도가 없습니다.
   - 따라서 점유자(대항력 없는 임차인, 소유자, 채무자 등)가 자진 퇴거 및 명도 합의를 거부할 경우, 낙찰자는 반드시 정식 '명도소송'(통상 4~6개월 이상 소요)을 제기하여 집행권원을 획득한 후 강제집행해야 합니다.
   - 이에 따른 명도 지연, 금융비용 증가, 소송 및 집행비용 리스크를 반드시 경고해야 합니다.
2. 유치권 및 법정지상권:
   - 비고란 등에 공사대금 유치권이나 분묘, 제시외 건물이 기재된 경우 성립 가능성(점유 여부, 피담보채권의 성격, 압류효력 발생 전후 등)을 엄밀히 지적합니다.
3. 체납 공용관리비:
   - 대법원 판례에 따라 아파트/집합건물의 경우 직전 3년간의 공용부분 관리비는 특별승계인(낙찰자)이 인수해야 하므로, 체납 관리비 확인 필요성을 명시합니다.

[출력 요구사항]
주어진 물건 정보와 1차 룰 엔진 분석 결과를 바탕으로 반드시 다음 JSON 구조로 응답하십시오:
{
  "special_rights_commentary": "유치권, 법정지상권, 대지권 미등기 등 특수 권리 분석",
  "building_risk": "제시외 건물, 불법 증축, 위반건축물 여부 및 이행강제금 리스크",
  "eviction_risk": "공매 명도 난이도, 인도명령 부재에 따른 명도소송 기간 및 비용 리스크",
  "unpaid_maintenance_fee_risk": "공용 관리비 체납 추정 및 판례상 인수 범위",
  "field_inspection_checklist": [
    "임장 시 필수 확인 사항 1",
    "임장 시 필수 확인 사항 2",
    "..."
  ],
  "overall_risk_grade": "안전 / 보통 / 주의 / 고위험 중 하나",
  "summary_opinion": "투자자를 위한 최종 전략 및 종합 투자의견 요약"
}
"""


class LLMEngine:
    """온비드 공매 물건 비정형 텍스트 및 정밀 리스크 분석기"""

    def __init__(self, api_key: str = OPENAI_API_KEY, model: str = OPENAI_MODEL):
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key) if api_key else None

    def analyze(
        self, item: AuctionItem, rule_result: RuleAnalysisResult
    ) -> LLMAnalysisResult:
        """1차 룰 결과와 공매 비고란 텍스트를 결합하여 LLM 리스크 분석 수행"""
        if not self.client:
            print("⚠️ OPENAI_API_KEY가 설정되어 있지 않아 규칙 기반 정밀 리스크 분석(Fallback)을 적용합니다.")
            return self._heuristic_analysis(item, rule_result)

        prompt_context = {
            "물건정보": {
                "물건관리번호": item.item_id,
                "물건명": item.name,
                "용도": item.item_type,
                "소재지": item.location,
                "감정평가액": item.appraisal_amount,
                "최저입찰가": item.minimum_bid_amount,
                "유찰횟수": item.failure_count,
                "비고란_원문": item.rmrk,
                "감정평가_요약": item.appraisal_summary,
            },
            "1차_룰엔진_분석결과": {
                "말소기준일자": rule_result.base_date,
                "선순위_대항력_임차인_존재여부": rule_result.has_opposing_tenant,
                "낙찰자_인수_보증금": rule_result.total_takeover_deposit,
                "실질_취득_원가": rule_result.effective_acquisition_cost,
                "감정가대비_취득비율": f"{rule_result.acquisition_cost_ratio}%",
                "주요_판정노트": rule_result.analysis_notes,
            }
        }

        user_content = f"다음 온비드 공매 물건에 대해 상세 리스크 분석을 수행하고 JSON으로 응답해 주세요:\n\n{json.dumps(prompt_context, ensure_ascii=False, indent=2)}"

        try:
            print(f"🤖 LLM({self.model}) 정밀 리스크 및 명도 분석을 호출합니다...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw_text = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_text)

            return LLMAnalysisResult(
                special_rights_commentary=parsed.get("special_rights_commentary", ""),
                building_risk=parsed.get("building_risk", ""),
                eviction_risk=parsed.get("eviction_risk", ""),
                unpaid_maintenance_fee_risk=parsed.get("unpaid_maintenance_fee_risk", ""),
                field_inspection_checklist=parsed.get("field_inspection_checklist", []),
                overall_risk_grade=parsed.get("overall_risk_grade", "보통"),
                summary_opinion=parsed.get("summary_opinion", ""),
            )
        except Exception as e:
            logger.warning(f"LLM API 호출 중 오류 발생: {e}. 휴리스틱 분석으로 전환합니다.")
            print(f"⚠️ LLM API 호출 실패 ({e}). 규칙 기반 분석으로 대체합니다.")
            return self._heuristic_analysis(item, rule_result)

    def _heuristic_analysis(
        self, item: AuctionItem, rule_result: RuleAnalysisResult
    ) -> LLMAnalysisResult:
        """API 키 부재 또는 실패 시 비고란 텍스트 정밀 감지를 통한 휴리스틱 분석 결과 생성"""
        rmrk_lower = (item.rmrk + " " + item.appraisal_summary).lower()

        # 1. 특수 권리 분석
        special_comments = []
        if "유치권" in rmrk_lower:
            special_comments.append(
                "🚨 비고란에 '유치권' 관련 신고 또는 주장이 포착되었습니다. "
                "유치권은 등기되지 않으며 낙찰자가 채무를 인수해야 하므로, "
                "실제 적법한 점유 여부 및 압류의 처분금지효 발생 전 점유개시 여부를 필히 확인해야 합니다."
            )
        if "법정지상권" in rmrk_lower or "토지만 매각" in rmrk_lower:
            special_comments.append(
                "⚠️ 법정지상권 성립 여부 확인 필요: 건물 또는 토지만 매각되는 물건의 경우, "
                "소유권 일치 여부 및 저당권 설정 당시 건물의 존재 여부 검토가 필수적입니다."
            )
        if not special_comments:
            special_comments.append("공고상 특별한 유치권, 법정지상권 등 특수 권리 신고 내역은 확인되지 않았습니다.")

        # 2. 건물 리스크
        building_comments = []
        if "위반건축물" in rmrk_lower or "불법" in rmrk_lower:
            building_comments.append("건축물대장상 위반건축물 등재 여부 및 이행강제금 부과 내역 확인이 필요합니다.")
        elif "제시외" in rmrk_lower:
            building_comments.append("제시외 건물(발코니 확장, 창고, 옥탑 등) 매각 포함 여부를 확인해야 합니다.")
        else:
            building_comments.append("현황상 공부와 일치하는 정형 주거용 집합건물로 파악됩니다.")

        # 3. 공매 특화 명도 리스크
        eviction_parts = [
            "📌 [공매 명도 주의]: 본 건은 온비드 공매 물건으로, 법원 경매와 달리 민사집행법상 '인도명령' 제도가 적용되지 않습니다.",
        ]
        if rule_result.has_opposing_tenant:
            eviction_parts.append(
                "대항력 있는 선순위 임차인이 거주 중이므로 보증금 반환 합의가 선행되어야 하며, "
                "인수 보증금 미정산 시 자진 인도를 기대하기 어렵습니다."
            )
        else:
            eviction_parts.append(
                "점유자(후순위 임차인 또는 소유자)가 자진 퇴거에 불응할 경우, "
                "정식 명도소송(소장 접수 후 판결까지 통상 4~6개월 소요) 및 강제집행 절차를 밟아야 하므로 "
                "이사비 협상과 명도 소송 일정을 병행 계획해야 합니다."
            )

        # 4. 공용 관리비 리스크
        maintenance_parts = []
        if "관리비" in rmrk_lower:
            maintenance_parts.append(
                "관리비 체납 내역이 비고란에 언급되어 있습니다. 대법원 판례상 최근 3년간의 공용부분 관리비는 "
                "낙찰자가 승계하여야 하므로 관리사무소를 통해 공용/전유 부분 금액을 정밀 분리 확인하십시오."
            )
        else:
            maintenance_parts.append(
                "집합건물 특성상 점유자 부재나 공실 기간 동안의 체납 관리비(공용부분) 승계 리스크가 존재하므로 "
                "입찰 전 관리사무소 탐문 조사가 권장됩니다."
            )

        # 5. 임장 체크리스트
        checklist = [
            "관리사무소 방문: 최근 3개년 공용부분 체납 관리비 총액 및 전용부분 분리 확인",
            "주민센터 방문: 전입세대확인서 열람을 통한 실제 세대원 전입일자 크로스체크",
            "현장 방문: 현관문 우편물 누적 상태, 계량기(수도/전기/가스) 회전 여부 확인",
            "점유자 대면 또는 탐문: 실제 점유 주체, 임대차 계약 진위 및 이사 협의 가능성 타진",
        ]
        if "유치권" in rmrk_lower:
            checklist.append("현관문 경고문 및 실제 시건장치 점유 상태 확인(유치권 배제 점유 증거 확보)")

        # 종합 리스크 등급 산정
        if "유치권" in rmrk_lower or rule_result.total_takeover_deposit > 0:
            grade = "고위험"
        elif rule_result.has_opposing_tenant or "관리비" in rmrk_lower:
            grade = "주의"
        elif item.failure_count >= 2:
            grade = "보통"
        else:
            grade = "안전"

        summary = (
            f"실질 취득 원가는 최저가 기준 {rule_result.effective_acquisition_cost:,}원(감정가 대비 {rule_result.acquisition_cost_ratio}%)이며, "
            f"인수 보증금은 {rule_result.total_takeover_deposit:,}원입니다. "
            f"공매 특성상 인도명령이 없으므로 명도 협상 기간을 최소 3~5개월 감안하여 입찰 전략을 수립하십시오."
        )

        return LLMAnalysisResult(
            special_rights_commentary=" ".join(special_comments),
            building_risk=" ".join(building_comments),
            eviction_risk=" ".join(eviction_parts),
            unpaid_maintenance_fee_risk=" ".join(maintenance_parts),
            field_inspection_checklist=checklist,
            overall_risk_grade=grade,
            summary_opinion=summary,
        )
