from __future__ import annotations

import logging
from pathlib import Path
import re
import shutil
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from fundamentals_agent.llm import LLMSettings

LOGGER = logging.getLogger("tests")
REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_ARTIFACTS_DIR = REPO_ROOT / "reports" / "test-artifacts"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "external_llm: tests that call a real OpenAI-compatible LLM provider",
    )
    logging.getLogger("tests").setLevel(logging.DEBUG)
    logging.getLogger("fundamentals_agent").setLevel(logging.DEBUG)
    for logger_name in ("httpx", "httpcore", "openai", "asyncio"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def pytest_sessionstart(session: pytest.Session) -> None:
    LOGGER.debug("Pytest session started at root: %s", session.config.rootpath)
    LOGGER.debug("Persistent test artifacts will be written under: %s", TEST_ARTIFACTS_DIR)


def pytest_runtest_setup(item: pytest.Item) -> None:
    LOGGER.debug("START %s", item.nodeid)


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:
    del nextitem
    LOGGER.debug("END %s", item.nodeid)


def _nodeid_to_path_fragment(nodeid: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid).strip("_")
    return normalized or "test"


@pytest.fixture
def report_output_dir(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Path:
    output_dir = TEST_ARTIFACTS_DIR / _nodeid_to_path_fragment(request.node.nodeid)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STOCK_ANALYSIS_REPORT_DIR", str(output_dir))
    LOGGER.debug("STOCK_ANALYSIS_REPORT_DIR for %s -> %s", request.node.nodeid, output_dir)
    return output_dir


class FakeMXData:
    def query(self, tool_query: str) -> dict[str, Any]:
        return {
            "query": tool_query,
            "data": {
                "data": {
                    "searchDataResultDTO": {
                        "entityTagDTOList": [
                            {
                                "fullName": "贵州茅台",
                                "secuCode": "600519",
                                "marketChar": ".SH",
                            }
                        ]
                    }
                }
            },
        }

    @staticmethod
    def parse_result(
        result: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str], int, str | None]:
        query = result["query"]
        if "公司概况" in query or "公司简介" in query:
            rows = [
                {"字段": "公司简介", "数值": "高端白酒龙头"},
                {"字段": "总股本", "数值": "12.56 亿股"},
            ]
            return (
                [
                    {
                        "sheet_name": "公司概况",
                        "fieldnames": ["字段", "数值"],
                        "rows": rows,
                    }
                ],
                ["[贵州茅台] 公司概况"],
                len(rows),
                None,
            )
        if "股东结构" in query or "十大股东" in query:
            return (
                [
                    {
                        "sheet_name": "股东结构",
                        "fieldnames": ["股东", "持股比例"],
                        "rows": [{"股东": "中国贵州茅台酒厂", "持股比例": "54.07%"}],
                    }
                ],
                [],
                1,
                None,
            )
        rows = [
            {"date": "2024", "每股收益": "59.49", "净资产收益率": "34.74%"},
            {"date": "2023", "每股收益": "56.28", "净资产收益率": "33.90%"},
        ]
        return (
            [
                {
                    "sheet_name": "核心指标",
                    "fieldnames": ["date", "每股收益", "净资产收益率"],
                    "rows": rows,
                }
            ],
            [],
            len(rows),
            None,
        )


@pytest.fixture
def fake_mx_data_client() -> FakeMXData:
    return FakeMXData()


class FakeChatModel:
    def __init__(self, content: str = "模型总结：贵州茅台盈利能力与股东结构表现稳定，Markdown 报告已生成。") -> None:
        self.content = content
        self.calls: list[list[Any]] = []

    def invoke(self, messages: list[Any]) -> AIMessage:
        self.calls.append(messages)
        return AIMessage(content=self.content)


@pytest.fixture
def fake_chat_model() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture
def patch_fake_chat_model(
    monkeypatch: pytest.MonkeyPatch,
    fake_chat_model: FakeChatModel,
) -> FakeChatModel:
    monkeypatch.setattr(
        "fundamentals_agent.graph.create_chat_model",
        lambda provider=None: fake_chat_model,
    )
    monkeypatch.setattr(
        "fundamentals_agent.graph.get_llm_settings",
        lambda: LLMSettings(
            provider="openai",
            api_base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4.1-mini",
        ),
    )
    return fake_chat_model


@pytest.fixture
def patch_fake_mx_data_client(
    monkeypatch: pytest.MonkeyPatch,
    fake_mx_data_client: FakeMXData,
) -> FakeMXData:
    monkeypatch.setattr(
        "fundamentals_agent.fundamentals.create_mx_data_client",
        lambda api_key=None: fake_mx_data_client,
    )
    return fake_mx_data_client
