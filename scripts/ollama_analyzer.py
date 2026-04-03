"""
Ollama AI全权分析模块
使用Ollama云模型进行完整地缘政治新闻分析
支持URL内容获取和深度分析
支持工具调用（网页搜索）
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import ollama

# 导入主题管理器
try:
    from theme_manager import ThemeManager
    HAS_THEME_MANAGER = True
except ImportError:
    HAS_THEME_MANAGER = False
    ThemeManager = None  # 避免Pylance警告
    print("警告: theme_manager未找到，将使用默认提示词")

# 导入网页搜索工具
try:
    from web_searcher import WebSearcher
    HAS_WEB_SEARCHER = True
except ImportError:
    HAS_WEB_SEARCHER = False
    WebSearcher = None
    print("警告: web_searcher未找到，网页搜索功能不可用")


class OllamaAnalyzer:
    """使用Ollama AI全权分析地缘政治新闻"""
    
    def __init__(self, model: str = "", config_path: str = ""):
        """
        初始化Ollama分析器
        
        Args:
            model: Ollama模型名称（为空时从配置文件读取）
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        
        # 加载模型配置（支持分离的翻译和分析模型）
        ollama_settings = self.config.get("ollama_settings", {})
        
        # 从配置加载不同用途的模型，如果配置为空则使用默认值
        default_model = "glm-4.6:cloud"
        self.analysis_model = ollama_settings.get("analysis_model", {}).get("name", default_model)
        self.translation_model = ollama_settings.get("translation_model", {}).get("name", default_model)
        self.summary_model = ollama_settings.get("summary_model", {}).get("name", default_model)
        
        # 如果没有ollama_settings配置，尝试从旧的ollama_models配置加载
        if not ollama_settings:
            ollama_models = self.config.get("ollama_models", {})
            self.analysis_model = ollama_models.get("analysis", default_model)
            self.translation_model = ollama_models.get("translation", default_model)
            self.summary_model = ollama_models.get("trend_summary", default_model)
        
        # 兼容旧的model参数
        self.model = model if model else self.analysis_model
        
        # 加载网页搜索配置
        search_config = ollama_settings.get("web_search", {})
        self.search_enabled = search_config.get("enabled", True) and HAS_WEB_SEARCHER
        self.search_max_results = search_config.get("max_results", 5)
        
        # 初始化网页搜索器
        self.searcher = None
        if self.search_enabled:
            try:
                self.searcher = WebSearcher(max_results=self.search_max_results)
                print(f"  ✓ 网页搜索工具已启用（最大结果数: {self.search_max_results}）")
            except Exception as e:
                print(f"  ⚠ 网页搜索工具初始化失败: {e}")
                self.search_enabled = False
        
        # 加载debug配置
        self.debug_config = self.config.get("debug", {})
        self.debug_enabled = self.debug_config.get("enabled", False)
        self.debug_log_content = self.debug_config.get("log_url_content", False)
        self.debug_log_prompt = self.debug_config.get("log_prompt", False)
        self.debug_log_file = self.debug_config.get("log_file", "logs/debug_url_content.log")
        self.debug_prompt_log_file = self.debug_config.get("prompt_log_file", "logs/debug_prompts.log")
        self.debug_max_length = self.debug_config.get("max_content_length", 500)
        
        # 初始化debug日志
        if self.debug_enabled and self.debug_log_content:
            self._init_debug_log()
        
        # 初始化提示词日志
        if self.debug_enabled and self.debug_log_prompt:
            self._init_prompt_log()
        
        # 打印模型配置信息
        print(f"  模型配置:")
        print(f"    分析模型: {self.analysis_model}")
        print(f"    翻译模型: {self.translation_model}")
        print(f"    总结模型: {self.summary_model}")
    
    def _init_debug_log(self):
        """初始化debug日志文件"""
        try:
            import os
            log_dir = os.path.dirname(self.debug_log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            # 写入日志头
            with open(self.debug_log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== OilAnalyzer Debug Log ===\n")
                f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Debug配置: enabled={self.debug_enabled}, log_content={self.debug_log_content}\n")
                f.write("=" * 50 + "\n\n")
            
            print(f"  ✓ Debug日志已初始化: {self.debug_log_file}")
        except Exception as e:
            print(f"  ✗ 初始化debug日志失败: {e}")
    
    def _init_prompt_log(self):
        """初始化提示词日志文件"""
        try:
            import os
            log_dir = os.path.dirname(self.debug_prompt_log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            # 写入日志头
            with open(self.debug_prompt_log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== OilAnalyzer Debug Prompt Log ===\n")
                f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"分析模型: {self.analysis_model}\n")
                f.write(f"翻译模型: {self.translation_model}\n")
                f.write(f"总结模型: {self.summary_model}\n")
                f.write("=" * 60 + "\n\n")
            
            print(f"  ✓ 提示词日志已初始化: {self.debug_prompt_log_file}")
        except Exception as e:
            print(f"  ✗ 初始化提示词日志失败: {e}")
    
    def _log_prompt(self, prompt: str, article_count: int, model: str):
        """记录提示词到debug日志"""
        if not self.debug_enabled or not self.debug_log_prompt:
            return
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 写入提示词日志
            with open(self.debug_prompt_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"[{timestamp}] 提示词构建完成\n")
                f.write(f"模型: {model}\n")
                f.write(f"文章数量: {article_count}\n")
                f.write(f"提示词长度: {len(prompt)}字符\n")
                f.write(f"{'='*60}\n")
                f.write(f"{prompt}\n")
                f.write(f"{'='*60}\n\n")
            
            print(f"  ✓ 提示词已记录到: {self.debug_prompt_log_file}")
            print(f"    提示词长度: {len(prompt)}字符")
            
        except Exception as e:
            print(f"  ✗ 记录提示词失败: {e}")
    
    def _log_debug(self, message: str, content: Optional[str] = None):
        """记录debug信息"""
        if not self.debug_enabled:
            return
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 控制台输出
            print(f"  [DEBUG] {message}")
            
            # 文件输出
            if self.debug_log_content:
                with open(self.debug_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] {message}\n")
                    
                    if content is not None:
                        # 限制内容长度
                        if len(content) > self.debug_max_length:
                            content = content[:self.debug_max_length] + f"\n... (截断，总长度: {len(content)}字符)"
                        
                        f.write(f"内容:\n{content}\n")
                    
                    f.write("-" * 50 + "\n")
        except Exception as e:
            print(f"  ✗ 记录debug日志失败: {e}")
        
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        possible_paths = []
        if config_path:
            possible_paths.append(config_path)
        possible_paths.extend([
            "config/config.json",
            "../config/config.json",
            os.path.join(os.path.dirname(__file__), "../config/config.json")
        ])
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"配置加载失败 {path}: {e}")
                    continue
        
        return {}
    
    def check_model_health(self, model: str) -> bool:
        """
        检查模型是否可用
        
        Args:
            model: 模型名称
            
        Returns:
            模型是否可用
        """
        try:
            print(f"    检查模型健康状态: {model}")
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": "test"}],
                options={"num_predict": 1}
            )
            print(f"    ✓ 模型 {model} 可用")
            return True
        except Exception as e:
            print(f"    ✗ 模型 {model} 不可用: {e}")
            return False
    
    def validate_models(self) -> Dict[str, bool]:
        """
        验证所有配置的模型是否可用
        
        Returns:
            各模型的健康状态字典
        """
        print(f"  验证模型健康状态...")
        
        models_to_check = [
            ("分析模型", self.analysis_model),
            ("翻译模型", self.translation_model),
            ("总结模型", self.summary_model)
        ]
        
        health_status = {}
        all_healthy = True
        
        for name, model in models_to_check:
            is_healthy = self.check_model_health(model)
            health_status[name] = is_healthy
            if not is_healthy:
                all_healthy = False
                print(f"    ⚠ {name} ({model}) 不可用")
        
        if all_healthy:
            print(f"  ✓ 所有模型健康检查通过")
        else:
            print(f"  ⚠ 部分模型不可用，请检查Ollama服务或模型配置")
        
        return health_status
    
    def _chat_with_tools(self, model: str, messages: List[Dict], use_search: bool = False) -> str:
        """
        带工具调用的聊天
        
        Args:
            model: 模型名称
            messages: 消息列表
            use_search: 是否启用搜索工具
            
        Returns:
            模型响应内容
        """
        kwargs = {
            "model": model,
            "messages": messages,
            "options": {"temperature": 0.3}
        }
        
        # 仅对分析模型启用搜索工具
        if use_search and self.search_enabled and self.searcher and model == self.analysis_model:
            kwargs["tools"] = [self.searcher.get_tool_definition()]
        
        # 保存原始响应（用于回退）
        response = ollama.chat(**kwargs)
        original_content = response.get('message', {}).get('content', '')
        
        # 处理工具调用
        if response.get('message', {}).get('tool_calls'):
            print(f"    🔧 模型请求调用工具...")
            
            # 添加模型的响应到消息列表
            messages.append(response['message'])
            
            # 执行工具调用
            for tool_call in response['message']['tool_calls']:
                function_name = tool_call['function']['name']
                arguments = tool_call['function']['arguments']
                
                print(f"    执行工具: {function_name}({arguments})")
                
                if function_name == 'web_search' and self.searcher:
                    # 执行搜索
                    search_results = self.searcher.search(
                        query=arguments.get('query', ''),
                        max_results=arguments.get('num_results', self.search_max_results)
                    )
                    
                    print(f"    📄 搜索结果长度: {len(search_results)} 字符")
                    
                    # 将搜索结果添加到消息列表
                    messages.append({
                        "role": "tool",
                        "content": search_results
                    })
            
            # 再次调用模型获取最终回答
            print(f"    🔄 将搜索结果返回模型...")
            print(f"    📊 当前消息列表长度: {len(messages)}")
            
            try:
                final_response = ollama.chat(
                    model=model,
                    messages=messages,
                    options={"temperature": 0.3}
                )
                
                result_text = final_response.get('message', {}).get('content', '')
                print(f"    📥 最终响应长度: {len(result_text)} 字符")
                
                # 如果返回空内容，使用原始响应
                if not result_text or len(result_text.strip()) == 0:
                    print(f"    ⚠ 模型返回空内容，使用原始响应（长度: {len(original_content)}）")
                    return original_content if original_content else '{"error": "模型返回空内容"}'
                
                return result_text
                
            except Exception as e:
                print(f"    ✗ 最终响应调用失败: {e}")
                return original_content if original_content else '{"error": "工具调用异常"}'
        
        return original_content
    
    def analyze_with_ai(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用Ollama AI全权分析新闻（改进版）
        支持URL内容获取和深度分析
        
        Args:
            news_data: 包含articles的新闻数据
            
        Returns:
            完整的AI分析结果
        """
        articles = news_data.get("articles", [])
        
        if not articles:
            return self._get_empty_analysis()
        
        # 获取每篇文章的完整内容
        print(f"  正在获取{len(articles)}篇文章的完整内容...")
        enriched_articles = self._enrich_articles_with_content(articles)
        
        # 构建分析提示词（使用完整内容）
        prompt = self._build_analysis_prompt(enriched_articles)
        
        # Debug模式下记录提示词
        if self.debug_enabled and self.debug_log_prompt:
            self._log_prompt(prompt, len(enriched_articles), self.analysis_model)
        
        try:
            # 调用Ollama API（支持工具调用）
            print(f"  正在使用分析模型({self.analysis_model})分析{len(enriched_articles)}篇文章...")
            
            # 使用带工具调用的聊天方法
            ai_response = self._chat_with_tools(
                model=self.model,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                use_search=True  # 启用搜索工具
            )
            
            # 提取JSON
            analysis_result = self._extract_json_from_response(ai_response)
            
            if analysis_result:
                # 添加元数据
                analysis_result["metadata"] = {
                    "model_used": self.model,
                    "articles_analyzed": len(enriched_articles),
                    "analysis_timestamp": datetime.now().isoformat(),
                    "raw_response": ai_response
                }
                
                # 生成趋势总评
                print(f"  正在生成趋势总评...")
                trend_summary = self._generate_trend_summary(enriched_articles, analysis_result)
                analysis_result["trend_summary"] = trend_summary
                
                # 翻译新闻标题为中文
                print(f"  正在翻译新闻标题...")
                enriched_articles = self._translate_titles(enriched_articles)
                
                # 生成新闻摘要
                print(f"  正在生成新闻摘要...")
                enriched_articles = self._generate_news_summaries(enriched_articles)
                
                # 分析事件影响力
                print(f"  正在分析事件影响力...")
                enriched_articles = self.batch_analyze_events(enriched_articles)
                
                # 将enriched_articles保存到analysis中，以便传递到报告生成器
                analysis_result["enriched_articles"] = enriched_articles
                
                print(f"  ✓ 分析完成")
                print(f"    危机评分: {analysis_result.get('crisis_score', 'N/A')}/10")
                print(f"    趋势: {analysis_result.get('trend', 'N/A')}")
                print(f"    总评: {trend_summary.get('overall_assessment', 'N/A')[:60]}...")
                
                return analysis_result
            else:
                print(f"  ✗ 无法解析AI响应")
                return self._get_fallback_analysis(enriched_articles, ai_response)
                
        except Exception as e:
            print(f"  ✗ Ollama分析失败: {e}")
            return self._get_error_analysis(str(e))
    
    def _generate_trend_summary(self, articles: List[Dict], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成趋势总评
        
        Args:
            articles: 文章列表
            analysis: 分析结果
            
        Returns:
            趋势总评
        """
        # 准备新闻摘要
        news_summary = self._prepare_news_summary_for_summary(articles)
        
        # 构建总评提示词
        prompt = f"""基于以下{len(articles)}篇地缘政治新闻，生成一份综合性的趋势总评报告。

新闻摘要：
{news_summary}

当前分析结果：
- 危机评分：{analysis.get('crisis_score', 'N/A')}/10
- 趋势：{analysis.get('trend', 'N/A')}
- 军事冲突强度：{analysis.get('intensity_assessment', {}).get('conflict_intensity', {}).get('score', 'N/A')}/10
- 外交紧张程度：{analysis.get('intensity_assessment', {}).get('diplomatic_tension', {}).get('score', 'N/A')}/10
- 原油危机程度：{analysis.get('intensity_assessment', {}).get('oil_crisis', {}).get('score', 'N/A')}/10

请生成一份趋势总评，包含以下内容：

1. **整体评估**（200字以内）：总结当前局势的核心特点和发展方向
2. **关键进展**（3条）：最重要的3个事件或发展
3. **风险因素**（3条）：需要关注的3个主要风险
4. **短期展望**（20字以内）：未来7天的预期发展
5. **油价影响**（100字以内）：对原油市场的具体影响
6. **置信度**：high/medium/low

请用JSON格式返回：
{{
    "overall_assessment": "中东局势持续升级，伊朗与以色列冲突进入第21天，能源设施遭受直接攻击，霍尔木兹海峡通行受威胁，全球石油供应面临中断风险...",
    "key_developments": [
        "以色列空袭科威特炼油厂，能源设施遭受直接攻击",
        "伊朗威胁封锁霍尔木兹海峡，全球石油供应面临中断风险",
        "美国加大外交斡旋力度，但收效甚微"
    ],
    "risk_factors": [
        "冲突可能蔓延至海湾其他国家",
        "能源价格持续上涨引发全球经济担忧",
        "外交渠道受阻，和平前景不明"
    ],
    "short_term_outlook": "7天内局势可能进一步升级，需密切关注霍尔木兹海峡通行情况",
    "oil_market_impact": "油价面临持续上涨压力，若海峡通行受阻，可能突破$120/桶",
    "confidence_level": "high"
}}

只返回JSON，不要有其他内容。"""

        try:
            print(f"  正在使用总结模型({self.summary_model})生成趋势总评...")
            
            response = ollama.chat(
                model=self.summary_model,  # 使用总结模型
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            ai_response = response['message']['content']
            summary_result = self._extract_json_from_response(ai_response)
            
            if summary_result:
                return summary_result
            else:
                return self._get_default_trend_summary(analysis)
                
        except Exception as e:
            print(f"    趋势总评生成失败: {e}")
            return self._get_default_trend_summary(analysis)
    
    def _translate_titles(self, articles: List[Dict]) -> List[Dict]:
        """
        使用翻译模型翻译新闻标题为中文
        
        Args:
            articles: 文章列表
            
        Returns:
            添加了title_cn字段的文章列表
        """
        if not articles:
            return articles
        
        # 提取标题
        titles = [article.get('title', '') for article in articles]
        
        # 构建翻译提示词
        titles_list = "\n".join(f"{i+1}. {title}" for i, title in enumerate(titles))
        
        prompt = f"""请将以下英文新闻标题翻译成中文，保持简洁准确，每行一个翻译：

{titles_list}

请用JSON格式返回：
{{
    "translations": ["翻译1", "翻译2", ...]
}}

只返回JSON，不要有其他内容。"""

        try:
            print(f"    正在使用翻译模型({self.translation_model})翻译{len(titles)}个标题...")
            
            response = ollama.chat(
                model=self.translation_model,  # 使用翻译模型
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            ai_response = response['message']['content']
            result = self._extract_json_from_response(ai_response)
            
            if result and 'translations' in result:
                translations = result['translations']
                
                # 应用翻译
                for i, article in enumerate(articles):
                    if i < len(translations):
                        article['title_cn'] = translations[i]
                    else:
                        article['title_cn'] = article.get('title', '')
                
                print(f"    ✓ 翻译完成")
            else:
                # 翻译失败，使用原标题
                for article in articles:
                    article['title_cn'] = article.get('title', '')
                print(f"    ⚠ 翻译解析失败，使用原标题")
                
        except Exception as e:
            print(f"    ✗ 翻译失败: {e}")
            # 回退到分析模型
            print(f"    回退到分析模型({self.analysis_model})...")
            try:
                response = ollama.chat(
                    model=self.analysis_model,
                    messages=[{'role': 'user', 'content': prompt}]
                )
                ai_response = response['message']['content']
                result = self._extract_json_from_response(ai_response)
                
                if result and 'translations' in result:
                    translations = result['translations']
                    for i, article in enumerate(articles):
                        if i < len(translations):
                            article['title_cn'] = translations[i]
                        else:
                            article['title_cn'] = article.get('title', '')
                    print(f"    ✓ 使用分析模型翻译完成")
                else:
                    for article in articles:
                        article['title_cn'] = article.get('title', '')
            except Exception as e2:
                print(f"    分析模型翻译也失败: {e2}")
                for article in articles:
                    article['title_cn'] = article.get('title', '')
        
        return articles
    
    def _generate_news_summaries(self, articles: List[Dict]) -> List[Dict]:
        """批量为每条新闻生成中文摘要"""
        if not articles:
            return articles
        
        print(f"    正在为{len(articles)}条新闻批量生成摘要...")
        
        # 准备新闻列表
        news_list = []
        for i, article in enumerate(articles):
            title = article.get('title_cn', article.get('title', ''))
            content = article.get('full_content', article.get('description', ''))[:500]  # 限制内容长度
            
            if not title and not content:
                news_list.append(f"{i+1}. 标题: N/A\n   内容: 无内容可供摘要")
            else:
                news_list.append(f"{i+1}. 标题: {title}\n   内容: {content[:300]}")
        
        news_text = "\n\n".join(news_list)
        
        # 构建批量摘要提示词
        prompt = f"""请为以下{len(articles)}条新闻各生成一句话摘要（每条20-30字），使用中文：

{news_text}

请用JSON格式返回：
{{
    "summaries": ["摘要1", "摘要2", "摘要3", ...]
}}

注意：
1. 摘要数量必须与新闻数量一致（{len(articles)}条）
2. 只返回JSON，不要有其他内容"""

        try:
            print(f"    正在使用分析模型({self.analysis_model})批量生成摘要...")
            
            response = ollama.chat(
                model=self.analysis_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": 0.3}
            )
            
            ai_response = response['message']['content']
            result = self._extract_json_from_response(ai_response)
            
            if result and 'summaries' in result:
                summaries = result['summaries']
                
                # 应用摘要
                for i, article in enumerate(articles):
                    if i < len(summaries):
                        summary = summaries[i].strip().strip('"').strip("'")
                        article['summary_cn'] = summary
                        print(f"    [{i+1}/{len(articles)}] {summary[:30]}...")
                    else:
                        title = article.get('title_cn', article.get('title', ''))
                        article['summary_cn'] = title[:50] if title else "摘要生成失败"
                
                print(f"    ✓ 批量摘要生成完成")
            else:
                # 批量处理失败，回退到逐条处理
                print(f"    ⚠ 批量摘要解析失败，回退到逐条处理...")
                for i, article in enumerate(articles):
                    title = article.get('title_cn', article.get('title', ''))
                    content = article.get('full_content', article.get('description', ''))[:300]
                    
                    if not title and not content:
                        article['summary_cn'] = "无内容可供摘要"
                        continue
                    
                    single_prompt = f"""请用一句话（20-30字）总结以下新闻的核心内容，使用中文：

标题：{title}
内容：{content}

只返回摘要文本，不要有其他内容。"""
                    
                    try:
                        single_response = ollama.chat(
                            model=self.model,
                            messages=[{'role': 'user', 'content': single_prompt}],
                            options={"temperature": 0.3}
                        )
                        summary = single_response['message']['content'].strip().strip('"').strip("'")
                        article['summary_cn'] = summary
                        print(f"    [{i+1}/{len(articles)}] {summary[:30]}...")
                    except Exception as e:
                        print(f"    摘要生成失败 [{i+1}]: {e}")
                        article['summary_cn'] = title[:50] if title else "摘要生成失败"
                
                print(f"    ✓ 逐条摘要生成完成")
                
        except Exception as e:
            print(f"    ✗ 批量摘要生成失败: {e}")
            # 错误处理：使用标题作为摘要
            for article in articles:
                title = article.get('title_cn', article.get('title', ''))
                article['summary_cn'] = title[:50] if title else "摘要生成失败"
        
        return articles
    
    def _prepare_news_summary_for_summary(self, articles: List[Dict]) -> str:
        """准备新闻摘要用于总评"""
        summary_parts = []
        
        for i, article in enumerate(articles[:15], 1):
            title = article.get('title', 'N/A')
            source = article.get('source', 'Unknown')
            summary_parts.append(f"{i}. [{source}] {title}")
        
        return "\n".join(summary_parts)
    
    def _get_default_trend_summary(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """获取默认趋势总评"""
        crisis_score = analysis.get('crisis_score', 5)
        trend = analysis.get('trend', 'stable')
        
        if crisis_score >= 8:
            overall = "局势高度紧张，冲突升级风险显著，需密切关注事态发展"
            confidence = "high"
        elif crisis_score >= 6:
            overall = "局势存在不确定性，多方面因素交织，需持续监控"
            confidence = "medium"
        else:
            overall = "局势相对稳定，但需关注潜在风险因素"
            confidence = "medium"
        
        return {
            "overall_assessment": overall,
            "key_developments": [
                "地缘政治冲突持续",
                "能源市场波动",
                "外交斡旋进行中"
            ],
            "risk_factors": [
                "冲突升级风险",
                "能源供应中断风险",
                "经济影响风险"
            ],
            "short_term_outlook": f"当前趋势为{trend}，危机评分{crisis_score}/10",
            "oil_market_impact": "油价面临不确定性，需关注局势发展",
            "confidence_level": confidence
        }
    
    def _enrich_articles_with_content(self, articles: List[Dict]) -> List[Dict]:
        """获取每篇文章的完整内容"""
        enriched = []
        
        for i, article in enumerate(articles, 1):
            url = article.get('url', '')
            title = article.get('title', 'N/A')
            source = article.get('source', 'Unknown')
            
            print(f"    [{i}/{len(articles)}] {title[:50]}...")
            
            # 获取完整内容
            full_content = ""
            if url:
                full_content = self._fetch_article_content(url)
            
            # 如果获取失败，使用描述作为fallback
            if not full_content:
                full_content = article.get('description', '')
            
            enriched.append({
                'title': title,
                'description': article.get('description', ''),
                'url': url,
                'source': source,
                'publishedAt': article.get('publishedAt', ''),
                'full_content': full_content if full_content else article.get('description', ''),
                'content_length': len(full_content) if full_content else 0
            })
        
        return enriched
    
    def _fetch_article_content(self, url: str) -> str:
        """获取文章完整内容"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # 记录debug信息
            self._log_debug(f"开始获取URL内容: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            # 记录HTTP状态码
            self._log_debug(f"HTTP状态码: {response.status_code}", f"URL: {url}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 移除不需要的元素
                for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                    element.decompose()
                
                # 获取正文内容
                content = ""
                
                # 尝试多种选择器
                selectors = [
                    'article',
                    'main',
                    '.article-body',
                    '.story-body',
                    '.post-content',
                    '.entry-content',
                    '[role="main"]',
                    '.content'
                ]
                
                for selector in selectors:
                    element = soup.select_one(selector)
                    if element:
                        content = element.get_text(separator='\n', strip=True)
                        break
                
                # 如果都没找到，获取body文本
                if not content:
                    body = soup.find('body')
                    if body:
                        content = body.get_text(separator='\n', strip=True)
                
                # 清理文本
                lines = [line.strip() for line in content.splitlines() if line.strip() and len(line.strip()) > 20]
                clean_content = '\n'.join(lines)
                
                # 记录获取到的内容长度
                self._log_debug(f"获取到内容长度: {len(clean_content)}字符", f"URL: {url}\n内容预览:\n{clean_content[:500]}")
                
                return clean_content
            
            self._log_debug(f"HTTP请求失败: {response.status_code}", f"URL: {url}")
            return ""
            
        except Exception as e:
            self._log_debug(f"获取URL内容失败: {e}", f"URL: {url}")
            print(f"      获取URL内容失败: {e}")
            return ""
    
    def _build_analysis_prompt(self, articles: List[Dict]) -> str:
        """构建分析提示词（使用主题管理器）"""
        
        # 尝试使用主题管理器
        if HAS_THEME_MANAGER and ThemeManager is not None:
            try:
                theme_manager = ThemeManager()
                prompt = theme_manager.format_analysis_prompt(articles)
                if prompt:
                    print(f"  ✓ 使用主题管理器构建提示词: {theme_manager.get_current_theme_id()}")
                    return prompt
            except Exception as e:
                print(f"  ⚠ 主题管理器构建失败，使用默认提示词: {e}")
        
        # 回退到默认提示词
        article_list = []
        
        for i, article in enumerate(articles[:15], 1):  # 最多15篇
            title = article.get('title', 'N/A')
            source = article.get('source', 'Unknown')
            date = article.get('publishedAt', '')[:10]
            content = article.get('full_content', article.get('description', ''))
            url = article.get('url', '')
            
            article_list.append(f"""
--- 文章{i} ---
标题: {title}
来源: {source}
日期: {date}
URL: {url}
内容: {content}
""")
        
        # 构建完整提示词
        prompt = f"""你是一位顶级的地缘政治分析师和危机评估专家。

请分析以下{len(articles)}篇新闻文章（已获取完整内容），提供全面的危机评估报告。

新闻文章：
{''.join(article_list)}

═══════════════════════════════════════════════════════════════
分析框架（基于完整文章内容）
═══════════════════════════════════════════════════════════════

【第一层：新闻分类】
将每篇新闻分类到以下三个类别之一：
- military: 军事冲突、战争、袭击、导弹、军队、伤亡
- diplomacy: 外交谈判、制裁、协议、和平、国际关系
- energy: 石油、天然气、能源供应、航运、海峡、炼油厂

【第二层：强度评估】
请对三个维度的强度进行1-10分评估：

1. 军事冲突强度 (conflict_intensity)
   - 1-3分：低强度（小规模摩擦、演习）
   - 4-6分：中等强度（局部冲突、空袭）
   - 7-8分：高强度（大规模军事行动、多国卷入）
   - 9-10分：极端强度（全面战争、核威胁）

2. 外交紧张程度 (diplomatic_tension)
   - 1-3分：低紧张（正常外交、合作）
   - 4-6分：中等紧张（外交抗议、制裁威胁）
   - 7-8分：高紧张（外交关系破裂、召回大使）
   - 9-10分：极端紧张（断交、全面制裁）

3. 原油危机程度 (oil_crisis)
   - 1-3分：低风险（正常供应、价格稳定）
   - 4-6分：中等风险（供应担忧、价格波动）
   - 7-8分：高风险（供应中断威胁、价格飙升）
   - 9-10分：极端风险（实际中断、价格失控）

【第三层：综合评估】
基于文章内容的深度分析：
- 危机评分 (crisis_score): 综合三维度的总体评分（1-10）
- 趋势判断 (trend): escalating（升级）/ de-escalating（降级）/ stable（稳定）
- 关键洞察 (key_insights): 从文章内容中提取5个最重要的发现
- 执行摘要 (executive_summary): 200字以上的综合摘要

═══════════════════════════════════════════════════════════════
输出格式
═══════════════════════════════════════════════════════════════

请用严格的JSON格式返回：

{{
    "key_metrics": {{
        "casualties": {{"deaths": 0, "injured": 0, "note": ""}},
        "military_actions": {{"missiles_fired": 0, "air_strikes": 0}},
        "economic_impact": {{"oil_price_change": "0%", "supply_disruption": false}}
    }},
    "classification": {{
        "military": ["新闻标题1", "新闻标题2"],
        "diplomacy": ["新闻标题3"],
        "energy": ["新闻标题4"]
    }},
    "intensity_assessment": {{
        "conflict_intensity": {{
            "score": 8.5,
            "level": "high",
            "description": "基于文章内容的详细描述（50字以上）"
        }},
        "diplomatic_tension": {{
            "score": 6.0,
            "level": "medium",
            "description": "基于文章内容的详细描述（50字以上）"
        }},
        "oil_crisis": {{
            "score": 7.5,
            "level": "high",
            "description": "基于文章内容的详细描述（50字以上）"
        }}
    }},
    "crisis_score": 7.5,
    "trend": "escalating",
    "trend_description": "基于文章内容的趋势描述（70-90字，简洁有力）",
    "key_insights": [
        "洞察1：从文章内容中提取的关键发现（50-80字）",
        "洞察2：从文章内容中提取的关键发现（50-80字）",
        "洞察3：从文章内容中提取的关键发现（50-80字）",
        "洞察4：从文章内容中提取的关键发现（50-80字）",
        "洞察5：从文章内容中提取的关键发现（50-80字）"
    ],
    "executive_summary": "基于所有文章内容的综合摘要（200字以上）"
}}

只返回JSON，不要有其他内容。"""

        return prompt
    
    def _extract_json_from_response(self, response: str) -> Dict:
        """从AI响应中提取JSON"""
        try:
            # 尝试直接解析
            return json.loads(response)
        except:
            # 尝试查找JSON块
            import re
            json_pattern = r'\{[\s\S]*\}'
            matches = re.findall(json_pattern, response)
            
            if matches:
                for match in matches:
                    try:
                        return json.loads(match)
                    except:
                        continue
            
            # 返回空字典而不是None
            return {}
    
    def _get_empty_analysis(self) -> Dict:
        """空分析结果"""
        return {
            "classification": {
                "military": [],
                "diplomacy": [],
                "energy": []
            },
            "intensity_assessment": {
                "conflict_intensity": {"level": "low", "score": 0, "description": "无相关新闻"},
                "diplomatic_tension": {"level": "low", "score": 0, "description": "无相关新闻"},
                "oil_crisis": {"level": "low", "score": 0, "description": "无相关新闻"}
            },
            "crisis_score": 0,
            "trend": "stable",
            "trend_description": "无数据",
            "key_insights": ["无可用数据"],
            "strategic_recommendations": ["等待新闻数据"],
            "executive_summary": "暂无新闻数据可供分析",
            "metadata": {
                "model_used": self.model,
                "articles_analyzed": 0,
                "analysis_timestamp": datetime.now().isoformat()
            }
        }
    
    def _get_fallback_analysis(self, articles: List[Dict], raw_response: str) -> Dict:
        """备用分析结果"""
        return {
            "classification": {
                "military": [a.get('title', '') for a in articles[:5]],
                "diplomacy": [],
                "energy": []
            },
            "intensity_assessment": {
                "conflict_intensity": {"level": "medium", "score": 5.0, "description": "需要人工审核"},
                "diplomatic_tension": {"level": "low", "score": 3.0, "description": "需要人工审核"},
                "oil_crisis": {"level": "low", "score": 3.0, "description": "需要人工审核"}
            },
            "crisis_score": 5.0,
            "trend": "stable",
            "trend_description": "AI分析结果无法解析，建议人工审核",
            "key_insights": ["AI分析结果无法解析"],
            "strategic_recommendations": ["请人工审核原始AI响应"],
            "executive_summary": "AI分析结果无法解析，已提供备用分析",
            "metadata": {
                "model_used": self.model,
                "articles_analyzed": len(articles),
                "analysis_timestamp": datetime.now().isoformat(),
                "raw_response": raw_response,
                "parse_error": True
            }
        }
    
    def _get_error_analysis(self, error_msg: str) -> Dict:
        """错误分析结果"""
        return {
            "classification": {
                "military": [],
                "diplomacy": [],
                "energy": []
            },
            "intensity_assessment": {
                "conflict_intensity": {"level": "unknown", "score": 0, "description": f"分析失败: {error_msg}"},
                "diplomatic_tension": {"level": "unknown", "score": 0, "description": f"分析失败: {error_msg}"},
                "oil_crisis": {"level": "unknown", "score": 0, "description": f"分析失败: {error_msg}"}
            },
            "crisis_score": 0,
            "trend": "unknown",
            "trend_description": f"分析失败: {error_msg}",
            "key_insights": [f"分析失败: {error_msg}"],
            "strategic_recommendations": ["请检查Ollama服务状态"],
            "executive_summary": f"AI分析失败: {error_msg}",
            "metadata": {
                "model_used": self.model,
                "articles_analyzed": 0,
                "analysis_timestamp": datetime.now().isoformat(),
                "error": error_msg
            }
        }
    
    def analyze_event_impact(self, title: str, description: str = "", source: str = "") -> Dict[str, Any]:
        """
        分析单个事件的影响力，返回星级评定
        
        Args:
            title: 事件标题
            description: 事件描述
            source: 新闻来源
            
        Returns:
            包含军事和经济维度星级评定的字典
        """
        # 构建分析提示词
        prompt = f"""请分析以下地缘政治事件的影响力，从两个维度进行评估：

事件标题：{title}
事件描述：{description}
新闻来源：{source}

评估维度：

1. 军事冲突严重程度 (military_score)
   - ★★★★★ (5分): 核设施攻击、大规模空袭、最高领袖死亡、全面战争
   - ★★★★☆ (4分): 导弹袭击城市、地面进攻、重大军事行动
   - ★★★☆☆ (3分): 局部冲突、无人机攻击、军事摩擦
   - ★★☆☆☆ (2分): 军事调动、外交声明、军事演习
   - ★☆☆☆☆ (1分): 间接影响、社会事件、人道主义

2. 经济影响 (economic_score)
   - ★★★★★ (5分): 油价暴涨>10%、海峡封锁、全球供应中断
   - ★★★★☆ (4分): 油价上涨5-10%、重要设施被攻击
   - ★★★☆☆ (3分): 油价小幅波动、外交紧张、市场担忧
   - ★★☆☆☆ (2分): 间接经济影响、区域不稳定
   - ★☆☆☆☆ (1分): 无直接影响、纯社会事件

请用JSON格式返回：
{{
    "military_score": 3,
    "economic_score": 2,
    "reasoning": "简短说明评分理由（30字以内）"
}}

只返回JSON，不要有其他内容。"""

        try:
            # 调用Ollama分析
            response = ollama.chat(
                model=self.analysis_model,  # 使用分析模型
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": 0.2}
            )
            
            ai_response = response['message']['content']
            result = self._extract_json_from_response(ai_response)
            
            if result:
                military_score = min(5, max(1, result.get('military_score', 3)))
                economic_score = min(5, max(1, result.get('economic_score', 3)))
                
                return {
                    "military_score": military_score,
                    "economic_score": economic_score,
                    "reasoning": result.get('reasoning', ''),
                    "military_stars": "★" * military_score + "☆" * (5 - military_score),
                    "economic_stars": "★" * economic_score + "☆" * (5 - economic_score)
                }
            else:
                # 默认中等评分
                return self._get_default_impact()
                
        except Exception as e:
            print(f"  ⚠ 事件影响力分析失败: {e}")
            return self._get_default_impact()
    
    def _get_default_impact(self) -> Dict[str, Any]:
        """返回默认影响力评分"""
        return {
            "military_score": 3,
            "economic_score": 3,
            "reasoning": "分析未完成",
            "military_stars": "★★★☆☆",
            "economic_stars": "★★★☆☆"
        }
    
    def batch_analyze_events(self, articles: List[Dict]) -> List[Dict]:
        """
        批量分析事件影响力（1次API调用）
        
        Args:
            articles: 文章列表
            
        Returns:
            添加了影响力标签的文章列表
        """
        if not articles:
            return articles
        
        print(f"  正在批量分析{len(articles)}个事件的影响力...")
        
        # 准备所有事件的标题和描述
        events_list = []
        for i, article in enumerate(articles):
            title = article.get('title_cn', article.get('title', ''))
            description = article.get('summary_cn', article.get('description', ''))
            source = article.get('source', '')
            
            events_list.append(f"{i+1}. 标题: {title}\n   来源: {source}\n   描述: {description[:200]}")
        
        events_text = "\n\n".join(events_list)
        
        # 构建批量分析提示词
        prompt = f"""请分析以下{len(articles)}个地缘政治事件的影响力，从两个维度进行评估：

事件列表：
{events_text}

评估维度：

1. 军事冲突严重程度 (military_score)
   - ★★★★★ (5分): 核设施攻击、大规模空袭、最高领袖死亡、全面战争
   - ★★★★☆ (4分): 导弹袭击城市、地面进攻、重大军事行动
   - ★★★☆☆ (3分): 局部冲突、无人机攻击、军事摩擦
   - ★★☆☆☆ (2分): 军事调动、外交声明、军事演习
   - ★☆☆☆☆ (1分): 间接影响、社会事件、人道主义

2. 经济影响 (economic_score)
   - ★★★★★ (5分): 油价暴涨>10%、海峡封锁、全球供应中断
   - ★★★★☆ (4分): 油价上涨5-10%、重要设施被攻击
   - ★★★☆☆ (3分): 油价小幅波动、外交紧张、市场担忧
   - ★★☆☆☆ (2分): 间接经济影响、区域不稳定
   - ★☆☆☆☆ (1分): 无直接影响、纯社会事件

请用JSON格式返回，包含所有{len(articles)}个事件的评估：
{{
    "impacts": [
        {{
            "military_score": 3,
            "economic_score": 2,
            "reasoning": "简短说明评分理由（30字以内）"
        }},
        ...
    ]
}}

注意：
1. impacts数组必须包含{len(articles)}个元素，与事件数量一致
2. 只返回JSON，不要有其他内容"""

        try:
            print(f"    正在使用分析模型({self.analysis_model})批量分析...")
            
            response = ollama.chat(
                model=self.analysis_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": 0.2}
            )
            
            ai_response = response['message']['content']
            result = self._extract_json_from_response(ai_response)
            
            if result and 'impacts' in result:
                impacts = result['impacts']
                
                # 应用影响力评估到每篇文章
                for i, article in enumerate(articles):
                    if i < len(impacts):
                        impact_data = impacts[i]
                        military_score = min(5, max(1, impact_data.get('military_score', 3)))
                        economic_score = min(5, max(1, impact_data.get('economic_score', 3)))
                        
                        article['impact'] = {
                            "military_score": military_score,
                            "economic_score": economic_score,
                            "reasoning": impact_data.get('reasoning', ''),
                            "military_stars": "★" * military_score + "☆" * (5 - military_score),
                            "economic_stars": "★" * economic_score + "☆" * (5 - economic_score)
                        }
                    else:
                        article['impact'] = self._get_default_impact()
                
                print(f"    ✓ 批量影响力分析完成")
            else:
                # 批量处理失败，使用默认值
                print(f"    ⚠ 批量分析解析失败，使用默认值")
                for article in articles:
                    article['impact'] = self._get_default_impact()
                
        except Exception as e:
            print(f"    ✗ 批量影响力分析失败: {e}")
            # 错误处理：使用默认值
            for article in articles:
                article['impact'] = self._get_default_impact()
        
        return articles


def main():
    """测试Ollama分析"""
    from data_fetcher import DataFetcher
    
    print("=" * 60)
    print("🤖 Ollama全权分析测试")
    print("=" * 60)
    
    # 1. 获取新闻
    print("\n[1/2] 获取新闻数据...")
    fetcher = DataFetcher()
    news_data = fetcher.get_geopolitical_news()
    print(f"✓ 获取到 {news_data.get('total_articles', 0)} 条新闻")
    
    # 2. AI分析
    print("\n[2/2] Ollama全权分析...")
    analyzer = OllamaAnalyzer(model="gpt-oss:120b-cloud")
    analysis = analyzer.analyze_with_ai(news_data)
    
    # 打印结果
    print("\n" + "=" * 60)
    print("📊 分析结果摘要")
    print("=" * 60)
    print(f"危机评分: {analysis.get('crisis_score', 'N/A')}/10")
    print(f"趋势: {analysis.get('trend', 'N/A')}")
    print(f"执行摘要: {analysis.get('executive_summary', 'N/A')}")
    
    # 保存结果
    os.makedirs("data", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    analysis_file = f"data/ollama_full_analysis_{timestamp}.json"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n✓ 分析结果已保存: {analysis_file}")


if __name__ == "__main__":
    main()