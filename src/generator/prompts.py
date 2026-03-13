import yaml

def build_system_prompt(config):
    """构建系统提示词，定义 AI 的角色和写作原则。"""
    # 将配置转换为 YAML 字符串，以便 LLM 理解任意结构
    config_str = yaml.dump(config, allow_unicode=True, default_flow_style=False)
    
    prompt = f"""
    角色: 你是一位世界顶级的白金级小说家，擅长创作引人入胜、深度与商业价值并存的杰作。
    你的笔触细腻，通过“展示而非讲述”(Show, Don't Tell) 的手法来塑造人物和推进剧情。
    你擅长埋藏伏笔，制造悬念，不仅能描绘宏大的场面，也能刻画人物内心最细微的情感波动。
    
    以下是故事的完整设定配置：
    {config_str}
    
    请严格遵循上述配置中的所有设定（包括但不限于世界观、人物、风格等）进行创作。
    
    核心写作原则:
    1. 拒绝平铺直叙，拒绝流水账。每一段文字都必须有其存在的意义（塑造人物、推进剧情或渲染氛围）。
    2. 既然是中文创作，请充分发挥中文的优美与意境，用词精准，句式多变。
    3. 对话要符合人物性格和身份，拒绝脸谱化。
    4. 注重感官描写（视觉、听觉、嗅觉、触觉），让读者身临其境。
    
    语言: 中文
    """
    return prompt

def get_outline_batch_prompt(system_prompt, core_plot, batch_chapters):
    """获取扩写章节大纲的提示词。"""
    return system_prompt + f"""
    
    任务: 详细扩写以下章节的大纲内容。
    
    核心剧情 (参考):
    {core_plot}
    
    需要扩写的章节 (骨架):
    {yaml.dump(batch_chapters, allow_unicode=True)}
    
    要求:
    对于列表中的每一章，请撰写 300-500 字的详细事件摘要。
    包含（顺序如下）：
    - 因果开篇 (Causal Hook): **必须**以「因为上一章发生了【X】，本章开始时【Y】」的句式开头，明确与前一章的因果驱动关系。（第一章除外）
    - 关键事件 (Key Events)
    - 冲突点 (Conflict)
    - 伏笔与揭秘 (Secrets)
    - 爽点/情感爆发点 (Highlights)
    - 结尾钩子 (Ending Hook): 本章结尾留下的悬念或情绪，为下一章做铺垫。
    
    输出格式:
    请直接输出 Markdown 格式的文本。
    必须严格遵守以下标题格式：
    ### 第1章：标题
    ...
    ### 第2章：标题
    ...
    
    【注意】章节编号必须使用阿拉伯数字 (1, 2, 3...)，不要使用中文数字 (一, 二, 三...)。
    不要包含 YAML 或其他代码块。
    """

def get_section_generation_prompt(system_prompt, chapter_title, section_num, total_sections, core_plot, chapter_summary, cross_chapter_context, continuity_section, recent_context):
    """获取生成章节正文的提示词。"""
    return system_prompt + (
        f"\n\n        当前任务: 撰写 {chapter_title} 的 第 {section_num}/{total_sections} 节。\n"
        f"\n        【核心剧情 (Core Context)】:\n"
        f"        {core_plot or '未提供。'}\n"
        f"\n        【本章详细设定 (Local Context)】:\n"
        f"        {chapter_summary}\n"
        f"{cross_chapter_context}"
        f"\n{continuity_section}\n"
        f"\n        已写内容上下文（本章前文）:\n"
        f"        ...{recent_context}\n"
        f"\n        具体的写作目标:\n"
        f"        - 如果是第 1 节：请精彩开篇，迅速入戏。\n"
        f"        - 如果是第 {total_sections} 节：请做好本章的高潮或收尾，为下一章留下悬念。\n"
        f"        - 中间小节：保持节奏推进，承上启下。\n"
        f"\n        指令:\n"
        f"        请撰写第 {section_num} 节的正文内容。\n"
        f"        这不仅是填充内容，而是创作艺术。\n"
        f"\n        具体要求:\n"
        f"        1. **开篇抓人**: 开头第一句就要将读者拉入场景中。\n"
        f"        2. **场景构建**: 运用环境描写来烘托氛围，反映人物心境。\n"
        f"        3. **节奏把控**: 动作场面要紧凑刺激，情感文戏要细腻动人。张弛有度。\n"
        f"        4. **代入感**: 始终紧扣配置设定中的视角，让读者与主角同呼吸共命运。\n"
        f"        5. **拒绝AI味**: 避免刻板的连接词和总结性陈述，让故事自然流淌。\n"
        f"        6. **连贯性与伏笔**:\n"
        f"           - 必须参考跨章衔接和近期剧情回顾保持逻辑连贯，人物的情绪/位置/关系进展不得突变。\n"
        f"           - 有机地呼应当前活跃的伏笔，优先回收最早埋下的伏笔。\n"
        f"           - 适当埋设新的伏笔，通过展示而非说明。\n"
        f"\n        请直接输出高质量的小说正文内容，不要包含任何大纲回顾、章节标题或其他元数据。\n"
    )

