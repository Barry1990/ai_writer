import os
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class LLMClient(ABC):
    """LLM 客户端抽象基类"""
    @abstractmethod
    def generate_content(self, prompt, generation_config=None):
        pass

class GeminiClient(LLMClient):
    def __init__(self, api_key=None, model_name="gemini-3-flash-preview", base_url=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API Key must be provided or set in GEMINI_API_KEY environment variable.")
        
        import google.generativeai as genai
        # 配置 API Key
        config_params = {"api_key": self.api_key}
        
        # 如果提供了 base_url，则通过 client_options 设置 api_endpoint
        # 注意：genai 的 api_endpoint 通常需要去掉协议头或符合特定格式，这里做个简单兼容
        if base_url:
            from google.api_core import client_options
            options = client_options.ClientOptions(api_endpoint=base_url.replace("https://", "").replace("http://", "").rstrip("/"))
            config_params["client_options"] = options
            logger.info(f"Gemini 将使用自定义地址: {base_url}")

        genai.configure(**config_params)
        self.model = genai.GenerativeModel(model_name)
        
        # Configure safety settings to avoid blocking content
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        logger.info(f"已初始化 Gemini 客户端，模型: {model_name}")

    def generate_content(self, prompt, generation_config=None):
        """Generates content using the Gemini model."""
        try:
            logger.info("--------------------------------------------------")
            logger.info("Gemini: 准备生成内容...")
            logger.debug(f"提示词输入 (PROMPT INPUT):\n{prompt}")
            
            response = self.model.generate_content(
                prompt, 
                generation_config=generation_config,
                safety_settings=self.safety_settings
            )
            
            # Log Token Usage
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                logger.info(f"Token 使用统计: 提示词: {usage.prompt_token_count}, 输出: {usage.candidates_token_count}, 总计: {usage.total_token_count}")
            
            logger.debug(f"API 响应输出 (RESPONSE OUTPUT):\n{response.text[:500]}...[已截断]")
            
            return response.text
        except Exception as e:
            logger.error(f"调用 Gemini API 时发生错误: {e}")
            raise

class OpenAIClient(LLMClient):
    def __init__(self, api_key=None, model_name="gpt-4o", base_url=None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API Key must be provided or set in OPENAI_API_KEY environment variable.")
        
        try:
            from openai import OpenAI
            # 支持自定义 base_url (兼容 OpenAI 的其他提供商)
            # 只有当 base_url 确实有值时才传入，否则 OpenAI SDK 使用默认值
            self.client = OpenAI(api_key=self.api_key, base_url=base_url)
            self.model_name = model_name
            logger.info(f"已初始化 OpenAI 客户端，模型: {model_name}" + (f"，地址: {base_url}" if base_url else ""))
        except ImportError:
            logger.error("未安装 openai 库，请运行 'pip install openai'")
            raise

    def generate_content(self, prompt, generation_config=None):
        """Generates content using the OpenAI model."""
        try:
            logger.info("--------------------------------------------------")
            logger.info("OpenAI: 准备生成内容...")
            logger.debug(f"提示词输入 (PROMPT INPUT):\n{prompt}")

            # 转换 generation_config (如果需要)
            # 这里简单处理，OpenAI 与 Gemini 的参数名不完全一致
            params = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            if generation_config:
                if "temperature" in generation_config:
                    params["temperature"] = generation_config["temperature"]
                if "max_output_tokens" in generation_config:
                    params["max_tokens"] = generation_config["max_output_tokens"]

            response = self.client.chat.completions.create(**params)
            
            content = response.choices[0].message.content
            
            # Log Token Usage
            usage = response.usage
            logger.info(f"Token 使用统计: 提示词: {usage.prompt_tokens}, 输出: {usage.completion_tokens}, 总计: {usage.total_tokens}")
            
            logger.debug(f"API 响应输出 (RESPONSE OUTPUT):\n{content[:500]}...[已截断]")
            
            return content
        except Exception as e:
            if "insufficient" in str(e).lower() or "balance" in str(e).lower():
                logger.error("❌ OpenAI API 余额不足：请检查您的账户余额或充值。")
            else:
                logger.error(f"调用 OpenAI API 时发生错误: {e}")
            raise

def get_llm_client(llm_config=None):
    """
    工厂方法获取 LLM 客户端。
    llm_config 格式:
    {
        'provider': 'openai', # 或 'gemini'
        'model': 'gpt-4o',
        'api_key': '...' (可选),
        'base_url': '...' (可选)
    }
    """
    if not llm_config:
        llm_config = {}

    # 优先级：配置文件 > 环境变量 LLM_PROVIDER > 默认 'gemini'
    provider = llm_config.get('provider') or os.environ.get("LLM_PROVIDER", "gemini")
    provider = provider.lower()
    
    model = llm_config.get('model')
    api_key = llm_config.get('api_key')
    
    # 逻辑：配置优先，环境变量次之。如果值为空字符串，则视为 None 使用默认地址或模型。
    def get_env_val(key):
        val = os.environ.get(key)
        return val if val and val.strip() else None

    if provider == 'openai':
        base_url = llm_config.get('base_url') or get_env_val("OPENAI_BASE_URL")
        default_model = get_env_val("OPENAI_MODEL") or "gpt-4o"
        return OpenAIClient(api_key=api_key, model_name=model or default_model, base_url=base_url)
    elif provider == 'gemini':
        base_url = llm_config.get('base_url') or get_env_val("GEMINI_BASE_URL")
        default_model = get_env_val("GEMINI_MODEL") or "gemini-3-flash-preview"
        return GeminiClient(api_key=api_key, model_name=model or default_model, base_url=base_url)
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")
