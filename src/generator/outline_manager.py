import os
import re
import yaml
import logging
from .prompts import get_core_plot_prompt, get_chapter_skeleton_prompt, get_outline_batch_prompt, get_chapter_plan_prompt
from src.utils import save_file

logger = logging.getLogger(__name__)

class OutlineManager:
    def __init__(self, llm, output_dir, config):
        self.llm = llm
        self.output_dir = output_dir
        self.config = config
        self.story_context = {}

    def generate_outline(self, system_prompt):
        logger.info("正在生成故事大纲 (迭代模式)...")
        
        # Phase 1: Core Plot (High-level Arc)
        core_plot = self._generate_core_plot(system_prompt)
        
        # Phase 2: Chapter Skeleton (Titles & One-sentence summaries)
        chapter_skeleton = self._generate_chapter_skeleton(system_prompt, core_plot)
        
        # Phase 3: Detailed Expansion (Batch processing)
        full_outline_text = f"{core_plot}\n\n### 三、 章节大纲 (详细版)\n\n"
        
        batch_size = 5
        total_chapters = len(chapter_skeleton)
        
        for i in range(0, total_chapters, batch_size):
            batch = chapter_skeleton[i : i + batch_size]
            start_num = batch[0]['chapter_num']
            end_num = batch[-1]['chapter_num']
            
            logger.info(f"正在扩展第 {start_num}-{end_num} 章的大纲细节...")
            prompt = get_outline_batch_prompt(system_prompt, core_plot, batch)
            batch_content = self.llm.generate_content(prompt)
            full_outline_text += batch_content + "\n\n"
            
        save_file(full_outline_text, os.path.join(self.output_dir, "outline.txt"))
        
        # NEW: Parse and save structured outline for token optimization
        self.parse_and_save_structured_outline(full_outline_text)
        
        return full_outline_text

    def _generate_core_plot(self, system_prompt):
        logger.info("Phase 1: 生成核心剧情 (Core Plot)...")
        prompt = get_core_plot_prompt(system_prompt)
        return self.llm.generate_content(prompt)

    def _generate_chapter_skeleton(self, system_prompt, core_plot):
        target_count = self.config.get('章节设置', {}).get('目标章数', 20)
        logger.info(f"Phase 2: 生成章节骨架 (目标 {target_count} 章)...")
        
        prompt = get_chapter_skeleton_prompt(system_prompt, core_plot, target_count)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.llm.generate_content(prompt, generation_config={"max_output_tokens": 8192})
                skeleton = self._safe_parse_yaml_list(response)
                
                if isinstance(skeleton, list) and len(skeleton) >= target_count * 0.8:
                    logger.info(f"骨架生成成功，共 {len(skeleton)} 章。")
                    return skeleton[:target_count]
                else:
                    logger.warning(f"骨架生成数量不符或格式错误 (Attempt {attempt+1}): {len(skeleton) if isinstance(skeleton, list) else 'Invalid'}")
            except Exception as e:
                logger.error(f"骨架生成处理失败: {e}")
                
        raise ValueError("无法生成有效的章节骨架，请检查配置或网络。")

    def _safe_parse_yaml_list(self, text):
        """更健壮地从 LLM 返回文本中提取并解析 YAML 列表。"""
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

        # 3. 兜底方案：行正则解析
        logger.warning("YAML 解析失败，尝试使用正则降级解析...")
        items = []
        current_item = {}
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

    def parse_and_save_structured_outline(self, full_text):
        """解析完整大纲并保存为结构化数据，以便后续分章调用时节省 Token。"""
        logger.info("正在解析并保存结构化大纲...")
        
        parts = full_text.split("### 三、 章节大纲 (详细版)")
        core_plot = parts[0].strip()
        chapters_text = parts[1].strip() if len(parts) > 1 else ""
        
        chapter_map = {}
        header_pattern = r"###\s*(第\s*[0-9一二三四五六七八九十百]+\s*章.*|Chapter\s*\d+.*)"
        matches = list(re.finditer(header_pattern, chapters_text))
        
        for i, match in enumerate(matches):
            header = match.group(1).strip()
            start_pos = match.end()
            end_pos = matches[i+1].start() if i + 1 < len(matches) else len(chapters_text)
            
            content = chapters_text[start_pos:end_pos].strip()
            
            num_match = re.search(r"(\d+)", header)
            chapter_num = -1
            
            if num_match:
                chapter_num = int(num_match.group(1))
            else:
                cn_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                for char in header:
                    if char in cn_map:
                        chapter_num = cn_map[char]
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
            logger.info(f"结构化大纲已保存，包含 {len(chapter_map)} 章详情。")
            return structure
        except Exception as e:
            logger.error(f"保存结构化大纲失败: {e}")
            return None

    def load_outline(self):
        outline_path = os.path.join(self.output_dir, "outline.txt")
        if os.path.exists(outline_path):
            logger.info("发现已有大纲文件，正在读取...")
            try:
                with open(outline_path, 'r', encoding='utf-8') as f:
                    outline = f.read()
                
                structure = None
                structure_path = os.path.join(self.output_dir, "outline_structure.yaml")
                if os.path.exists(structure_path):
                     with open(structure_path, 'r', encoding='utf-8') as f:
                        structure = yaml.safe_load(f)
                     logger.info("已加载结构化大纲。")
                else:
                    structure = self.parse_and_save_structured_outline(outline)
                
                return outline, structure
            except Exception as e:
                logger.warning(f"读取大纲失败: {e}")
        return None, None

    def get_chapter_plan(self, outline):
        chapter_plan_path = os.path.join(self.output_dir, "chapter_plan.yaml")
        if os.path.exists(chapter_plan_path):
            try:
                with open(chapter_plan_path, 'r', encoding='utf-8') as f:
                    chapter_plan = yaml.safe_load(f)
                logger.info("已加载已有章节计划。")
                return chapter_plan
            except Exception as e:
                logger.error(f"加载章节计划失败: {e}")
        
        target_count = self.config.get('章节设置', {}).get('目标章数', 20)
        logger.info(f"正在提取章节计划 (目标章数: {target_count})...")
        
        prompt = get_chapter_plan_prompt(outline, target_count)
        generation_config = {"max_output_tokens": 81920}
        
        response = self.llm.generate_content(prompt, generation_config=generation_config)
        chapter_plan = self._safe_parse_yaml_list(response)
        
        if isinstance(chapter_plan, list) and chapter_plan:
            logger.info(f"成功提取了 {len(chapter_plan)} 章 (目标: {target_count})")
            # Save chapter plan
            try:
                with open(chapter_plan_path, 'w', encoding='utf-8') as f:
                    yaml.dump(chapter_plan, f, allow_unicode=True)
            except Exception as e:
                logger.error(f"保存章节计划失败: {e}")
            return chapter_plan
        else:
            logger.warning("无法将章节计划解析为列表。")
            return []

    def reconcile_plan_with_disk(self, chapter_plan):
        """协调计划与磁盘上的现有目录。"""
        existing_dirs = {}
        try:
            for item in os.listdir(self.output_dir):
                if os.path.isdir(os.path.join(self.output_dir, item)):
                    match = re.match(r"第(\d+)章_(.*)", item)
                    if match:
                        existing_dirs[int(match.group(1))] = item
            
            for i, chapter_info in enumerate(chapter_plan):
                chapter_num = i + 1
                if chapter_num in existing_dirs:
                    existing_name = existing_dirs[chapter_num]
                    disk_title = existing_name.split('_', 1)[1]
                    
                    if isinstance(chapter_info, dict):
                        if chapter_info.get('title') != disk_title:
                            logger.warning(f"检测到第 {chapter_num} 章已有目录 '{existing_name}'，将覆盖计划中的标题。")
                            chapter_info['title'] = disk_title
                    else:
                        chapter_plan[i] = {'title': disk_title, 'summary': chapter_info}
            
            # Save the reconciled plan back to disk
            chapter_plan_path = os.path.join(self.output_dir, "chapter_plan.yaml")
            with open(chapter_plan_path, 'w', encoding='utf-8') as f:
                yaml.dump(chapter_plan, f, allow_unicode=True)
                
        except Exception as e:
            logger.error(f"协调目录时出错: {e}")
        
        return chapter_plan
