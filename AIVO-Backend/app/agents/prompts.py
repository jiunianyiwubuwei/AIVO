"""Agent Prompt 配置"""

# 系统提示词模板
SYSTEM_PROMPTS = {
    "interviewer": """你是一个专业的面试官，擅长技术面试。请根据用户的表现给予客观评价。

面试原则：
1. 保持专业、友好的态度
2. 问题循序渐进，从基础到深入
3. 评价客观具体，给出改进建议
4. 鼓励候选人发挥真实水平""",

    "interviewer_resume": """你是一个专业的技术面试官，同时擅长简历分析和评估。

面试原则：
1. 仔细阅读简历内容，了解候选人背景
2. 问题要与简历中的经历和技术栈相关
3. 评价客观具体，给出可行的改进建议
4. 鼓励候选人发挥真实水平""",

    "general": """你是一个智能助手，可以回答各种问题。请保持回答简洁、准确、有帮助。""",
}

# 问题生成 Prompt 模板
QUESTION_GENERATION_PROMPT = """你是一个专业的技术面试官，同时擅长简历分析和评估。

面试方向: {direction}

{filled_resume_content}

{filled_resume_scoring}

请生成 {count} 道与"{direction}"相关的面试问题，每道问题需要包含:
- id: 唯一标识
- number: 问题编号 (如 "1", "2")
- content: 问题内容
- category: 问题分类 (如 "基础知识", "项目经验", "算法")
- difficulty: 难度等级 1-5
- expected_duration: 期望回答时长(秒)

请以JSON格式返回，返回结构如下:
{{
    "questions": [...],
    "resumeScore": 简历评分(0-100的整数，基于5个维度的综合评分),
    "resumeAnalysis": "简要说明简历的主要内容和质量评估",
    "resumeStrengths": ["简历优点1", "简历优点2"],
    "resumeWeaknesses": ["简历缺点1", "简历缺点2"],
    "type": "面试方向"
}}

{filled_scoring_principles}"""

# 简历评分说明
RESUME_SCORING_SECTION = """**简历评分标准 (0-100分)**:
1. **基本信息完整性** (0-20分): 姓名、联系方式、教育背景、工作经验等基本信息是否完整
2. **技术技能匹配度** (0-20分): 技术栈与面试方向"{direction}"的匹配程度
3. **项目经验质量** (0-20分): 项目描述是否具体、是否有技术难点和成果展示
4. **工作经历连贯性** (0-20分): 职业发展路径是否合理、跳槽是否频繁
5. **简历规范程度** (0-20分): 格式规范、无错别字、表达清晰"""

# 简历内容填充
RESUME_CONTENT_TEMPLATE = """**候选人简历内容:**
```
{resume_content}
```

请仔细阅读以上简历内容（如果内容看起来像乱码或不可读，请标注）。"""

# 简历评分原则
RESUME_SCORING_PRINCIPLES = """**重要评分原则**:
- 除非简历内容明显不完整或与职位完全不匹配，否则评分应在 50-85 分之间
- 即使简历有小的格式问题，也不应该给低于 40 分
- 只有简历内容非常匮乏、存在严重问题时才能给低于 40 分
- 尽量给出中等偏上的分数，鼓励候选人
- 必须仔细阅读并分析简历内容后才能评分
- 不要因为简历看起来简单就给低分，新人也应该得到合理的分数"""

# 回答评估 Prompt
ANSWER_EVALUATION_PROMPT = """请评估以下面试回答。

问题: {question}

回答: {answer}

追问次数: {follow_up_count}

请评估以下方面:
1. 回答的准确性 (0-20分)
2. 回答的完整性 (0-20分)
3. 技术深度 (0-20分)
4. 表达清晰度 (0-20分)
5. 项目经验相关性 (0-20分)

总分: (0-100分)

请判断是否需要追问（当分数低于60分或回答不够深入时需要追问）。

请以JSON格式返回评估结果:
{{
    "score": 总分,
    "accuracy": 准确性得分,
    "completeness": 完整性得分,
    "depth": 技术深度得分,
    "clarity": 表达清晰度得分,
    "relevance": 项目经验相关性得分,
    "evaluation": "详细评价文字",
    "suggestions": "改进建议",
    "follow_up_needed": 是否需要追问 (当分数低于60或回答不够详细时应为true),
    "follow_up_question": "如果需要追问，生成一个合适的追问问题"
}}"""

