from __future__ import annotations

from pathlib import Path
import re

REQUIRED_REPORT_SNIPPETS = (
    "# 沪深京个股基本面报告",
    "- 数据来源：东方财富妙想 skills / mx-data",
    "- 数据范围：近五年年度财报",
    "- 外部 LLM：",
    "## 外部 LLM 整理结果",
    "## 原始查询明细",
    "### 盈利指标",
    "### 估值指标",
    "### 现金流量指标",
    "### 财务风险指标",
)
TABLE_SEPARATOR_PATTERN = re.compile(r":?-{3,}:?")


def find_generated_markdown_reports(root_dir: Path) -> list[Path]:
    return sorted(root_dir.rglob("fundamentals_*.md"))


def assert_single_markdown_report(report_dir: Path) -> Path:
    report_files = sorted(report_dir.glob("fundamentals_*.md"))
    if len(report_files) != 1:
        raise AssertionError(
            f"期望在 {report_dir} 下找到 1 个 markdown 报告，实际为 {len(report_files)} 个：{report_files}"
        )
    return report_files[0]


def count_markdown_table_data_rows(report_text: str) -> int:
    data_rows = 0
    inside_table_data = False
    for line in report_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            inside_table_data = False
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and all(TABLE_SEPARATOR_PATTERN.fullmatch(cell) for cell in cells):
            inside_table_data = True
            continue

        if inside_table_data:
            data_rows += 1
    return data_rows


def assert_report_contains_queries(report_text: str, expected_queries: list[str] | tuple[str, ...]) -> None:
    missing_queries = [query for query in expected_queries if f"查询语句：{query}" not in report_text]
    if missing_queries:
        raise AssertionError(f"报告缺少预期查询语句：{missing_queries}")


def validate_markdown_report(
    report_path: Path,
    *,
    expected_symbol: str | None = None,
    expected_name: str | None = None,
    min_query_statements: int = 4,
    min_table_data_rows: int = 1,
    forbidden_snippets: tuple[str, ...] = (),
) -> str:
    report_text = report_path.read_text(encoding="utf-8")

    for snippet in REQUIRED_REPORT_SNIPPETS:
        if snippet not in report_text:
            raise AssertionError(f"报告 {report_path} 缺少关键内容：{snippet}")

    if report_text.count("查询语句：") < min_query_statements:
        raise AssertionError(
            f"报告 {report_path} 查询语句数量不足：期望至少 {min_query_statements} 条"
        )

    if count_markdown_table_data_rows(report_text) < min_table_data_rows:
        raise AssertionError(
            f"报告 {report_path} 表格数据行数不足：期望至少 {min_table_data_rows} 行"
        )

    for snippet in forbidden_snippets:
        if snippet in report_text:
            raise AssertionError(f"报告 {report_path} 不应包含内容：{snippet}")

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
    min_query_statements: int = 4,
    min_table_data_rows: int = 1,
    forbidden_snippets: tuple[str, ...] = (),
) -> tuple[Path, str]:
    report_path = assert_single_markdown_report(report_dir)
    report_text = validate_markdown_report(
        report_path,
        expected_symbol=expected_symbol,
        expected_name=expected_name,
        min_query_statements=min_query_statements,
        min_table_data_rows=min_table_data_rows,
        forbidden_snippets=forbidden_snippets,
    )
    return report_path, report_text