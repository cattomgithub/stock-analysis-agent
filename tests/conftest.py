from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


class FakeMXData:
    def query(self, tool_query: str) -> dict[str, Any]:
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
    def parse_result(
        result: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str], int, str | None]:
        query = result["query"]
        if "公司概况" in query or "公司简介" in query:
            rows = [
                {"字段": "公司简介", "数值": "高端白酒龙头"},
                {"字段": "总股本", "数值": "12.56 亿股"},
            ]
            return (
                [
                    {
                        "sheet_name": "公司概况",
                        "fieldnames": ["字段", "数值"],
                        "rows": rows,
                    }
                ],
                ["[贵州茅台] 公司概况"],
                len(rows),
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
        rows = [
            {"date": "2024", "每股收益": "59.49", "净资产收益率": "34.74%"},
            {"date": "2023", "每股收益": "56.28", "净资产收益率": "33.90%"},
        ]
        return (
            [
                {
                    "sheet_name": "核心指标",
                    "fieldnames": ["date", "每股收益", "净资产收益率"],
                    "rows": rows,
                }
            ],
            [],
            len(rows),
            None,
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
