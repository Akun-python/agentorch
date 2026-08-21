from __future__ import annotations

SYSTEM_PROMPT = """你是中文文本改写助手。

你的唯一任务，是把用户提供的中文文本改写成另一条语义等价、表达自然的新句子。
必须严格遵守：
1. 保持原意、事实、情绪倾向、立场不变。
2. 保留关键术语、专有名词、数字与业务领域信息。
3. 只输出结果本身，不要解释，不要分析，不要加标题。
4. 输出必须是单条中文句子，不要分点，不要 Markdown，不要代码块。
5. 不要编造原文没有的新信息。"""


def build_rewrite_prompt(*, source_text: str, domain_label: str | None) -> str:
    cleaned_text = (source_text or "").strip()
    if not cleaned_text:
        raise ValueError("原始文本不能为空。")
    cleaned_domain = (domain_label or "").strip() or "未标注"
    return f"""请把下面的中文文本改写成一句新的中文表述。

约束：
1. 保持核心语义、事实、情绪倾向与结论不变。
2. 保留领域相关术语和关键词，不要新增事实。
3. 在不改变原意的前提下，可以调整措辞、语序和句式。
4. 表达自然、通顺、完整，不要明显拉长。
5. 最终只返回一条中文句子。
6. 不要返回 JSON、代码块、XML 标签、工具调用标记或额外说明。

领域标签：{cleaned_domain}
原始文本：{cleaned_text}"""
