import os
import re
import yaml
import sys

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

def get_novel_title(configs_dir="configs"):
    """
    Finds the most recently modified config file in the configs directory
    and extracts the novel title.
    """
    if not os.path.exists(configs_dir):
        return "Merged_Novel"

    yaml_files = [
        os.path.join(configs_dir, f) 
        for f in os.listdir(configs_dir) 
        if f.endswith('.yaml') or f.endswith('.yml')
    ]
    
    if not yaml_files:
        return "Merged_Novel"

    # Sort by modification time, newest first
    yaml_files.sort(key=os.path.getmtime, reverse=True)
    
    latest_config_path = yaml_files[0]
    print(f"Using configuration file: {latest_config_path}")
    
    config = load_config(latest_config_path)
    if config and '故事' in config and '标题' in config['故事']:
        return config['故事']['标题']
    
    return "Merged_Novel"

def natural_sort_key(s):
    """
    Key for natural sorting (e.g., sorting ["1", "2", "10"] correctly).
    EXTRACTS THE FIRST NUMBER found in the string.
    """
    numbers = re.findall(r'\d+', s)
    if numbers:
        return int(numbers[0])
    return 0

def merge_novel(output_dir="output"):
    if not os.path.exists(output_dir):
        print(f"Output directory '{output_dir}' not found.")
        return

    novel_title = get_novel_title()
    output_filename = f"{novel_title}.txt"
    
    print(f"Merging novel '{novel_title}' from '{output_dir}'...")

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

    for chapter_dir_name in chapters:
        chapter_path = os.path.join(output_dir, chapter_dir_name)
        
        # Add Chapter Title (the directory name usually contains it)
        # Format: 第X章_Title -> 第X章 Title
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
    merge_novel()
