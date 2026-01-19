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
    config_path = "configs/princess_harem.yaml" # This has 60 chapters target
    config = load_config(config_path)
    
    # Initialize generator
    generator = StoryGenerator(config)
    
    # Run outline generation only
    logger.info("Starting iterative outline generation test...")
    outline = generator.generate_outline()
    
    # Verify basics
    if not outline:
        logger.error("FAILURE: Outline is empty.")
        return

    # Check file size/length
    lines = outline.split('\n')
    logger.info(f"Generated outline length: {len(outline)} characters, {len(lines)} lines.")
    
    # Check for chapter headers
    chapter_headers = [line for line in lines if "###" in line and "章" in line]
    logger.info(f"Found {len(chapter_headers)} chapter headers in the outline text.")
    
    if len(chapter_headers) >= 55: # Allow some variance but should be close to 60
        logger.info("SUCCESS: Outline generation covers the target chapter count.")
    else:
        logger.warning(f"FAILURE: Expected ~60 chapters, found {len(chapter_headers)}.")

if __name__ == "__main__":
    main()
