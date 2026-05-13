ai_for_detect - AgentTorch 批量改写中文句子

用途
1. 读取 `自建ai数据集` 里的 xlsx 文件
2. 对每条 `文本` 调用 AgentTorch
3. 生成一条“原意不变、表达不同”的改写句子
4. 输出到 `outputs/*_ai生成.xlsx`

输入要求
- 默认文本列：`文本`
- 默认标签列：`领域标签`

运行前准备
本项目启动时会自动加载同目录下的 `.env`：
`projects/ai_for_detect/.env`

默认提供了本地 `.env` 模板，你只需要把里面的 key 改成自己的即可。

最小必填项
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `AI_FOR_DETECT_MODEL` 或 `OPENAI_MODEL` 或 `OPENAI_CHAT_MODEL`

示例运行：
py -3.14 -m projects.ai_for_detect.run_generate_ai_text --model gpt-4.1-mini --max-rows 20

处理全部文件：
py -3.14 -m projects.ai_for_detect.run_generate_ai_text

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
