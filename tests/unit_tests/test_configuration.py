import json

from langgraph.pregel import Pregel

from simple_agent.fundamentals import (
    build_fundamental_report,
    detect_cn_stock_codes,
    extract_cn_stock_targets,
)
from simple_agent.graph import graph


def test_graph_compiles() -> None:
    assert isinstance(graph, Pregel)


def test_extract_cn_stock_targets_filters_non_stocks() -> None:
    targets = extract_cn_stock_targets("请分析 600519、000001、920047 和 159915")
    assert [target.symbol for target in targets] == [
        "600519.SH",
        "000001.SZ",
        "920047.BJ",
    ]


def test_detect_cn_stock_codes_tool() -> None:
    result = detect_cn_stock_codes.invoke({"text": "看看 600519 和 sz000001"})
    payload = json.loads(result)
    assert payload == {
        "contains_cn_stock_code": True,
        "codes": ["600519.SH", "000001.SZ"],
    }


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
        if "公司概况" in query or "公司简介" in query:
            rows = [{"字段": "公司简介", "数值": "高端白酒龙头"}]
        else:
            rows = [{"date": "2024", "指标": "示例值"}]
        return (
            [{"sheet_name": "示例", "fieldnames": list(rows[0].keys()), "rows": rows}],
            [],
            len(rows),
            None,
        )


def test_build_fundamental_report_writes_markdown(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "simple_agent.fundamentals.create_mx_data_client",
        lambda api_key=None: FakeMXData(),
    )

    report_path, targets, markdown_text = build_fundamental_report(
        "请分析 600519 的基本面",
        output_dir=str(tmp_path),
    )

    assert report_path.exists()
    assert [target.symbol for target in targets] == ["600519.SH"]
    assert "贵州茅台" in markdown_text
    assert "高端白酒龙头" in markdown_text
