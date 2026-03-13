import os
import yaml
import logging

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.memory_path = os.path.join(output_dir, "memory.yaml")
        self.story_memory = {
            'summary': [],          # 已经发生的故事概要（按章节）
            'foreshadowing': [],    # 埋下的伏笔（未回收）
            'chapter_endings': []   # 每章结尾的细粒度状态（位置/情绪/关系/钩子）
        }
        self.load_memory()

    def update_story_memory(self, chapter_num, data):
        """根据分析结果更新故事记忆。"""
        if not data:
            return

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
        
        self.save_memory()

    def get_chapter_ending_context(self, chapter_num):
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
        return ""

    def get_continuity_section(self):
        """获取用于 Prompt 的连贯性信息部分。"""
        recent_summaries = self.story_memory["summary"][-5:]
        active_foreshadowing = self.story_memory["foreshadowing"]
        
        return (
            "        【故事记忆 (Continuity & Foreshadowing)】:\n"
            f"        近期剧情回顾（最近5章）: {recent_summaries}\n"
            f"        当前活跃的伏笔/悬念: {active_foreshadowing}"
        )

    def save_memory(self):
        """Persist story memory to disk."""
        try:
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.story_memory, f, allow_unicode=True)
            logger.info("故事记忆已保存。")
        except Exception as e:
            logger.error(f"保存记忆失败: {e}")

    def load_memory(self):
        """Load story memory from disk if exists."""
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data:
                        self.story_memory = data
                logger.info("已加载已有故事记忆。")
            except Exception as e:
                logger.error(f"加载记忆失败: {e}")

    def get_completed_chapters(self):
        completed_chapters = set()
        for summary in self.story_memory.get('summary', []):
            import re
            match = re.match(r"第\s*(\d+)\s*章", summary)
            if match:
                completed_chapters.add(int(match.group(1)))
        return completed_chapters
