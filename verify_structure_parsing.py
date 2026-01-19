import logging
import os
import yaml
from src.generator import StoryGenerator
from src.utils import load_config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load config
    config_path = "configs/princess_harem.yaml"
    config = load_config(config_path)
    
    # Initialize generator
    generator = StoryGenerator(config)
    
    # Load existing outline
    outline_path = "output/outline.txt"
    if not os.path.exists(outline_path):
        logger.error("Outline file not found. Run verify_iterative_outline.py (or main) first.")
        return
        
    with open(outline_path, 'r', encoding='utf-8') as f:
        full_text = f.read()
        
    logger.info(f"Loaded outline: {len(full_text)} chars.")
    
    # Test Parsing Method
    logger.info("Testing _parse_and_save_structured_outline...")
    generator._parse_and_save_structured_outline(full_text)
    
    # Verify Output
    struct_path = "output/outline_structure.yaml"
    if os.path.exists(struct_path):
        logger.info("SUCCESS: outline_structure.yaml created.")
        
        with open(struct_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        logger.info(f"Core Plot Length: {len(data.get('core_plot', ''))}")
        chapters = data.get('chapters', {})
        logger.info(f"Parsed Chapters Count: {len(chapters)}")
        
        if len(chapters) > 50:
             logger.info("SUCCESS: High chapter count parsed.")
        else:
             logger.warning(f"WARNING: Low chapter count parsed ({len(chapters)}). Parser regex might need tuning.")
             
        # Check Chapter 1 Content
        if 1 in chapters:
            logger.info("Chapter 1 Title: " + chapters[1]['title'])
            logger.info("Chapter 1 Content Preview: " + chapters[1]['content'][:100] + "...")
    else:
        logger.error("FAILURE: outline_structure.yaml was NOT created.")

if __name__ == "__main__":
    main()
