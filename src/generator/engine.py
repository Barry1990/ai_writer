import os
import logging
from ..llm import get_llm_client
from .prompts import build_system_prompt
from .memory_manager import MemoryManager
from .outline_manager import OutlineManager
from .chapter_manager import ChapterManager

logger = logging.getLogger(__name__)

class StoryGenerator:
    def __init__(self, config, output_dir="output"):
        self.config = config
        
        # 提取小说标题并创建专用文件夹
        novel_title = "未命名小说"
        if isinstance(config.get('故事'), dict):
            novel_title = config.get('故事', {}).get('标题', '未命名小说')
        elif isinstance(config.get('基本信息'), dict):
             novel_title = config.get('基本信息', {}).get('标题', '未命名小说')

        safe_title = "".join([c for c in novel_title if c.isalnum() or c in (' ', '_', '-')]).strip()
        self.output_dir = os.path.join(output_dir, safe_title)
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"项目输出目录设定为: {self.output_dir}")

        self.llm = get_llm_client(config.get('llm'))
        self.system_prompt = build_system_prompt(config)
        
        self.memory_manager = MemoryManager(self.output_dir)
        self.outline_manager = OutlineManager(self.llm, self.output_dir, config)
        self.chapter_manager = ChapterManager(self.llm, self.output_dir, config, self.memory_manager)

    def run(self):
        # 1. Outline Management
        outline, structured_outline = self.outline_manager.load_outline()
        if not outline:
            outline = self.outline_manager.generate_outline(self.system_prompt)
            # Re-load or parse to get structured_outline
            _, structured_outline = self.outline_manager.load_outline()
        
        # 2. Chapter Planning
        chapter_plan = self.outline_manager.get_chapter_plan(outline)
        chapter_plan = self.outline_manager.reconcile_plan_with_disk(chapter_plan)
        
        # 3. Chapter Generation
        completed_chapters = self.memory_manager.get_completed_chapters()
        
        for i, chapter_info in enumerate(chapter_plan, 1):
            if i in completed_chapters:
                logger.info(f"第 {i} 章已记录在记忆中，跳过生成。")
                continue
                
            self.chapter_manager.generate_chapter_content(
                i, chapter_info, self.system_prompt, structured_outline
            )
