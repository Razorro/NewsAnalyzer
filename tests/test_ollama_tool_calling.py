"""
Ollama Tool Calling 单元测试
测试web_search工具调用功能
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加scripts目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from web_searcher import WebSearcher


class TestWebSearcher(unittest.TestCase):
    """测试WebSearcher类"""
    
    def test_tool_definition_format(self):
        """测试工具定义格式是否正确"""
        tool_def = WebSearcher.get_tool_definition()
        
        # 验证基本结构
        self.assertEqual(tool_def['type'], 'function')
        self.assertEqual(tool_def['function']['name'], 'web_search')
        
        # 验证参数定义
        params = tool_def['function']['parameters']
        self.assertEqual(params['type'], 'object')
        self.assertIn('query', params['properties'])
        self.assertIn('query', params['required'])
        
        print("✓ 工具定义格式正确")
    
    @patch('duckduckgo_search.DDGS')
    def test_search_success(self, mock_ddgs):
        """测试搜索成功场景"""
        # 模拟搜索结果
        mock_results = [
            {
                'title': 'Test Title 1',
                'href': 'https://example.com/1',
                'body': 'Test description 1'
            },
            {
                'title': 'Test Title 2',
                'href': 'https://example.com/2',
                'body': 'Test description 2'
            }
        ]
        
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = mock_results
        mock_ddgs.return_value.__enter__.return_value = mock_ddgs_instance
        
        # 创建搜索器并执行搜索
        searcher = WebSearcher(max_results=5)
        result = searcher.search("test query")
        
        # 验证结果
        self.assertIn('Test Title 1', result)
        self.assertIn('https://example.com/1', result)
        self.assertIn('Test Title 2', result)
        
        print("✓ 搜索成功测试通过")
    
    @patch('duckduckgo_search.DDGS')
    def test_search_no_results(self, mock_ddgs):
        """测试无搜索结果场景"""
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = []
        mock_ddgs.return_value.__enter__.return_value = mock_ddgs_instance
        
        searcher = WebSearcher(max_results=5)
        result = searcher.search("nonexistent query xyz123")
        
        self.assertIn('未找到', result)
        print("✓ 无结果测试通过")
    
    @patch('duckduckgo_search.DDGS')
    def test_search_error_handling(self, mock_ddgs):
        """测试搜索错误处理"""
        mock_ddgs.side_effect = Exception("Network error")
        
        searcher = WebSearcher(max_results=5)
        result = searcher.search("test query")
        
        self.assertIn('搜索失败', result)
        self.assertIn('Network error', result)
        print("✓ 错误处理测试通过")


class TestOllamaToolCalling(unittest.TestCase):
    """测试Ollama工具调用功能"""
    
    @patch('ollama_analyzer.ollama')
    def test_chat_without_tool_calls(self, mock_ollama):
        """测试没有工具调用的普通对话"""
        # 模拟普通响应
        mock_ollama.chat.return_value = {
            'message': {
                'content': 'This is a normal response without tool calls.'
            }
        }
        
        from ollama_analyzer import OllamaAnalyzer
        
        # 创建分析器（禁用搜索以避免初始化问题）
        with patch.object(OllamaAnalyzer, '__init__', lambda self, **kwargs: None):
            analyzer = OllamaAnalyzer()
            analyzer.search_enabled = False
            analyzer.searcher = None
            analyzer.analysis_model = 'test-model'
            
            messages = [{'role': 'user', 'content': 'test'}]
            result = analyzer._chat_with_tools('test-model', messages, use_search=False)
        
        self.assertEqual(result, 'This is a normal response without tool calls.')
        print("✓ 普通对话测试通过")
    
    @patch('ollama_analyzer.ollama')
    def test_chat_with_tool_calls(self, mock_ollama):
        """测试带工具调用的对话"""
        print("\n" + "="*60)
        print("📋 测试场景：用户询问伊朗局势，模型触发web search")
        print("="*60)
        
        # 用户的原始问题
        user_question = 'What is happening in Iran?'
        print(f"\n👤 用户问题: {user_question}")
        
        # 第一次调用：返回工具调用请求
        tool_call_response = {
            'message': {
                'content': '',
                'tool_calls': [{
                    'function': {
                        'name': 'web_search',
                        'arguments': {
                            'query': 'Iran Israel conflict'
                        }
                    }
                }]
            }
        }
        
        # 第二次调用：返回最终回答
        final_response = {
            'message': {
                'content': 'Based on the search results, the conflict continues...'
            }
        }
        
        mock_ollama.chat.side_effect = [tool_call_response, final_response]
        
        from ollama_analyzer import OllamaAnalyzer
        
        with patch.object(OllamaAnalyzer, '__init__', lambda self, **kwargs: None):
            analyzer = OllamaAnalyzer()
            analyzer.search_enabled = True
            analyzer.search_max_results = 5
            analyzer.analysis_model = 'test-model'
            
            # 模拟搜索器 - 返回真实的搜索结果
            mock_searcher = Mock()
            search_result = """[1] Iran launches missile attack on Israel
    链接: https://news.example.com/iran-missile
    摘要: Iran has launched a missile attack on Israel, escalating tensions in the Middle East...