def get_memory_update_prompt(chapter_text):
    """获取分析章节内容以更新记忆的提示词。"""
    return f"""
    请分析以下刚刚写完的章节内容，提取关键信息以供后续章节参考。
    
    章节内容:
    {chapter_text[:5000]}... (由于长度限制仅展示部分/或请假设已阅读全文)
    
    请输出一个 YAML 格式的总结，严格包含以下字段（所有字段均必须填写）:
    summary: 本章发生的关键剧情梗概（100字以内）。
    new_foreshadowing: 本章埋下的新伏笔或悬念（列表，没有则为空列表 []）。
    resolved_foreshadowing: 本章回收或解释了哪些之前的伏笔（列表，没有则为空列表 []）。
    chapter_ending:
      location: 本章结尾时，主要人物所在的场景或地点（一句话）。
      character_states:
        人物A姓名: 该人物在本章结尾的情绪与状态（一句话）。
        人物B姓名: 该人物在本章结尾的情绪与状态（一句话）。
      relationship_progress: 主要人物之间的关系在本章结束后的状态（一句话）。
      ending_hook: 本章最后留下的悬念或情绪钩子，用于引出下一章（一句话）。
    """

def get_core_plot_prompt(system_prompt):
    """获取生成核心剧情的提示词。"""
    return system_prompt + f"""
    
    任务: 构思这部小说的核心剧情架构。
    
    请输出:
    1. **故事梗概 (Synopsis)**: 300字左右，涵盖背景、冲突、高潮和结局。
    2. **核心诡计/转折**: 故事中最大的反转或悬念是什么。
    3. **角色成长**: 主角的人物弧光 (Character Arc) 和关键变化节点。
    4. **整体结构**: 使用三幕式结构简单描述剧情走向（第一幕：... 第二幕：... 第三幕：...）。
    
    注意：**不需要**生成具体的章节列表，只要顶层设计。
    """

def get_chapter_skeleton_prompt(system_prompt, core_plot, target_count):
    """获取生成章节骨架的提示词。"""
    return system_prompt + f"""
    
    任务: 基于核心剧情，规划详细的章节骨架。
    
    核心剧情:
    {core_plot}
    
    要求:
    1. 必须严格生成 **{target_count}** 个章节。
    2. 每个章节只需要提供:
       - 章节号 (1-{target_count})
       - 标题 (Title)
       - 一句话梗概 (Logline)
    3. 以 YAML 列表格式输出。
    
    输出示例:
    - chapter_num: 1
      title: "初入异界"
      logline: "主角醒来发现自己穿越，遭遇第一次危机。"
    - chapter_num: 2
      title: "神秘救星"
      logline: "被神秘人救下，得知世界真相。"
    """

def get_chapter_plan_prompt(outline, target_count):
    """获取从大纲提取章节计划的提示词。"""
    return f"""
    根据以下故事大纲，提取详细的章节列表。
    
    【重要要求】
    1. 必须生成 EXACTLY (确切地) {target_count} 个章节及标题。
    2. 大纲中如果出现 "1-3章" 这种范围，请必须将其展开为 第1章、第2章、第3章，并为每一章赋予独立的标题和具体的情节摘要。
    3. 必须覆盖大纲的所有内容，不要遗漏。
    
    仅返回一个 YAML 格式的列表，其中每一项包含 'title' (章节标题) 和 'summary' (章节摘要)。
    不要包含 markdown 标记 (```yaml)，只返回纯文本 YAML。
    
    大纲:
    {outline}
    
    格式示例:
    - title: "久别重逢"
      summary: "苏浅在酒会被顾沉刁难..."
    - title: "深夜加班"
      summary: "由于工作室危机，苏浅不得不..."
    """
