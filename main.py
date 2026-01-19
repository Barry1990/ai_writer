import logging
import os
import argparse
from src.utils import setup_logging, load_config
from src.generator import StoryGenerator

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Check for configs directory
    configs_dir = os.path.join(os.path.dirname(__file__), "configs")
    if not os.path.exists(configs_dir):
        os.makedirs(configs_dir, exist_ok=True)
        # Fallback if no configs exist yet? Handled by initial copy in previous steps.

    parser = argparse.ArgumentParser(description="AI 小说生成器")
    parser.add_argument("--config", help="配置文件路径", default=None)
    parser.add_argument("--list", action="store_true", help="列出可用配置")
    args = parser.parse_args()
    
    config_path = args.config
    
    # Interactive Selection if no config specified
    if not config_path:
        print("\n=== AI 小说生成器配置选择 ===\n")
        
        # Scan configs directory
        config_files = [f for f in os.listdir(configs_dir) if f.endswith('.yaml') or f.endswith('.yml')]
        
        # Also check root config.yaml
        root_config = "config.yaml"
        if os.path.exists(root_config):
            config_files.insert(0, root_config)
            
        if not config_files:
            logger.error("在 'configs/' 目录或根目录下未找到配置文件。")
            return

        print("可用配置列表:")
        for idx, f in enumerate(config_files):
            # Try to read the title from the yaml for better display
            try:
                # Quick read max 10 lines to find "标题"
                title = "未知标题"
                with open(os.path.join(configs_dir if f != root_config else ".", f), 'r', encoding='utf-8') as yml:
                    for _ in range(20):
                        line = yml.readline()
                        if "标题:" in line:
                            title = line.split("标题:")[1].strip().strip('"')
                            break
                print(f"{idx + 1}. {f}  \t(标题: {title})")
            except:
                print(f"{idx + 1}. {f}")
        
        print("\n0. 退出")
        
        try:
            choice = input("\n请选择一个配置 (输入数字): ")
            if choice == '0':
                return
            
            selected_idx = int(choice) - 1
            if 0 <= selected_idx < len(config_files):
                selected_file = config_files[selected_idx]
                config_path = os.path.join(configs_dir if selected_file != root_config else ".", selected_file)
            else:
                print("选择无效。")
                return
        except ValueError:
            print("输入无效。")
            return

    if not config_path:
        return

    try:
        print(f"\n正在加载配置: {config_path} ...")
        config = load_config(config_path)
        logger.info(f"配置已加载: {config_path}")
        
        generator = StoryGenerator(config)
        generator.run()
        
        logger.info("故事生成完成。")
        
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)

if __name__ == "__main__":
    main()
