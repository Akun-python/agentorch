ai_for_detect - AgentTorch 批量生成 AI 风格句子

用途
1. 读取 `自建ai数据集` 里的 xlsx 文件
2. 对每条 `文本` 调用 AgentTorch
3. 生成一条“原意不变，但更像 AI 写作”的中文句子
4. 输出到 `outputs/*_ai生成.xlsx`

输入要求
- 默认文本列：`文本`
- 默认标签列：`领域标签`

运行前准备
本项目不会主动读取 `.env`。
请先在当前 PowerShell 会话里注入接口环境变量，再执行脚本。

示例：
$env:OPENAI_API_KEY="你的key"
$env:OPENAI_BASE_URL="你的base_url"
py -3.14 -m projects.ai_for_detect.run_generate_ai_text --model gpt-4.1-mini --max-rows 20

处理全部文件：
py -3.14 -m projects.ai_for_detect.run_generate_ai_text --model gpt-4.1-mini

处理单个文件：
py -3.14 -m projects.ai_for_detect.run_generate_ai_text `
  --input-path "projects/ai_for_detect/自建ai数据集/银行.xlsx" `
  --model gpt-4.1-mini

常用参数
- `--max-rows 20`：先抽样验证
- `--flush-every 10`：每 10 条落盘一次，便于中断续跑
- `--overwrite`：忽略旧输出重新生成
- `--min-request-interval 0.5`：给接口限速

输出列
- `AI生成文本`
- `AI生成模型`
- `生成线程ID`
- `生成状态`
