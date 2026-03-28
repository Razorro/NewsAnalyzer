#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OilAnalyzer - 地缘政治新闻分析系统
支持两种运行模式：
1. 一次性运行模式：运行一次，生成最近几天的新闻分析和报告
2. 持续运行模式：第一次运行与一次性运行相同，后续只分析增量新闻
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

from data_fetcher import DataFetcher
from ollama_analyzer import OllamaAnalyzer
from report_generator import ReportGenerator


class OilAnalyzer:
    """OilAnalyzer主类"""
    
    def __init__(self, config_path: str = None, web_mode: bool = False):
        """初始化OilAnalyzer
        
        Args:
            config_path: 配置文件路径
            web_mode: 是否为Web模式（Web模式下不生成HTML报告）
        """
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.web_mode = web_mode
        
        # 初始化组件
        self.fetcher = DataFetcher(config_path)
        self.analyzer = OllamaAnalyzer(model="gpt-oss:120b-cloud", config_path=config_path)
        
        # 只在非Web模式下初始化报告生成器
        if not web_mode:
            self.report_generator = ReportGenerator(output_dir="reports")
        else:
            self.report_generator = None
        
        # 已处理的新闻URL记录
        self.processed_urls_file = "data/processed_urls.json"
        self.processed_urls = self._load_processed_urls()
        
        # 上次分析结果记录（用于增量评估）
        self.last_analysis_file = "data/last_analysis.json"
        self.last_analysis = self._load_last_analysis()
        
        # 运行状态
        self.is_first_run = True
        
        # 冷启动数据缓存
        self.cold_start_data = None
        
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
                    continue
        
        return {}
    
    def _load_processed_urls(self) -> set:
        """加载已处理的URL记录"""
        if os.path.exists(self.processed_urls_file):
            try:
                with open(self.processed_urls_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('urls', []))
            except Exception as e:
                print(f"加载已处理URL记录失败: {e}")
        
        return set()
    
    def _save_processed_urls(self):
        """保存已处理的URL记录"""
        os.makedirs(os.path.dirname(self.processed_urls_file), exist_ok=True)
        
        try:
            with open(self.processed_urls_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'urls': list(self.processed_urls),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存已处理URL记录失败: {e}")
    
    def _load_last_analysis(self) -> Dict[str, Any]:
        """加载上次分析结果"""
        if os.path.exists(self.last_analysis_file):
            try:
                with open(self.last_analysis_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载上次分析结果失败: {e}")
        return {}
    
    def _save_last_analysis(self, analysis: Dict[str, Any], summary: Dict[str, Any]):
        """保存当前分析结果供下次使用"""
        os.makedirs(os.path.dirname(self.last_analysis_file), exist_ok=True)
        
        # 保留最近10次历史记录
        history = self.last_analysis.get('history', [])
        history.append({
            'timestamp': datetime.now().isoformat(),
            'crisis_score': summary.get('crisis_score'),
            'crisis_level': summary.get('crisis_level'),
            'trend': summary.get('trend'),
            'dimensions': summary.get('dimensions')
        })
        history = history[-10:]  # 只保留最近10次
        
        data = {
            'last_analysis': {
                'crisis_score': summary.get('crisis_score'),
                'crisis_level': summary.get('crisis_level'),
                'trend': summary.get('trend'),
                'dimensions': summary.get('dimensions'),
                'key_insights': analysis.get('key_insights', []),
                'executive_summary': analysis.get('executive_summary', ''),
                'timestamp': datetime.now().isoformat()
            },
            'history': history
        }
        
        try:
            with open(self.last_analysis_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✓ 分析结果已保存: {self.last_analysis_file}")
        except Exception as e:
            print(f"保存分析结果失败: {e}")
    
    def _calculate_incremental(self, current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
        """计算增量变化"""
        if not previous:
            return {
                'is_first_run': True,
                'crisis_score_delta': 0,
                'dimension_changes': {},
                'new_insights': current.get('key_insights', []),
                'trend_changed': False
            }
        
        current_score = current.get('crisis_score', 0)
        previous_score = previous.get('crisis_score', 0)
        
        current_dims = current.get('dimensions', {})
        previous_dims = previous.get('dimensions', {})
        
        # 计算三个维度的变化
        dimension_changes = {}
        for dim in ['military', 'diplomacy', 'energy']:
            curr_dim = current_dims.get(dim, {})
            prev_dim = previous_dims.get(dim, {})
            
            curr_score = curr_dim.get('score', 0)
            prev_score = prev_dim.get('score', 0)
            
            dimension_changes[dim] = {
                'delta': round(curr_score - prev_score, 2),
                'current_score': curr_score,
                'previous_score': prev_score,
                'direction': 'up' if curr_score > prev_score else 'down' if curr_score < prev_score else 'stable'
            }
        
        # 识别新的洞察
        current_insights = set(current.get('key_insights', []))
        previous_insights = set(previous.get('key_insights', []))
        new_insights = list(current_insights - previous_insights)
        
        return {
            'is_first_run': False,
            'crisis_score_delta': round(current_score - previous_score, 2),
            'dimension_changes': dimension_changes,
            'new_insights': new_insights,
            'trend_changed': current.get('trend') != previous.get('trend'),
            'previous_timestamp': previous.get('timestamp'),
            'current_timestamp': current.get('timestamp')
        }
    
    def run_once(self) -> Dict[str, Any]:
        """
        一次性运行模式
        
        Returns:
            包含分析结果和报告路径的字典
        """
        print("=" * 60)
        print("🚀 OilAnalyzer 一次性运行模式")
        print("=" * 60)
        
        # 第1步：获取新闻
        print("\n[第1步/第5步] 获取地缘政治新闻...")
        news_data = self.fetcher.get_geopolitical_news()
        articles_count = news_data.get('total_articles', 0)
        print(f"✓ 获取到 {articles_count} 条新闻")
        
        if articles_count == 0:
            print("⚠ 没有获取到新闻，Pipeline终止")
            return self._get_empty_result()
        
        # 第2步：关键词预过滤
        print("\n[第2步/第5步] 关键词预过滤...")
        articles = news_data.get('articles', [])
        filtered_articles = self.fetcher._filter_articles_by_keywords(articles)
        news_data['articles'] = filtered_articles
        print(f"✓ 过滤后保留 {len(filtered_articles)} 篇相关新闻")
        
        if len(filtered_articles) == 0:
            print("⚠ 过滤后没有相关新闻，Pipeline终止")
            return self._get_empty_result()
        
        # 第3步：Ollama全权分析（含URL内容获取）
        print("\n[第3步/第5步] Ollama AI分析（含URL内容获取）...")
        analysis = self.analyzer.analyze_with_ai(news_data)
        
        # 第3.5步：全面翻译
        print("\n[第3.5步] 全面翻译确保中文...")
        news_data, analysis = self._translate_all_content(news_data, analysis)
        
        # 翻译executive_summary
        exec_summary = analysis.get('executive_summary', '')
        if exec_summary and not self._is_chinese(exec_summary):
            print("  翻译执行摘要...")
            analysis['executive_summary'] = self._translate_with_ollama(exec_summary)
        
        # 第4步：汇总总结
        print("\n[第4步/第5步] 生成汇总...")
        summary = self._generate_summary(analysis, news_data)
        
        # 将新闻摘要和影响力数据添加到新闻数据中
        enriched_articles = analysis.get('enriched_articles', [])
        for i, article in enumerate(news_data.get('articles', [])):
            if i < len(enriched_articles):
                enriched = enriched_articles[i]
                if 'summary_cn' in enriched:
                    article['summary_cn'] = enriched['summary_cn']
                if 'title_cn' in enriched:
                    article['title_cn'] = enriched['title_cn']
                if 'impact' in enriched:
                    article['impact'] = enriched['impact']
        
        # 第5步：生成HTML报告（仅非Web模式）
        if not self.web_mode:
            print("\n[第5步/第5步] 生成HTML报告...")
            report_path = self.report_generator.generate(analysis, news_data)
        else:
            print("\n[第5步/第5步] 跳过HTML报告生成（Web模式）")
            report_path = ""
        
        # 保存JSON数据
        json_path = self._save_json_data(analysis, news_data)
        
        # 保存到last_analysis.json（用于Web界面）
        self._save_last_analysis(analysis, summary)
        
        # 更新已处理URL记录
        for article in filtered_articles:
            url = article.get('url', '')
            if url:
                self.processed_urls.add(url)
        self._save_processed_urls()
        
        # 打印最终结果
        print("\n" + "=" * 60)
        print("📊 分析完成")
        print("=" * 60)
        print(f"危机评分: {analysis.get('crisis_score', 'N/A')}/10")
        print(f"趋势: {analysis.get('trend', 'N/A')}")
        print(f"HTML报告: {report_path}")
        print(f"JSON数据: {json_path}")
        print("=" * 60)
        
        return {
            "analysis": analysis,
            "news_data": news_data,
            "summary": summary,
            "report_path": report_path,
            "json_path": json_path,
            "timestamp": datetime.now().isoformat()
        }
    
    def run_continuous(self, interval_minutes: int = 60):
        """
        持续运行模式
        
        Args:
            interval_minutes: 检查间隔（分钟）
        """
        print("=" * 60)
        print("🔄 OilAnalyzer 持续运行模式")
        print("=" * 60)
        print(f"检查间隔: {interval_minutes} 分钟")
        print("按 Ctrl+C 停止监控")
        print("=" * 60)
        
        # 第一次运行：与一次性运行相同
        print("\n📊 第一次运行：生成完整报告...")
        result = self.run_once()
        self.is_first_run = False
        
        # 后续运行：只分析增量新闻
        while True:
            try:
                print(f"\n⏳ 等待 {interval_minutes} 分钟后进行下一次检查...")
                time.sleep(interval_minutes * 60)
                
                print(f"\n🔍 检查增量新闻 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]...")
                self._run_incremental()
                
            except KeyboardInterrupt:
                print("\n\n⏹ 收到停止信号，正在关闭监控...")
                break
            except Exception as e:
                print(f"\n✗ 运行出错: {e}")
                print("继续运行...")
    
    def _run_incremental(self):
        """运行增量分析"""
        # 获取新闻
        news_data = self.fetcher.get_geopolitical_news()
        articles = news_data.get('articles', [])
        
        # 过滤已处理的URL
        new_articles = []
        for article in articles:
            url = article.get('url', '')
            if url and url not in self.processed_urls:
                new_articles.append(article)
        
        if not new_articles:
            print("  ✓ 没有新的增量新闻")
            return
        
        print(f"  ✓ 发现 {len(new_articles)} 条增量新闻")
        
        # 关键词预过滤
        filtered_articles = self.fetcher._filter_articles_by_keywords(new_articles)
        
        if not filtered_articles:
            print("  ✓ 过滤后没有相关新闻")
            return
        
        print(f"  ✓ 过滤后保留 {len(filtered_articles)} 篇相关新闻")
        
        # 更新news_data
        news_data['articles'] = filtered_articles
        
        # 分析
        print("  ✓ 正在分析增量新闻...")
        analysis = self.analyzer.analyze_with_ai(news_data)
        
        # 翻译
        news_data, analysis = self._translate_all_content(news_data, analysis)
        
        # 生成报告（仅非Web模式）
        if not self.web_mode:
            report_path = self.report_generator.generate(analysis, news_data)
        else:
            report_path = ""
        
        json_path = self._save_json_data(analysis, news_data)
        
        # 保存到last_analysis.json（用于Web界面）
        summary = self._generate_summary(analysis, news_data)
        self._save_last_analysis(analysis, summary)
        
        # 更新已处理URL记录
        for article in filtered_articles:
            url = article.get('url', '')
            if url:
                self.processed_urls.add(url)
        self._save_processed_urls()
        
        print(f"  ✓ 增量分析完成")
        print(f"    危机评分: {analysis.get('crisis_score', 'N/A')}/10")
        print(f"    趋势: {analysis.get('trend', 'N/A')}")
        if not self.web_mode:
            print(f"    HTML报告: {report_path}")
        else:
            print(f"    数据已更新（Web模式）")
    
    def _generate_summary(self, analysis: Dict[str, Any], news_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成汇总"""
        crisis_score = analysis.get('crisis_score', 0)
        trend = analysis.get('trend', 'stable')
        severity = analysis.get('severity_assessment', {})
        classification = analysis.get('classification', {})
        
        summary = {
            "crisis_level": self._get_crisis_level(crisis_score),
            "crisis_score": crisis_score,
            "trend": trend,
            "dimensions": {
                "military": {
                    "count": len(classification.get('military', [])),
                    "severity": severity.get('military', {}).get('level', 'low'),
                    "score": severity.get('military', {}).get('score', 0)
                },
                "diplomacy": {
                    "count": len(classification.get('diplomacy', [])),
                    "severity": severity.get('diplomacy', {}).get('level', 'low'),
                    "score": severity.get('diplomacy', {}).get('score', 0)
                },
                "energy": {
                    "count": len(classification.get('energy', [])),
                    "severity": severity.get('energy', {}).get('level', 'low'),
                    "score": severity.get('energy', {}).get('score', 0)
                }
            },
            "total_articles": news_data.get('total_articles', 0),
            "executive_summary": analysis.get('executive_summary', '')
        }
        
        print(f"  危机等级: {summary['crisis_level']}")
        print(f"  军事新闻: {summary['dimensions']['military']['count']}条")
        print(f"  外交新闻: {summary['dimensions']['diplomacy']['count']}条")
        print(f"  能源新闻: {summary['dimensions']['energy']['count']}条")
        
        return summary
    
    def _get_crisis_level(self, score: float) -> str:
        """获取危机等级"""
        if score >= 8:
            return "🔴 极高风险"
        elif score >= 6:
            return "🟠 高风险"
        elif score >= 4:
            return "🟡 中等风险"
        else:
            return "🟢 低风险"
    
    def _save_json_data(self, analysis: Dict[str, Any], news_data: Dict[str, Any]) -> str:
        """保存JSON数据"""
        os.makedirs("data", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存分析结果
        analysis_file = f"data/geopolitical_analysis_{timestamp}.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
        
        # 保存新闻数据
        news_file = f"data/geopolitical_news_{timestamp}.json"
        with open(news_file, 'w', encoding='utf-8') as f:
            json.dump(news_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✓ 分析数据已保存: {analysis_file}")
        print(f"✓ 新闻数据已保存: {news_file}")
        
        return analysis_file
    
    def _translate_all_content(self, news_data: Dict[str, Any], analysis: Dict[str, Any]) -> tuple:
        """批量翻译所有内容，减少Ollama调用次数"""
        import ollama
        
        print("  收集需要翻译的文本...")
        
        # 收集所有需要翻译的文本
        texts_to_translate = []
        text_mapping = []
        
        # 1. 收集新闻标题
        articles = news_data.get('articles', [])
        for article in articles:
            title = article.get('title', '')
            if title and not self._is_chinese(title):
                texts_to_translate.append(title)
                text_mapping.append(('title', article))
        
        # 2. 收集分类标题
        classification = analysis.get('classification', {})
        for cat in ['military', 'diplomacy', 'energy']:
            titles = classification.get(cat, [])
            for title in titles:
                if not self._is_chinese(title):
                    texts_to_translate.append(title)
                    text_mapping.append(('class_title', (cat, title)))
        
        # 3. 收集趋势描述
        trend_desc = analysis.get('trend_description', '')
        if trend_desc and not self._is_chinese(trend_desc):
            texts_to_translate.append(trend_desc)
            text_mapping.append(('trend_desc', analysis))
        
        # 4. 收集关键洞察和建议
        for key in ['key_insights', 'strategic_recommendations']:
            items = analysis.get(key, [])
            for item in items:
                if not self._is_chinese(item):
                    texts_to_translate.append(item)
                    text_mapping.append((key, item))
        
        # 5. 收集执行摘要
        exec_summary = analysis.get('executive_summary', '')
        if exec_summary and not self._is_chinese(exec_summary):
            texts_to_translate.append(exec_summary)
            text_mapping.append(('executive_summary', analysis))
        
        if not texts_to_translate:
            print("  ✓ 无需翻译，所有内容已是中文")
            return news_data, analysis
        
        print(f"  需要翻译 {len(texts_to_translate)} 条内容")
        print(f"  正在批量翻译...")
        
        # 批量翻译（1次Ollama调用）
        try:
            texts_list = "\n".join(f"{i+1}. {text}" for i, text in enumerate(texts_to_translate))
            
            prompt = f"""请将以下英文文本翻译成中文，保持简洁准确，每行一个翻译：

{texts_list}

请用JSON格式返回：
{{
    "translations": ["翻译1", "翻译2", ...]
}}

只返回JSON，不要有其他内容。"""

            response = ollama.chat(
                model="gpt-oss:20b-cloud",
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": 0.3}
            )
            
            ai_response = response['message']['content']
            
            # 提取翻译结果
            import re
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            if json_match:
                translations_data = json.loads(json_match.group())
                translations = translations_data.get('translations', [])
            else:
                # 尝试解析每一行
                translations = [line.strip() for line in ai_response.strip().split('\n') if line.strip()]
            
            print(f"  ✓ 翻译完成，获得 {len(translations)} 条翻译")
            
            # 应用翻译
            for i, (text_type, obj) in enumerate(text_mapping):
                if i < len(translations):
                    translated_text = translations[i].strip()
                    
                    if text_type == 'title':
                        obj['title_cn'] = translated_text
                    elif text_type == 'class_title':
                        cat, original_title = obj
                        # 更新analysis中的分类标题
                        if cat in classification:
                            idx = classification[cat].index(original_title)
                            if idx >= 0:
                                classification[cat][idx] = translated_text
                    elif text_type == 'trend_desc':
                        obj['trend_description'] = translated_text
                    elif text_type == 'executive_summary':
                        obj['executive_summary'] = translated_text
                    elif text_type in ['key_insights', 'strategic_recommendations']:
                        # 更新analysis中的洞察/建议
                        if text_type in analysis:
                            for j, item in enumerate(analysis[text_type]):
                                if item == obj:
                                    analysis[text_type][j] = translated_text
                                    break
            
        except Exception as e:
            print(f"  ✗ 批量翻译失败: {e}")
            # 回退到逐条翻译
            print("  回退到逐条翻译...")
            for article in articles:
                if not self._is_chinese(article.get('title', '')):
                    article['title_cn'] = self._translate_with_ollama(article['title'])
        
        return news_data, analysis
    
    def _is_chinese(self, text: str) -> bool:
        """检查文本是否包含中文"""
        if not text:
            return False
        return any('\u4e00' <= char <= '\u9fff' for char in text)
    
    def _translate_with_ollama(self, text: str) -> str:
        """使用Ollama翻译单条文本（作为fallback）"""
        import ollama
        
        try:
            prompt = f"请将以下英文翻译成中文，保持简洁：\n\n{text}\n\n只返回翻译结果。"
            response = ollama.chat(
                model="gpt-oss:20b-cloud",
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response['message']['content'].strip()
        except Exception as e:
            print(f"    翻译失败: {e}")
            return text
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """空结果"""
        return {
            "analysis": {},
            "news_data": {},
            "summary": {"crisis_level": "无数据", "crisis_score": 0},
            "report_path": "",
            "json_path": "",
            "timestamp": datetime.now().isoformat()
        }
    
    def load_cold_start_data(self) -> Dict[str, Any]:
        """
        冷启动：加载最新的报告数据
        
        Returns:
            包含最新分析结果的字典
        """
        print("❄️ 冷启动：加载最新报告数据...")
        
        # 查找reports目录下最新的报告文件
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            print("  ⚠ reports目录不存在")
            return self._get_empty_result()
        
        # 查找所有HTML报告文件
        report_files = []
        for file in os.listdir(reports_dir):
            if file.startswith("geopolitical_report_") and file.endswith(".html"):
                report_files.append(os.path.join(reports_dir, file))
        
        if not report_files:
            print("  ⚠ 没有找到报告文件")
            return self._get_empty_result()
        
        # 按修改时间排序，获取最新的报告
        latest_report = max(report_files, key=os.path.getmtime)
        print(f"  ✓ 找到最新报告: {latest_report}")
        
        # 查找对应的JSON数据文件
        report_basename = os.path.basename(latest_report)
        timestamp = report_basename.replace("geopolitical_report_", "").replace(".html", "")
        
        # 查找对应的分析JSON文件
        analysis_file = f"data/geopolitical_analysis_{timestamp}.json"
        news_file = f"data/geopolitical_news_{timestamp}.json"
        
        if not os.path.exists(analysis_file):
            print(f"  ⚠ 没有找到对应的分析文件: {analysis_file}")
            return self._get_empty_result()
        
        try:
            # 加载分析数据
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
            
            # 加载新闻数据（如果存在）
            news_data = {}
            if os.path.exists(news_file):
                with open(news_file, 'r', encoding='utf-8') as f:
                    news_data = json.load(f)
            
            # 生成汇总
            summary = self._generate_summary(analysis, news_data)
            
            print(f"  ✓ 冷启动数据加载完成")
            print(f"    危机评分: {analysis.get('crisis_score', 'N/A')}/10")
            print(f"    趋势: {analysis.get('trend', 'N/A')}")
            print(f"    时间戳: {timestamp}")
            
            # 缓存冷启动数据
            self.cold_start_data = {
                "analysis": analysis,
                "news_data": news_data,
                "summary": summary,
                "report_path": latest_report,
                "json_path": analysis_file,
                "timestamp": timestamp
            }
            
            return self.cold_start_data
            
        except Exception as e:
            print(f"  ✗ 加载冷启动数据失败: {e}")
            return self._get_empty_result()
    
    def run_web_mode(self, interval_minutes: int = 60, host: str = "0.0.0.0", port: int = 5000):
        """
        Web模式运行（冷启动 + 后台异步更新）
        
        Args:
            interval_minutes: 检查间隔（分钟）
            host: Web服务器监听地址
            port: Web服务器端口
        """
        print("=" * 60)
        print("🌐 OilAnalyzer Web模式")
        print("=" * 60)
        print(f"检查间隔: {interval_minutes} 分钟")
        print(f"访问地址: http://{host}:{port}")
        print("=" * 60)
        
        # 冷启动：加载最新报告数据
        print("\n❄️ 冷启动阶段...")
        cold_data = self.load_cold_start_data()
        
        if cold_data.get('analysis'):
            print("✓ 冷启动完成，用户可立即看到内容")
        else:
            print("⚠ 冷启动未找到数据，将进行首次分析")
            cold_data = self.run_once()
        
        # 启动Web服务器
        try:
            from web_server import WebServer, create_dashboard_template
            
            # 创建仪表盘模板
            create_dashboard_template()
            
            # 创建Web服务器
            server = WebServer(self, host=host, port=port)
            
            # 在后台启动Web服务器
            server.start_background()
            
            print(f"\n🚀 Web服务器已启动: http://{host}:{port}")
            print("📊 用户可立即看到冷启动数据")
            print("🔄 后台将进行增量更新...")
            
            # 后台异步更新
            self.is_first_run = False
            
            while True:
                try:
                    print(f"\n⏳ 等待 {interval_minutes} 分钟后进行下一次检查...")
                    time.sleep(interval_minutes * 60)
                    
                    print(f"\n🔍 检查增量新闻 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]...")
                    self._run_incremental()
                    
                except KeyboardInterrupt:
                    print("\n\n⏹ 收到停止信号，正在关闭监控...")
                    break
                except Exception as e:
                    print(f"\n✗ 运行出错: {e}")
                    print("继续运行...")
                    
        except ImportError as e:
            print(f"✗ 无法启动Web服务器: {e}")
            print("请运行: pip install flask")
            sys.exit(1)
    
    def get_timeline_data(self, max_items: int = 10) -> List[Dict[str, Any]]:
        """
        获取事件时间线数据（按时间倒序）
        
        Args:
            max_items: 最大事件数量
            
        Returns:
            按时间排序的事件列表
        """
        timeline_events = []
        
        # 从last_analysis中获取事件
        if self.last_analysis and 'last_analysis' in self.last_analysis:
            last_analysis = self.last_analysis['last_analysis']
            
            # 获取关键洞察作为事件
            key_insights = last_analysis.get('key_insights', [])
            timestamp = last_analysis.get('timestamp', '')
            
            for i, insight in enumerate(key_insights[:max_items]):
                timeline_events.append({
                    'timestamp': timestamp,
                    'title': insight,
                    'source': 'AI分析',
                    'category': 'insight'
                })
        
        # 从news_data中获取新闻事件
        if hasattr(self, 'cold_start_data') and self.cold_start_data:
            news_data = self.cold_start_data.get('news_data', {})
            articles = news_data.get('articles', [])
            
            for article in articles[:max_items]:
                published_at = article.get('publishedAt', '')
                title_cn = article.get('title_cn', article.get('title', ''))
                source = article.get('source', '')
                
                if published_at and title_cn:
                    timeline_events.append({
                        'timestamp': published_at,
                        'title': title_cn,
                        'source': source,
                        'category': 'news'
                    })
        
        # 按时间倒序排序
        timeline_events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # 返回指定数量的事件
        return timeline_events[:max_items]


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='OilAnalyzer - 地缘政治新闻分析系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  一次性运行: python oil_analyzer.py --once
  持续运行: python oil_analyzer.py --continuous --interval 60
  持续运行+Web界面: python oil_analyzer.py --continuous --web --interval 5
        """
    )
    
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--once', action='store_true', help='一次性运行模式')
    parser.add_argument('--continuous', action='store_true', help='持续运行模式')
    parser.add_argument('--interval', type=int, default=60, help='持续运行模式下的检查间隔（分钟），默认60分钟')
    parser.add_argument('--web', action='store_true', help='启用Web界面（仅持续运行模式）')
    parser.add_argument('--port', type=int, default=5000, help='Web服务器端口，默认5000')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Web服务器监听地址，默认0.0.0.0')
    
    args = parser.parse_args()
    
    # 创建OilAnalyzer实例
    analyzer = OilAnalyzer(config_path=args.config)
    
    # 根据参数选择运行模式
    if args.once:
        # 一次性运行模式
        result = analyzer.run_once()
        sys.exit(0 if result.get('report_path') else 1)
    elif args.continuous:
        # 持续运行模式
        if args.web:
            # 启用Web界面
            try:
                from web_server import WebServer, create_dashboard_template
                
                # 创建仪表盘模板
                create_dashboard_template()
                
                # 创建Web服务器
                server = WebServer(analyzer, host=args.host, port=args.port)
                
                # 在后台启动Web服务器
                server.start_background()
                
                # 运行持续监控
                analyzer.run_continuous(interval_minutes=args.interval)
                
            except ImportError as e:
                print(f"✗ 无法启动Web服务器: {e}")
                print("请运行: pip install flask")
                sys.exit(1)
        else:
            # 无Web界面的持续监控
            analyzer.run_continuous(interval_minutes=args.interval)
    else:
        # 默认：一次性运行模式
        result = analyzer.run_once()
        sys.exit(0 if result.get('report_path') else 1)


if __name__ == "__main__":
    main()