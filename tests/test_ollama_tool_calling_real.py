"""
Ollama Tool Calling 集成测试
真正调用Web搜索和Ollama API
"""
import sys
import os
import json

# 添加scripts目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from web_searcher import WebSearcher


def test_real_web_search():
    """测试真实的Web搜索"""
    print("\n" + "="*60)
    print("🔍 真实Web搜索测试")
    print("="*60)
    
    searcher = WebSearcher(max_results=3)
    
    # 测试搜索
    query = "Iran Israel conflict latest news 2026"
    print(f"\n📡 搜索关键词: {query}")
    print("-" * 40)
    
    results = searcher.search(query)
    print(results)
    
    return results


def test_ollama_tool_calling_with_real_search():
    """测试Ollama tool calling（使用真实搜索）"""
    print("\n" + "="*60)
    print("🤖 Ollama Tool Calling 集成测试")
    print("="*60)
    
    try:
        import ollama
    except ImportError:
        print("❌ ollama 库未安装，请运行: pip install ollama")
        return False
    
    # 初始化搜索器
    searcher = WebSearcher(max_results=3)
    
    # 用户问题
    user_question = "What is the latest situation between Iran and Israel?"
    print(f"\n👤 用户问题: {user_question}")
    print("-" * 40)
    
    # 构建消息
    messages = [
        {
            "role": "user",
            "content": user_question
        }
    ]
    
    # 工具定义
    tools = [searcher.get_tool_definition()]
    
    try:
        print("\n🤖 第一次调用Ollama（请求工具调用）...")
        
        # 第一次调用：让模型决定是否需要搜索
        response = ollama.chat(
            model="glm-4.6:cloud",  # 使用配置的模型
            messages=messages,
            tools=tools,
            options={"temperature": 0.3}
        )
        
        # 检查是否有工具调用
        if response.get('message', {}).get('tool_calls'):
            print("✅ 模型请求调用 web_search 工具")
            
            # 获取工具调用信息
            tool_call = response['message']['tool_calls'][0]
            function_name = tool_call['function']['name']
            arguments = tool_call['function']['arguments']
            
            print(f"   工具名称: {function_name}")
            print(f"   搜索参数: {arguments}")
            
            # 将模型的响应添加到消息列表
            messages.append(response['message'])
            
            # 执行真实的搜索
            print("\n🔍 执行真实搜索...")
            search_query = arguments.get('query', '')
            search_results = searcher.search(search_query)
            
            print(f"\n📄 搜索结果:")
            print(search_results)
            
            # 将搜索结果添加到消息列表
            messages.append({
                "role": "tool",
                "content": search_results
            })
            
            # 第二次调用：将搜索结果返回给模型
            print("\n🤖 第二次调用Ollama（返回搜索结果）...")
            final_response = ollama.chat(
                model="glm-4.6:cloud",
                messages=messages,
                options={"temperature": 0.3}
            )
            
            final_answer = final_response['message']['content']
            print(f"\n💬 模型最终回答:")
            print(final_answer)
            
            return True
            
        else:
            # 模型没有请求工具调用，直接返回回答
            print("ℹ️ 模型未请求工具调用，直接回答")
            answer = response['message']['content']
            print(f"\n💬 模型回答:")
            print(answer)
            return True
            
    except Exception as e:
        print(f"❌ Ollama调用失败: {e}")
        print("\n💡 可能的原因:")
        print("   1. Ollama服务未启动")
        print("   2. 模型名称不正确")
        print("   3. 网络连接问题")
        return False


def test_direct_search_and_analyze():
    """直接搜索并分析（不依赖Ollama tool calling）"""
    print("\n" + "="*60)
    print("📊 直接搜索+分析测试")
    print("="*60)
    
    # 1. 执行搜索
    searcher = WebSearcher(max_results=5)
    query = "Iran Israel military conflict 2026"
    
    print(f"\n🔍 搜索: {query}")
    print("-" * 40)
    
    search_results = searcher.search(query)
    print(search_results)
    
    # 2. 尝试用Ollama分析搜索结果
    try:
        import ollama
        
        print("\n🤖 使用Ollama分析搜索结果...")
        
        prompt = f"""基于以下搜索结果，分析伊朗和以色列的最新局势：

{search_results}

请提供：
1. 当前局势概述
2. 关键事件
3. 潜在影响

用中文回答。"""
        
        response = ollama.chat(
            model="glm-4.6:cloud",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3}
        )
        
        analysis = response['message']['content']
        print("\n📝 分析结果:")
        print(analysis)
        
    except Exception as e:
        print(f"\n⚠️ Ollama分析失败: {e}")
        print("仅展示搜索结果")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🧪 Ollama Tool Calling 真实测试")
    print("="*60)
    
    results = []
    
    # 测试1: 真实Web搜索
    print("\n\n[测试1/3] 真实Web搜索")
    try:
        search_result = test_real_web_search()
        results.append(("真实Web搜索", True))
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results.append(("真实Web搜索", False))
    
    # 测试2: Ollama Tool Calling
    print("\n\n[测试2/3] Ollama Tool Calling")
    try:
        tool_calling_result = test_ollama_tool_calling_with_real_search()
        results.append(("Ollama Tool Calling", tool_calling_result))
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results.append(("Ollama Tool Calling", False))
    
    # 测试3: 直接搜索+分析
    print("\n\n[测试3/3] 直接搜索+分析")
    try:
        test_direct_search_and_analyze()
        results.append(("直接搜索+分析", True))
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results.append(("直接搜索+分析", False))
    
    # 汇总结果
    print("\n\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {status} - {test_name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    print("\n" + "-"*60)
    print(f"总计: {passed}/{total} 测试通过")
    print("="*60)
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)