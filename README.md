# 股票分析 Agent

## 分析对象

- 沪深京市场
    - [ ] 个股
    - [ ] ETF
        - [ ] 宽基 ETF
        - [ ] 行业 ETF
        - [ ] 策略 ETF
        - [ ] 海外 ETF
        - [ ] 商品 ETF
        - [ ] 债券 ETF
        - [ ] 货币 ETF
    - [ ] 可转债
- 港股
    - [ ] 个股
    - [ ] ETF
- 美股
    - [ ] 个股
    - [ ] ETF

## 分析指标

- 基本面
    - 盈利能力
        - 每股收益 (EPS)
        - 净利润增长率
        - 净资产收益率 (ROE)
    - 估值指标
        - 市盈率 (P/E)
        - 市净率 (P/B)
        - 市销率 (P/S)
    - 现金流
        - 自由现金流 (FCF)
        - 营业现金流量
    - 负债情况
        - 资产负债率
        - 流动比率
- 技术面
    - MA
    - MACD
    - RSI
    - KDJ
    - BOLL
    - 趋势线
    - 支撑/阻力线
    - 成交量
        - 量价背离
        - 放量突破
    - K线形态
        - 十字星
        - 大阳线
        - 头肩顶
        - 双底
- 消息面
    - 公司公告
    - 行业动态
    - 政策变动

## 路线图

- [ ] 基本面 Agent 最小实现: 沪深京个股基本面信息收集
- [ ] 技术面 Agent 最小实现
- [ ] 消息面 Agent 最小实现

## 当前运行逻辑

1. 用户输入包含沪深京市场个股代码的请求
2. agent 从用户输入中提取沪深京市场个股代码
3. agent 使用提取出的个股代码调用东方财富妙想 mx-data skill，查询个股基本面相关数据
4. agent 将查询结果整理并写入 Markdown 文件
5. agent 返回“个股基本面信息收集完成”的结果提示

## 用例

向 `graph` 传入包含沪深京个股代码的请求，例如: 

```python
from fundamentals_agent.graph import graph

result = graph.invoke(
    {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
)

print(result["messages"][-1].content)
```

运行后会在 `STOCK_ANALYSIS_REPORT_DIR` 指定目录生成 markdown 文件，默认输出到项目根目录下的 `reports/`。该目录用于保存生成结果，默认不纳入版本控制。

东方财富妙想 skill 默认直接读取项目内子模块 `./eastmoney-mx-skills`；只有你想覆盖默认位置时，才需要额外设置 `EASTMONEY_MX_SKILLS_DIR` 或 `EASTMONEY_MX_DATA_PATH`。

当前实现不依赖外部 LLM。主流程只围绕“识别个股代码 -> 调用东方财富妙想 skill -> 写入 Markdown -> 返回完成提示”执行，避免把总结类能力混入基本面信息收集链路。

## 测试

- 单元测试和集成测试均不依赖外部 LLM
- 默认测试通过 fake mx-data client 验证“识别代码 -> 查询 -> 写 Markdown -> 返回完成提示”的完整链路
- 若要接入东方财富妙想接口，需要额外配置 `MX_APIKEY`

1. 运行本地单元测试和 mock 集成测试:

```bash
uv sync --dev
uv run python -m pytest tests/unit_tests -q
uv run python -m pytest tests/integration_tests/test_graph.py -q
```

## Reference docs

- LangChain quickstart: https://docs.langchain.com/oss/python/langchain/quickstart
- LangChain deployment: https://docs.langchain.com/oss/python/langchain/deploy
