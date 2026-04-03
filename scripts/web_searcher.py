"""
网页搜索工具模块
使用DuckDuckGo搜索引擎获取最新信息
"""
from typing import Dict, List, Optional
import json


class WebSearcher:
    """网页搜索工具，为Ollama模型提供搜索能力"""
    
    # Ollama工具定义
    SEARCH_TOOL = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索网页获取最新信息，用于补充新闻背景、验证信息或获取最新动态",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，建议使用英文关键词以获得更好的搜索结果"
                    }
                },
                "required": ["query"]
            }
        }
    }
    
    def __init__(self, max_results: int = 5):
        """
        初始化搜索器
        
        Args:
            max_results: 最大搜索结果数量，默认5条
        """
        self.max_results = max_results
        self._check_dependencies()
    
    def _check_dependencies(self):
        """检查依赖是否已安装"""
        try:
            # 尝试使用新包名 ddgs
            from ddgs import DDGS
            self.DDGS = DDGS
        except ImportError:
            try:
                # 回退到旧包名
                from duckduckgo_search import DDGS
                self.DDGS = DDGS
                import warnings
                warnings.warn(
                    "duckduckgo_search 包已重命名为 ddgs，请运行: pip install ddgs",
                    DeprecationWarning
                )
            except ImportError:
                raise ImportError(
                    "请安装 ddgs 库: pip install ddgs"
                )
    
    def search(self, query: str, max_results: Optional[int] = None) -> str:
        """
        执行网页搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数量，None则使用默认值
            
        Returns:
            格式化的搜索结果字符串
        """
        results_count = max_results or self.max_results
        
        try:
            print(f"    🔍 搜索: {query}")
            
            with self.DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=results_count))
            
            if not results:
                return "未找到相关搜索结果。"
            
            # 格式化搜索结果
            formatted_results = []
            for i, result in enumerate(results, 1):
                title = result.get('title', '无标题')
                href = result.get('href', '')
                body = result.get('body', '无摘要')
                
                formatted_results.append(
                    f"[{i}] {title}\n"
                    f"    链接: {href}\n"
                    f"    摘要: {body}"
                )
            
            search_output = "\n\n".join(formatted_results)
            print(f"    ✓ 找到 {len(results)} 条搜索结果")
            
            return search_output
            
        except Exception as e:
            error_msg = f"搜索失败: {str(e)}"
            print(f"    ✗ {error_msg}")
            return error_msg
    
    def search_and_format_for_prompt(self, query: str) -> str:
        """
        搜索并将结果格式化为适合添加到prompt的格式
        
        Args:
            query: 搜索关键词
            
        Returns:
            格式化的搜索结果，可直接添加到prompt中
        """
        results = self.search(query)
        
        if "搜索失败" in results or "未找到" in results:
            return ""
        
        return f"""
【网页搜索结果】
搜索关键词: {query}

{results}

【搜索结果结束】
"""
    
    @staticmethod
    def get_tool_definition() -> Dict:
        """获取工具定义，用于Ollama工具调用"""
        return WebSearcher.SEARCH_TOOL


def test_searcher():
    """测试搜索器功能"""
    print("=" * 60)
    print("🔍 网页搜索工具测试")
    print("=" * 60)
    
    searcher = WebSearcher(max_results=3)
    
    # 测试搜索
    test_query = "Iran Israel conflict latest news"
    print(f"\n测试搜索: {test_query}")
    print("-" * 40)
    
    results = searcher.search(test_query)
    print(results)
    
    print("\n" + "=" * 60)
    print("测试完成")


if __name__ == "__main__":
    test_searcher()