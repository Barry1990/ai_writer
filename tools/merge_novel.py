import os
import re
import yaml
import sys

import argparse

def load_config(config_path):
    """Loads configuration from a YAML file."""
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config {config_path}: {e}")
        return None

def get_novel_title(output_dir, configs_dir="configs"):
    """
    Attempts to find the novel title.
    1. From outline_structure.yaml if it exists in output_dir.
    2. From the most recently modified config file.
    """
    
    # Priority 1: Check output_dir for existing structure info
    structure_path = os.path.join(output_dir, "outline_structure.yaml")
    if os.path.exists(structure_path):
        config = load_config(structure_path)
        if config and 'novel_title' in config: # If we added it there (planning to)
             return config['novel_title']
        
    # Check outline.txt for a title? Usually "### 第1章" style, hard to parse title from filename.
    # Fallback to config scanning
    if os.path.exists(configs_dir):
        yaml_files = [
            os.path.join(configs_dir, f) 
            for f in os.listdir(configs_dir) 
            if f.endswith('.yaml') or f.endswith('.yml')
        ]
        
        if yaml_files:
            # Sort by modification time, newest first
            yaml_files.sort(key=os.path.getmtime, reverse=True)
            for cfg_path in yaml_files:
                config = load_config(cfg_path)
                if config and '故事' in config and '标题' in config['故事']:
                    return config['故事']['标题']

    # Final fallback: use the directory name itself
    return os.path.basename(os.path.abspath(output_dir))

def natural_sort_key(s):
    """
    Key for natural sorting (e.g., sorting ["1", "2", "10"] correctly).
    EXTRACTS THE FIRST NUMBER found in the string.
    """
    numbers = re.findall(r'\d+', s)
    if numbers:
        return int(numbers[0])
    return 0

def merge_novel(output_dir):
    if not os.path.exists(output_dir):
        print(f"Output directory '{output_dir}' not found.")
        return

    novel_title = get_novel_title(output_dir)
    output_filename = os.path.join(output_dir, f"{novel_title}.txt")
    
    print(f"Merging novel from '{output_dir}'...")
    print(f"Novel Title: {novel_title}")

    merged_content = []
    
    # Add title
    merged_content.append(f"{novel_title}\n\n")

    # Get chapter directories
    chapters = []
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path) and "第" in item and "章" in item:
            chapters.append(item)
    
    # Sort chapters by number
    chapters.sort(key=natural_sort_key)

    if not chapters:
        print(f"No chapters found in '{output_dir}'.")
        return

    for chapter_dir_name in chapters:
        chapter_path = os.path.join(output_dir, chapter_dir_name)
        
        # Add Chapter Title
        chapter_title_formatted = chapter_dir_name.replace('_', ' ')
        merged_content.append(f"\n\n{chapter_title_formatted}\n\n")
        print(f"Processing {chapter_dir_name}...")
        
        # Get section files
        sections = []
        for item in os.listdir(chapter_path):
            if item.endswith(".txt") and "第" in item and "节" in item:
                sections.append(item)
        
        # Sort sections by number
        sections.sort(key=natural_sort_key)
        
        for section_file in sections:
            section_path = os.path.join(chapter_path, section_file)
            try:
                with open(section_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    merged_content.append(content)
                    merged_content.append("\n\n") # Separator between sections
            except Exception as e:
                print(f"Error reading {section_path}: {e}")

    # Write to file
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write("".join(merged_content))
        print(f"\nSuccess! Merged novel saved to: {os.path.abspath(output_filename)}")
    except Exception as e:
        print(f"Error writing output file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="合并小说章节")
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
        merge_novel(target_dir)
    else:
        print("Error: No directory found to merge. Please specify with --dir")
