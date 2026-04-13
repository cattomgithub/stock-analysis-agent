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

1. 用户输入包含沪深京市场个股代码或股票名称的请求
2. agent 从用户输入中提取沪深京市场个股代码或股票名称
3. agent 使用提取出的代码或名称调用东方财富妙想 mx-data skill，查询个股基本面相关数据
4. agent 将查询结果交给外部 LLM 整理为易于阅读的 Markdown 正文
5. agent 返回“个股基本面信息收集完成”的结果提示

## 用例

向 `graph` 传入包含沪深京个股代码或股票名称的请求，例如: 

```python
from fundamentals_agent.graph import graph

result = graph.invoke(
    {"messages": [{"role": "user", "content": "请分析贵州茅台的基本面"}]}
)

print(result["messages"][-1].content)
```

运行后会在 `STOCK_ANALYSIS_REPORT_DIR` 指定目录生成 markdown 文件，默认输出到项目根目录下的 `reports/`。该目录用于保存生成结果，默认不纳入版本控制。

东方财富妙想 skill 默认直接读取项目内子模块 `./eastmoney-mx-skills`；只有你想覆盖默认位置时，才需要额外设置 `EASTMONEY_MX_SKILLS_DIR` 或 `EASTMONEY_MX_DATA_PATH`。

当前实现会在 mx-data 查询完成后，调用外部 LLM 生成更易读的 Markdown 正文，同时保留原始查询明细作为附录，便于追溯数据来源与查询语句。

## 外部 LLM 配置

fundamentals agent 主流程现在依赖外部 LLM 整理 mx-data 查询结果。当前支持两类 provider：

- OpenAI 兼容接口
- 智谱 GLM 接口

主流程通过 [src/fundamentals_agent/report_formatting.py](src/fundamentals_agent/report_formatting.py) 读取 `FUNDAMENTALS_LLM_PROVIDER` 并调用 [src/fundamentals_agent/llm_clients.py](src/fundamentals_agent/llm_clients.py) 中的 Chat Completions 客户端。如果未配置 provider、API Key 或模型名，报告生成会直接失败并返回明确错误。

### 必填配置

请先在 `.env` 中补充所需 provider 的配置，`.env.example` 已增加对应示例：

```dotenv
FUNDAMENTALS_LLM_PROVIDER=openai

OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=30

ZHIPU_API_KEY=
ZHIPU_MODEL=
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZHIPU_TIMEOUT_SECONDS=30
```

- `FUNDAMENTALS_LLM_PROVIDER` 必须显式设置为 `openai` 或 `zhipu`
- `OPENAI_MODEL` 和 `ZHIPU_MODEL` 需要按你的账号可用模型手动填写
- 如果你有代理网关或企业网关，可以覆盖 `OPENAI_BASE_URL` 或 `ZHIPU_BASE_URL`
- 未填写当前 provider 对应的 `API_KEY` 和 `MODEL` 时，模块会直接抛出配置错误，避免发起不完整请求

### 主流程行为

- 代码输入会直接按沪深京市场规则识别并查询
- 股票名称输入会先用名称请求一次 mx-data，解析出标准证券代码后，再继续四组基本面查询
- 外部 LLM 只负责整理 mx-data 已返回的内容，不应额外编造公司信息
- 最终 markdown 文件包含两部分：外部 LLM 整理结果，以及原始查询明细附录

## 独立 LLM 客户端模块

仓库仍然保留独立模块 [src/fundamentals_agent/llm_clients.py](src/fundamentals_agent/llm_clients.py)，你也可以在主流程之外单独调用 OpenAI 或智谱接口。

### 使用示例

```python
from fundamentals_agent.llm_clients import create_openai_client, create_zhipu_client

openai_client = create_openai_client()
openai_result = openai_client.prompt(
    "请用三句话说明什么是自由现金流",
    system_prompt="你是一名严谨的中文投研助手。",
)
print(openai_result.content)

zhipu_client = create_zhipu_client()
zhipu_result = zhipu_client.chat(
    [
        {"role": "system", "content": "你是一名严谨的中文投研助手。"},
        {"role": "user", "content": "请解释市盈率的常见误区。"},
    ]
)
print(zhipu_result.content)
```

模块返回统一的 `LLMResponse` 对象，包含：

- `provider`：调用的 provider 名称
- `model`：实际返回的模型名称
- `content`：首个 assistant 回复文本
- `usage`：接口返回的 token 使用情况
- `raw_response`：完整原始 JSON，便于你在独立脚本里做二次处理

## 测试

- fundamentals agent 主链路的单元测试使用 fake mx-data client + fake LLM summarizer，验证“识别输入 -> 查询 mx-data -> 调用外部 LLM -> 写入 Markdown”的完整业务链路
- 集成测试会真实调用东方财富妙想 mx-data skill，但默认仍使用 fake LLM summarizer，避免把外部 LLM 网络波动引入回归测试
- 外部 LLM 客户端模块继续保留独立单元测试，验证配置读取、请求组装和响应解析
- 单元测试使用可记录查询语句的 fake mx-data client，并按股票代码动态生成测试数据，避免测试产物退化为固定硬编码文案
- 集成测试直接调用真实东方财富妙想 mx-data skill，验证用户真实输入能否触发实际查询并生成 Markdown 报告
- 测试产物统一输出到 `reports/test-artifacts/<sanitized-nodeid>/`，便于对生成的 Markdown 报告做回归检查
- 运行真实集成测试前需要配置 `MX_APIKEY`；未配置时集成测试会跳过并在 pytest 汇总中明确提示

推荐按下面四步执行测试流程：

1. 语法检查：确认 `src/` 和 `tests/` 下没有语法错误
2. 单元测试：验证代码提取、查询计划、工具封装和报告生成函数，确认查询语句与用户输入一致
3. 集成测试：用真实东方财富妙想 skill 验证 LangGraph 主链路可以完成端到端执行
4. Markdown 产物校验：检查 `reports/test-artifacts/` 下新生成报告的结构、查询语句和表格数据行数

如果你要验证新增的外部 LLM 模块，可以额外运行：

```bash
uv run python -m pytest tests/unit_tests/test_llm_clients.py -q
```

如果本地使用 `make`，可以直接运行完整测试流程：

```bash
uv sync --dev
make test-flow
```

等价的逐步命令如下：

```bash
uv sync --dev
uv run python -m compileall -q src tests
uv run python -m pytest tests/unit_tests -q
uv run python -m pytest tests/integration_tests -q
uv run python -m tests.verify_test_artifacts
```

`make test` 现在等价于 `make test-flow`。其中：

- 单元测试会断言程序确实按 `股票代码/名称识别 -> 四个基础查询 bundle -> 外部 LLM 整理` 组装完整链路，而不是只比对固定返回文案
- 集成测试会在本地有 `MX_APIKEY` 时真正调用东方财富妙想 mx-data skill
- 最后一步会验证测试期间实际生成的 Markdown 文件至少包含外部 LLM 整理结果、四条查询语句、结构化表格数据、股票标识、数据来源和四个基础章节，避免只测返回消息而漏掉最终产物质量

## Reference docs

- LangChain quickstart: https://docs.langchain.com/oss/python/langchain/quickstart
- LangChain deployment: https://docs.langchain.com/oss/python/langchain/deploy
