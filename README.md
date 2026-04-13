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

## Quickstart

1. Sync the project with `uv`:

```bash
uv sync --dev
```

Upgrade dependencies and refresh the lockfile when needed:

```bash
uv sync --dev -U
```

2. Configure environment variables:

PowerShell:

```powershell
$env:MX_APIKEY="your_api_key_here"
$env:EASTMONEY_MX_SKILLS_DIR="../eastmoney-mx-skills"
$env:STOCK_ANALYSIS_REPORT_DIR="./reports"
$env:STOCK_ANALYSIS_LLM_PROVIDER="openai"
$env:OPENAI_API_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_API_KEY="your_openai_key"
$env:OPENAI_MODEL="gpt-4.1-mini"
# 使用智谱时改成 zhipu，并设置下面三项
# $env:STOCK_ANALYSIS_LLM_PROVIDER="zhipu"
# $env:ZHIPU_API_BASE_URL="https://open.bigmodel.cn/api/paas/v4/"
# $env:ZHIPU_API_KEY="your_zhipu_key"
# $env:ZHIPU_MODEL="glm-4.5-air"
```

Bash:

```bash
export MX_APIKEY=your_api_key_here
export EASTMONEY_MX_SKILLS_DIR=../eastmoney-mx-skills
export STOCK_ANALYSIS_REPORT_DIR=./reports
export STOCK_ANALYSIS_LLM_PROVIDER=openai
export OPENAI_API_BASE_URL=https://api.openai.com/v1
export OPENAI_API_KEY=your_openai_key
export OPENAI_MODEL=gpt-4.1-mini
# 使用智谱时改成 zhipu，并设置下面三项
# export STOCK_ANALYSIS_LLM_PROVIDER=zhipu
# export ZHIPU_API_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
# export ZHIPU_API_KEY=your_zhipu_key
# export ZHIPU_MODEL=glm-4.5-air
```

3. Run locally:

```bash
uv run langgraph dev
```

Optional `make` wrappers on systems with GNU Make:

```bash
make dev
make upgrade
make run
```

## Usage

向 graph 传入包含沪深京个股代码的用户请求，例如：

```python
from fundamentals_agent.graph import graph

result = graph.invoke(
    {"messages": [{"role": "user", "content": "请分析 600519 的基本面"}]}
)

print(result["messages"][-1].content)
```

运行后会在 `STOCK_ANALYSIS_REPORT_DIR` 指定目录生成 markdown 文件，默认输出到项目根目录下的 `reports/`。该目录用于保存生成结果，默认不纳入版本控制。

如果已配置 `STOCK_ANALYSIS_LLM_PROVIDER` 以及对应的 `API_BASE_URL`、`API_KEY`、`MODEL` 变量，agent 会在生成 Markdown 报告后调用 OpenAI 或智谱模型，给出一段中文总结；未配置时会退回到基础结果输出。

## Tests and lint

```bash
make unit-tests
make integration-tests
make llm-tests
make test
make lint
make format
```

### Windows

PowerShell 下推荐按下面顺序测试：

1. 仅跑本地单元测试和 mock 集成测试：

```powershell
uv sync --dev
uv run python -m pytest tests/unit_tests -q
uv run python -m pytest tests/integration_tests/test_graph.py -q
```

2. 跑真实 OpenAI 模型集成测试：

```powershell
$env:STOCK_ANALYSIS_LLM_PROVIDER="openai"
$env:OPENAI_API_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_API_KEY="your_openai_key"
$env:OPENAI_MODEL="gpt-4.1-mini"
uv run python -m pytest tests/integration_tests/test_live_llm.py -q -m external_llm
```

3. 跑真实智谱模型集成测试：

```powershell
$env:STOCK_ANALYSIS_LLM_PROVIDER="zhipu"
$env:ZHIPU_API_BASE_URL="https://open.bigmodel.cn/api/paas/v4/"
$env:ZHIPU_API_KEY="your_zhipu_key"
$env:ZHIPU_MODEL="glm-4.5-air"
uv run python -m pytest tests/integration_tests/test_live_llm.py -q -m external_llm
```

### macOS

在 zsh 或 bash 下可以直接执行：

1. 仅跑本地单元测试和 mock 集成测试：

```bash
uv sync --dev
uv run python -m pytest tests/unit_tests -q
uv run python -m pytest tests/integration_tests/test_graph.py -q
```

2. 跑真实 OpenAI 模型集成测试：

```bash
export STOCK_ANALYSIS_LLM_PROVIDER=openai
export OPENAI_API_BASE_URL=https://api.openai.com/v1
export OPENAI_API_KEY=your_openai_key
export OPENAI_MODEL=gpt-4.1-mini
uv run python -m pytest tests/integration_tests/test_live_llm.py -q -m external_llm
```

3. 跑真实智谱模型集成测试：

```bash
export STOCK_ANALYSIS_LLM_PROVIDER=zhipu
export ZHIPU_API_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
export ZHIPU_API_KEY=your_zhipu_key
export ZHIPU_MODEL=glm-4.5-air
uv run python -m pytest tests/integration_tests/test_live_llm.py -q -m external_llm
```

单元测试和默认集成测试不依赖外部 LLM 或东方财富真实接口；真实 LLM 集成测试只依赖你选择的 OpenAI 或智谱配置。若要接入真实东方财富妙想接口，再额外配置 `MX_APIKEY`。

## Reference docs

- LangChain quickstart: https://docs.langchain.com/oss/python/langchain/quickstart
- LangChain deployment: https://docs.langchain.com/oss/python/langchain/deploy