[2] Israel responds to Iran attack
    链接: https://news.example.com/israel-response
    摘要: Israel has vowed to respond to Iran's missile attack..."""
            
            mock_searcher.search.return_value = search_result
            mock_searcher.get_tool_definition.return_value = {
                'type': 'function',
                'function': {'name': 'web_search'}
            }
            analyzer.searcher = mock_searcher
            
            messages = [{'role': 'user', 'content': user_question}]
            
            print(f"\n🤖 模型响应: 请求调用 web_search 工具")
            print(f"   搜索关键词: 'Iran Israel conflict'")
            
            result = analyzer._chat_with_tools('test-model', messages, use_search=True)
            
            print(f"\n🔍 搜索返回内容:")
            print(search_result)
            
            print(f"\n🤖 模型最终回答:")
            print(f"   {result}")
        
        # 验证搜索被调用
        mock_searcher.search.assert_called_once()
        
        # 验证最终结果
        self.assertIn('conflict continues', result)
        print("\n✓ 工具调用测试通过")
    
    @patch('ollama_analyzer.ollama')
    def test_tool_call_error_recovery(self, mock_ollama):
        """测试工具调用错误恢复"""
        # 模拟工具调用后搜索失败
        tool_call_response = {
            'message': {
                'content': '',
                'tool_calls': [{
                    'function': {
                        'name': 'web_search',
                        'arguments': {'query': 'test'}
                    }
                }]
            }
        }
        
        # 搜索失败后，模型返回错误处理响应
        error_response = {
            'message': {
                'content': 'Search failed, but here is my analysis based on existing knowledge...'
            }
        }
        
        mock_ollama.chat.side_effect = [tool_call_response, error_response]
        
        from ollama_analyzer import OllamaAnalyzer
        
        with patch.object(OllamaAnalyzer, '__init__', lambda self, **kwargs: None):
            analyzer = OllamaAnalyzer()
            analyzer.search_enabled = True
            analyzer.search_max_results = 5
            analyzer.analysis_model = 'test-model'
            
            # 模拟搜索失败
            mock_searcher = Mock()
            mock_searcher.search.return_value = "搜索失败: Network error"
            mock_searcher.get_tool_definition.return_value = {'type': 'function', 'function': {'name': 'web_search'}}
            analyzer.searcher = mock_searcher
            
            messages = [{'role': 'user', 'content': 'test'}]
            result = analyzer._chat_with_tools('test-model', messages, use_search=True)
        
        self.assertIn('existing knowledge', result)
        print("✓ 错误恢复测试通过")


class TestToolCallingIntegration(unittest.TestCase):
    """集成测试：完整的工具调用流程"""
    
    @patch('ollama_analyzer.ollama')
    @patch('duckduckgo_search.DDGS')
    def test_full_tool_calling_flow(self, mock_ddgs, mock_ollama):
        """测试完整的工具调用流程"""
        # 模拟搜索结果
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {
                'title': 'Iran launches missile attack',
                'href': 'https://news.example.com/iran',
                'body': 'Iran has launched missiles at Israel...'
            }
        ]
        mock_ddgs.return_value.__enter__.return_value = mock_ddgs_instance
        
        # 模拟Ollama响应
        tool_call_response = {
            'message': {
                'content': '',
                'tool_calls': [{
                    'function': {
                        'name': 'web_search',
                        'arguments': {'query': 'Iran Israel latest news'}
                    }
                }]
            }
        }
        
        final_response = {
            'message': {
                'content': '{"analysis": "Based on search results, Iran has launched missiles..."}'
            }
        }
        
        mock_ollama.chat.side_effect = [tool_call_response, final_response]
        
        from ollama_analyzer import OllamaAnalyzer
        
        with patch.object(OllamaAnalyzer, '__init__', lambda self, **kwargs: None):
            analyzer = OllamaAnalyzer()
            analyzer.search_enabled = True
            analyzer.search_max_results = 5
            analyzer.analysis_model = 'test-model'
            
            # 使用真实的WebSearcher
            analyzer.searcher = WebSearcher(max_results=5)
            
            messages = [{'role': 'user', 'content': 'Analyze Iran situation'}]
            result = analyzer._chat_with_tools('test-model', messages, use_search=True)
        
        # 验证结果包含搜索内容
        self.assertIn('missiles', result)
        print("✓ 完整流程测试通过")


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 Ollama Tool Calling 单元测试")
    print("=" * 60)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestWebSearcher))
    suite.addTests(loader.loadTestsFromTestCase(TestOllamaToolCalling))
    suite.addTests(loader.loadTestsFromTestCase(TestToolCallingIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ 所有测试通过!")
    else:
        print("❌ 部分测试失败")
        if result.failures:
            print(f"   失败: {len(result.failures)}")
        if result.errors:
            print(f"   错误: {len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()