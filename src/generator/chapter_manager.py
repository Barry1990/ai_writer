import os
import logging
import yaml
from .prompts import get_section_generation_prompt, get_memory_update_prompt
from src.utils import save_file

logger = logging.getLogger(__name__)

class ChapterManager:
    def __init__(self, llm, output_dir, config, memory_manager):
        self.llm = llm
        self.output_dir = output_dir
        self.config = config
        self.memory_manager = memory_manager

    def generate_chapter_content(self, chapter_num, chapter_info, system_prompt, structured_outline):
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
        
        chapter_config = self.config.get('章节设置', {})
        section_count = chapter_config.get('每章小节数', 1)
        
        safe_dir_name = "".join([c for c in chapter_title if c.isalpha() or c.isdigit() or c in (' ', '_', '-', '.')]).strip()
        chapter_dir = os.path.join(self.output_dir, safe_dir_name)
        os.makedirs(chapter_dir, exist_ok=True)
        
        full_chapter_text = f"# {chapter_title.replace('_', ' ')}\n\n"
        
        for section_num in range(1, section_count + 1):
            section_file_path = os.path.join(chapter_dir, f"第{section_num}节.txt")
            if os.path.exists(section_file_path):
                logger.info(f"  -> {chapter_title} 第 {section_num} 节 已存在，跳过生成。")
                try:
                    with open(section_file_path, 'r', encoding='utf-8') as f:
                        section_content = f.read()
                    full_chapter_text += f"\n\n--- 第 {section_num} 节 ---\n\n" + section_content
                except Exception as e:
                    logger.warning(f"读取已有章节内容失败: {e}")
                continue

            logger.info(f"  -> 正在生成 {chapter_title} 第 {section_num} 节...")
            
            # Context preparation
            core_plot = ""
            current_chapter_outline = chapter_summary
            
            if structured_outline:
                core_plot = structured_outline.get('core_plot', '')
                chapters_map = structured_outline.get('chapters', {})
                if chapter_num in chapters_map:
                    ch_data = chapters_map[chapter_num]
                    current_chapter_outline = f"{ch_data.get('title', '')}\n{ch_data.get('content', '')}"
                    if chapter_num + 1 in chapters_map:
                         next_ch = chapters_map[chapter_num + 1]
                         current_chapter_outline += f"\n\n(预告: 下一章 {next_ch.get('title', '')})"
            
            section_content = self._generate_section_content(
                system_prompt,
                chapter_num, 
                section_num, 
                section_count, 
                current_chapter_outline,
                full_chapter_text, 
                chapter_title,
                core_plot=core_plot
            )
            
            save_file(section_content, os.path.join(chapter_dir, f"第{section_num}节.txt"))
            full_chapter_text += f"\n\n--- 第 {section_num} 节 ---\n\n" + section_content
            
        # Analysis and Memory Update
        self._analyze_and_update_memory(chapter_num, full_chapter_text)
            
        return full_chapter_text

    def _generate_section_content(self, system_prompt, chapter_num, section_num, total_sections, chapter_summary, previous_context, chapter_title="", core_plot=""):
        recent_context = previous_context[-3000:] if len(previous_context) > 3000 else previous_context
        
        cross_chapter_context = ""
        if section_num == 1 and chapter_num > 1:
            prev_ending = self.memory_manager.get_chapter_ending_context(chapter_num - 1)
            if prev_ending:
                cross_chapter_context = (
                    f"\n        ⚠️【跨章衔接（极其重要）】上一章（第 {chapter_num - 1} 章）结尾状态:\n"
                    f"        {prev_ending}\n"
                    f"\n        本章第一节必须从上述状态无缝延续，不得与之矛盾。\n"
                    f"        人物情绪、所在地点、关系进展必须保持一致，不可凭空跳跃或重置。\n"
                )
            else:
                logger.debug(f"第 {chapter_num} 章第一节：未找到第 {chapter_num - 1} 章结尾状态，跳过跨章注入。")
        
        continuity_section = self.memory_manager.get_continuity_section()
        
        prompt = get_section_generation_prompt(
            system_prompt, chapter_title, section_num, total_sections, 
            core_plot, chapter_summary, cross_chapter_context, 
            continuity_section, recent_context
        )
        
        return self.llm.generate_content(prompt)

    def _analyze_and_update_memory(self, chapter_num, chapter_text):
        logger.info(f"正在分析第 {chapter_num} 章以更新故事记忆...")
        prompt = get_memory_update_prompt(chapter_text)
        
        try:
            response = self.llm.generate_content(prompt)
            clean_response = response.replace("```yaml", "").replace("```", "").strip()
            data = yaml.safe_load(clean_response)
            self.memory_manager.update_story_memory(chapter_num, data)
        except Exception as e:
            logger.error(f"分析章节以更新记忆失败: {e}")
