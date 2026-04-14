from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Any

import pytest

from external_llm import LLMResponse

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

    @staticmethod
    def _annual_years() -> tuple[str, ...]:
        return ("2024", "2023", "2022", "2021", "2020")

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

        years = self._annual_years()

        if "每股收益" in query or "净资产收益率" in query:
            rows = [
                {
                    "date": year,
                    "每股收益": f"{5 + seed / 10 - index * 0.2:.2f}",
                    "净资产收益率": f"{15 + seed % 7 - index}.4%",
                }
                for index, year in enumerate(years)
            ]
            rows.insert(
                1,
                {
                    "date": "2024-09-30",
                    "每股收益": f"{4.8 + seed / 10:.2f}",
                    "净资产收益率": f"{14 + seed % 7}.1%",
                },
            )
            return (
                [
                    {
                        "sheet_name": "盈利指标",
                        "fieldnames": ["date", "每股收益", "净资产收益率"],
                        "rows": rows,
                    }
                ],
                [f"[{company_name}] 盈利指标", f"symbol={symbol}"],
                len(rows),
                None,
            )
        if "市盈率" in query or "市净率" in query:
            rows = [
                {
                    "date": year,
                    "市盈率": f"{12 + seed % 8 - index * 0.5:.1f}",
                    "市净率": f"{2 + seed % 5 - index * 0.1:.1f}",
                }
                for index, year in enumerate(years)
            ]
            return (
                [
                    {
                        "sheet_name": "估值指标",
                        "fieldnames": ["date", "市盈率", "市净率"],
                        "rows": rows,
                    }
                ],
                [f"[{company_name}] 估值指标"],
                len(rows),
                None,
            )
        if "经营活动产生的现金流量净额" in query or "投资活动现金流出小计" in query:
            rows = [
                {
                    "date": year,
                    "净利润": f"{100 + seed - index}亿",
                    "固定资产和投资性房地产折旧": f"{8 + index}亿",
                    "使用权资产折旧": "3亿",
                    "无形资产摊销": "2亿",
                    "长期待摊费用摊销": "1亿",
                    "投资活动现金流出小计": f"{60 + index}亿",
                    "经营活动产生的现金流量净额": f"{120 + seed - index}亿",
                }
                for index, year in enumerate(years)
            ]
            return (
                [
                    {
                        "sheet_name": "现金流量指标",
                        "fieldnames": [
                            "date",
                            "净利润",
                            "固定资产和投资性房地产折旧",
                            "使用权资产折旧",
                            "无形资产摊销",
                            "长期待摊费用摊销",
                            "投资活动现金流出小计",
                            "经营活动产生的现金流量净额",
                        ],
                        "rows": rows,
                    }
                ],
                [f"[{company_name}] 现金流量指标"],
                len(rows),
                None,
            )

        rows = [
            {
                "date": year,
                "流动比率": f"{1 + seed % 3 - index * 0.1:.1f}",
                "资产负债率": f"{20 + seed % 15 - index}.10%",
            }
            for index, year in enumerate(years)
        ]
        return (
            [
                {
                    "sheet_name": "财务风险指标",
                    "fieldnames": ["date", "流动比率", "资产负债率"],
                    "rows": rows,
                }
            ],
            [f"[{company_name}] 财务风险指标"],
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
