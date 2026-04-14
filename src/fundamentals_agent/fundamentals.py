"""Helpers for CN stock fundamental reports backed by Eastmoney MX skills."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool

from .metrics import REPORT_QUERY_BUNDLES, filter_section_tables
from .report_formatting import summarize_reports_with_external_llm

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MX_SKILLS_DIR = REPO_ROOT / "eastmoney-mx-skills"
logger = logging.getLogger(__name__)


def resolve_mx_skills_dir() -> Path:
    configured_dir = os.getenv("EASTMONEY_MX_SKILLS_DIR")
    resolved_dir = Path(configured_dir) if configured_dir else DEFAULT_MX_SKILLS_DIR
    logger.debug("Resolved Eastmoney MX skills directory: %s", resolved_dir)
    return resolved_dir


def resolve_mx_data_module_path() -> Path:
    configured_path = os.getenv("EASTMONEY_MX_DATA_PATH")
    if configured_path:
        module_path = Path(configured_path)
        logger.debug("Resolved Eastmoney MX data module from env: %s", module_path)
        return module_path
    module_path = resolve_mx_skills_dir() / "mx-data" / "mx_data.py"
    logger.debug("Resolved Eastmoney MX data module path: %s", module_path)
    return module_path

SHANGHAI_PREFIXES = ("600", "601", "603", "605", "688", "689")
SHENZHEN_PREFIXES = ("000", "001", "002", "003", "300", "301")
BEIJING_PREFIXES = ("4", "8", "920")
STOCK_CODE_PATTERN = re.compile(
    r"(?<!\d)(?:(?P<prefix>SH|SZ|BJ)\s*)?(?P<code>\d{6})(?:\.(?P<suffix>SH|SZ|BJ))?(?!\d)",
    re.IGNORECASE,
)
NAME_BODY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:请|帮我|麻烦|想|想要|请帮我|给我|帮忙)?"
        r"(?:分析|看看|看下|查询|研究|了解|关注|梳理|总结|介绍|评估|说明|聊聊)?"
        r"\s*(?P<body>[\u4e00-\u9fffA-Za-z0-9、，,和及与/\s]{2,48}?)"
        r"(?:的)?(?:基本面|财务|公司概况|盈利能力|估值|资产负债|现金流|股东结构|情况|业务)"
    ),
    re.compile(
        r"(?P<body>[\u4e00-\u9fffA-Za-z0-9、，,和及与/\s]{2,48}?)"
        r"(?:这只|这家)?(?:股票|个股|公司)(?:的)?(?:基本面|财务|情况|业务|估值|盈利)?"
    ),
)
NAME_SPLIT_PATTERN = re.compile(r"(?:、|，|,|/|\s+|和|及|与)+")
NAME_LEADING_NOISE_PATTERN = re.compile(
    r"^(?:请|帮我|麻烦|想|想要|请帮我|给我|帮忙|分析|看看|看下|查询|研究|了解|关注|梳理|总结|介绍|评估|说明|聊聊)+"
)
NAME_TRAILING_NOISE_PATTERN = re.compile(
    r"(?:的|股票|个股|公司|基本面|财务|情况|业务|估值|盈利|表现)+$"
)
GENERIC_NAME_TOKENS = {
    "基本面",
    "个股",
    "股票",
    "公司",
    "财务",
    "情况",
    "业务",
    "估值",
    "盈利",
    "表现",
}


@dataclass(frozen=True, slots=True)
class StockTarget:
    code: str
    market: str

    @property
    def symbol(self) -> str:
        return f"{self.code}.{self.market}"


@dataclass(slots=True)
class SectionResult:
    title: str
    query_text: str
    tables: list[dict[str, Any]]
    conditions: list[str]
    error: str | None = None


@dataclass(slots=True)
class StockReport:
    target: StockTarget
    entity_label: str
    sections: list[SectionResult]


def _normalize_name_candidate(candidate: str) -> str:
    normalized = candidate.strip()
    previous = None
    while normalized and normalized != previous:
        previous = normalized
        normalized = NAME_LEADING_NOISE_PATTERN.sub("", normalized).strip()
        normalized = NAME_TRAILING_NOISE_PATTERN.sub("", normalized).strip()
    return normalized


def _looks_like_stock_name(candidate: str) -> bool:
    if not candidate:
        return False
    if candidate in GENERIC_NAME_TOKENS:
        return False
    if candidate.isdigit():
        return False
    if not (2 <= len(candidate) <= 12):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", candidate))


def extract_cn_stock_name_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    sanitized_text = STOCK_CODE_PATTERN.sub(" ", text)

    for pattern in NAME_BODY_PATTERNS:
        for match in pattern.finditer(sanitized_text):
            body = str(match.group("body") or "")
            for token in NAME_SPLIT_PATTERN.split(body):
                normalized = _normalize_name_candidate(token)
                if not _looks_like_stock_name(normalized):
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                candidates.append(normalized)

    if not candidates:
        for token in NAME_SPLIT_PATTERN.split(sanitized_text):
            normalized = _normalize_name_candidate(token)
            if not _looks_like_stock_name(normalized):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(normalized)

    whole_candidate = _normalize_name_candidate(
        re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", sanitized_text)
    )
    has_explicit_separator = bool(re.search(r"\s[和及与]\s|[、，,/]", sanitized_text))
    if (
        not candidates
        and not has_explicit_separator
        and _looks_like_stock_name(whole_candidate)
        and whole_candidate not in seen
    ):
        seen.add(whole_candidate)
        candidates.append(whole_candidate)
    return candidates


def infer_market_from_code(code: str) -> str | None:
    if code.startswith(SHANGHAI_PREFIXES):
        return "SH"
    if code.startswith(SHENZHEN_PREFIXES):
        return "SZ"
    if code.startswith(BEIJING_PREFIXES):
        return "BJ"
    return None


def extract_cn_stock_targets(text: str) -> list[StockTarget]:
    targets: list[StockTarget] = []
    seen: set[str] = set()
    for match in STOCK_CODE_PATTERN.finditer(text):
        code = match.group("code")
        explicit_market = (match.group("suffix") or match.group("prefix") or "").upper()
        inferred_market = infer_market_from_code(code)
        if inferred_market is None:
            continue
        if explicit_market and explicit_market != inferred_market:
            continue
        symbol = f"{code}.{inferred_market}"
        if symbol in seen:
            continue
        seen.add(symbol)
        targets.append(StockTarget(code=code, market=inferred_market))
    return targets


def _load_module(module_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("eastmoney_mx_data", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载东方财富妙想模块: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_mx_data_class() -> type[Any]:
    module_path = resolve_mx_data_module_path()
    if not module_path.is_file():
        raise FileNotFoundError(
            f"未找到东方财富妙想 mx-data 模块: {module_path}"
        )
    try:
        module = _load_module(module_path)
    except ModuleNotFoundError as exc:
        missing = exc.name or "未知依赖"
        raise RuntimeError(
            f"加载东方财富妙想 mx-data 失败，缺少依赖 {missing}。"
        ) from exc

    mx_data_class = getattr(module, "MXData", None)
    if mx_data_class is None:
        raise RuntimeError("东方财富妙想 mx-data 模块中缺少 MXData 类")
    return mx_data_class


def create_mx_data_client(api_key: str | None = None) -> Any:
    return load_mx_data_class()(api_key=api_key or os.getenv("MX_APIKEY"))


def _iter_entity_tags(result: dict[str, Any]) -> list[dict[str, Any]]:
    search_result = (
        ((result.get("data") or {}).get("data") or {}).get("searchDataResultDTO") or {}
    )
    entity_tags = search_result.get("entityTagDTOList") or []
    return [entity for entity in entity_tags if isinstance(entity, dict)]


def extract_stock_target_from_result(result: dict[str, Any]) -> StockTarget | None:
    for entity in _iter_entity_tags(result):
        code = re.sub(r"\D", "", str(entity.get("secuCode") or "").strip())
        if len(code) != 6:
            continue

        explicit_market = str(entity.get("marketChar") or "").replace(".", "").strip().upper()
        inferred_market = infer_market_from_code(code)
        market = explicit_market if explicit_market in {"SH", "SZ", "BJ"} else inferred_market
        if market is None:
            continue
        if inferred_market is not None and market != inferred_market:
            market = inferred_market
        return StockTarget(code=code, market=market)
    return None


def extract_entity_label(result: dict[str, Any], fallback_symbol: str) -> str:
    for entity in _iter_entity_tags(result):
        full_name = str(entity.get("fullName") or "").strip()
        secu_code = str(entity.get("secuCode") or "").strip()
        market_char = str(entity.get("marketChar") or "").strip()
        if full_name:
            code_part = f" ({secu_code}{market_char})" if secu_code else ""
            return f"{full_name}{code_part}"
    return fallback_symbol


def build_section_queries(target: StockTarget) -> tuple[tuple[str, str], ...]:
    return tuple(
        (title, f"{target.symbol} {suffix}")
        for title, suffix in REPORT_QUERY_BUNDLES
    )


def resolve_stock_target_from_name(client: Any, stock_name: str) -> StockTarget:
    resolution_query = f"{stock_name} 公司简介 主营业务"
    logger.debug("Resolving stock name %s with %s", stock_name, resolution_query)
    result = client.query(resolution_query)
    target = extract_stock_target_from_result(result)
    if target is None:
        raise ValueError(f"未能从东方财富妙想 mx-data 识别股票名称：{stock_name}")
    return target


def query_fundamental_section(
    client: Any,
    target: StockTarget,
    title: str,
    query_text: str,
) -> tuple[SectionResult, str]:
    logger.debug("Querying section %s for %s with %s", title, target.symbol, query_text)
    result = client.query(query_text)
    tables, conditions, _total_rows, error = client.parse_result(result)
    filtered_tables = filter_section_tables(title, tables)
    return (
        SectionResult(
            title=title,
            query_text=query_text,
            tables=filtered_tables,
            conditions=conditions,
            error=error,
        ),
        extract_entity_label(result, target.symbol),
    )


def collect_stock_report(client: Any, target: StockTarget) -> StockReport:
    sections: list[SectionResult] = []
    entity_label = target.symbol
    logger.debug("Collecting report sections for %s", target.symbol)
    for title, query_text in build_section_queries(target):
        try:
            section, resolved_entity_label = query_fundamental_section(
                client,
                target,
                title,
                query_text,
            )
            if resolved_entity_label != target.symbol:
                entity_label = resolved_entity_label
        except Exception as exc:
            logger.debug("Section %s failed for %s: %s", title, target.symbol, exc)
            section = SectionResult(
                title=title,
                query_text=query_text,
                tables=[],
                conditions=[],
                error=str(exc),
            )
        sections.append(section)
    return StockReport(target=target, entity_label=entity_label, sections=sections)


def resolve_report_dir(output_dir: str | None = None) -> Path:
    report_dir = Path(output_dir) if output_dir else Path(
        os.getenv("STOCK_ANALYSIS_REPORT_DIR", str(REPO_ROOT / "reports"))
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Resolved report output directory: %s", report_dir)
    return report_dir


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>")


def render_markdown_table(fieldnames: list[str], rows: list[dict[str, Any]], max_rows: int = 20) -> str:
    if not fieldnames or not rows:
        return "暂无结构化数据。"

    lines = [
        "| " + " | ".join(_markdown_cell(name) for name in fieldnames) + " |",
        "| " + " | ".join(["---"] * len(fieldnames)) + " |",
    ]
    for row in rows[:max_rows]:
        lines.append(
            "| "
            + " | ".join(_markdown_cell(row.get(fieldname, "")) for fieldname in fieldnames)
            + " |"
        )
    if len(rows) > max_rows:
        lines.append("")
        lines.append(f"仅展示前 {max_rows} 行，剩余数据已省略。")
    return "\n".join(lines)


def render_section(section: SectionResult) -> str:
    lines = [f"### {section.title}", "", f"查询语句：{section.query_text}", ""]
    if section.error:
        lines.append(f"查询失败：{section.error}")
        return "\n".join(lines)

    if not section.tables:
        lines.append("未返回可解析的目标指标数据。")
        return "\n".join(lines)

    for table in section.tables:
        sheet_name = str(table.get("sheet_name") or section.title)
        fieldnames = list(table.get("fieldnames") or [])
        rows = list(table.get("rows") or [])
        lines.extend([
            f"#### {sheet_name}",
            "",
            render_markdown_table(fieldnames, rows),
            "",
        ])

    if section.conditions:
        lines.append("筛选条件：")
        for condition in section.conditions:
            normalized = " ".join(condition.splitlines()).strip()
            lines.append(f"- {normalized}")
    return "\n".join(lines).rstrip()


def _render_report_detail_sections(reports: list[StockReport]) -> list[str]:
    lines: list[str] = []
    for report in reports:
        lines.extend(
            [
                f"## {report.entity_label}",
                "",
                f"- 股票代码：{report.target.symbol}",
                "",
            ]
        )
        for section in report.sections:
            lines.extend([render_section(section), "", ""])
    return lines


def render_markdown_report(
    user_input: str,
    reports: list[StockReport],
    llm_summary_markdown: str,
    llm_provider: str,
    llm_model: str,
) -> str:
    target_list = "、".join(report.target.symbol for report in reports)
    lines = [
        "# 沪深京个股基本面报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 原始输入：{user_input}",
        f"- 识别股票：{target_list}",
        "- 数据来源：东方财富妙想 skills / mx-data",
        f"- 外部 LLM：{llm_provider} / {llm_model}",
        "",
        "## 外部 LLM 整理结果",
        "",
        llm_summary_markdown.strip(),
        "",
        "## 原始查询明细",
        "",
    ]
    lines.extend(_render_report_detail_sections(reports))
    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(
    markdown_text: str,
    reports: list[StockReport],
    output_dir: str | None = None,
) -> Path:
    report_dir = resolve_report_dir(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    code_segment = "_".join(report.target.code for report in reports[:3])
    if len(reports) > 3:
        code_segment = f"{code_segment}_{len(reports)}stocks"
    file_path = report_dir / f"fundamentals_{code_segment}_{timestamp}.md"
    file_path.write_text(markdown_text, encoding="utf-8")
    logger.debug("Wrote markdown report to %s", file_path)
    return file_path


def render_completion_message(report_path: Path, targets: list[StockTarget]) -> str:
    resolved = "、".join(target.symbol for target in targets)
    return "\n".join(
        [
            f"已识别股票：{resolved}",
            "已调用东方财富妙想 mx-data skill 完成个股基本面查询。",
            "已调用外部 LLM 完成结果整理。",
            f"已生成 Markdown 报告：{report_path}",
            "个股基本面信息收集完成。",
        ]
    )


def collect_reports_from_input(user_input: str) -> tuple[list[StockTarget], list[StockReport]]:
    client = create_mx_data_client()
    code_targets = extract_cn_stock_targets(user_input)
    stock_names = extract_cn_stock_name_candidates(user_input)
    logger.debug(
        "Extracted stock candidates from input %r: codes=%s names=%s",
        user_input,
        [target.symbol for target in code_targets],
        stock_names,
    )
    if not code_targets and not stock_names:
        raise ValueError(
            "未检测到沪深京个股代码或股票名称，请提供 6 位个股代码，或明确的个股名称，例如 600519、000001、贵州茅台。"
        )

    targets: list[StockTarget] = []
    seen_symbols: set[str] = set()
    for target in code_targets:
        if target.symbol in seen_symbols:
            continue
        seen_symbols.add(target.symbol)
        targets.append(target)

    unresolved_names: list[str] = []
    for stock_name in stock_names:
        try:
            resolved_target = resolve_stock_target_from_name(client, stock_name)
        except Exception as exc:
            logger.debug("Failed to resolve stock name %s: %s", stock_name, exc)
            unresolved_names.append(stock_name)
            continue
        if resolved_target.symbol in seen_symbols:
            continue
        seen_symbols.add(resolved_target.symbol)
        targets.append(resolved_target)

    if not targets:
        unresolved_text = "、".join(unresolved_names) or user_input
        raise ValueError(f"未能识别为沪深京个股：{unresolved_text}")

    reports = [collect_stock_report(client, target) for target in targets]
    return targets, reports


def build_fundamental_report(
    user_input: str,
    output_dir: str | None = None,
) -> tuple[Path, list[StockTarget], str]:
    logger.debug("Building fundamental report for input: %s", user_input)
    targets, reports = collect_reports_from_input(user_input)
    llm_response = summarize_reports_with_external_llm(user_input, reports)
    markdown_text = render_markdown_report(
        user_input,
        reports,
        llm_response.content,
        llm_response.provider,
        llm_response.model,
    )
    report_path = write_markdown_report(markdown_text, reports, output_dir)
    logger.debug("Finished report generation at %s", report_path)
    return report_path, targets, markdown_text


@tool
def detect_cn_stock_codes(text: str) -> str:
    """Detect supported沪深京个股代码或股票名称 from user input."""

    targets = extract_cn_stock_targets(text)
    stock_names = extract_cn_stock_name_candidates(text)
    payload = {
        "contains_cn_stock_code": bool(targets),
        "contains_cn_stock_target": bool(targets or stock_names),
        "codes": [target.symbol for target in targets],
        "names": stock_names,
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def generate_cn_stock_fundamental_report(
    user_input: str,
    output_dir: str | None = None,
) -> str:
    """Generate a Markdown fundamental report for沪深京 individual stocks using Eastmoney MX skills and an external LLM."""

    try:
        report_path, targets, _markdown_text = build_fundamental_report(user_input, output_dir)
    except Exception as exc:
        return f"生成基本面报告失败：{exc}"

    return render_completion_message(report_path, targets)


__all__ = [
    "StockTarget",
    "build_fundamental_report",
    "build_section_queries",
    "collect_reports_from_input",
    "create_mx_data_client",
    "detect_cn_stock_codes",
    "extract_cn_stock_name_candidates",
    "extract_cn_stock_targets",
    "generate_cn_stock_fundamental_report",
    "render_markdown_report",
    "render_completion_message",
]