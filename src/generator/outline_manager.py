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
        chapter_cfg = self.config.get('chapter_settings') or self.config.get('章节设置', {})
        self.target_count = chapter_cfg.get('target_chapters') or chapter_cfg.get('目标章数', 20)

    def generate_outline(self, system_prompt):
        logger.info(f"正在生成故事大纲 (迭代模式，目标 {self.target_count} 章)...")
        
        # Phase 1: Core Plot (High-level Arc)
        core_plot = self._generate_core_plot(system_prompt)
        
        # Phase 2: Chapter Skeleton (Titles & One-sentence summaries)
        chapter_skeleton = self._generate_chapter_skeleton(system_prompt, core_plot)
        
        # 确保骨架包含正确的连续章节编号
        for idx, item in enumerate(chapter_skeleton, 1):
            if 'chapter_num' not in item or not str(item['chapter_num']).isdigit():
                item['chapter_num'] = idx

        # Phase 3: Detailed Expansion (Batch processing with auto-verification)
        full_outline_text = f"{core_plot}\n\n### 三、 章节大纲 (详细版)\n\n"
        
        chapter_cfg = self.config.get('chapter_settings') or self.config.get('章节设置', {})
        batch_size = chapter_cfg.get('outline_batch_size', 2)  # 默认每次生成 2 章，确保质量与完整性
        total_chapters = len(chapter_skeleton)
        
        for i in range(0, total_chapters, batch_size):
            batch = chapter_skeleton[i : i + batch_size]
            start_num = batch[0]['chapter_num']
            end_num = batch[-1]['chapter_num']
            
            logger.info(f"正在扩展第 {start_num}-{end_num} 章的大纲细节 (共 {len(batch)} 章)...")
            batch_content = self._expand_batch_with_verification(system_prompt, core_plot, batch)
            full_outline_text += batch_content.strip() + "\n\n"
            
        # 全局完整性校验与单章补缺
        full_outline_text = self._ensure_all_chapters_present(system_prompt, core_plot, chapter_skeleton, full_outline_text)

        save_file(full_outline_text, os.path.join(self.output_dir, "outline.txt"))
        
        # Parse and save structured outline for token optimization
        self.parse_and_save_structured_outline(full_outline_text)
        
        return full_outline_text

    def _extract_chapter_numbers_from_text(self, text):
        """从文本中提取所有出现的大纲章节编号。"""
        found = set()
        # 匹配 ### 第1章、### 第 1 章、### Chapter 1 等
        pattern = r"###\s*(?:第?\s*(\d+)\s*[章.]?|Chapter\s*(\d+))"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            num_str = match.group(1) or match.group(2)
            if num_str and num_str.isdigit():
                found.add(int(num_str))
        return found

    def _expand_batch_with_verification(self, system_prompt, core_plot, batch):
        """扩写一批章节的大纲，并自动校验章节完整性，若有缺失则定向补全。"""
        expected_nums = [c['chapter_num'] for c in batch]
        prompt = get_outline_batch_prompt(system_prompt, core_plot, batch)
        
        batch_content = ""
        for attempt in range(3):
            try:
                batch_content = self.llm.generate_content(prompt)
                if batch_content and batch_content.strip():
                    break
                logger.warning(f"第 {expected_nums[0]}-{expected_nums[-1]} 章大纲生成内容为空 (Attempt {attempt+1}/3)，准备重试...")
            except Exception as e:
                logger.warning(f"第 {expected_nums[0]}-{expected_nums[-1]} 章大纲生成异常 (Attempt {attempt+1}/3): {e}")
                if attempt == 2:
                    raise e

        # 校验是否输出了该批次期望的所有章节
        found_nums = self._extract_chapter_numbers_from_text(batch_content)
        missing_nums = [n for n in expected_nums if n not in found_nums]
        
        if missing_nums:
            logger.warning(f"第 {expected_nums[0]}-{expected_nums[-1]} 章扩写缺少章节: {missing_nums}，正在定向补齐...")
            missing_batch = [c for c in batch if c['chapter_num'] in missing_nums]
            
            for missing_chapter in missing_batch:
                chap_num = missing_chapter['chapter_num']
                logger.info(f"  -> 正在定向补齐 第 {chap_num} 章 大纲...")
                single_prompt = get_outline_batch_prompt(system_prompt, core_plot, [missing_chapter])
                for retry in range(2):
                    try:
                        supp_content = self.llm.generate_content(single_prompt)
                        if supp_content and supp_content.strip():
                            batch_content += "\n\n" + supp_content.strip()
                            break
                    except Exception as e:
                        logger.warning(f"第 {chap_num} 章定向补齐失败 (Attempt {retry+1}): {e}")

        return batch_content

    def _ensure_all_chapters_present(self, system_prompt, core_plot, chapter_skeleton, full_outline_text):
        """终极大纲门禁：校验 1 到 target_count 是否全部存在，若仍有缺失则最终补全。"""
        found_nums = self._extract_chapter_numbers_from_text(full_outline_text)
        expected_nums = [c['chapter_num'] for c in chapter_skeleton]
        missing_nums = [n for n in expected_nums if n not in found_nums]
        
        if not missing_nums:
            logger.info(f"大纲完整性校验通过：已完整覆盖全部 {len(expected_nums)} 章。")
            return full_outline_text

        logger.warning(f"大纲完整性全局检查发现仍缺少 {len(missing_nums)} 章: {missing_nums}，进行最终补齐...")
        for chap_num in missing_nums:
            chap_item = next((c for c in chapter_skeleton if c['chapter_num'] == chap_num), None)
            if not chap_item:
                continue
            logger.info(f"正在为大纲最终补齐 第 {chap_num} 章...")
            single_prompt = get_outline_batch_prompt(system_prompt, core_plot, [chap_item])
            try:
                supp_content = self.llm.generate_content(single_prompt)
                if supp_content and supp_content.strip():
                    full_outline_text += "\n\n" + supp_content.strip()
            except Exception as e:
                logger.error(f"最终补齐第 {chap_num} 章大纲失败: {e}")

        return full_outline_text

    def _generate_core_plot(self, system_prompt):
        logger.info("Phase 1: 生成核心剧情 (Core Plot)...")
        prompt = get_core_plot_prompt(system_prompt)
        return self.llm.generate_content(prompt)

    def _generate_chapter_skeleton(self, system_prompt, core_plot):
        logger.info(f"Phase 2: 生成章节骨架 (目标 {self.target_count} 章)...")
        prompt = get_chapter_skeleton_prompt(system_prompt, core_plot, self.target_count)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.llm.generate_content(prompt, generation_config={"max_output_tokens": 8192})
                skeleton = self._safe_parse_yaml_list(response)
                
                if isinstance(skeleton, list) and len(skeleton) >= self.target_count * 0.8:
                    logger.info(f"骨架生成成功，共 {len(skeleton)} 章。")
                    return skeleton[:self.target_count]
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
        # 优化正则表达式，支持 "### 第1章", "### 1.", "### Chapter 1" 等格式
        header_pattern = r"###\s*(第?\s*\d+\s*[章.]?|Chapter\s*\d+|第?\s*[一二三四五六七八九十百]+\s*[章.]?).*"
        matches = list(re.finditer(header_pattern, chapters_text))
        
        if not matches:
             logger.warning("未在大纲中解析到任何章节标题，请检查大纲格式。")
        
        for i, match in enumerate(matches):
            header = match.group(0).replace("###", "").strip()
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
                # 清理标题，移除 "第1章：" 等前缀
                clean_title = re.sub(r"^(第?\s*\d+\s*[章.]?\s*[:：]?\s*|Chapter\s*\d+\s*[:：]?\s*)", "", header).strip()
                chapter_map[chapter_num] = {
                    'title': clean_title or header,
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
            logger.info(f"结构化大纲已保存，包含 {len(chapter_map)}/{self.target_count} 章详情。")
            
            if len(chapter_map) < self.target_count:
                missing = [n for n in range(1, self.target_count + 1) if n not in chapter_map]
                logger.warning(f"⚠️ 警告：结构化大纲章节数量少于目标章数 ({len(chapter_map)}/{self.target_count})，缺失章节: {missing}")
                
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
                
                structure_path = os.path.join(self.output_dir, "outline_structure.yaml")
                if os.path.exists(structure_path):
                    with open(structure_path, 'r', encoding='utf-8') as f:
                        structure = yaml.safe_load(f)
                    logger.info("已加载结构化大纲。")
                    
                    # 检查结构化大纲是否完整（若低于目标章数的 80%，重新解析或提示）
                    if structure and len(structure.get('chapters', {})) < self.target_count * 0.8:
                        logger.warning(f"结构化大纲章节数不足 ({len(structure.get('chapters', {}))}/{self.target_count})，正在尝试从大纲全文重新解析...")
                        structure = self.parse_and_save_structured_outline(outline)
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
                if chapter_plan and len(chapter_plan) >= self.target_count * 0.8:
                    logger.info(f"已加载已有章节计划，共 {len(chapter_plan)} 章。")
                    return chapter_plan
                elif chapter_plan:
                    logger.warning(f"发现章节计划文件仅包含 {len(chapter_plan)} 章，低于目标 {self.target_count} 章，将重新构建。")
                else:
                    logger.warning("发现空的章节计划文件，将尝试重新提取。")
            except Exception as e:
                logger.error(f"加载章节计划失败: {e}")
        
        # 优先从结构化大纲中按 1 到 target_count 构建计划，保证章节编号对齐不跳号
        _, structure = self.load_outline()
        if structure and structure.get('chapters'):
            logger.info("正在从结构化大纲中严格对齐构建章节计划...")
            chapters = structure['chapters']
            chapter_plan = []
            
            # 严格按照 1 到 target_count 循序构建，绝不压缩或跳号
            for num in range(1, self.target_count + 1):
                if num in chapters:
                    chapter_plan.append({
                        'chapter_num': num,
                        'title': chapters[num]['title'],
                        'summary': chapters[num]['content']
                    })
                else:
                    logger.warning(f"大纲中未找到第 {num} 章，使用默认信息占位。")
                    chapter_plan.append({
                        'chapter_num': num,
                        'title': f"第{num}章",
                        'summary': f"第{num}章情节待定。"
                    })
            
            try:
                with open(chapter_plan_path, 'w', encoding='utf-8') as f:
                    yaml.dump(chapter_plan, f, allow_unicode=True)
                logger.info(f"成功构建并保存章节计划，共 {len(chapter_plan)} 章 (目标: {self.target_count})。")
                return chapter_plan
            except Exception as e:
                logger.error(f"保存章节计划失败: {e}")

        logger.info(f"正在从大纲全文中提取章节计划 (目标章数: {self.target_count})...")
        prompt = get_chapter_plan_prompt(outline, self.target_count)
        generation_config = {"max_output_tokens": 81920}
        
        response = self.llm.generate_content(prompt, generation_config=generation_config)
        chapter_plan = self._safe_parse_yaml_list(response)
        
        if isinstance(chapter_plan, list) and chapter_plan:
            logger.info(f"成功提取了 {len(chapter_plan)} 章 (目标: {self.target_count})")
            # 规范化 chapter_num
            for i, c in enumerate(chapter_plan, 1):
                if isinstance(c, dict) and 'chapter_num' not in c:
                    c['chapter_num'] = i
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
        if not chapter_plan:
            return []
            
        existing_dirs = {}
        try:
            for item in os.listdir(self.output_dir):
                if os.path.isdir(os.path.join(self.output_dir, item)):
                    match = re.match(r"第(\d+)章_(.*)", item)
                    if match:
                        existing_dirs[int(match.group(1))] = item
            
            for i, chapter_info in enumerate(chapter_plan):
                chapter_num = chapter_info.get('chapter_num', i + 1) if isinstance(chapter_info, dict) else (i + 1)
                if chapter_num in existing_dirs:
                    existing_name = existing_dirs[chapter_num]
                    disk_title = existing_name.split('_', 1)[1]
                    
                    if isinstance(chapter_info, dict):
                        if chapter_info.get('title') != disk_title:
                            logger.warning(f"检测到第 {chapter_num} 章已有目录 '{existing_name}'，将同步计划中的标题。")
                            chapter_info['title'] = disk_title
                    else:
                        chapter_plan[i] = {'chapter_num': chapter_num, 'title': disk_title, 'summary': chapter_info}
            
            # Save the reconciled plan back to disk
            chapter_plan_path = os.path.join(self.output_dir, "chapter_plan.yaml")
            with open(chapter_plan_path, 'w', encoding='utf-8') as f:
                yaml.dump(chapter_plan, f, allow_unicode=True)
                
        except Exception as e:
            logger.error(f"协调目录时出错: {e}")
        
        return chapter_plan
