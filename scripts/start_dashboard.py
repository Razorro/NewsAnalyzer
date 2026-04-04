#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动RSS新闻监控仪表盘
"""
import json
import os
import sys
import time
import threading

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from news_fetcher import DataFetcher
from ollama_analyzer import OllamaAnalyzer
from rss_manager import RSSManager
from web_server import WebServer


def main():
    """启动RSS仪表盘"""
    print("=" * 60)
    print("🛢️ OilAnalyzer - RSS新闻监控仪表盘")
    print("=" * 60)
    
    # 加载配置
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✓ 配置文件已加载: {config_path}")
    except Exception as e:
        print(f"✗ 加载配置文件失败: {e}")
        config = {}
    
    # 初始化组件
    print("\n[1/4] 初始化数据获取器...")
    fetcher = DataFetcher()
    print("  ✓ DataFetcher 初始化完成")
    
    print("\n[2/4] 初始化Ollama分析器...")
    analyzer = OllamaAnalyzer()
    print(f"  ✓ OllamaAnalyzer 初始化完成")
    print(f"    分析模型: {analyzer.analysis_model}")
    print(f"    翻译模型: {analyzer.translation_model}")
    
    print("\n[3/4] 初始化RSS管理器...")
    rss_manager = RSSManager(fetcher, analyzer, config)
    rss_manager.init_default_feeds()
    
    feeds = rss_manager.get_feeds()
    enabled_count = sum(1 for f in feeds if f['enabled'])
    print(f"  ✓ RSS管理器初始化完成")
    print(f"    订阅源总数: {len(feeds)}")
    print(f"    已启用: {enabled_count}")
    
    # 恢复未完成的分析任务（12小时内的pending/analyzing状态新闻）
    print("\n[3.5/4] 检查待分析任务...")
    rss_manager.resume_pending_analysis(hours=12)
    
    print("\n[4/4] 初始化Web服务器...")
    # 创建一个简单的分析器包装类
    class AnalyzerWrapper:
        def __init__(self):
            self.last_analysis_file = "data/last_analysis.json"
            self.cold_start_data = {}
        
        def load_cold_start_data(self):
            return {}
        
        def get_timeline_data(self, max_items=10):
            return []
    
    wrapper = AnalyzerWrapper()
    server = WebServer(wrapper, host="0.0.0.0", port=5000)
    server.init_rss_manager(rss_manager)
    print("  ✓ Web服务器初始化完成")
    
    # 启动定时拉取任务
    print("\n[定时任务] 启动RSS定时拉取...")
    fetch_interval = config.get("rss_panel", {}).get("fetch_interval_minutes", 30)
    
    def periodic_fetch():
        """定时拉取RSS"""
        while True:
            try:
                time.sleep(fetch_interval * 60)
                print(f"\n⏰ 定时拉取触发 (间隔: {fetch_interval}分钟)")
                rss_manager.run_fetch_cycle()
            except Exception as e:
                print(f"定时拉取出错: {e}")
    
    fetch_thread = threading.Thread(target=periodic_fetch, daemon=True)
    fetch_thread.start()
    print(f"  ✓ 定时任务已启动，每 {fetch_interval} 分钟拉取一次")
    
    # 启动首次拉取
    print("\n[首次拉取] 开始获取新闻...")
    def initial_fetch():
        time.sleep(3)  # 等待服务器启动
        try:
            rss_manager.run_fetch_cycle()
        except Exception as e:
            print(f"首次拉取出错: {e}")
    
    initial_thread = threading.Thread(target=initial_fetch, daemon=True)
    initial_thread.start()
    
    # 显示访问信息
    print("\n" + "=" * 60)
    print("🚀 启动完成！")
    print("=" * 60)
    print(f"\n📡 访问地址:")
    print(f"   RSS新闻监控: http://localhost:5000/rss")
    print(f"\n⏰ 定时拉取: 每 {fetch_interval} 分钟")
    print(f"   首次拉取将在3秒后开始...")
    print(f"\n按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    # 启动Web服务器
    try:
        server.start(debug=False)
    except KeyboardInterrupt:
        print("\n\n⏹ 服务器已停止")
    except Exception as e:
        print(f"\n✗ 服务器启动失败: {e}")


if __name__ == "__main__":
    main()