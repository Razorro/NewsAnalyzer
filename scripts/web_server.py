#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OilAnalyzer Web服务器
提供动态仪表盘和SSE实时推送
"""
import json
import os
import sqlite3
import time
import threading
from datetime import datetime
from typing import Dict, Any

try:
    from flask import Flask, render_template, Response, jsonify, send_from_directory, request
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    print("警告: Flask未安装，Web服务器功能不可用。安装命令: pip install flask")


class WebServer:
    """OilAnalyzer Web服务器"""
    
    def __init__(self, oil_analyzer, host: str = "0.0.0.0", port: int = 5000):
        """
        初始化Web服务器
        
        Args:
            oil_analyzer: OilAnalyzer实例
            host: 监听主机
            port: 监听端口
        """
        if not HAS_FLASK:
            raise ImportError("Flask未安装，请运行: pip install flask")
        
        self.analyzer = oil_analyzer
        self.host = host
        self.port = port
        
        # RSS管理器（延迟初始化）
        self.rss_manager = None
        
        # 创建Flask应用
        self.app = Flask(__name__, 
                        template_folder='../templates',
                        static_folder='../static')
        
        # 注册路由
        self._register_routes()
        
        # 客户端连接管理
        self.clients = []
        self.clients_lock = threading.Lock()
    
    def init_rss_manager(self, rss_manager):
        """初始化RSS管理器"""
        self.rss_manager = rss_manager
        print("✓ RSS管理器已关联到Web服务器")
    
    def _register_routes(self):
        """注册路由"""
        
        @self.app.route('/')
        def dashboard():
            """仪表盘页面"""
            return render_template('dashboard.html')
        
        @self.app.route('/api/analysis')
        def get_analysis():
            """获取最新分析结果"""
            try:
                if os.path.exists(self.analyzer.last_analysis_file):
                    with open(self.analyzer.last_analysis_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return jsonify(data)
                else:
                    return jsonify({'error': '暂无分析数据'}), 404
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/history')
        def get_history():
            """获取历史分析记录"""
            try:
                if os.path.exists(self.analyzer.last_analysis_file):
                    with open(self.analyzer.last_analysis_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return jsonify(data.get('history', []))
                else:
                    return jsonify([])
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/stream')
        def stream():
            """SSE实时推送"""
            return Response(self._event_stream(), 
                          mimetype='text/event-stream',
                          headers={
                              'Cache-Control': 'no-cache',
                              'Connection': 'keep-alive',
                              'X-Accel-Buffering': 'no'
                          })
        
        @self.app.route('/static/<path:filename>')
        def static_files(filename):
            """静态文件服务"""
            return send_from_directory('../static', filename)
        
        @self.app.route('/api/dashboard-config')
        def get_dashboard_config():
            """获取仪表盘配置"""
            try:
                config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'dashboard_config.json')
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    return jsonify(config)
                else:
                    # 返回默认配置
                    return jsonify({
                        "layout": {"columns": 2, "gap": "20px"},
                        "theme": {
                            "primary_color": "#00ffff",
                            "accent_color": "#ff00ff",
                            "background": "#0a0a0f"
                        },
                        "components": []
                    })
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/timeline')
        def get_timeline():
            """获取事件时间线数据"""
            try:
                max_items = request.args.get('max_items', 10, type=int)
                timeline_data = self.analyzer.get_timeline_data(max_items=max_items)
                return jsonify(timeline_data)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/cold-start')
        def get_cold_start_data():
            """获取冷启动数据"""
            try:
                if hasattr(self.analyzer, 'cold_start_data') and self.analyzer.cold_start_data:
                    return jsonify(self.analyzer.cold_start_data)
                else:
                    # 如果没有冷启动数据，尝试加载
                    cold_data = self.analyzer.load_cold_start_data()
                    return jsonify(cold_data)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # ==================== RSS相关路由 ====================
        
        @self.app.route('/rss')
        def rss_dashboard():
            """RSS新闻监控仪表盘"""
            return render_template('news_dashboard.html')
        
        @self.app.route('/api/rss/feeds', methods=['GET'])
        def get_rss_feeds():
            """获取所有订阅源"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                feeds = self.rss_manager.get_feeds()
                return jsonify(feeds)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/feeds', methods=['POST'])
        def add_rss_feed():
            """添加订阅源"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                data = request.get_json()
                name = data.get('name', '').strip()
                url = data.get('url', '').strip()
                
                if not name or not url:
                    return jsonify({'success': False, 'message': '名称和URL不能为空'})
                
                result = self.rss_manager.add_feed(name, url)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/feeds/<int:feed_id>', methods=['DELETE'])
        def delete_rss_feed(feed_id):
            """删除订阅源"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                result = self.rss_manager.delete_feed(feed_id)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/feeds/<int:feed_id>/toggle', methods=['POST'])
        def toggle_rss_feed(feed_id):
            """启用/禁用订阅源"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                data = request.get_json()
                enabled = data.get('enabled', True)
                result = self.rss_manager.toggle_feed(feed_id, enabled)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/news')
        def get_rss_news():
            """获取新闻列表"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                limit = request.args.get('limit', 50, type=int)
                offset = request.args.get('offset', 0, type=int)
                news = self.rss_manager.get_news_list(limit=limit, offset=offset)
                return jsonify(news)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/dashboard-stats')
        def get_rss_dashboard_stats():
            """获取RSS看板统计数据"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                stats = self.rss_manager.get_dashboard_stats()
                return jsonify(stats)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/alerts')
        def get_rss_alerts():
            """获取预警列表"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                limit = request.args.get('limit', 5, type=int)
                alerts = self.rss_manager.get_alerts(limit=limit)
                return jsonify(alerts)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/stream')
        def rss_stream():
            """RSS SSE实时推送"""
            if not self.rss_manager:
                return Response("RSS管理器未初始化", status=500)
            
            return Response(self._rss_event_stream(), 
                          mimetype='text/event-stream',
                          headers={
                              'Cache-Control': 'no-cache',
                              'Connection': 'keep-alive',
                              'X-Accel-Buffering': 'no'
                          })
        
        @self.app.route('/api/rss/fetch', methods=['POST'])
        def trigger_rss_fetch():
            """手动触发RSS拉取"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                # 在后台线程中运行拉取
                thread = threading.Thread(target=self.rss_manager.run_fetch_cycle, daemon=True)
                thread.start()
                return jsonify({'success': True, 'message': '拉取任务已启动'})
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/queue-length')
        def get_queue_length():
            """获取分析队列长度"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                queue_length = self.rss_manager.analysis_queue.qsize()
                return jsonify({'queue_length': queue_length})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # ==================== 主题管理API ====================
        
        @self.app.route('/api/rss/themes', methods=['GET'])
        def get_themes():
            """获取所有主题"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                themes = self.rss_manager.get_themes()
                return jsonify(themes)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/themes', methods=['POST'])
        def add_theme():
            """添加新主题"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                data = request.get_json()
                name = data.get('name', '').strip()
                description = data.get('description', '').strip()
                
                if not name:
                    return jsonify({'success': False, 'message': '主题名称不能为空'})
                
                result = self.rss_manager.add_theme(name, description)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/themes/<int:theme_id>', methods=['DELETE'])
        def delete_theme(theme_id):
            """删除主题"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                result = self.rss_manager.delete_theme(theme_id)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/themes/<int:theme_id>/suggest', methods=['POST'])
        def suggest_keywords(theme_id):
            """AI推荐关键词"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                # 获取主题信息
                themes = self.rss_manager.get_themes()
                theme = next((t for t in themes if t['id'] == theme_id), None)
                
                if not theme:
                    return jsonify({'success': False, 'message': '主题不存在'})
                
                # 调用Ollama推荐
                keywords = self.rss_manager.suggest_keywords_for_theme(
                    theme['name'], 
                    theme.get('description', '')
                )
                
                return jsonify({
                    'success': True,
                    'keywords': keywords
                })
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/themes/<int:theme_id>/import', methods=['POST'])
        def import_keywords(theme_id):
            """批量导入关键词"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                data = request.get_json()
                keywords = data.get('keywords', [])
                
                if not keywords:
                    return jsonify({'success': False, 'message': '关键词列表为空'})
                
                result = self.rss_manager.import_keywords_to_theme(theme_id, keywords)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/themes/update-stats', methods=['POST'])
        def update_keyword_stats():
            """更新关键词匹配统计"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                self.rss_manager.update_keyword_match_counts()
                return jsonify({'success': True, 'message': '统计已更新'})
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        # ==================== 主题关键词精细管理 API ====================
        
        @self.app.route('/api/rss/themes/tree', methods=['GET'])
        def get_themes_tree():
            """获取主题树状结构（用于树状展示）"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                themes = self.rss_manager.get_themes_with_keywords()
                return jsonify(themes)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/themes/<int:theme_id>/keywords', methods=['GET'])
        def get_theme_keywords(theme_id):
            """获取主题下的关键词"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                keywords = self.rss_manager.get_theme_keywords(theme_id)
                return jsonify(keywords)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/themes/<int:theme_id>/keywords', methods=['POST'])
        def add_theme_keyword(theme_id):
            """向主题添加关键词"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                data = request.get_json()
                keyword = data.get('keyword', '').strip()
                
                if not keyword:
                    return jsonify({'success': False, 'message': '关键词不能为空'})
                
                result = self.rss_manager.add_keyword_to_theme_v2(theme_id, keyword)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/themes/keywords/<int:keyword_id>', methods=['PUT'])
        def update_theme_keyword(keyword_id):
            """更新主题下的关键词"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                data = request.get_json()
                new_keyword = data.get('keyword', '').strip()
                
                if not new_keyword:
                    return jsonify({'success': False, 'message': '关键词不能为空'})
                
                result = self.rss_manager.update_theme_keyword(keyword_id, new_keyword)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/themes/keywords/<int:keyword_id>', methods=['DELETE'])
        def delete_theme_keyword(keyword_id):
            """删除主题下的关键词"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                result = self.rss_manager.delete_theme_keyword(keyword_id)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/themes/<int:theme_id>/toggle', methods=['POST'])
        def toggle_theme(theme_id):
            """启用/禁用主题"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                data = request.get_json()
                enabled = data.get('enabled', True)
                
                result = self.rss_manager.toggle_theme(theme_id, enabled)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/keywords/stats', methods=['GET'])
        def get_keyword_stats():
            """获取关键词统计概览"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                stats = self.rss_manager.get_keyword_stats()
                return jsonify(stats)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/keywords/search', methods=['GET'])
        def search_keywords():
            """搜索关键词"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                query = request.args.get('q', '').strip()
                if not query:
                    return jsonify([])
                
                keywords = self.rss_manager.search_keywords(query)
                return jsonify(keywords)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rss/keywords/migrate', methods=['POST'])
        def migrate_keywords():
            """从配置文件迁移关键词到数据库"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                self.rss_manager.migrate_keywords_from_config()
                return jsonify({'success': True, 'message': '迁移完成'})
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/rss/keyword-categories/<int:category_id>/toggle', methods=['POST'])
        def toggle_keyword_category(category_id):
            """启用/禁用关键词分类"""
            if not self.rss_manager:
                return jsonify({'error': 'RSS管理器未初始化'}), 500
            
            try:
                data = request.get_json()
                enabled = data.get('enabled', True)
                
                result = self.rss_manager.toggle_keyword_category(category_id, enabled)
                return jsonify(result)
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
    
    def _rss_event_stream(self):
        """RSS SSE事件流生成器"""
        messages = self.rss_manager.register_sse_client()
        
        print(f"  ✓ RSS客户端连接")
        
        try:
            # 发送初始数据
            yield f"data: {json.dumps({'type': 'connected', 'message': '已连接'}, ensure_ascii=False)}\n\n"
            
            # 持续推送新消息
            last_check = 0
            while True:
                # 检查新消息
                while messages:
                    try:
                        message = messages.pop(0)
                        yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                    except IndexError:
                        break
                
                time.sleep(1)  # 每秒检查一次
                
        except GeneratorExit:
            pass
        finally:
            self.rss_manager.unregister_sse_client(messages)
            print(f"  ✓ RSS客户端断开")
    
    def _event_stream(self):
        """SSE事件流生成器"""
        client_id = id(threading.current_thread())
        
        with self.clients_lock:
            self.clients.append(client_id)
        
        print(f"  ✓ 客户端连接: {client_id}")
        
        try:
            # 发送初始数据
            if os.path.exists(self.analyzer.last_analysis_file):
                with open(self.analyzer.last_analysis_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
            # 持续推送更新
            last_modified = 0
            while True:
                try:
                    if os.path.exists(self.analyzer.last_analysis_file):
                        current_modified = os.path.getmtime(self.analyzer.last_analysis_file)
                        
                        if current_modified > last_modified:
                            with open(self.analyzer.last_analysis_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                            last_modified = current_modified
                    
                    time.sleep(5)  # 每5秒检查一次更新
                    
                except Exception as e:
                    print(f"  ✗ SSE推送错误: {e}")
                    time.sleep(5)
        
        finally:
            with self.clients_lock:
                if client_id in self.clients:
                    self.clients.remove(client_id)
            print(f"  ✓ 客户端断开: {client_id}")
    
    def notify_update(self, analysis_data: Dict[str, Any]):
        """通知所有客户端有更新（用于主动推送）"""
        # SSE会自动检测文件变化，这里可以用于未来扩展
        pass
    
    def start(self, debug: bool = False):
        """启动Web服务器"""
        print("=" * 60)
        print("🌐 OilAnalyzer Web服务器启动")
        print("=" * 60)
        print(f"访问地址: http://{self.host}:{self.port}")
        print(f"按 Ctrl+C 停止服务器")
        print("=" * 60)
        
        try:
            self.app.run(host=self.host, port=self.port, debug=debug, threaded=True)
        except KeyboardInterrupt:
            print("\n\n⏹ Web服务器已停止")
        except Exception as e:
            print(f"\n✗ Web服务器启动失败: {e}")
    
    def start_background(self):
        """在后台启动Web服务器"""
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        print(f"✓ Web服务器已在后台启动: http://{self.host}:{self.port}")
        return thread


def create_dashboard_template():
    """创建仪表盘HTML模板"""
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OilAnalyzer 实时监控仪表盘</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
        
        :root {
            --cyber-bg: #0a0a0f;
            --cyber-card: #0d1117;
            --cyber-cyan: #00ffff;
            --cyber-magenta: #ff00ff;
            --cyber-green: #00ff00;
            --cyber-orange: #ff6600;
            --cyber-red: #ff0040;
            --cyber-border: #30363d;
            --cyber-text: #e6edf3;
            --cyber-gray: #8b949e;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Share Tech Mono', monospace;
            background: var(--cyber-bg);
            min-height: 100vh;
            color: var(--cyber-text);
            background-image: 
                linear-gradient(rgba(0,255,255,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,255,255,0.03) 1px, transparent 1px);
            background-size: 50px 50px;
        }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        .header {
            text-align: center;
            padding: 30px;
            background: linear-gradient(135deg, rgba(0,255,255,0.1), rgba(255,0,255,0.1));
            border: 2px solid var(--cyber-cyan);
            margin-bottom: 20px;
        }
        
        .header h1 {
            font-family: 'Orbitron', sans-serif;
            font-size: 36px;
            color: var(--cyber-cyan);
            text-shadow: 0 0 20px var(--cyber-cyan);
            margin-bottom: 10px;
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 20px;
            background: var(--cyber-green);
            color: black;
            font-weight: bold;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        
        .cyber-card {
            background: var(--cyber-card);
            border: 1px solid var(--cyber-border);
            padding: 25px;
            margin-bottom: 20px;
            position: relative;
        }
        
        .cyber-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--cyber-cyan), var(--cyber-magenta), var(--cyber-green));
        }
        
        .card-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 18px;
            color: var(--cyber-cyan);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .score-display { text-align: center; margin: 20px 0; }
        
        .score-number {
            font-family: 'Orbitron', sans-serif;
            font-size: 100px;
            font-weight: 900;
            color: var(--cyber-cyan);
            text-shadow: 0 0 30px var(--cyber-cyan);
            animation: glow 2s ease-in-out infinite alternate;
        }
        
        @keyframes glow {
            from { text-shadow: 0 0 30px var(--cyber-cyan); }
            to { text-shadow: 0 0 60px var(--cyber-cyan), 0 0 90px var(--cyber-cyan); }
        }
        
        .trend-badge {
            display: inline-block;
            padding: 10px 25px;
            font-weight: bold;
            margin-top: 15px;
        }
        
        .trend-up { background: var(--cyber-red); color: white; }
        .trend-down { background: var(--cyber-green); color: black; }
        .trend-stable { background: var(--cyber-orange); color: black; }
        
        .dimensions-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-top: 20px;
        }
        
        .dimension-card {
            background: rgba(0,255,255,0.05);
            border: 1px solid var(--cyber-border);
            padding: 20px;
            text-align: center;
        }
        
        .dimension-score {
            font-family: 'Orbitron', sans-serif;
            font-size: 36px;
            font-weight: 700;
            margin: 10px 0;
        }
        
        .dimension-delta {
            font-size: 14px;
            margin-top: 5px;
        }
        
        .delta-up { color: var(--cyber-red); }
        .delta-down { color: var(--cyber-green); }
        .delta-stable { color: var(--cyber-gray); }
        
        .insights-list { list-style: none; }
        
        .insights-list li {
            padding: 15px;
            margin-bottom: 10px;
            background: rgba(0,255,255,0.05);
            border-left: 4px solid var(--cyber-cyan);
        }
        
        .new-insight { border-left-color: var(--cyber-magenta); }
        
        .timestamp {
            text-align: center;
            color: var(--cyber-gray);
            font-size: 12px;
            margin-top: 20px;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            color: var(--cyber-gray);
        }
        
        @media (max-width: 768px) {
            .dimensions-grid { grid-template-columns: 1fr; }
            .score-number { font-size: 60px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛢️ OILANALYZER</h1>
            <p>实时地缘政治威胁监控仪表盘</p>
            <span class="status-badge" id="status">📡 连接中...</span>
        </div>
        
        <div class="cyber-card">
            <div class="card-title">📊 威胁等级</div>
            <div class="score-display">
                <div class="score-number" id="crisis-score">--</div>
                <div style="color: var(--cyber-gray);">/ 10</div>
                <div class="trend-badge" id="trend-badge">加载中...</div>
            </div>
        </div>
        
        <div class="cyber-card">
            <div class="card-title">📈 三维评估</div>
            <div class="dimensions-grid">
                <div class="dimension-card">
                    <div>⚔️ 军事</div>
                    <div class="dimension-score" id="military-score">--</div>
                    <div class="dimension-delta" id="military-delta">--</div>
                </div>
                <div class="dimension-card">
                    <div>🤝 外交</div>
                    <div class="dimension-score" id="diplomacy-score">--</div>
                    <div class="dimension-delta" id="diplomacy-delta">--</div>
                </div>
                <div class="dimension-card">
                    <div>⛽ 能源</div>
                    <div class="dimension-score" id="energy-score">--</div>
                    <div class="dimension-delta" id="energy-delta">--</div>
                </div>
            </div>
        </div>
        
        <div class="cyber-card">
            <div class="card-title">💡 关键洞察</div>
            <ul class="insights-list" id="insights-list">
                <li class="loading">加载中...</li>
            </ul>
        </div>
        
        <div class="timestamp" id="timestamp">最后更新: --</div>
    </div>
    
    <script>
        // SSE连接
        const eventSource = new EventSource('/stream');
        
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                updateDashboard(data);
                document.getElementById('status').textContent = '🟢 实时连接';
            } catch (e) {
                console.error('解析数据失败:', e);
            }
        };
        
        eventSource.onerror = function() {
            document.getElementById('status').textContent = '🔴 连接断开';
        };
        
        function updateDashboard(data) {
            const lastAnalysis = data.last_analysis || {};
            const incremental = data.incremental || {};
            
            // 更新危机评分
            const score = lastAnalysis.crisis_score || 0;
            document.getElementById('crisis-score').textContent = score.toFixed(1);
            
            // 更新趋势
            const trend = lastAnalysis.trend || 'stable';
            const trendBadge = document.getElementById('trend-badge');
            trendBadge.className = 'trend-badge';
            
            if (trend === 'escalating') {
                trendBadge.textContent = '⬆ 升级';
                trendBadge.classList.add('trend-up');
            } else if (trend === 'de-escalating') {
                trendBadge.textContent = '⬇ 降级';
                trendBadge.classList.add('trend-down');
            } else {
                trendBadge.textContent = '➡ 稳定';
                trendBadge.classList.add('trend-stable');
            }
            
            // 更新三个维度
            const dimensions = lastAnalysis.dimensions || {};
            const dimChanges = incremental.dimension_changes || {};
            
            ['military', 'diplomacy', 'energy'].forEach(dim => {
                const dimData = dimensions[dim] || {};
                const change = dimChanges[dim] || {};
                
                document.getElementById(`${dim}-score`).textContent = (dimData.score || 0).toFixed(1);
                
                const deltaEl = document.getElementById(`${dim}-delta`);
                const delta = change.delta || 0;
                
                if (delta > 0) {
                    deltaEl.textContent = `▲ +${delta.toFixed(2)}`;
                    deltaEl.className = 'dimension-delta delta-up';
                } else if (delta < 0) {
                    deltaEl.textContent = `▼ ${delta.toFixed(2)}`;
                    deltaEl.className = 'dimension-delta delta-down';
                } else {
                    deltaEl.textContent = '━ 无变化';
                    deltaEl.className = 'dimension-delta delta-stable';
                }
            });
            
            // 更新洞察列表
            const insights = lastAnalysis.key_insights || [];
            const newInsights = incremental.new_insights || [];
            const insightsList = document.querySelector('.insights-list');
            
            insightsList.innerHTML = insights.map(insight => {
                const isNew = newInsights.includes(insight);
                return `<li class="${isNew ? 'new-insight' : ''}">${isNew ? '🆕 ' : '▸ '}${insight}</li>`;
            }).join('');
            
            // 更新时间戳
            const timestamp = lastAnalysis.timestamp || '未知';
            document.querySelector('.timestamp').textContent = `最后更新: ${timestamp}`;
        }
        
        // 初始加载
        fetch('/api/analysis')
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    updateDashboard(data);
                }
            })
            .catch(err => console.error('加载失败:', err));
    </script>
</body>
</html>'''
    
    template_path = os.path.join(template_dir, 'dashboard.html')
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✓ 仪表盘模板已创建: {template_path}")


def main():
    """测试Web服务器"""
    if not HAS_FLASK:
        print("✗ Flask未安装，无法启动Web服务器")
        print("请运行: pip install flask")
        return
    
    # 创建仪表盘模板
    create_dashboard_template()
    
    # 创建测试用的NewsAnalyzer实例
    from news_analyzer import OilAnalyzer
    
    analyzer = OilAnalyzer()
    server = WebServer(analyzer, host="0.0.0.0", port=5000)
    
    # 启动服务器
    server.start()


if __name__ == "__main__":
    main()