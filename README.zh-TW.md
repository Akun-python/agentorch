<h1 align="center">agentorch</h1>

<p align="center">
  <img src="resource/agentorch-icon.svg" alt="agentorch icon" width="110">
</p>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh-CN.md">zh-CN</a> |
  <a href="README.zh-TW.md">zh-TW</a> |
  <a href="README.fr.md">fr</a> |
  <a href="README.ja.md">ja</a> |
  <a href="README.ko.md">ko</a> |
  <a href="README.es.md">es</a>
</p>

<p align="center">
  <img alt="version v0.1.0" src="https://img.shields.io/badge/version-v0.1.0-2563eb?style=flat-square">
  <img alt="python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="downloads" src="https://img.shields.io/github/downloads/Akun-python/agentorch/total?style=flat-square">
  <img alt="license MIT" src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square">
</p>

`agentorch` 是一個程式碼優先、非同步優先的 Python 多智能體編排框架。

它面向需要明確工程邊界的系統，而不是只靠提示詞堆疊的黑盒流程。

當你的場景需要工具調用、檢索證據、記憶治理、工作流與多角色協作同時運作時，`agentorch` 提供可控且可檢查的執行模型。

![agentorch Architecture Overview](resource/architecture_overview.svg)

## WHY

### 為什麼需要這個框架 🎯

專案在「單助手 + 單提示詞」階段通常很快，但進入工程化後常見問題是：

- 角色變多後邊界模糊
- 工具能力變強後風險失控
- 上下文變長後狀態難追蹤
- 檢索變複雜後證據難復核

`agentorch` 把這些問題從隱式 prompt 技巧轉成顯式軟體結構。

### 對工程團隊的價值 🧭

- 執行裝配可導出、可觀察
- 策略可配置、可版本化
- 可從單智能體平滑擴展到多智能體
- 可持續迭代推理與檢索策略

### 對研究團隊的價值 🔬

- 推理策略可切換（如 `react`、`plan_execute`）
- RAG 與上下文策略可比較
- 支援進化搜尋與實驗
- 長任務狀態可保留與復用

### 常見使用場景

- 代碼助手：需要檔案/命令/Git 協作
- 知識助手：需要可追溯證據輸出
- 自動化流程：需要節點級 DAG 控制
- 長週期任務：需要跨回合記憶治理

## WHAT

### 核心入口 API

- `create_agent(...)`
- `create_multi_agent(...)`

建議先使用高階 facade API，再按需要下沉到底層組件。

### 關鍵能力模組 🧩

- 模型適配層（OpenAI 與相容接口）
- 工具註冊與工具包
- 沙箱執行與權限策略
- 知識庫與 RAG 策略
- 記憶管理與治理
- 工作流 DAG 編排與執行
- 可觀測性事件與追蹤

### 這裡的「編排」具體是什麼

在 `agentorch` 中，編排是可實作、可檢查的具體機制：

- 總指揮負責路由與委派
- 任務包是顯式執行單元
- 交接是結構化記錄
- 共享狀態受策略約束
- 工具可見面與權限可控

### 相容性與穩定性

- Python `3.10+`
- 核心依賴維持精簡
- 高層 API 面向穩定使用
- 相容導出可支援舊代碼遷移

## HOW

### 安裝 📦

本地可編輯安裝：

```bash
pip install -e .
```

直接由 GitHub 安裝：

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

可選依賴範例：

```bash
pip install -e ".[neo4j]"
```

### 環境變數配置

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

建議明確控制 `.env` 載入時機，不要隱式注入。

### 推薦落地順序

1. 先用單智能體跑通核心任務。
2. 再加工具，先收斂權限面。
3. 再加 RAG，先驗證證據品質。
4. 最後引入多智能體委派。

### 驗證命令

```powershell
py -3.10 -m pytest -q
```

```powershell
py -3.10 -m pytest -q agentorch/tests/test_readme_contracts.py
```

### 工程守則 ✅

- 工具白名單保持最小化
- 執行 thread_id 顯式化
- 長任務拆成可檢查步驟
- 任務完成後關閉 agent/runtime

## QUICKSTART

### 1) 最小可運行示例

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="你是簡潔且準確的助手。",
    reasoning="react",
)

result = agent.run_sync(
    "請用三個要點說明什麼是智能體編排。",
    thread_id="quickstart-zh-tw-001",
)

print(result.output_text)
agent.close()
```

### 2) 工具調用示例

```python
from pydantic import BaseModel

from agentorch import ToolRegistry, create_agent, tool

class AddInput(BaseModel):
    a: int
    b: int

@tool(description="Add two integers.")
async def add_numbers(input: AddInput):
    return {"sum": input.a + input.b}

agent = create_agent(
    model="gpt-4.1-mini",
    tools=ToolRegistry.from_tools(add_numbers),
    reasoning="react",
)

result = agent.run_sync("請呼叫 add_numbers 計算 12 + 30。", thread_id="quickstart-tools-zh-tw-001")
print(result.output_text)
agent.close()
```

### 3) 多智能體起步示例

```python
from agentorch import create_agent, create_multi_agent

planner = create_agent(model="gpt-4.1-mini", reasoning="plan_execute", name="planner")
reviewer = create_agent(model="gpt-4.1-mini", reasoning="react", name="reviewer")

team = create_multi_agent(
    model="gpt-4.1-mini",
    agents=[
        {"agent": planner, "name": "planner", "role": "planner"},
        {"agent": reviewer, "name": "reviewer", "role": "reviewer"},
    ],
    system_prompt="協調專家並輸出一個最終答案。",
)

result = team.run_sync("先規劃再評審一個遷移方案。", thread_id="quickstart-team-zh-tw-001")
print(result.output_text)
team.close()
```

### 4) 下一步建議

- 加入 `knowledge_paths` 與 `enable_rag=True`
- 引入 workflow DAG 固化步驟順序
- 開啟 observability 做成本與品質分析
- 用策略物件固定團隊邊界

MIT License.
