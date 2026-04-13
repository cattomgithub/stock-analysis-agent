"""LangGraph workflow for CN stock fundamental analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from .fundamentals import build_fundamental_report
from .llm import create_chat_model, get_llm_settings

logger = logging.getLogger(__name__)


def _message_text(message: Any) -> str:
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


def _last_user_message(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, dict):
            if message.get("role") == "user":
                return _message_text(message)
            continue

        if getattr(message, "type", "") == "human":
            return _message_text(message)
    return ""


def _render_base_response(report_path: Path, symbols: list[str], provider: str | None) -> str:
    lines = [
        f"已识别股票代码：{'、'.join(symbols)}",
        f"已生成 Markdown 报告：{report_path}",
    ]
    if provider:
        lines.append(f"LLM 提供方：{provider}")
    else:
        lines.append("LLM 提供方：未配置，已返回基础结果。")
    return "\n".join(lines)


def _summarize_report_with_llm(
    user_input: str,
    markdown_text: str,
    report_path: Path,
    symbols: list[str],
) -> tuple[str | None, str | None]:
    try:
        settings = get_llm_settings()
        llm = create_chat_model(provider=settings.provider)
    except ValueError:
        logger.debug("No LLM configuration detected, falling back to base response")
        return None, None

    prompt = (
        "你是沪深京个股基本面分析助手。"
        "请基于提供的 Markdown 报告，用中文输出 2 到 4 句总结。"
        "只使用报告中已有的信息，不要编造未提供的数据。"
        "总结里必须明确提到股票代码，并提醒用户 Markdown 报告已经生成。"
    )
    try:
        logger.debug(
            "Invoking LLM summary provider=%s model for report %s",
            settings.provider,
            report_path,
        )
        response = llm.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=(
                        f"用户请求：{user_input}\n"
                        f"股票代码：{'、'.join(symbols)}\n"
                        f"报告路径：{report_path}\n"
                        f"报告内容：\n{markdown_text}"
                    )
                ),
            ]
        )
    except Exception as exc:
        logger.debug("LLM summary generation failed for %s: %s", report_path, exc)
        return f"LLM 总结生成失败：{exc}", settings.provider

    logger.debug("LLM summary generated successfully for %s", report_path)
    return _message_text(response).strip(), settings.provider


def analyze_request(state: MessagesState) -> dict[str, list[AIMessage]]:
    user_input = _last_user_message(state["messages"]).strip()
    logger.debug("Analyzing request with user input: %s", user_input)
    if not user_input:
        response = "请输入包含沪深京个股代码的请求，例如：请分析 600519 的基本面。"
    else:
        try:
            report_path, targets, markdown_text = build_fundamental_report(user_input)
        except Exception as exc:
            logger.debug("Fundamental report generation failed: %s", exc)
            response = f"生成基本面报告失败：{exc}"
        else:
            symbols = [target.symbol for target in targets]
            llm_summary, provider = _summarize_report_with_llm(
                user_input,
                markdown_text,
                report_path,
                symbols,
            )
            base_response = _render_base_response(report_path, symbols, provider)
            response = f"{llm_summary}\n\n{base_response}" if llm_summary else base_response
            logger.debug("Completed analyze_request for %s with report %s", symbols, report_path)
    return {"messages": [AIMessage(content=response)]}


builder = StateGraph(MessagesState)
builder.add_node("analyze_request", analyze_request)
builder.add_edge(START, "analyze_request")
builder.add_edge("analyze_request", END)

graph = builder.compile()
