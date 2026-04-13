import pytest

from simple_agent import fundamentals
from simple_agent.graph import graph

pytestmark = pytest.mark.anyio


class FakeMXData:
    def query(self, tool_query: str) -> dict:
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
    def parse_result(result: dict) -> tuple[list[dict], list[str], int, str | None]:
        query = result["query"]
        if "公司简介" in query:
            return (
                [
                    {
                        "sheet_name": "公司概况",
                        "fieldnames": ["字段", "数值"],
                        "rows": [
                            {"字段": "公司简介", "数值": "高端白酒龙头"},
                            {"字段": "总股本", "数值": "12.56 亿股"},
                        ],
                    }
                ],
                ["[贵州茅台] 公司概况"],
                2,
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
        return (
            [
                {
                    "sheet_name": "核心指标",
                    "fieldnames": ["date", "每股收益", "净资产收益率"],
                    "rows": [
                        {"date": "2024", "每股收益": "59.49", "净资产收益率": "34.74%"},
                        {"date": "2023", "每股收益": "56.28", "净资产收益率": "33.90%"},
                    ],
                }
            ],
            [],
            2,
            None,
        )


async def test_graph_generates_markdown_report(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("STOCK_ANALYSIS_REPORT_DIR", str(tmp_path))
    monkeypatch.setattr(fundamentals, "create_mx_data_client", lambda api_key=None: FakeMXData())

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
    )

    output_text = str(result["messages"][-1].content)
    assert "600519.SH" in output_text
    assert "Markdown 报告" in output_text
    assert list(tmp_path.glob("fundamentals_*.md"))
