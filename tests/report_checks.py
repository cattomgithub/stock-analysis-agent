from __future__ import annotations

from pathlib import Path

REQUIRED_REPORT_SNIPPETS = (
    "# 沪深京个股基本面报告",
    "- 数据来源：东方财富妙想 skills / mx-data",
    "### 公司概况",
    "### 盈利与估值",
    "### 资产与现金流",
    "### 股东结构",
)


def find_generated_markdown_reports(root_dir: Path) -> list[Path]:
    return sorted(root_dir.rglob("fundamentals_*.md"))


def assert_single_markdown_report(report_dir: Path) -> Path:
    report_files = sorted(report_dir.glob("fundamentals_*.md"))
    if len(report_files) != 1:
        raise AssertionError(
            f"期望在 {report_dir} 下找到 1 个 markdown 报告，实际为 {len(report_files)} 个：{report_files}"
        )
    return report_files[0]


def validate_markdown_report(
    report_path: Path,
    *,
    expected_symbol: str | None = None,
    expected_name: str | None = None,
) -> str:
    report_text = report_path.read_text(encoding="utf-8")

    for snippet in REQUIRED_REPORT_SNIPPETS:
        if snippet not in report_text:
            raise AssertionError(f"报告 {report_path} 缺少关键内容：{snippet}")

    if expected_symbol is not None:
        expected_lines = (
            f"- 识别股票：{expected_symbol}",
            f"- 股票代码：{expected_symbol}",
        )
        for line in expected_lines:
            if line not in report_text:
                raise AssertionError(f"报告 {report_path} 缺少股票标识：{line}")

    if expected_name is not None and expected_name not in report_text:
        raise AssertionError(f"报告 {report_path} 缺少公司名称：{expected_name}")

    return report_text


def assert_generated_markdown_report(
    report_dir: Path,
    *,
    expected_symbol: str | None = None,
    expected_name: str | None = None,
) -> tuple[Path, str]:
    report_path = assert_single_markdown_report(report_dir)
    report_text = validate_markdown_report(
        report_path,
        expected_symbol=expected_symbol,
        expected_name=expected_name,
    )
    return report_path, report_text