"""LangGraph workflow for CN stock fundamental analysis."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from .fundamentals import build_fundamental_report, render_completion_message

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


def analyze_request(state: MessagesState) -> dict[str, list[AIMessage]]:
    user_input = _last_user_message(state["messages"]).strip()
    logger.debug("Analyzing request with user input: %s", user_input)
    if not user_input:
        response = "请输入包含沪深京个股代码的请求，例如：请分析 600519 的基本面。"
    else:
        try:
            report_path, targets, _markdown_text = build_fundamental_report(user_input)
        except Exception as exc:
            logger.debug("Fundamental report generation failed: %s", exc)
            response = f"生成基本面报告失败：{exc}"
        else:
            response = render_completion_message(report_path, targets)
            logger.debug(
                "Completed analyze_request for %s with report %s",
                [target.symbol for target in targets],
                report_path,
            )
    return {"messages": [AIMessage(content=response)]}


builder = StateGraph(MessagesState)
builder.add_node("analyze_request", analyze_request)
builder.add_edge(START, "analyze_request")
builder.add_edge("analyze_request", END)

graph = builder.compile()
