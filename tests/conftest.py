from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Any

import pytest

from fundamentals_agent.llm_clients import LLMResponse

LOGGER = logging.getLogger("tests")
REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_ARTIFACTS_DIR = REPO_ROOT / "reports" / "test-artifacts"
QUERY_SYMBOL_PATTERN = re.compile(r"(?P<code>\d{6})\.(?P<market>SH|SZ|BJ)")
NAME_SYMBOL_MAP = {
    "贵州茅台": "600519.SH",
    "平安银行": "000001.SZ",
    "北交测试": "920047.BJ",
}


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


def pytest_configure(config: pytest.Config) -> None:
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
    def __init__(self) -> None:
        self.query_log: list[str] = []

    @staticmethod
    def company_name(symbol: str) -> str:
        code, market = symbol.split(".")
        return f"测试样本{market}{code}"

    @staticmethod
    def _extract_symbol(tool_query: str) -> str:
        match = QUERY_SYMBOL_PATTERN.search(tool_query)
        if match is None:
            for stock_name, symbol in NAME_SYMBOL_MAP.items():
                if stock_name in tool_query:
                    return symbol
            raise AssertionError(f"无法从查询语句中识别股票代码: {tool_query}")
        return f"{match.group('code')}.{match.group('market')}"

    @staticmethod
    def _seed(symbol: str) -> int:
        return int(symbol[:6][-2:])

    def query(self, tool_query: str) -> dict[str, Any]:
        symbol = self._extract_symbol(tool_query)
        code, market = symbol.split(".")
        self.query_log.append(tool_query)
        return {
            "query": tool_query,
            "data": {
                "data": {
                    "searchDataResultDTO": {
                        "entityTagDTOList": [
                            {
                                "fullName": self.company_name(symbol),
                                "secuCode": code,
                                "marketChar": f".{market}",
                            }
                        ]
                    }
                }
            },
        }

    def parse_result(
        self,
        result: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str], int, str | None]:
        query = result["query"]
        symbol = self._extract_symbol(query)
        company_name = self.company_name(symbol)
        seed = self._seed(symbol)

        if "公司概况" in query or "公司简介" in query:
            rows = [
                {
                    "字段": "公司简介",
                    "数值": f"{company_name} 围绕 {symbol} 的主营业务测试样本",
                },
                {"字段": "总股本", "数值": f"{10 + seed / 100:.2f} 亿股"},
            ]
            return (
                [
                    {
                        "sheet_name": "公司概况",
                        "fieldnames": ["字段", "数值"],
                        "rows": rows,
                    }
                ],
                [f"[{company_name}] 公司概况", f"symbol={symbol}"],
                len(rows),
                None,
            )
        if "股东结构" in query or "十大股东" in query:
            row = {
                "股东": f"{company_name} 控股股东",
                "持股比例": f"{40 + seed % 10}.0{seed % 7}%",
            }
            return (
                [
                    {
                        "sheet_name": "股东结构",
                        "fieldnames": ["股东", "持股比例"],
                        "rows": [row],
                    }
                ],
                [f"[{company_name}] 股东结构"],
                1,
                None,
            )
        if "资产负债率" in query or "自由现金流" in query:
            rows = [
                {
                    "date": "2024",
                    "资产负债率": f"{20 + seed % 15}.10%",
                    "经营活动现金流净额": f"{100 + seed} 亿",
                },
                {
                    "date": "2023",
                    "资产负债率": f"{19 + seed % 12}.80%",
                    "经营活动现金流净额": f"{90 + seed} 亿",
                },
            ]
            return (
                [
                    {
                        "sheet_name": "资产与现金流",
                        "fieldnames": ["date", "资产负债率", "经营活动现金流净额"],
                        "rows": rows,
                    }
                ],
                [f"[{company_name}] 资产与现金流"],
                len(rows),
                None,
            )

        rows = [
            {
                "date": "2024",
                "每股收益": f"{50 + seed / 10:.2f}",
                "净资产收益率": f"{30 + seed % 10}.40%",
            },
            {
                "date": "2023",
                "每股收益": f"{45 + seed / 10:.2f}",
                "净资产收益率": f"{28 + seed % 10}.10%",
            },
        ]
        return (
            [
                {
                    "sheet_name": "核心指标",
                    "fieldnames": ["date", "每股收益", "净资产收益率"],
                    "rows": rows,
                }
            ],
            [f"[{company_name}] 盈利与估值"],
            len(rows),
            None,
        )


class RecordingMXDataClient:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.query_log: list[str] = []

    def query(self, tool_query: str) -> dict[str, Any]:
        self.query_log.append(tool_query)
        return self._delegate.query(tool_query)

    def parse_result(
        self,
        result: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str], int, str | None]:
        return self._delegate.parse_result(result)


class FakeLLMSummarizer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        user_input: str,
        reports: list[Any],
        *,
        client: Any | None = None,
        env: Any | None = None,
    ) -> LLMResponse:
        del client, env
        summary_lines: list[str] = []
        serialized_reports: list[dict[str, Any]] = []
        for report in reports:
            serialized_reports.append(
                {
                    "symbol": report.target.symbol,
                    "entity_label": report.entity_label,
                }
            )
            summary_lines.extend(
                [
                    f"## {report.entity_label}",
                    "",
                    "### 核心结论",
                    f"- 已基于东方财富 mx-data 汇总 {report.target.symbol} 的基本面数据。",
                    "### 财务与估值要点",
                ]
            )
            for section in report.sections:
                row_count = sum(len(table.get("rows") or []) for table in section.tables)
                if section.error:
                    summary_lines.append(f"- {section.title}: 该部分数据不足（{section.error}）。")
                else:
                    summary_lines.append(f"- {section.title}: 共解析 {row_count} 行结构化数据。")
            summary_lines.extend(
                [
                    "### 风险与关注点",
                    "- 本摘要仅基于本次 mx-data 返回结果整理，不包含额外外部信息。",
                    "",
                ]
            )

        content = "\n".join(summary_lines).strip()
        self.calls.append(
            {
                "user_input": user_input,
                "reports": json.loads(json.dumps(serialized_reports, ensure_ascii=False)),
                "content": content,
            }
        )
        return LLMResponse(
            provider="openai",
            model="fake-openai-test",
            content=content,
            usage={"total_tokens": len(content)},
            raw_response={"choices": [{"message": {"role": "assistant", "content": content}}]},
        )


@pytest.fixture
def fake_mx_data_client() -> FakeMXData:
    return FakeMXData()


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


@pytest.fixture
def fake_llm_summarizer() -> FakeLLMSummarizer:
    return FakeLLMSummarizer()


@pytest.fixture
def patch_fake_llm_summarizer(
    monkeypatch: pytest.MonkeyPatch,
    fake_llm_summarizer: FakeLLMSummarizer,
) -> FakeLLMSummarizer:
    monkeypatch.setattr(
        "fundamentals_agent.fundamentals.summarize_reports_with_external_llm",
        fake_llm_summarizer,
    )
    return fake_llm_summarizer


@pytest.fixture
def patch_live_mx_data_client(
    monkeypatch: pytest.MonkeyPatch,
) -> RecordingMXDataClient:
    from fundamentals_agent.fundamentals import create_mx_data_client

    if not os.getenv("MX_APIKEY"):
        pytest.skip("未配置 MX_APIKEY，跳过真实东方财富妙想集成测试。")

    live_mx_data_client = RecordingMXDataClient(create_mx_data_client())
    monkeypatch.setattr(
        "fundamentals_agent.fundamentals.create_mx_data_client",
        lambda api_key=None: live_mx_data_client,
    )
    return live_mx_data_client
