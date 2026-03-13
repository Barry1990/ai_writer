import logging
import os
import yaml
from dotenv import load_dotenv

def setup_logging(log_level=logging.INFO, log_file="ai_writer.log"):
    """Sets up logging configuration and loads environment variables."""
    # Load environment variables from .env file
    load_dotenv(override=True)
    
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # Console Handler
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # File Handler
    if log_file:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

def load_config(config_path):
    """Loads configuration from a YAML file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到配置文件: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_file(content, filepath):
    """Saves content to a file, creating directories if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"已保存文件: {filepath}")

def read_file(filepath):
    """Reads content from a file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"找不到文件: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()
