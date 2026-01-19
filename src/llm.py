import os
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key=None, model_name="gemini-3-flash-preview"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API Key must be provided or set in GEMINI_API_KEY environment variable.")
        
        genai.configure(api_key=self.api_key)
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
            logger.info("准备生成内容...")
            # Log prompt carefully (it might be huge)
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
        except ValueError as e:
            # Handle cases where response.text is not available (e.g., safety block or finish reason 8)
            logger.error(f"生成内容失败: {e}")
            if 'response' in locals():
                logger.error(f"Response feedback: {response.prompt_feedback}")
                if response.candidates:
                     logger.error(f"Candidate finish reason: {response.candidates[0].finish_reason}")
                     logger.error(f"Candidate safety ratings: {response.candidates[0].safety_ratings}")
            raise
        except Exception as e:
            logger.error(f"调用 Gemini API 时发生未知错误: {e}")
            raise