# 追问生成 Prompt
FOLLOW_UP_PROMPT = """基于之前的问答，生成一个合适的追问。

主问题: {question}

回答: {answer}

之前的追问:
{previous_text}

请根据以上内容，生成一个针对性的追问。追问应该:
1. 深入探讨回答中的关键点
2. 考察候选人的实际经验
3. 逐步深入，挖掘更深层次的理解

直接返回追问内容，不需要其他解释。"""

# 面试总结 Prompt
SUMMARY_PROMPT = """请根据以下面试问答内容，生成详细的面试总结和建议。

面试统计：
- 回答问题数: {main_count} 道
- 总得分: {total_score} 分
- 平均得分: {avg_score:.1f} 分

问答内容：
{qa_text}

请生成包含以下内容的面试总结（请用中文回复）:

## 整体评价
（对候选人的整体表现给出评价）

## 亮点总结
（列出候选人表现优秀的 2-3 个方面，每点一句话）

## 待改进点
（列出需要改进的 2-3 个方面，每点一句话）

## 下一步建议
（针对待改进点，给出具体可行的 2-3 条建议）

请确保建议具体、可操作，紧密结合候选人的实际回答内容。"""

# 通用聊天 Prompt
CHAT_PROMPT = """请回答用户的问题。如果有上下文，请结合上下文回答。

{history_context}

用户: {user_message}

请用中文回答。"""


def get_resume_content_section(resume_content: str, direction: str) -> str:
    """获取简历内容部分"""
    if resume_content:
        return RESUME_CONTENT_TEMPLATE.format(resume_content=resume_content[:6000])
    return ""


def get_resume_scoring_section(direction: str, has_resume: bool) -> str:
    """获取简历评分部分"""
    if has_resume:
        return RESUME_SCORING_SECTION.format(direction=direction)
    return ""


def get_scoring_principles_section(has_resume: bool) -> str:
    """获取评分原则部分"""
    if has_resume:
        return RESUME_SCORING_PRINCIPLES
    return ""


def build_question_generation_prompt(
    direction: str,
    resume_content: str = None,
    count: int = 5,
) -> str:
    """构建问题生成 Prompt"""
    has_resume = bool(resume_content)

    return QUESTION_GENERATION_PROMPT.format(
        direction=direction,
        filled_resume_content=get_resume_content_section(resume_content, direction),
        filled_resume_scoring=get_resume_scoring_section(direction, has_resume),
        count=count,
        filled_scoring_principles=get_scoring_principles_section(has_resume),
    )


def build_summary_prompt(
    qa_pairs: list,
    main_count: int,
    total_score: int,
    avg_score: float,
) -> str:
    """构建面试总结 Prompt"""
    qa_text = "\n\n".join([
        f"问题 {i+1}: {pair['question']}"
        f"\n回答: {pair['answer']}"
        f"\n得分: {pair['score']}分"
        f"\n评价: {pair['feedback']}"
        for i, pair in enumerate(qa_pairs) if not pair.get("is_follow_up")
    ])

    # 添加追问信息
    follow_ups = [p for p in qa_pairs if p.get("is_follow_up")]
    if follow_ups:
        qa_text += "\n\n--- 追问记录 ---"
        for i, pair in enumerate(follow_ups, 1):
            qa_text += f"\n追问 {i}: {pair['question']}\n回答: {pair['answer']}"

    return SUMMARY_PROMPT.format(
        main_count=main_count,
        total_score=total_score,
        avg_score=avg_score,
        qa_text=qa_text,
    )
