import logging
import os
from src.utils import setup_logging
from src.llm import GeminiClient

def main():
    # 1. Setup Logging
    log_file = "verify_logging.log"
    if os.path.exists(log_file):
        os.remove(log_file)
        
    setup_logging(log_level=logging.DEBUG, log_file=log_file)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting logging verification...")
    
    # 2. Make a simple API call
    try:
        client = GeminiClient()
        response = client.generate_content("Hello! Please reply with 'Logging Test'.")
        logger.info(f"API Response: {response}")
    except Exception as e:
        logger.error(f"API Call Failed: {e}")
        return

    # 3. Verify Log File Content
    logger.info("Verifying log file content...")
    
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"Log File Size: {len(content)} bytes")
        
        has_token_usage = "Token 使用统计" in content
        has_prompt = "提示词输入" in content
        
        if has_token_usage and has_prompt:
            print("SUCCESS: Log file contains Token Usage and Prompt.")
        else:
            print(f"FAILURE: Missing logs. Token Usage: {has_token_usage}, Prompt: {has_prompt}")
    else:
        print("FAILURE: Log file was not created.")

if __name__ == "__main__":
    main()
