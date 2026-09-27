"""
BidScope CLI Entry Point
Provides search and analyze subcommands for Onbid auction property analysis.
"""

import sys
import argparse
from typing import Optional
from tabulate import tabulate

from api_client import OnbidApiClient
from models import AuctionItem, RightItem, Tenant
from rule_engine import RuleEngine
from llm_engine import LLMEngine
from reporter import Reporter
import cache_manager


def handle_search(args: argparse.Namespace) -> None:
    """조건별 온비드 공매 물건 검색 핸들러"""
    client = OnbidApiClient()
    result = client.search_items(
        region=args.region,
        start_date=args.start_date,
        end_date=args.end_date,
        item_type=args.type,
        page=args.page,
        refresh=args.refresh,
    )

    items = result.get("items", [])
    total_count = result.get("total_count", len(items))

    print("\n" + "=" * 80)
    print(f"🔍 [온비드 공매 물건 검색 결과] (총 {total_count}건, {args.page}페이지)")
    print("=" * 80)

    if not items:
        print("검색 조건에 일치하는 물건이 없습니다.")
        print("=" * 80 + "\n")
        return

    table_data = []
    for it in items:
        table_data.append([
            it.get("item_id"),
            it.get("item_type", "기타"),
            it.get("name", "")[:35] + ("..." if len(it.get("name", "")) > 35 else ""),
            f"{it.get('appraisal_amount', 0):,}원",
            f"{it.get('minimum_bid_amount', 0):,}원",
            f"{it.get('failure_count', 0)}회",
            it.get("bid_period", ""),
        ])

    headers = ["물건관리번호", "용도", "물건명", "감정평가액", "최저입찰가", "유찰", "입찰기간"]
    print(tabulate(table_data, headers=headers, tablefmt="rounded_grid"))
    print("\n💡 특정 물건의 권리분석 및 리포트를 생성하려면 아래 명령어를 실행하십시오:")
    sample_id = items[0].get("item_id")
    print(f"   python cli.py analyze --id \"{sample_id}\" --llm\n")


def handle_analyze(args: argparse.Namespace) -> None:
    """단건 분석 및 마크다운 리포트 생성 핸들러"""
    item_id = args.id.strip()
    if not item_id:
        print("❌ 물건관리번호(--id)를 입력해 주세요.")
        sys.exit(1)

    client = OnbidApiClient()
    raw_data = client.get_item_detail(item_id, refresh=args.refresh)

    # Pydantic AuctionItem 모델 변환
    rights = [RightItem(**r) for r in raw_data.get("rights", [])]
    tenants = [Tenant(**t) for t in raw_data.get("tenants", [])]

    item = AuctionItem(
        item_id=raw_data.get("item_id", item_id),
        pbct_no=raw_data.get("pbct_no", ""),
        name=raw_data.get("name", f"온비드 공매 물건 ({item_id})"),
        item_type=raw_data.get("item_type", "부동산"),
        location=raw_data.get("location", ""),
        appraisal_amount=raw_data.get("appraisal_amount", 0),
        minimum_bid_amount=raw_data.get("minimum_bid_amount", 0),
        bid_start_date=raw_data.get("bid_start_date", ""),
        bid_end_date=raw_data.get("bid_end_date", ""),
        dividend_closing_date=raw_data.get("dividend_closing_date", None),
        failure_count=raw_data.get("failure_count", 0),
        rmrk=raw_data.get("rmrk", ""),
        appraisal_summary=raw_data.get("appraisal_summary", ""),
        status=raw_data.get("status", "입찰진행"),
        rights=rights,
        tenants=tenants,
    )

    # 1. 결정론적 1차 룰 엔진 권리분석
    print("⚖️ [1차] 결정론적 권리분석(Rule Engine)을 시작합니다...")
    rule_result = RuleEngine.analyze(item)

    # 2. 2차 정밀 LLM 리스크 분석 (옵션: --llm)
    llm_result = None
    if args.llm:
        print("🧠 [2차] 정밀 리스크 & 명도 분석(LLM Engine)을 시작합니다...")
        llm_engine = LLMEngine()
        llm_result = llm_engine.analyze(item, rule_result)

    # 3. 마크다운 리포트 생성 및 저장
    cache_path = str(cache_manager.get_item_cache_path(item_id))
    report_file = Reporter.generate_and_save_report(
        item=item,
        rule_result=rule_result,
        llm_result=llm_result,
        cache_source_path=cache_path,
    )

    # 4. 콘솔 요약 출력
    Reporter.print_console_summary(
        item=item,
        rule_result=rule_result,
        llm_result=llm_result,
        report_path=report_file,
    )


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 정의"""
    parser = argparse.ArgumentParser(
        prog="bidscope",
        description="📌 Project BidScope: 온비드 공매 분석 및 듀얼 리포트(Rule + LLM) 생성 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령어")

    # 1. search 서브커맨드
    search_parser = subparsers.add_parser("search", help="온비드 공매 물건 조건별 검색 및 로컬 캐싱")
    search_parser.add_argument("--region", type=str, default=None, help="시/군/구 단위 지역명 (예: '서울특별시 영등포구')")
    search_parser.add_argument("--start-date", type=str, default=None, help="입찰 시작 기간 (YYYY-MM-DD)")
    search_parser.add_argument("--end-date", type=str, default=None, help="입찰 마감 기간 (YYYY-MM-DD)")
    search_parser.add_argument("--type", type=str, default=None, help="용도 구분 (아파트, 다세대, 오피스텔 등)")
    search_parser.add_argument("--page", type=int, default=1, help="페이지 번호 (기본값: 1)")
    search_parser.add_argument("--refresh", action="store_true", help="캐시를 무시하고 최신 데이터 조회")

    # 2. analyze 서브커맨드
    analyze_parser = subparsers.add_parser("analyze", help="물건관리번호 단건 권리분석 및 Markdown 리포트 생성")
    analyze_parser.add_argument("--id", type=str, required=True, help="온비드 물건관리번호 (예: '2025-10482-001')")
    analyze_parser.add_argument("--llm", action="store_true", help="LLM 정밀 리스크 및 명도소송 분석 포함")
    analyze_parser.add_argument("--refresh", action="store_true", help="캐시를 무시하고 최신 데이터 재호출")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "search":
        handle_search(args)
    elif args.command == "analyze":
        handle_analyze(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
