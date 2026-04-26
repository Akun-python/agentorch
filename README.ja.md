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

`agentorch` は、コードファーストかつ非同期ファーストの Python マルチエージェント編成フレームワークです。

これは、プロンプトだけに依存したブラックボックスではなく、実運用で制御可能な境界を重視した設計です。

ツール呼び出し、RAG、メモリ、ワークフロー、委譲を同時に扱う場合でも、`agentorch` は明示的な実行モデルを提供します。

![agentorch Architecture Overview](resource/architecture_overview.svg)

## WHY

### なぜこのフレームワークか 🎯

「単一エージェント + 単一プロンプト」は初期には速いですが、実装が進むと次の課題が出ます：

- 役割が増え、責務境界が曖昧になる
- ツールが増え、安全制御が難しくなる
- コンテキストが長くなり、状態追跡が難しくなる
- 検索結果の根拠が検証しづらくなる

`agentorch` はこれらをソフトウェア構造として明示化します。

### エンジニアリング上の価値 🧭

- runtime 構成をエクスポートして確認可能
- ポリシーを設定・バージョン管理可能
- 単一エージェントから多エージェントへ段階移行可能
- 推論/RAG/ワークフロー戦略を安全に反復可能

### 研究用途での価値 🔬

- 推論モードを切替可能（`react`, `plan_execute` など）
- RAG とコンテキスト戦略を比較可能
- 進化探索による構成探索が可能
- 長期タスク状態を保持・再利用可能

### 代表的なユースケース

- コーディング支援（ファイル/コマンド/Git 制御）
- 根拠提示が必要な知識支援
- DAG ベースの自動化処理
- 長期間の対話・作業支援

## WHAT

### 主な API

- `create_agent(...)`
- `create_multi_agent(...)`

通常はこの2つの façade API から始めるのが推奨です。

### 主要ランタイム要素 🧩

- モデルアダプタ
- ツールレジストリとバンドル
- サンドボックス実行とポリシー
- ナレッジベースと RAG 戦略
- メモリ管理とガバナンス
- DAG ワークフロー実行
- 観測/イベント記録

### ここでの「編成」の意味

`agentorch` では、編成は具体的な実体として扱われます：

- Commander がルーティングと委譲を担当
- Task packet は型付きで追跡可能
- Handoff は明示的な記録として残る
- 共有メモリはポリシーで制御
- ツール公開範囲は制限可能

### 互換性

- Python `3.10+`
- 依存はコア最小構成
- 高レベル API は安定利用向け
- 互換エクスポートで既存統合を支援

## HOW

### インストール 📦

ローカル editable install:

```bash
pip install -e .
```

GitHub から直接 install:

```bash
pip install "git+https://github.com/Akun-python/agentorch.git"
```

オプション依存の例:

```bash
pip install -e ".[neo4j]"
```

### 環境変数

```env
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`.env` は明示的に読み込む運用を推奨します。

### 導入順序の推奨

1. まず単一エージェントを安定化
2. 次に最小権限でツール追加
3. 次に RAG を追加し根拠品質を検証
4. 最後に多エージェント委譲を導入

### 検証コマンド

```powershell
py -3.10 -m pytest -q
```

```powershell
py -3.10 -m pytest -q agentorch/tests/test_readme_contracts.py
```

### 実運用ガードレール ✅

- ツール許可リストは最小化
- thread_id を明示して追跡性を確保
- 長い処理は段階化
- 実行後は agent/runtime を明示的に close

## QUICKSTART

### 1) 最小サンプル

```python
from agentorch import create_agent

agent = create_agent(
    model="gpt-4.1-mini",
    system_prompt="簡潔で正確なアシスタントとして振る舞ってください。",
    reasoning="react",
)

result = agent.run_sync(
    "エージェント編成とは何かを3つの要点で説明してください。",
    thread_id="quickstart-ja-001",
)

print(result.output_text)
agent.close()
```

### 2) ツール呼び出しサンプル

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

result = agent.run_sync("add_numbers で 12 + 30 を計算してください。", thread_id="quickstart-tools-ja-001")
print(result.output_text)
agent.close()
```

### 3) マルチエージェント開始例

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
    system_prompt="専門エージェントを協調し、最終回答を返してください。",
)

result = team.run_sync("移行計画を作成しレビューしてください。", thread_id="quickstart-team-ja-001")
print(result.output_text)
team.close()
```

### 4) 次のステップ

- `knowledge_paths` と `enable_rag=True` を追加
- 順序制御が必要なら workflow DAG を導入
- observability で品質/コストを分析
- ポリシーをコード化して運用を安定化

MIT License.
