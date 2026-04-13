"""Stock analysis agent package."""

from simple_agent.fundamentals import (
	build_fundamental_report,
	detect_cn_stock_codes,
	generate_cn_stock_fundamental_report,
)

__all__ = [
	"build_fundamental_report",
	"detect_cn_stock_codes",
	"generate_cn_stock_fundamental_report",
]
