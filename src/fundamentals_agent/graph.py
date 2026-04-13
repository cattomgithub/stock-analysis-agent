"""LangGraph workflow for CN stock fundamental analysis."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from .fundamentals import generate_cn_stock_fundamental_report


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
    if not user_input:
        response = "请输入包含沪深京个股代码的请求，例如：请分析 600519 的基本面。"
    else:
        response = generate_cn_stock_fundamental_report.invoke({"user_input": user_input})
    return {"messages": [AIMessage(content=response)]}


builder = StateGraph(MessagesState)
builder.add_node("analyze_request", analyze_request)
builder.add_edge(START, "analyze_request")
builder.add_edge("analyze_request", END)

graph = builder.compile()
