import os
import re
import yaml
import sys
import logging
import argparse

# 将项目根目录添加到路径，以便导入 src 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llm import get_llm_client
from src.utils import setup_logging

logger = logging.getLogger(__name__)

def natural_sort_key(s):
    """自然排序键，提取第一个数字。"""
    numbers = re.findall(r'\d+', s)
    if numbers:
        return int(numbers[0])
    return 0

def load_text(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def get_all_sections(output_dir):
    """按顺序获取所有小节的信息。"""
    all_sections = []
    if not os.path.exists(output_dir):
        return []
        
    chapter_dirs = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d)) and "第" in d and "章" in d]
    chapter_dirs.sort(key=natural_sort_key)
    
    for c_dir in chapter_dirs:
        c_path = os.path.join(output_dir, c_dir)
        sections = [f for f in os.listdir(c_path) if f.endswith(".txt") and "第" in f and "节" in f]
        sections.sort(key=natural_sort_key)
        for s_file in sections:
            content = load_text(os.path.join(c_path, s_file))
            all_sections.append({
                "chapter": c_dir,
                "section": s_file,
                "content": content
            })
    return all_sections

def extract_edges(text, lines=15):
    """提取文本的首尾各若干行。始终返回 (head, tail) 元组。"""
    all_lines = text.strip().split('\n')
    if not all_lines:
        return "", ""
    head = "\n".join(all_lines[:lines])
    tail = "\n".join(all_lines[-lines:])
    return head, tail

def analyze_novel(output_dir):
    setup_logging(log_file=os.path.join(output_dir, "novel_analysis.log"))
    logger.info(f"开始对目录 {output_dir} 进行小说衔接连贯性专项分析...")
    
    if not os.path.exists(output_dir):
        print(f"找不到输出目录: {output_dir}")
        return

    sections = get_all_sections(output_dir)
    if len(sections) < 2:
        print("章节数量不足，无法进行衔接性分析。")
        return

    # 构建衔接对照组
    comparison_data = []
    for i in range(len(sections) - 1):
        prev = sections[i]
        curr = sections[i+1]
        
        _, prev_tail = extract_edges(prev['content'])
        curr_head, _ = extract_edges(curr['content'])
        
        comparison_data.append(f"""
【衔接组 {i+1}】
<<< 上文结束点: {prev['chapter']} - {prev['section']} >>>
{prev_tail}

>>> 下文开始点: {curr['chapter']} - {curr['section']} >>>
{curr_head}
--------------------------------------------------
""")

    comparison_text = "\n".join(comparison_data)

    # 初始化 LLM
    llm = get_llm_client()
    
    # 构建精准分析 Prompt
    prompt = f"""
    角色: 你是一位极其严苛的小说审校专家，专门负责检测连贯性断层。
    任务: 给出以下小说相邻【衔接组】的衔接性评估。你需要判断前一节的结尾到下一节的开始时，剧情、动作、环境或逻辑是否存在“断层”或“剧烈跳跃”。
    
    分析重点:
    1. **动作衔接**: 前一秒主角在喝茶，后一秒是否突然在打仗而没有交代过程？
    2. **环境一致性**: 环境描写是否突变（如深夜转瞬间变正午）？
    3. **逻辑延续**: 前文提到的紧急情况，在后文开头是否被无视了？
    4. **语气跳跃**: 角色的情绪或叙事的基调是否发生了不自然的转变？
    
    【待分析衔接片段】
    {comparison_text[:12000]}... (仅分析前 12000 字相关片段)
    
    请输出一份专项分析报告：
    
    # 小说章节衔接性连贯性专项报告
    
    ## 总体评估: [流畅 / 轻微跳跃 / 严重断层]
    
    ## 详细节点排查 (请指出具体哪一组衔接有问题):
    - [衔接组 X]: 问题描述 (如果没问题则略过)
    
    ## 核心问题总结:
    ...
    
    ## 改进建议:
    ...
    
    请用中文回复。
    """
    
    print("\n正在针对章节“首尾衔接处”进行专项分析，请稍候...\n")
    try:
        analysis_report = llm.generate_content(prompt, generation_config={"max_output_tokens": 4096})
        
        report_path = os.path.join(output_dir, "transition_analysis_report.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(analysis_report)
            
        print("=" * 50)
        print(analysis_report)
        print("=" * 50)
        print(f"\n专项分析报告已保存至: {os.path.abspath(report_path)}")
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        print(f"分析过程中发生错误: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="分析小说衔接性")
    parser.add_argument("--dir", help="小说内容所在目录 (例如 output/我的小说)", default=None)
    args = parser.parse_args()

    target_dir = args.dir
    if not target_dir:
        # Default to the most recently modified directory in output/
        base_output = "output"
        if os.path.exists(base_output):
            subdirs = [os.path.join(base_output, d) for d in os.listdir(base_output) if os.path.isdir(os.path.join(base_output, d))]
            if subdirs:
                subdirs.sort(key=os.path.getmtime, reverse=True)
                target_dir = subdirs[0]
                print(f"No directory specified. Using most recent: {target_dir}")
    
    if target_dir:
        analyze_novel(target_dir)
    else:
        print("Error: No directory found to analyze. Please specify with --dir")
