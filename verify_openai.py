import os
import unittest
from unittest.mock import MagicMock, patch
import sys

# 将 src 目录添加到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.llm import get_llm_client, OpenAIClient, GeminiClient

class TestLLMClient(unittest.TestCase):

    def test_factory_gemini_default(self):
        client = get_llm_client()
        self.assertIsInstance(client, GeminiClient)

    def test_factory_openai(self):
        # Mocking OpenAI to avoid actual API calls and dependency on API key during initialization
        with patch('openai.OpenAI') as mock_openai:
            os.environ["OPENAI_API_KEY"] = "sk-test-key"
            client = get_llm_client({'provider': 'openai', 'model': 'gpt-4o'})
            self.assertIsInstance(client, OpenAIClient)
            self.assertEqual(client.model_name, "gpt-4o")

    @patch('openai.OpenAI')
    def test_openai_generate_content(self, mock_openai_class):
        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="模拟的 OpenAI 响应"))]
        mock_completion.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        
        mock_client.chat.completions.create.return_value = mock_completion
        
        os.environ["OPENAI_API_KEY"] = "sk-test-key"
        client = OpenAIClient(model_name="gpt-4o")
        
        response = client.generate_content("你好", generation_config={"temperature": 0.7})
        
        self.assertEqual(response, "模拟的 OpenAI 响应")
        mock_client.chat.completions.create.assert_called_once()
        args, kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(kwargs['model'], "gpt-4o")
        self.assertEqual(kwargs['temperature'], 0.7)
        self.assertEqual(kwargs['messages'], [{"role": "user", "content": "你好"}])

if __name__ == "__main__":
    unittest.main()
