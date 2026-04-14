"""Canonical fundamentals metric schema shared across collection and formatting."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Any

FREE_CASH_FLOW_FORMULA = (
    "净利润+固定资产和投资性房地产折旧+使用权资产折旧+无形资产摊销+长期待摊费用摊销-投资活动现金流出"
)


@dataclass(frozen=True, slots=True)
class FundamentalMetric:
    label: str
    query_label: str | None = None
    aliases: tuple[str, ...] = ()
    description: str | None = None
    include_in_queries: bool = True
    include_in_schema: bool = True

    @property
    def query_term(self) -> str:
        return self.query_label or self.label

    def known_labels(self) -> tuple[str, ...]:
        labels: list[str] = []
        for candidate in (self.label, self.query_term, *self.aliases):
            normalized = candidate.strip()
            if normalized and normalized not in labels:
                labels.append(normalized)
        return tuple(labels)


@dataclass(frozen=True, slots=True)
class FundamentalMetricGroup:
    title: str
    metrics: tuple[FundamentalMetric, ...]
    history_scope: str | None = "近五年 年报"

    def query_terms(self) -> tuple[str, ...]:
        terms = [metric.query_term for metric in self.metrics if metric.include_in_queries]
        if self.history_scope:
            terms.append(self.history_scope)
        return tuple(terms)

    def report_metrics(self) -> tuple[FundamentalMetric, ...]:
        return tuple(metric for metric in self.metrics if metric.include_in_schema)

    def report_metric_labels(self) -> tuple[str, ...]:
        return tuple(metric.label for metric in self.report_metrics())


FUNDAMENTAL_METRIC_GROUPS: tuple[FundamentalMetricGroup, ...] = (
    FundamentalMetricGroup(
        title="盈利指标",
        metrics=(
            FundamentalMetric("每股收益", aliases=("EPS",)),
            FundamentalMetric("净资产收益率", aliases=("ROE",)),
        ),
    ),
    FundamentalMetricGroup(
        title="估值指标",
        metrics=(
            FundamentalMetric("市盈率", aliases=("PE", "P/E")),
            FundamentalMetric("市净率", aliases=("PB", "P/B")),
        ),
    ),
    FundamentalMetricGroup(
        title="现金流量指标",
        metrics=(
            FundamentalMetric(
                "自由现金流量",
                aliases=("FCF", "自由现金流"),
                description=f"按公式计算：{FREE_CASH_FLOW_FORMULA}",
                include_in_queries=False,
            ),
            FundamentalMetric(
                "营业现金流量",
                query_label="经营活动产生的现金流量净额",
                aliases=(
                    "经营活动现金流净额",
                    "经营活动现金流量净额",
                    "经营现金流净额",
                ),
            ),
            FundamentalMetric(
                "净利润",
                aliases=(
                    "归属于上市公司股东的净利润",
                    "归属于母公司所有者的净利润",
                    "归母净利润",
                ),
                include_in_schema=False,
            ),
            FundamentalMetric(
                "固定资产和投资性房地产折旧",
                include_in_schema=False,
            ),
            FundamentalMetric(
                "使用权资产折旧",
                include_in_schema=False,
            ),
            FundamentalMetric(
                "无形资产摊销",
                include_in_schema=False,
            ),
            FundamentalMetric(
                "长期待摊费用摊销",
                include_in_schema=False,
            ),
            FundamentalMetric(
                "投资活动现金流出",
                query_label="投资活动现金流出小计",
                aliases=("投资活动现金流出小计", "投资活动现金流量流出小计"),
                include_in_schema=False,
            ),
        ),
    ),
    FundamentalMetricGroup(
        title="财务风险指标",
        metrics=(
            FundamentalMetric("流动比率"),
            FundamentalMetric("资产负债率"),
        ),
    ),
)

REPORT_QUERY_BUNDLES: tuple[tuple[str, str], ...] = tuple(
    (group.title, " ".join(group.query_terms()))
    for group in FUNDAMENTAL_METRIC_GROUPS
)

_METRIC_KEY_FIELD_NAMES = frozenset({"字段", "指标", "项目", "科目", "名称"})
_METADATA_FIELD_NAMES = frozenset(
    {
        "date",
        "year",
        "period",
        "quarter",
        "日期",
        "年份",
        "报告期",
        "截至日期",
        "统计期",
        "时间",
        "季度",
    }
)


def _normalize_label(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return text.lower()


def _unique_preserving_order(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


@lru_cache(maxsize=1)
def _metric_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for group in FUNDAMENTAL_METRIC_GROUPS:
        for metric in group.metrics:
            for label in metric.known_labels():
                alias_map[_normalize_label(label)] = metric.label
    return alias_map


@lru_cache(maxsize=1)
def _metric_group_map() -> dict[str, FundamentalMetricGroup]:
    return {group.title: group for group in FUNDAMENTAL_METRIC_GROUPS}


def canonicalize_metric_label(label: Any) -> str | None:
    normalized = _normalize_label(label)
    if not normalized:
        return None
    return _metric_alias_map().get(normalized)


def get_metric_group(title: str) -> FundamentalMetricGroup | None:
    return _metric_group_map().get(title)


def is_metadata_field(fieldname: str) -> bool:
    return _is_metadata_field(fieldname)


def _is_metric_key_field(fieldname: str) -> bool:
    return fieldname.strip() in _METRIC_KEY_FIELD_NAMES


def _is_metadata_field(fieldname: str) -> bool:
    return _normalize_label(fieldname) in _METADATA_FIELD_NAMES


def _normalize_fieldnames(table: dict[str, Any]) -> list[str]:
    fieldnames = [str(name).strip() for name in list(table.get("fieldnames") or [])]
    if fieldnames:
        return [name for name in fieldnames if name]

    rows = [row for row in list(table.get("rows") or []) if isinstance(row, dict)]
    if not rows:
        return []
    return [str(name).strip() for name in rows[0].keys() if str(name).strip()]


def _filter_key_value_table(
    title: str,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    metric_key_field = next((name for name in fieldnames if _is_metric_key_field(name)), None)
    if metric_key_field is None:
        return None

    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        canonical_label = canonicalize_metric_label(row.get(metric_key_field, ""))
        if canonical_label is None:
            continue
        normalized_row = {fieldname: row.get(fieldname, "") for fieldname in fieldnames}
        normalized_row[metric_key_field] = canonical_label
        filtered_rows.append(normalized_row)

    if not filtered_rows:
        return None
    return {
        "sheet_name": title,
        "fieldnames": fieldnames,
        "rows": filtered_rows,
    }


def _filter_columnar_table(
    title: str,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    selected_fields: list[tuple[str, str]] = []
    contains_metric_field = False
    for fieldname in fieldnames:
        canonical_label = canonicalize_metric_label(fieldname)
        if canonical_label is not None:
            selected_fields.append((fieldname, canonical_label))
            contains_metric_field = True
            continue
        if _is_metadata_field(fieldname):
            selected_fields.append((fieldname, fieldname))

    if not contains_metric_field:
        return None

    output_fieldnames = _unique_preserving_order(
        [output_name for _source_name, output_name in selected_fields]
    )
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized_row: dict[str, Any] = {}
        for source_name, output_name in selected_fields:
            normalized_row[output_name] = row.get(source_name, "")
        filtered_rows.append(normalized_row)

    return {
        "sheet_name": title,
        "fieldnames": output_fieldnames,
        "rows": filtered_rows,
    }


def filter_section_tables(title: str, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered_tables: list[dict[str, Any]] = []
    for table in tables:
        fieldnames = _normalize_fieldnames(table)
        rows = [row for row in list(table.get("rows") or []) if isinstance(row, dict)]
        if not fieldnames or not rows:
            continue

        filtered_table = _filter_key_value_table(title, fieldnames, rows)
        if filtered_table is None:
            filtered_table = _filter_columnar_table(title, fieldnames, rows)
        if filtered_table is not None:
            filtered_tables.append(filtered_table)
    return filtered_tables


def serialize_metric_schema() -> list[dict[str, Any]]:
    return [
        {
            "title": group.title,
            "metrics": [
                {
                    "label": metric.label,
                    "query_term": metric.query_term,
                    "aliases": [
                        alias
                        for alias in metric.known_labels()
                        if alias not in {metric.label, metric.query_term}
                    ],
                    "description": metric.description,
                }
                for metric in group.report_metrics()
            ],
            "history_scope": group.history_scope,
        }
        for group in FUNDAMENTAL_METRIC_GROUPS
    ]


__all__ = [
    "FREE_CASH_FLOW_FORMULA",
    "FUNDAMENTAL_METRIC_GROUPS",
    "REPORT_QUERY_BUNDLES",
    "FundamentalMetric",
    "FundamentalMetricGroup",
    "canonicalize_metric_label",
    "filter_section_tables",
    "get_metric_group",
    "is_metadata_field",
    "serialize_metric_schema",
]