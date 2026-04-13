from __future__ import annotations

from pathlib import Path

from tests.report_checks import find_generated_markdown_reports, validate_markdown_report

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_ARTIFACTS_DIR = REPO_ROOT / "reports" / "test-artifacts"


def main() -> None:
    report_files = find_generated_markdown_reports(TEST_ARTIFACTS_DIR)
    if not report_files:
        raise AssertionError(f"未在 {TEST_ARTIFACTS_DIR} 下找到 markdown 测试产物")

    for report_path in report_files:
        validate_markdown_report(report_path)

    print(f"Validated {len(report_files)} markdown reports under {TEST_ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()