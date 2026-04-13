"""LLM-backed formatting helpers for fundamentals reports."""

from __future__ import annotations

from collections.abc import Mapping
import json
import re
from typing import TYPE_CHECKING, Any

from external_llm import LLMProvider, LLMResponse, create_llm_client, load_llm_provider

if TYPE_CHECKING:
    from .fundamentals import StockReport

_MARKDOWN_FENCE_PATTERN = re.compile(
    r"^```(?:markdown|md)?\s*(?P<body>.*)\s*```$",
    re.IGNORECASE | re.DOTALL,
)

FORMATTER_SYSTEM_PROMPT = """你是一名严谨的中文股票基本面整理助手。
你会收到东方财富妙想 mx-data 的结构化查询结果，请把它们整理成适合直接写入 Markdown 文件的内容。

输出要求：
1. 只根据给定数据整理内容，不要补充未提供的外部事实，不要编造。
2. 输出必须是 Markdown 正文，不要使用代码块围栏。
3. 每只股票至少包含“核心结论”“财务与估值要点”“风险与关注点”三个小节。
4. 尽量保留关键数值、同比/历史对比和股票代码。
5. 如果某一部分数据缺失或查询失败，明确写“该部分数据不足”。
6. 不要输出免责声明，不要要求用户补充信息。"""


def load_fundamentals_llm_provider(
    env: Mapping[str, str] | None = None,
) -> LLMProvider:
    return load_llm_provider("FUNDAMENTALS_LLM_PROVIDER", env=env)


def _serialize_reports_for_llm(reports: list[StockReport]) -> list[dict[str, Any]]:
    serialized_reports: list[dict[str, Any]] = []
    for report in reports:
        serialized_reports.append(
            {
                "symbol": report.target.symbol,
                "entity_label": report.entity_label,
                "sections": [
                    {
                        "title": section.title,
                        "query_text": section.query_text,
                        "conditions": list(section.conditions),
                        "error": section.error,
                        "tables": [
                            {
                                "sheet_name": str(table.get("sheet_name") or section.title),
                                "fieldnames": list(table.get("fieldnames") or []),
                                "rows": list(table.get("rows") or []),
                            }
                            for table in section.tables
                        ],
                    }
                    for section in report.sections
                ],
            }
        )
    return serialized_reports


def build_fundamentals_formatting_prompt(
    user_input: str,
    reports: list[StockReport],
) -> str:
    payload = {
        "user_input": user_input.strip(),
        "reports": _serialize_reports_for_llm(reports),
    }
    return "\n".join(
        [
            "请根据下面 JSON 中的东方财富妙想 mx-data 查询结果，整理成适合直接写入 Markdown 文件的中文报告正文。",
            "重点突出每只股票的公司概况、盈利与估值、资产与现金流、股东结构中的关键信息。",
            "如果某个部分没有有效数据或查询失败，请直接说明该部分数据不足。",
            "JSON 数据如下：",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def sanitize_llm_markdown(content: str) -> str:
    normalized = content.strip()
    if not normalized:
        raise RuntimeError("外部 LLM 未返回可写入 Markdown 的内容")

    fenced_match = _MARKDOWN_FENCE_PATTERN.match(normalized)
    if fenced_match is not None:
        normalized = fenced_match.group("body").strip()
    if not normalized:
        raise RuntimeError("外部 LLM 未返回可写入 Markdown 的内容")
    return normalized


def summarize_reports_with_external_llm(
    user_input: str,
    reports: list[StockReport],
    *,
    client: Any | None = None,
    env: Mapping[str, str] | None = None,
) -> LLMResponse:
    provider = load_fundamentals_llm_provider(env)
    llm_client = client or create_llm_client(provider, env=env)
    response = llm_client.prompt(
        build_fundamentals_formatting_prompt(user_input, reports),
        system_prompt=FORMATTER_SYSTEM_PROMPT,
        temperature=0.1,
    )
    return LLMResponse(
        provider=response.provider,
        model=response.model,
        content=sanitize_llm_markdown(response.content),
        usage=response.usage,
        raw_response=response.raw_response,
    )


__all__ = [
    "FORMATTER_SYSTEM_PROMPT",
    "build_fundamentals_formatting_prompt",
    "load_fundamentals_llm_provider",
    "sanitize_llm_markdown",
    "summarize_reports_with_external_llm",
]