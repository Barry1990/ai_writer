import logging
import os
import yaml
import re
from .llm import get_llm_client

from .utils import save_file

logger = logging.getLogger(__name__)

class StoryGenerator:
    def __init__(self, config, output_dir="output"):
        self.config = config
        
        # 提取小说标题并创建专用文件夹
        novel_title = "未命名小说"
        if isinstance(config.get('故事'), dict):
            novel_title = config.get('故事', {}).get('标题', '未命名小说')
        elif isinstance(config.get('基本信息'), dict): # 兼容旧格式或不同层级
             novel_title = config.get('基本信息', {}).get('标题', '未命名小说')

        # 清洗文件夹名称，移除非法字符
        safe_title = "".join([c for c in novel_title if c.isalnum() or c in (' ', '_', '-')]).strip()
        self.output_dir = os.path.join(output_dir, safe_title)
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"项目输出目录设定为: {self.output_dir}")

        self.llm = get_llm_client(config.get('llm'))
        self.story_context = {}
        # 记忆系统：用于存储故事梗概和伏笔
        self.story_memory = {
            'summary': [],          # 已经发生的故事概要（按章节）
            'foreshadowing': [],    # 埋下的伏笔（未回收）
            'chapter_endings': []   # 每章结尾的细粒度状态（位置/情绪/关系/钩子）
        }

    def _build_system_prompt(self):
        # 将配置转换为 YAML 字符串，以便 LLM 理解任意结构
        config_str = yaml.dump(self.config, allow_unicode=True, default_flow_style=False)
        
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

    def generate_outline(self):
        logger.info("正在生成故事大纲 (迭代模式)...")
        
        # Phase 1: Core Plot (High-level Arc)
        core_plot = self._generate_core_plot()
        
        # Phase 2: Chapter Skeleton (Titles & One-sentence summaries)
        chapter_skeleton = self._generate_chapter_skeleton(core_plot)
        
        # Phase 3: Detailed Expansion (Batch processing)
        full_outline_text = f"{core_plot}\n\n### 三、 章节大纲 (详细版)\n\n"
        
        batch_size = 5 # Process 5 chapters at a time to ensure high detail and avoid truncation
        total_chapters = len(chapter_skeleton)
        
        for i in range(0, total_chapters, batch_size):
            batch = chapter_skeleton[i : i + batch_size]
            start_num = batch[0]['chapter_num']
            end_num = batch[-1]['chapter_num']
            
            logger.info(f"正在扩展第 {start_num}-{end_num} 章的大纲细节...")
            batch_content = self._expand_chapter_batch(core_plot, batch)
            full_outline_text += batch_content + "\n\n"
            
        self.story_context['outline'] = full_outline_text
        save_file(full_outline_text, os.path.join(self.output_dir, "outline.txt"))
        
        # NEW: Parse and save structured outline for token optimization
        self._parse_and_save_structured_outline(full_outline_text)
        
        return full_outline_text

    def _parse_and_save_structured_outline(self, full_text):
        """解析完整大纲并保存为结构化数据，以便后续分章调用时节省 Token。"""
        logger.info("正在解析并保存结构化大纲...")
        
        # Split Core Plot and Chapters
        parts = full_text.split("### 三、 章节大纲 (详细版)")
        core_plot = parts[0].strip()
        chapters_text = parts[1].strip() if len(parts) > 1 else ""
        
        # Simple regex to split based on "### 第X章"
        # Assuming format: ### 第1章：Title\nContent...
        chapter_map = {}
        
        # Find all chapter headers
        # Find all chapter headers
        # Regex to match: ### (第X章...) OR ### (Chapter X...)
        # Supports Arabic (1, 2) and Chinese (一, 二) numerals
        header_pattern = r"###\s*(第\s*[0-9一二三四五六七八九十百]+\s*章.*|Chapter\s*\d+.*)"
        matches = list(re.finditer(header_pattern, chapters_text))
        
        for i, match in enumerate(matches):
            header = match.group(1).strip()
            start_pos = match.end()
            end_pos = matches[i+1].start() if i + 1 < len(matches) else len(chapters_text)
            
            content = chapters_text[start_pos:end_pos].strip()
            
            # Extract chapter number
            # Try Arabic first
            num_match = re.search(r"(\d+)", header)
            chapter_num = -1
            
            if num_match:
                chapter_num = int(num_match.group(1))
            else:
                # Try Chinese numerals mapping (simple implementation)
                cn_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                # Find first matching char
                for char in header:
                    if char in cn_map:
                        chapter_num = cn_map[char]
                        # Handle teen numbers roughly if needed, but strict prompt usually avoids complex mixed numbers
                        break
            
            if chapter_num != -1:
                chapter_map[chapter_num] = {
                    'title': header,
                    'content': content
                }
            else:
                 logger.warning(f"无法解析章节编号: {header}")
        
        structure = {
            'core_plot': core_plot,
            'chapters': chapter_map
        }
        
        try:
            with open(os.path.join(self.output_dir, "outline_structure.yaml"), 'w', encoding='utf-8') as f:
                yaml.dump(structure, f, allow_unicode=True)
            self.story_context['structured_outline'] = structure
            logger.info(f"结构化大纲已保存，包含 {len(chapter_map)} 章详情。")
        except Exception as e:
            logger.error(f"保存结构化大纲失败: {e}")

    def _generate_core_plot(self):
        logger.info("Phase 1: 生成核心剧情 (Core Plot)...")
        prompt = self._build_system_prompt() + f"""
        
        任务: 构思这部小说的核心剧情架构。
        
        请输出:
        1. **故事梗概 (Synopsis)**: 300字左右，涵盖背景、冲突、高潮和结局。
        2. **核心诡计/转折**: 故事中最大的反转或悬念是什么。
        3. **角色成长**: 主角的人物弧光 (Character Arc) 和关键变化节点。
        4. **整体结构**: 使用三幕式结构简单描述剧情走向（第一幕：... 第二幕：... 第三幕：...）。
        
        注意：**不需要**生成具体的章节列表，只要顶层设计。
        """
        return self.llm.generate_content(prompt)

    def _generate_chapter_skeleton(self, core_plot):
        target_count = self.config.get('章节设置', {}).get('目标章数', 20)
        logger.info(f"Phase 2: 生成章节骨架 (目标 {target_count} 章)...")
        
        prompt = self._build_system_prompt() + f"""
        
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
        
        # Try-catch loop to ensure we get a valid list
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.llm.generate_content(prompt, generation_config={"max_output_tokens": 8192}) # Skeleton is cheap, 8k is enough for 100+ chapters
                skeleton = self._safe_parse_yaml_list(response)
                
                if isinstance(skeleton, list) and len(skeleton) >= target_count * 0.8: # Allow small margin of error
                    logger.info(f"骨架生成成功，共 {len(skeleton)} 章。")
                    return skeleton[:target_count] # Enforce exact count if over-generated
                else:
                    logger.warning(f"骨架生成数量不符或格式错误 (Attempt {attempt+1}): {len(skeleton) if isinstance(skeleton, list) else 'Invalid'}")
            except Exception as e:
                logger.error(f"骨架生成处理失败: {e}")
                
        raise ValueError("无法生成有效的章节骨架，请检查配置或网络。")

    def _safe_parse_yaml_list(self, text):
        """更健壮地从 LLM 返回文本中提取并解析 YAML 列表。"""
        import yaml
        
        # 1. 优先尝试从 Markdown 代码块提取
        yaml_block_match = re.search(r"```(?:yaml|json)?\s*(.*?)```", text, re.DOTALL)
        if yaml_block_match:
            try:
                data = yaml.safe_load(yaml_block_match.group(1))
                if isinstance(data, list): return data
            except: pass

        # 2. 尝试清洗整体文本（移除干扰信息）
        clean_text = text.replace("```yaml", "").replace("```json", "").replace("```", "").strip()
        try:
            data = yaml.safe_load(clean_text)
            if isinstance(data, list): return data
        except: pass

        # 3. 兜底方案：行正则解析 (针对常见的 - key: value 格式)
        logger.warning("YAML 解析失败，尝试使用正则降级解析...")
        items = []
        current_item = {}
        
        # 匹配 "- key: value" 或 "  key: value"
        # 针对 Logline 这种可能包含冒号或特殊字符的情况，使用懒惰匹配
        pattern = re.compile(r"^\s*-\s*([^:]+):\s*(.*)|^\s*([^:]+):\s*(.*)")
        
        for line in clean_text.split('\n'):
            line = line.strip()
            if not line: continue
            
            match = pattern.match(line)
            if match:
                groups = match.groups()
                if groups[0] is not None: # 开始新项
                    if current_item: items.append(current_item)
                    current_item = {groups[0].strip(): groups[1].strip().strip('"').strip("'")}
                elif groups[2] is not None: # 当前项的属性
                    current_item[groups[2].strip()] = groups[3].strip().strip('"').strip("'")
        
        if current_item: items.append(current_item)
        return items

    def _expand_chapter_batch(self, core_plot, batch_chapters):
        prompt = self._build_system_prompt() + f"""
        
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
        return self.llm.generate_content(prompt)

    def generate_chapter_content(self, chapter_num, chapter_info):
        # chapter_info 可以是简单的摘要字符串，也可以是包含 title/summary 的字典
        chapter_title = f"第{chapter_num}章"
        chapter_summary = ""
        
        if isinstance(chapter_info, dict):
            title = chapter_info.get('title', '')
            if title:
                chapter_title = f"第{chapter_num}章_{title}"
            chapter_summary = chapter_info.get('summary', '')
        else:
            chapter_summary = str(chapter_info)

        logger.info(f"正在生成 {chapter_title}...")
        
        # 获取章节设置
        chapter_config = self.config.get('章节设置', {})
        section_count = chapter_config.get('每章小节数', 1)
        
        # 创建章节目录
        # Sanitize directory name to avoid invalid characters
        safe_dir_name = "".join([c for c in chapter_title if c.isalpha() or c.isdigit() or c in (' ', '_', '-', '.')]).strip()
        chapter_dir = os.path.join(self.output_dir, safe_dir_name)
        os.makedirs(chapter_dir, exist_ok=True)
        
        full_chapter_text = f"# {chapter_title.replace('_', ' ')}\n\n" # 用于上下文累积, 包含标题
        
        for section_num in range(1, section_count + 1):
            # RESUME CHECK: Check if section file already exists
            section_file_path = os.path.join(chapter_dir, f"第{section_num}节.txt")
            if os.path.exists(section_file_path):
                logger.info(f"  -> {chapter_title} 第 {section_num} 节 已存在，跳过生成。")
                try:
                    with open(section_file_path, 'r', encoding='utf-8') as f:
                        section_content = f.read()
                    # Append header and content to full text for context
                    full_chapter_text += f"\n\n--- 第 {section_num} 节 ---\n\n" + section_content
                except Exception as e:
                    logger.warning(f"读取已有章节内容失败: {e}")
                continue

            logger.info(f"  -> 正在生成 {chapter_title} 第 {section_num} 节...")
            
            # PREPARE OPTIMIZED CONTEXT
            core_plot = ""
            current_chapter_outline = chapter_summary # Fallback
            
            structured_outline = self.story_context.get('structured_outline')
            if structured_outline:
                core_plot = structured_outline.get('core_plot', '')
                chapters_map = structured_outline.get('chapters', {})
                if chapter_num in chapters_map:
                    ch_data = chapters_map[chapter_num]
                    # Combine title and content
                    current_chapter_outline = f"{ch_data.get('title', '')}\n{ch_data.get('content', '')}"
                    
                    # Optional: Add next chapter's logline for foreshadowing
                    if chapter_num + 1 in chapters_map:
                         next_ch = chapters_map[chapter_num + 1]
                         current_chapter_outline += f"\n\n(预告: 下一章 {next_ch.get('title', '')})"
            
            section_content = self._generate_section_content(
                chapter_num, 
                section_num, 
                section_count, 
                current_chapter_outline, # Optimized outline injection
                full_chapter_text, 
                chapter_title,
                core_plot=core_plot # Pass core plot
            )

            
            # 保存每一节
            save_file(section_content, os.path.join(chapter_dir, f"第{section_num}节.txt"))
            
            full_chapter_text += f"\n\n--- 第 {section_num} 节 ---\n\n" + section_content
            
        # 章节写完后，进行记忆更新（分析本章剧情和伏笔）
        self._update_story_memory(chapter_num, full_chapter_text)
            
        return full_chapter_text

    def _update_story_memory(self, chapter_num, chapter_text):
        logger.info(f"正在分析第 {chapter_num} 章以更新故事记忆...")
        prompt = f"""
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
        
        try:
            response = self.llm.generate_content(prompt)
            import yaml
            clean_response = response.replace("```yaml", "").replace("```", "").strip()
            data = yaml.safe_load(clean_response)
            
            if data:
                self.story_memory['summary'].append(f"第 {chapter_num} 章: {data.get('summary', '无')}")
                
                # 添加新伏笔
                for foreshadow in data.get('new_foreshadowing', []) or []:
                    self.story_memory['foreshadowing'].append(foreshadow)
                
                # 真正从列表中移除已回收的伏笔（前缀模糊匹配，避免误删）
                resolved = data.get('resolved_foreshadowing', []) or []
                if resolved:
                    logger.info(f"回收伏笔: {resolved}")
                    before_count = len(self.story_memory['foreshadowing'])
                    self.story_memory['foreshadowing'] = [
                        f for f in self.story_memory['foreshadowing']
                        if not any(str(r)[:15] in str(f) for r in resolved)
                    ]
                    after_count = len(self.story_memory['foreshadowing'])
                    logger.info(f"伏笔列表从 {before_count} 条减少到 {after_count} 条。")
                
                # 保存细粒度章节结尾状态
                ending = data.get('chapter_ending', {}) or {}
                if ending:
                    ending['chapter'] = chapter_num
                    if 'chapter_endings' not in self.story_memory:
                        self.story_memory['chapter_endings'] = []
                    self.story_memory['chapter_endings'].append(ending)
                    logger.info(f"已保存第 {chapter_num} 章结尾状态: {ending.get('location', '未知')}")
                    
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
        
        # Save memory after update
        self.save_memory()

    def _get_chapter_ending(self, chapter_num):
        """从记忆中取指定章节的结尾状态，格式化为可注入 Prompt 的文本。"""
        endings = self.story_memory.get('chapter_endings', [])
        for ending in reversed(endings):  # 倒序查找最近的记录
            if ending.get('chapter') == chapter_num:
                char_states = ending.get('character_states', {})
                if isinstance(char_states, dict):
                    char_states_str = "\n".join(
                        f"  - {name}: {state}" for name, state in char_states.items()
                    )
                else:
                    char_states_str = str(char_states)
                return (
                    f"地点: {ending.get('location', '未知')}\n"
                    f"人物状态:\n{char_states_str}\n"
                    f"关系进展: {ending.get('relationship_progress', '未知')}\n"
                    f"结尾钩子: {ending.get('ending_hook', '未知')}"
                )
        return ""  # 没有记录则返回空

    def save_memory(self):
        """Persist story memory to disk."""
        try:
            memory_path = os.path.join(self.output_dir, "memory.yaml")
            with open(memory_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.story_memory, f, allow_unicode=True)
            logger.info("故事记忆已保存。")
        except Exception as e:
            logger.error(f"保存记忆失败: {e}")

    def load_memory(self):
        """Load story memory from disk if exists."""
        memory_path = os.path.join(self.output_dir, "memory.yaml")
        if os.path.exists(memory_path):
            try:
                with open(memory_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data:
                        self.story_memory = data
                logger.info("已加载已有故事记忆。")
            except Exception as e:
                logger.error(f"加载记忆失败: {e}")

    def _generate_section_content(self, chapter_num, section_num, total_sections, chapter_summary, previous_context, chapter_title="", core_plot=""):
        # 截取最近的上下文（最后3000字，比原来的2000字更多），保留更多前文信息
        recent_context = previous_context[-3000:] if len(previous_context) > 3000 else previous_context
        
        # 跨章节衔接：仅在每章第一节，注入上一章的细粒度结尾状态
        cross_chapter_context = ""
        if section_num == 1 and chapter_num > 1:
            prev_ending = self._get_chapter_ending(chapter_num - 1)
            if prev_ending:
                cross_chapter_context = (
                    f"\n        ⚠️【跨章衔接（极其重要）】上一章（第 {chapter_num - 1} 章）结尾状态:\n"
                    f"        {prev_ending}\n"
                    f"\n        本章第一节必须从上述状态无缝延续，不得与之矛盾。\n"
                    f"        人物情绪、所在地点、关系进展必须保持一致，不可凭空跳跃或重置。\n"
                )
            else:
                import logging
                logging.getLogger(__name__).debug(f"第 {chapter_num} 章第一节：未找到第 {chapter_num - 1} 章结尾状态，跳过跨章注入。")
        
        # 近期摘要：只取最近5章，避免列表过长降低信噪比
        recent_summaries = self.story_memory["summary"][-5:]
        active_foreshadowing = self.story_memory["foreshadowing"]
        
        continuity_section = (
            "        【故事记忆 (Continuity & Foreshadowing)】:\n"
            f"        近期剧情回顾（最近5章）: {recent_summaries}\n"
            f"        当前活跃的伏笔/悬念: {active_foreshadowing}"
        )
        
        prompt = self._build_system_prompt() + (
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
        
        return self.llm.generate_content(prompt)


    def run(self):
        # RESUME CHECK: Try to load existing outline
        outline_path = os.path.join(self.output_dir, "outline.txt")
        if os.path.exists(outline_path):
            logger.info("发现已有大纲文件，正在读取...")
            try:
                with open(outline_path, 'r', encoding='utf-8') as f:
                    outline = f.read()
                self.story_context['outline'] = outline
                
                # Check for structured outline
                structure_path = os.path.join(self.output_dir, "outline_structure.yaml")
                if os.path.exists(structure_path):
                     with open(structure_path, 'r', encoding='utf-8') as f:
                        self.story_context['structured_outline'] = yaml.safe_load(f)
                     logger.info("已加载结构化大纲。")
                else:
                    # Parse it now if missing
                    self._parse_and_save_structured_outline(outline)
                    
            except Exception as e:
                logger.warning(f"读取大纲失败，将重新生成: {e}")
                outline = self.generate_outline()
        else:
            outline = self.generate_outline()
        
        # RESUME CHECK: Load memory
        self.load_memory()
        
        # RESUME CHECK: Try to load existing chapter plan to ensure deterministic titles
        chapter_plan_path = os.path.join(self.output_dir, "chapter_plan.yaml")
        chapter_plan = []
        if os.path.exists(chapter_plan_path):
            try:
                with open(chapter_plan_path, 'r', encoding='utf-8') as f:
                    chapter_plan = yaml.safe_load(f)
                logger.info("已加载已有章节计划。")
            except Exception as e:
                logger.error(f"加载章节计划失败: {e}")
        
        if not chapter_plan:
            chapter_plan = self._extract_chapter_plan(outline)
            # Save chapter plan
            try:
                with open(chapter_plan_path, 'w', encoding='utf-8') as f:
                    yaml.dump(chapter_plan, f, allow_unicode=True)
            except Exception as e:
                logger.error(f"保存章节计划失败: {e}")
        
        # RESUME CHECK: Reconcile plan with existing directories on disk
        # This prevents duplicate chapters if the plan title differs from the existing directory
        existing_dirs = {} # Map chapter_num -> full_dir_name
        try:
            for item in os.listdir(self.output_dir):
                if os.path.isdir(os.path.join(self.output_dir, item)):
                    # Match pattern "第1章_Title"
                    match = re.match(r"第(\d+)章_(.*)", item)
                    if match:
                        existing_dirs[int(match.group(1))] = item
            
            # Update plan to match existing directories
            for i, chapter_info in enumerate(chapter_plan):
                chapter_num = i + 1
                if chapter_num in existing_dirs:
                    existing_name = existing_dirs[chapter_num]
                    # Extract title from existing directory name
                    # existing_name is like "第1章_Title"
                    # We want to force the generator to use this Title
                    # Update the plan object
                    current_title = chapter_info.get('title') if isinstance(chapter_info, dict) else str(chapter_info)
                    disk_title = existing_name.split('_', 1)[1]
                    
                    if current_title != disk_title:
                        logger.warning(f"检测到第 {chapter_num} 章已有目录 '{existing_name}'，将覆盖计划中的标题 '{current_title}'。")
                        if isinstance(chapter_info, dict):
                            chapter_info['title'] = disk_title
                        else:
                            # If it was a string, we convert to dict
                            chapter_plan[i] = {'title': disk_title, 'summary': chapter_info}
                            
            # Save the reconciled plan back to disk to ensure consistency for next run
            try:
                with open(chapter_plan_path, 'w', encoding='utf-8') as f:
                    yaml.dump(chapter_plan, f, allow_unicode=True)
            except Exception as e:
                logger.error(f"保存协调后的章节计划失败: {e}")
                
        except Exception as e:
            logger.error(f"协调目录时出错: {e}")
        
        # RESUME CHECK: Identify completed chapters from memory
        completed_chapters = set()
        for summary in self.story_memory.get('summary', []):
            # Parse "第 X 章: ..."
            match = re.match(r"第\s*(\d+)\s*章", summary)
            if match:
                completed_chapters.add(int(match.group(1)))
        
        for i, chapter_info in enumerate(chapter_plan, 1):
            if i in completed_chapters:
                logger.info(f"第 {i} 章已记录在记忆中，跳过生成。")
                continue
                
            self.generate_chapter_content(i, chapter_info)

    def _extract_chapter_plan(self, outline):
        """Helper to get a structured list of chapters from the raw outline text."""
        target_count = self.config.get('章节设置', {}).get('目标章数', 20)
        logger.info(f"正在提取章节计划 (目标章数: {target_count})...")
        
        prompt = f"""
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
        # Increase token limit for long lists
        generation_config = {"max_output_tokens": 81920}
        
        response = self.llm.generate_content(prompt, generation_config=generation_config)
        
        chapters = self._safe_parse_yaml_list(response)
        if isinstance(chapters, list) and chapters:
            logger.info(f"成功提取了 {len(chapters)} 章 (目标: {target_count})")
            return chapters
        else:
            logger.warning("无法将章节计划解析为列表，返回空列表。")
            return []
