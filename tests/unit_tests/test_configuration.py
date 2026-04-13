import json
import logging

from fundamentals_agent.fundamentals import (
    build_fundamental_report,
    detect_cn_stock_codes,
    extract_cn_stock_targets,
)
from fundamentals_agent.graph import graph

logger = logging.getLogger(__name__)


def test_graph_compiles() -> None:
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")


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


def test_build_fundamental_report_writes_markdown(
    patch_fake_mx_data_client,
    report_output_dir,
) -> None:
    report_path, targets, markdown_text = build_fundamental_report(
        "请分析 600519 的基本面",
        output_dir=str(report_output_dir),
    )
    logger.debug("Generated report path in unit test: %s", report_path)

    assert report_path.exists()
    assert [target.symbol for target in targets] == ["600519.SH"]
    assert "贵州茅台" in markdown_text
    assert "高端白酒龙头" in markdown_text
