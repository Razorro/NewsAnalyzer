"""
RSS新闻管理器
负责RSS订阅源管理、新闻拉取、AI分析和整体情绪更新
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from queue import Queue
import hashlib

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    print("警告: feedparser未安装，将无法使用RSS功能。安装命令: pip install feedparser")


class RSSManager:
    """RSS新闻管理器"""
    
    def __init__(self, data_fetcher, ollama_analyzer, config: Dict = None):
        """
        初始化RSS管理器
        
        Args:
            data_fetcher: DataFetcher实例
            ollama_analyzer: OllamaAnalyzer实例
            config: 配置字典
        """
        self.data_fetcher = data_fetcher
        self.ollama_analyzer = ollama_analyzer
        self.config = config or {}
        
        # 数据库路径
        self.db_path = "data/rss_news.db"
        
        # 分析队列
        self.analysis_queue = Queue()
        
        # SSE客户端管理
        self.sse_clients = []
        self.sse_lock = threading.Lock()
        
        # 当前整体情绪
        self.current_sentiment = self._load_sentiment()
        
        # 初始化数据库
        self._init_database()
        
        # 启动分析工作线程
        self._start_analysis_worker()
        
        # 加载配置
        self.fetch_interval = self.config.get("rss_panel", {}).get("fetch_interval_minutes", 30)
        self.max_news_per_feed = self.config.get("rss_panel", {}).get("max_news_per_feed", 20)
        
        print(f"✓ RSS管理器初始化完成")
        print(f"  数据库: {self.db_path}")
        print(f"  拉取间隔: {self.fetch_interval}分钟")
    
    def _migrate_database(self, conn, cursor):
        """数据库迁移 - 处理表结构变更"""
        try:
            # 检查themes表是否有category_id列
            cursor.execute("PRAGMA table_info(themes)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'category_id' not in columns:
                print("  🔄 执行数据库迁移：添加themes.category_id列")
                cursor.execute('ALTER TABLE themes ADD COLUMN category_id INTEGER')
                conn.commit()
                print("  ✓ 数据库迁移完成")
        except Exception as e:
            print(f"  ⚠ 数据库迁移警告: {e}")
    
    def _init_database(self):
        """初始化SQLite数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 先执行数据库迁移
        self._migrate_database(conn, cursor)
        
        # 新闻表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                title_cn TEXT,
                source TEXT,
                source_name TEXT,
                url TEXT UNIQUE,
                published_at TEXT,
                summary TEXT,
                summary_cn TEXT,
                full_content TEXT,
                ollama_analysis TEXT,
                analysis_status TEXT DEFAULT 'pending',
                is_important INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 订阅源表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                enabled INTEGER DEFAULT 1,
                last_fetched TEXT,
                article_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 整体情绪历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sentiment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                sentiment_json TEXT,
                trigger_news_id TEXT,
                tension_score REAL,
                negative_pct REAL,
                change_summary TEXT
            )
        ''')
        
        # 主题表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                enabled INTEGER DEFAULT 1,
                category_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES keyword_categories(id) ON DELETE SET NULL
            )
        ''')
        
        # 主题关键词表（旧表，保留用于兼容）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS theme_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                is_auto_generated INTEGER DEFAULT 0,
                match_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE,
                UNIQUE(theme_id, keyword)
            )
        ''')
        
        # 关键词分类表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                color TEXT DEFAULT '#00ffff',
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 关键词表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                keyword_cn TEXT,
                category_id INTEGER,
                source TEXT DEFAULT 'manual',
                match_count INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES keyword_categories(id) ON DELETE SET NULL
            )
        ''')
        
        # 创建唯一索引防止重复关键词
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_keyword_unique 
            ON keywords(keyword, category_id)
        ''')
        
        conn.commit()
        conn.close()
        
        # 初始化默认分类
        self._init_default_categories()
        
        print(f"  ✓ 数据库表初始化完成")
    
    def _load_sentiment(self) -> Dict:
        """加载当前整体情绪"""
        default_sentiment = {
            "version": 0,
            "updated_at": datetime.now().isoformat(),
            "sentiment_index": {"negative": 50, "neutral": 40, "positive": 10},
            "tension_score": {"current": 5.0, "previous": 5.0, "trend": "stable"},
            "oil_outlook": {"direction": "震荡", "confidence": 0.5, "score": 5.0},
            "dominant_factors": ["等待数据更新"],
            "recent_change": None,
            "history": []
        }
        
        sentiment_file = "data/overall_sentiment.json"
        if os.path.exists(sentiment_file):
            try:
                with open(sentiment_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return default_sentiment
    
    def _save_sentiment(self):
        """保存整体情绪"""
        os.makedirs("data", exist_ok=True)
        with open("data/overall_sentiment.json", 'w', encoding='utf-8') as f:
            json.dump(self.current_sentiment, f, indent=2, ensure_ascii=False)
    
    def _start_analysis_worker(self):
        """启动后台分析工作线程"""
        def worker():
            while True:
                try:
                    news_id = self.analysis_queue.get()
                    self._analyze_article(news_id)
                except Exception as e:
                    print(f"分析工作线程错误: {e}")
                finally:
                    self.analysis_queue.task_done()
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        print(f"  ✓ 分析工作线程已启动")
    
    def resume_pending_analysis(self, hours: int = 12):
        """
        恢复未完成的分析任务（仅限最近N小时内的新闻）
        超过时间范围的未完成新闻将被删除
        
        Args:
            hours: 时间范围（小时），默认12小时
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 计算时间阈值
        threshold = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 删除超过时间范围的未完成新闻
        cursor.execute('''
            DELETE FROM news 
            WHERE analysis_status != 'completed' 
            AND created_at < ?
        ''', (threshold,))
        
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            print(f"  🗑️ 已删除 {deleted_count} 条过期未完成新闻（>{hours}小时）")
        
        conn.commit()
        
        # 查询未完成且在时间范围内的新闻
        cursor.execute('''
            SELECT id, title FROM news 
            WHERE analysis_status != 'completed' 
            AND created_at >= ?
            ORDER BY created_at DESC
        ''', (threshold,))
        
        pending_news = cursor.fetchall()
        conn.close()
        
        if not pending_news:
            print(f"  ✓ 无需恢复的分析任务（{hours}小时内）")
            return
        
        print(f"  🔄 恢复 {len(pending_news)} 条待分析新闻...")
        
        # 加入分析队列
        for row in pending_news:
            self.analysis_queue.put(row['id'])
            print(f"    - {row['title'][:40]}...")
        
        print(f"  ✓ 已加入分析队列: {len(pending_news)} 条")
    
    def _init_default_categories(self):
        """初始化默认关键词分类"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 默认分类
        default_categories = [
            ("military", "军事", "#ff0040"),
            ("diplomacy", "外交", "#00ffff"),
            ("energy", "能源", "#ff6600"),
            ("economic", "经济", "#00ff00"),
            ("technology", "科技", "#ff00ff"),
            ("politics", "政治", "#ffff00"),
        ]
        
        for name, display_name, color in default_categories:
            cursor.execute('''
                INSERT OR IGNORE INTO keyword_categories (name, display_name, color)
                VALUES (?, ?, ?)
            ''', (name, display_name, color))
        
        conn.commit()
        conn.close()
        
        print(f"  ✓ 已初始化 {len(default_categories)} 个默认分类")
    
    def init_default_feeds(self):
        """初始化默认订阅源（从config加载）"""
        # 检查数据库中是否已有订阅源
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM feeds')
        feed_count = cursor.fetchone()[0]
        
        # 如果已有订阅源，跳过初始化
        if feed_count > 0:
            conn.close()
            print(f"  ✓ 数据库已有 {feed_count} 个订阅源，跳过默认初始化")
            return
        
        # 只在数据库为空时才插入默认订阅源
        rss_feeds = self.config.get("geopolitical_news", {}).get("news_sources", {}).get("rss_feeds", {})
        
        if not rss_feeds:
            conn.close()
            print("⚠ 配置中未找到RSS源")
            return
        
        for name, url in rss_feeds.items():
            cursor.execute('''
                INSERT OR IGNORE INTO feeds (name, url, enabled)
                VALUES (?, ?, 1)
            ''', (name, url))
        
        conn.commit()
        conn.close()
        
        print(f"  ✓ 已初始化 {len(rss_feeds)} 个默认订阅源")
    
    def get_feeds(self) -> List[Dict]:
        """获取所有订阅源"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM feeds ORDER BY name')
        feeds = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return feeds
    
    def add_feed(self, name: str, url: str) -> Dict:
        """添加订阅源"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO feeds (name, url, enabled)
                VALUES (?, ?, 1)
            ''', (name, url))
            
            feed_id = cursor.lastrowid
            conn.commit()
            
            return {"success": True, "id": feed_id, "message": "订阅源添加成功"}
        except sqlite3.IntegrityError:
            return {"success": False, "message": "订阅源URL已存在"}
        except Exception as e:
            return {"success": False, "message": f"添加失败: {str(e)}"}
        finally:
            conn.close()
    
    def delete_feed(self, feed_id: int) -> Dict:
        """删除订阅源"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM feeds WHERE id = ?', (feed_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        if deleted:
            return {"success": True, "message": "订阅源已删除"}
        else:
            return {"success": False, "message": "订阅源不存在"}
    
    def toggle_feed(self, feed_id: int, enabled: bool) -> Dict:
        """启用/禁用订阅源"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE feeds SET enabled = ? WHERE id = ?', (1 if enabled else 0, feed_id))
        updated = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        if updated:
            return {"success": True, "message": "状态已更新"}
        else:
            return {"success": False, "message": "订阅源不存在"}
    
    def fetch_all_feeds(self) -> List[Dict]:
        """拉取所有启用的订阅源"""
        if not HAS_FEEDPARSER:
            print("⚠ feedparser未安装，无法拉取RSS")
            return []
        
        feeds = self.get_feeds()
        enabled_feeds = [f for f in feeds if f['enabled']]
        
        all_articles = []
        
        print(f"  开始拉取 {len(enabled_feeds)} 个订阅源...")
        
        for feed in enabled_feeds:
            articles = self._fetch_single_feed(feed)
            all_articles.extend(articles)
        
        # 去重
        unique_articles = self._deduplicate(all_articles)
        
        print(f"  ✓ 拉取完成: {len(all_articles)} 条 → 去重后 {len(unique_articles)} 条")
        
        return unique_articles
    
    def _fetch_single_feed(self, feed: Dict) -> List[Dict]:
        """拉取单个订阅源"""
        articles = []
        
        try:
            print(f"    拉取: {feed['name']}...")
            
            feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            
            parsed = feedparser.parse(feed['url'], request_headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml'
            })
            
            if parsed.bozo and not parsed.entries:
                print(f"    ⚠ 解析失败: {feed['name']}")
                return articles
            
            count = 0
            for entry in parsed.entries[:self.max_news_per_feed]:
                # 生成唯一ID
                url = entry.get('link', '')
                news_id = self._generate_news_id(url, entry.get('title', ''))
                
                # 解析发布时间并统一格式
                published = entry.get('published', entry.get('updated', ''))
                published_iso = self._normalize_date(published)
                
                article = {
                    'id': news_id,
                    'title': entry.get('title', ''),
                    'source': feed['name'],
                    'source_name': feed['name'],
                    'url': url,
                    'published_at': published_iso,
                    'summary': entry.get('summary', entry.get('description', ''))[:500],
                    'full_content': ''
                }
                
                articles.append(article)
                count += 1
            
            print(f"    ✓ {feed['name']}: {count} 条")
            
            # 更新订阅源统计
            self._update_feed_stats(feed['id'], count)
            
        except Exception as e:
            print(f"    ✗ {feed['name']} 失败: {e}")
        
        return articles
    
    def _normalize_date(self, date_str: str) -> str:
        """将各种日期格式统一转换为ISO格式（UTC时区）"""
        if not date_str:
            return datetime.now().isoformat()
        
        date_str = date_str.strip()
        
        try:
            # 优先使用dateutil.parser，它能自动识别各种格式
            try:
                from dateutil import parser as date_parser
                from datetime import timezone
                
                dt = date_parser.parse(date_str)
                
                # 如果没有时区信息，假设为UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                # 转换为UTC时区
                dt_utc = dt.astimezone(timezone.utc)
                
                print(f"  ✓ 日期解析成功: '{date_str}' → {dt_utc.isoformat()}")
                return dt_utc.isoformat()
                
            except ImportError:
                print(f"  ⚠ dateutil未安装，尝试手动解析: {date_str}")
            except Exception as e:
                print(f"  ⚠ dateutil解析失败: {date_str} - {e}，尝试手动解析")
            
            # 如果dateutil失败，尝试手动解析
            from datetime import timezone
            
            formats = [
                '%a, %d %b %Y %H:%M:%S %z',  # Wed, 25 Mar 2026 14:24:11 +0000
                '%a, %d %b %Y %H:%M:%S %Z',  # Wed, 25 Mar 2026 14:24:11 GMT
                '%Y-%m-%dT%H:%M:%S%z',       # 2026-03-25T14:24:11+0000
                '%Y-%m-%dT%H:%M:%SZ',        # 2026-03-25T14:24:11Z
                '%Y-%m-%d %H:%M:%S',         # 2026-03-25 14:24:11
                '%a, %d %b %Y %H:%M:%S',     # Wed, 25 Mar 2026 14:24:11
                '%Y-%m-%dT%H:%M:%S.%f%z',    # 2026-03-25T14:24:11.000+0000
                '%Y-%m-%dT%H:%M:%S.%fZ',     # 2026-03-25T14:24:11.000Z
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    
                    # 如果没有时区信息，假设为UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    
                    # 转换为UTC时区
                    dt_utc = dt.astimezone(timezone.utc)
                    
                    print(f"  ✓ 手动解析成功: '{date_str}' → {dt_utc.isoformat()}")
                    return dt_utc.isoformat()
                except:
                    continue
            
            # 所有格式都失败
            print(f"  ✗ 日期解析失败: '{date_str}'，使用当前时间")
            return datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            print(f"  ✗ 日期解析异常: {date_str} - {e}")
            from datetime import timezone
            return datetime.now(timezone.utc).isoformat()
    
    def _generate_news_id(self, url: str, title: str) -> str:
        """生成新闻唯一ID"""
        content = f"{url}_{title}"
        hash_obj = hashlib.md5(content.encode())
        return f"news_{hash_obj.hexdigest()[:12]}"
    
    def _update_feed_stats(self, feed_id: int, article_count: int):
        """更新订阅源统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE feeds 
            SET last_fetched = ?, article_count = article_count + ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), article_count, feed_id))
        
        conn.commit()
        conn.close()
    
    def _deduplicate(self, articles: List[Dict]) -> List[Dict]:
        """去重"""
        seen_urls = set()
        unique = []
        
        for article in articles:
            url = article.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(article)
        
        return unique
    
    def save_articles(self, articles: List[Dict]) -> List[str]:
        """保存文章到数据库，返回新文章ID列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        new_ids = []
        
        for article in articles:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO news (id, title, source, source_name, url, published_at, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article['id'],
                    article['title'],
                    article['source'],
                    article['source_name'],
                    article['url'],
                    article['published_at'],
                    article['summary']
                ))
                
                if cursor.rowcount > 0:
                    new_ids.append(article['id'])
            except Exception as e:
                print(f"保存文章失败: {e}")
        
        conn.commit()
        conn.close()
        
        return new_ids
    
    def _analyze_article(self, news_id: str):
        """分析单篇文章"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取文章
        cursor.execute('SELECT * FROM news WHERE id = ?', (news_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return
        
        article = dict(row)
        
        # 更新状态为分析中
        cursor.execute('UPDATE news SET analysis_status = ? WHERE id = ?', ('analyzing', news_id))
        conn.commit()
        
        # 通知队列更新（开始分析）
        self._notify_queue_update()
        
        # 准备分析内容
        title = article.get('title', '')
        summary = article.get('summary', '')
        content = f"{title}\n{summary}"
        
        try:
            # 调用Ollama分析
            analysis_result = self._call_ollama_analysis(content, title)
            
            # 判断是否为重要事件
            is_important = self._is_important_event(analysis_result)
            
            # 保存分析结果
            cursor.execute('''
                UPDATE news 
                SET ollama_analysis = ?, analysis_status = ?, is_important = ?
                WHERE id = ?
            ''', (json.dumps(analysis_result, ensure_ascii=False), 'completed', 1 if is_important else 0, news_id))
            
            conn.commit()
            
            # 通知前端
            self._notify_news_analyzed(news_id, article, analysis_result)
            
            # 通知队列更新（分析完成）
            self._notify_queue_update()
            
            # 如果是重要事件，更新整体情绪
            if is_important:
                self._update_overall_sentiment(news_id, analysis_result)
            
            print(f"  ✓ 分析完成: {title[:30]}...")
            
        except Exception as e:
            print(f"  ✗ 分析失败 {news_id}: {e}")
            
            cursor.execute('UPDATE news SET analysis_status = ? WHERE id = ?', ('failed', news_id))
            conn.commit()
            
            # 通知队列更新（分析失败）
            self._notify_queue_update()
        
        finally:
            conn.close()
    
    def _call_ollama_analysis(self, content: str, title: str) -> Dict:
        """调用Ollama分析新闻"""
        prompt = f"""请分析以下新闻内容，返回JSON格式的分析结果：

新闻标题：{title}
新闻内容：{content[:800]}

请返回以下结构的JSON（不要包含其他内容）：
{{
    "classification": {{
        "category": "军事/外交/能源/经济",
        "subcategory": "具体子类别",
        "confidence": 0.0-1.0
    }},
    "sentiment": {{
        "polarity": "positive/neutral/negative",
        "intensity": 0.0-1.0,
        "label": "中文情绪标签"
    }},
    "entities": {{
        "countries": ["涉及国家"],
        "organizations": ["涉及组织"],
        "locations": ["涉及地点"]
    }},
    "impact_assessment": {{
        "oil_impact": "low/medium/high/extreme",
        "oil_impact_score": 0.0-10.0,
        "geopolitical_severity": "low/medium/high/critical",
        "market_reaction": "expect_bearish/neutral/bullish"
    }},
    "key_insights": ["关键洞察1", "关键洞察2"],
    "chinese_summary": "一句话中文摘要"
}}"""

        try:
            import ollama
            
            response = ollama.chat(
                model=self.ollama_analyzer.translation_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": 0.3}
            )
            
            result_text = response['message']['content']
            
            # 提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            print(f"Ollama调用失败: {e}")
        
        # 返回默认值
        return self._get_default_analysis()
    
    def _get_default_analysis(self) -> Dict:
        """返回默认分析结果"""
        return {
            "classification": {"category": "unknown", "subcategory": "unknown", "confidence": 0},
            "sentiment": {"polarity": "neutral", "intensity": 0.5, "label": "中性"},
            "entities": {"countries": [], "organizations": [], "locations": []},
            "impact_assessment": {"oil_impact": "medium", "oil_impact_score": 5.0, "geopolitical_severity": "medium", "market_reaction": "neutral"},
            "key_insights": ["分析未完成"],
            "chinese_summary": "等待分析..."
        }
    
    def _is_important_event(self, analysis: Dict) -> bool:
        """判断是否为重要事件"""
        impact = analysis.get('impact_assessment', {})
        
        # 油价影响评分 >= 7
        if impact.get('oil_impact_score', 0) >= 7:
            return True
        
        # 严重程度为critical
        if impact.get('geopolitical_severity') == 'critical':
            return True
        
        # 油价影响为extreme
        if impact.get('oil_impact') == 'extreme':
            return True
        
        return False
    
    def _update_overall_sentiment(self, trigger_news_id: str, analysis: Dict):
        """更新整体情绪"""
        print(f"  🔄 更新整体情绪...")
        
        # 准备当前情绪状态
        current_state = json.dumps(self.current_sentiment, ensure_ascii=False)
        
        # 准备新事件信息
        new_event = json.dumps(analysis, ensure_ascii=False)
        
        # 构建提示词
        prompt = f"""基于当前整体情绪状态和新发生的重要事件，请更新整体市场情绪。

当前整体情绪状态：
{current_state}

新事件分析：
{new_event}

请返回更新后的整体情绪JSON：
{{
    "sentiment_index": {{
        "negative": 0-100,
        "neutral": 0-100,
        "positive": 0-100
    }},
    "tension_score": {{
        "current": 0-10,
        "trend": "rising/stable/falling"
    }},
    "oil_outlook": {{
        "direction": "看涨/震荡/看跌",
        "confidence": 0-1,
        "score": 0-10
    }},
    "dominant_factors": ["因素1", "因素2", "因素3"],
    "change_summary": "一句话说明变化原因"
}}

只返回JSON，不要有其他内容。"""

        try:
            import ollama
            
            response = ollama.chat(
                model=self.ollama_analyzer.analysis_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": 0.3}
            )
            
            result_text = response['message']['content']
            
            # 提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                update_result = json.loads(json_match.group())
                
                # 更新情绪数据
                previous_tension = self.current_sentiment.get('tension_score', {}).get('current', 5.0)
                
                self.current_sentiment['version'] = self.current_sentiment.get('version', 0) + 1
                self.current_sentiment['updated_at'] = datetime.now().isoformat()
                self.current_sentiment['sentiment_index'] = update_result.get('sentiment_index', self.current_sentiment['sentiment_index'])
                
                new_tension = update_result.get('tension_score', {}).get('current', previous_tension)
                trend = update_result.get('tension_score', {}).get('trend', 'stable')
                
                self.current_sentiment['tension_score'] = {
                    "current": new_tension,
                    "previous": previous_tension,
                    "trend": trend
                }
                
                self.current_sentiment['oil_outlook'] = update_result.get('oil_outlook', self.current_sentiment['oil_outlook'])
                self.current_sentiment['dominant_factors'] = update_result.get('dominant_factors', self.current_sentiment['dominant_factors'])
                
                self.current_sentiment['recent_change'] = {
                    "trigger_news_id": trigger_news_id,
                    "change_summary": update_result.get('change_summary', ''),
                    "analyzed_at": datetime.now().isoformat()
                }
                
                # 添加历史记录
                history_entry = {
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "tension": new_tension,
                    "negative": self.current_sentiment['sentiment_index'].get('negative', 50)
                }
                self.current_sentiment['history'] = self.current_sentiment.get('history', [])[-23:] + [history_entry]
                
                # 保存
                self._save_sentiment()
                
                # 保存到数据库
                self._save_sentiment_to_db(trigger_news_id, update_result)
                
                # 通知前端
                self._notify_sentiment_update()
                
                print(f"  ✓ 整体情绪已更新: 紧张度 {previous_tension:.1f} → {new_tension:.1f} ({trend})")
                
        except Exception as e:
            print(f"  ✗ 整体情绪更新失败: {e}")
    
    def _save_sentiment_to_db(self, trigger_news_id: str, update_result: Dict):
        """保存情绪历史到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sentiment_history (timestamp, sentiment_json, trigger_news_id, tension_score, negative_pct, change_summary)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            json.dumps(update_result, ensure_ascii=False),
            trigger_news_id,
            update_result.get('tension_score', {}).get('current', 0),
            update_result.get('sentiment_index', {}).get('negative', 0),
            update_result.get('change_summary', '')
        ))
        
        conn.commit()
        conn.close()
    
    def _notify_news_analyzed(self, news_id: str, article: Dict, analysis: Dict):
        """通知前端新闻分析完成"""
        message = {
            "type": "news_analyzed",
            "data": {
                "id": news_id,
                "title": article.get('title', ''),
                "title_cn": analysis.get('chinese_summary', ''),
                "source": article.get('source_name', ''),
                "source_name": article.get('source_name', ''),
                "url": article.get('url', ''),
                "published_at": article.get('published_at', ''),
                "summary_cn": analysis.get('chinese_summary', ''),
                "ollama_analysis": analysis,
                "analysis_status": "completed",  # 添加状态字段
                "is_important": 1 if self._is_important_event(analysis) else 0
            }
        }
        
        print(f"  📤 SSE推送新闻: {article.get('title', '')[:40]}...")
        
        self._broadcast_sse(message)
    
    def _notify_sentiment_update(self):
        """通知前端整体情绪更新"""
        message = {
            "type": "sentiment_updated",
            "data": self.current_sentiment
        }
        
        self._broadcast_sse(message)
    
    def _notify_queue_update(self):
        """通知前端队列长度更新"""
        queue_length = self.analysis_queue.qsize()
        message = {
            "type": "queue_updated",
            "data": {
                "queue_length": queue_length
            }
        }
        
        self._broadcast_sse(message)
    
    def _broadcast_sse(self, message: Dict):
        """广播SSE消息"""
        with self.sse_lock:
            disconnected = []
            
            for client in self.sse_clients:
                try:
                    client.append(message)
                except:
                    disconnected.append(client)
            
            for client in disconnected:
                self.sse_clients.remove(client)
    
    def register_sse_client(self):
        """注册SSE客户端"""
        messages = []
        
        with self.sse_lock:
            self.sse_clients.append(messages)
        
        return messages
    
    def unregister_sse_client(self, messages):
        """注销SSE客户端"""
        with self.sse_lock:
            if messages in self.sse_clients:
                self.sse_clients.remove(messages)
    
    def get_news_list(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取新闻列表（按发布时间倒序，同发布时间按入库时间倒序）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 添加调试：先查询所有新闻的状态分布
        cursor.execute('''
            SELECT analysis_status, COUNT(*) as count 
            FROM news 
            GROUP BY analysis_status
        ''')
        status_counts = cursor.fetchall()
        print(f"  📊 新闻状态分布: {dict(status_counts)}")
        
        cursor.execute('''
            SELECT * FROM news 
            WHERE analysis_status = 'completed'
            ORDER BY published_at DESC, created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        rows = cursor.fetchall()
        
        # 添加调试：打印返回的新闻数量和最新几条的标题
        print(f"  📰 返回 {len(rows)} 条已完成分析的新闻")
        if rows:
            for i, row in enumerate(rows[:3]):
                print(f"    {i+1}. {row['title'][:50]}... (状态: {row['analysis_status']}, 时间: {row['created_at']})")
        
        conn.close()
        
        result = []
        for row in rows:
            news_item = dict(row)
            if news_item.get('ollama_analysis'):
                try:
                    news_item['ollama_analysis'] = json.loads(news_item['ollama_analysis'])
                except:
                    news_item['ollama_analysis'] = self._get_default_analysis()
            result.append(news_item)
        
        return result
    
    def get_dashboard_stats(self) -> Dict:
        """获取看板统计数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 今日新闻数
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM news WHERE DATE(created_at) = ? and analysis_status = 'completed'", (today,))
        today_count = cursor.fetchone()[0]
        
        # 重要事件数
        cursor.execute('SELECT COUNT(*) FROM news WHERE is_important = 1 and DATE(created_at) = ?', (today,))
        alert_count = cursor.fetchone()[0]
        
        # 活跃订阅源数
        cursor.execute('SELECT COUNT(*) FROM feeds WHERE enabled = 1')
        active_feeds = cursor.fetchone()[0]
        
        # 分类分布（仅包含今日新闻和12小时内的已完成新闻）
        twelve_hours_ago = (datetime.now() - timedelta(hours=12)).isoformat()
        cursor.execute('''
            SELECT ollama_analysis FROM news 
            WHERE analysis_status = 'completed' 
            AND (DATE(created_at) = ? OR created_at >= ?)
        ''', (today, twelve_hours_ago))
        rows = cursor.fetchall()
        
        category_counts = {"军事": 0, "外交": 0, "能源": 0, "经济": 0, "unknown": 0}
        sentiment_counts = {"negative": 0, "neutral": 0, "positive": 0}
        total_oil_impact = 0
        oil_count = 0
        
        for row in rows:
            if row[0]:
                try:
                    analysis = json.loads(row[0])
                    category = analysis.get('classification', {}).get('category', 'unknown')
                    
                    if category in category_counts:
                        category_counts[category] += 1
                    else:
                        category_counts['unknown'] += 1
                    
                    polarity = analysis.get('sentiment', {}).get('polarity', 'neutral')
                    if polarity in sentiment_counts:
                        sentiment_counts[polarity] += 1
                    
                    oil_score = analysis.get('impact_assessment', {}).get('oil_impact_score', 0)
                    if oil_score > 0:
                        total_oil_impact += oil_score
                        oil_count += 1
                except:
                    pass
        
        conn.close()
        
        avg_oil_impact = total_oil_impact / oil_count if oil_count > 0 else 0
        
        return {
            "today_count": today_count,
            "analyzed_count": today_count,  # 已分析数等于今日新闻数
            "alert_count": alert_count,
            "active_feeds": active_feeds,
            "category_distribution": category_counts,
            "sentiment_summary": sentiment_counts,
            "avg_oil_impact": round(avg_oil_impact, 1),
            "overall_sentiment": self.current_sentiment
        }
    
    def get_alerts(self, limit: int = 5) -> List[Dict]:
        """获取预警列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, title, source_name, ollama_analysis, created_at 
            FROM news 
            WHERE is_important = 1 AND analysis_status = 'completed'
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        alerts = []
        for row in rows:
            alert = dict(row)
            if alert.get('ollama_analysis'):
                try:
                    analysis = json.loads(alert['ollama_analysis'])
                    alert['oil_impact_score'] = analysis.get('impact_assessment', {}).get('oil_impact_score', 0)
                except:
                    alert['oil_impact_score'] = 0
            alerts.append(alert)
        
        return alerts
    
    def _filter_by_keywords(self, articles: List[Dict]) -> List[Dict]:
        """
        使用关键词过滤相关文章（从SQLite数据库读取关键词）
        
        Args:
            articles: 文章列表
            
        Returns:
            过滤后的文章列表
        """
        # 从SQLite获取所有启用的关键词
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT keyword FROM keywords 
            WHERE enabled = 1
        ''')
        keywords = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not keywords:
            print("  ⚠ 未找到关键词配置，跳过过滤")
            return articles
        
        filtered = []
        for article in articles:
            # 组合标题和摘要进行匹配
            text = (
                article.get('title', '') + ' ' + 
                article.get('summary', '')
            ).lower()
            
            # 计算匹配的关键词数量
            match_count = sum(1 for kw in keywords if kw.lower() in text)
            
            # 至少匹配1个关键词才保留
            if match_count >= 1:
                article['keyword_matches'] = match_count
                filtered.append(article)
        
        # 按匹配数量排序（最相关的在前）
        filtered.sort(key=lambda x: x.get('keyword_matches', 0), reverse=True)
        
        print(f"  关键词过滤: {len(articles)}篇 → {len(filtered)}篇")
        
        return filtered
    
    def run_fetch_cycle(self):
        """运行一次完整的拉取-分析周期"""
        print(f"\n{'='*60}")
        print(f"🔄 RSS拉取周期开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # 1. 拉取所有订阅源
        articles = self.fetch_all_feeds()
        
        if not articles:
            print("  ⚠ 没有获取到新文章")
            return
        
        # 2. 关键词过滤（新增）
        filtered_articles = self._filter_by_keywords(articles)
        
        if not filtered_articles:
            print("  ⚠ 过滤后无相关文章")
            return
        
        # 3. 保存过滤后的文章
        new_ids = self.save_articles(filtered_articles)
        
        print(f"  ✓ 新文章: {len(new_ids)} 条")
        
        # 4. 将新文章加入分析队列
        for news_id in new_ids:
            self.analysis_queue.put(news_id)
        
        print(f"  ✓ 已加入分析队列: {len(new_ids)} 条")
    
    # ==================== 主题管理方法 ====================
    
    def get_themes(self) -> List[Dict]:
        """获取所有主题及其关键词"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取所有主题
        cursor.execute('SELECT * FROM themes ORDER BY created_at DESC')
        themes = [dict(row) for row in cursor.fetchall()]
        
        # 为每个主题获取关键词和匹配统计
        for theme in themes:
            cursor.execute('''
                SELECT keyword, is_auto_generated, match_count 
                FROM theme_keywords 
                WHERE theme_id = ? 
                ORDER BY match_count DESC
            ''', (theme['id'],))
            theme['keywords'] = [dict(row) for row in cursor.fetchall()]
            theme['keyword_count'] = len(theme['keywords'])
            theme['total_matches'] = sum(k['match_count'] for k in theme['keywords'])
        
        conn.close()
        return themes
    
    def add_theme(self, name: str, description: str = "", keywords: Optional[List[str]] = None) -> Dict:
        """添加新主题（自动创建对应分类）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 创建主题
            cursor.execute('''
                INSERT INTO themes (name, description)
                VALUES (?, ?)
            ''', (name, description))
            
            theme_id = cursor.lastrowid
            
            # 自动创建对应的关键词分类
            category_name = f"theme_{theme_id}"
            display_name = f"主题: {name}"
            
            # 生成随机颜色
            import random
            colors = ['#00ffff', '#ff00ff', '#00ff00', '#ff6600', '#ffff00', '#ff0040']
            color = random.choice(colors)
            
            cursor.execute('''
                INSERT INTO keyword_categories (name, display_name, color)
                VALUES (?, ?, ?)
            ''', (category_name, display_name, color))
            
            category_id = cursor.lastrowid
            
            # 更新主题，关联分类ID
            cursor.execute('''
                UPDATE themes SET category_id = ? WHERE id = ?
            ''', (category_id, theme_id))
            
            # 如果提供了关键词，批量添加
            if keywords:
                for keyword in keywords:
                    keyword = keyword.strip()
                    if keyword:
                        cursor.execute('''
                            INSERT OR IGNORE INTO keywords (keyword, category_id, source)
                            VALUES (?, ?, 'theme')
                        ''', (keyword, category_id))
            
            conn.commit()
            
            return {"success": True, "id": theme_id, "category_id": category_id, "message": "主题创建成功"}
        except sqlite3.IntegrityError:
            conn.rollback()
            return {"success": False, "message": "主题名称已存在"}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"创建失败: {str(e)}"}
        finally:
            conn.close()
    
    def delete_theme(self, theme_id: int) -> Dict:
        """删除主题"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM themes WHERE id = ?', (theme_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                return {"success": True, "message": "主题已删除"}
            else:
                return {"success": False, "message": "主题不存在"}
        except Exception as e:
            return {"success": False, "message": f"删除失败: {str(e)}"}
        finally:
            conn.close()
    
    def add_keyword_to_theme(self, theme_id: int, keyword: str, is_auto: bool = False) -> Dict:
        """向主题添加关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO theme_keywords (theme_id, keyword, is_auto_generated)
                VALUES (?, ?, ?)
            ''', (theme_id, keyword, 1 if is_auto else 0))
            
            if cursor.rowcount > 0:
                conn.commit()
                return {"success": True, "message": "关键词添加成功"}
            else:
                return {"success": False, "message": "关键词已存在"}
        except Exception as e:
            return {"success": False, "message": f"添加失败: {str(e)}"}
        finally:
            conn.close()
    
    def delete_keyword_from_theme(self, keyword_id: int) -> Dict:
        """从主题删除关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM theme_keywords WHERE id = ?', (keyword_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                return {"success": True, "message": "关键词已删除"}
            else:
                return {"success": False, "message": "关键词不存在"}
        except Exception as e:
            return {"success": False, "message": f"删除失败: {str(e)}"}
        finally:
            conn.close()
    
    def suggest_keywords_for_theme(self, theme_name: str, description: str = "") -> List[str]:
        """使用Ollama为主题推荐关键词"""
        prompt = f"""请为主题"{theme_name}"推荐20个相关的英文关键词，用于RSS新闻过滤。

主题描述：{description if description else "无"}

要求：
1. 关键词应该是英文
2. 关键词应该与主题高度相关
3. 关键词可以是单词或短语
4. 返回JSON格式

请返回：
{{
    "keywords": ["keyword1", "keyword2", "keyword3", ...]
}}

只返回JSON，不要有其他内容。"""

        try:
            import ollama
            
            response = ollama.chat(
                model=self.ollama_analyzer.translation_model,
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": 0.5}
            )
            
            result_text = response['message']['content']
            
            # 提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                return result.get('keywords', [])
            
        except Exception as e:
            print(f"Ollama推荐失败: {e}")
        
        return []
    
    def import_keywords_to_theme(self, theme_id: int, keywords: List[str]) -> Dict:
        """批量导入关键词到主题（使用新分类系统）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取主题的分类ID
            cursor.execute('SELECT category_id FROM themes WHERE id = ?', (theme_id,))
            theme = cursor.fetchone()
            
            if not theme:
                conn.close()
                return {"success": False, "message": "主题不存在", "imported": 0, "total": len(keywords)}
            
            category_id = theme[0]
            
            if not category_id:
                conn.close()
                return {"success": False, "message": "主题未关联分类", "imported": 0, "total": len(keywords)}
            
            # 批量导入关键词到 keywords 表（新表）
            success_count = 0
            for keyword in keywords:
                keyword = keyword.strip()
                if not keyword:
                    continue
                
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO keywords (keyword, category_id, source)
                        VALUES (?, ?, 'ai_suggest')
                    ''', (keyword, category_id))
                    if cursor.rowcount > 0:
                        success_count += 1
                except:
                    continue
            
            conn.commit()
            conn.close()
            
            return {"success": True, "imported": success_count, "total": len(keywords)}
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return {"success": False, "message": str(e), "imported": 0, "total": len(keywords)}
    
    def update_keyword_match_counts(self):
        """更新所有关键词的匹配统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取所有关键词
        cursor.execute('SELECT id, keyword FROM theme_keywords')
        keywords = cursor.fetchall()
        
        for kw_id, keyword in keywords:
            # 统计匹配的新闻数量
            cursor.execute('''
                SELECT COUNT(*) FROM news 
                WHERE (title LIKE ? OR summary LIKE ?) 
                AND analysis_status = 'completed'
            ''', (f'%{keyword}%', f'%{keyword}%'))
            
            match_count = cursor.fetchone()[0]
            
            # 更新统计
            cursor.execute('UPDATE theme_keywords SET match_count = ? WHERE id = ?', (match_count, kw_id))
        
        conn.commit()
        conn.close()
        
        print(f"  ✓ 关键词匹配统计已更新")
    
    # ==================== 关键词管理方法（SQLite版本） ====================
    
    def get_keyword_categories(self) -> List[Dict]:
        """获取所有关键词分类"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT kc.*, COUNT(k.id) as keyword_count
            FROM keyword_categories kc
            LEFT JOIN keywords k ON k.category_id = kc.id
            GROUP BY kc.id
            ORDER BY kc.name
        ''')
        
        categories = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return categories
    
    def add_keyword_category(self, name: str, display_name: str, color: str = '#00ffff') -> Dict:
        """添加新分类"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO keyword_categories (name, display_name, color)
                VALUES (?, ?, ?)
            ''', (name, display_name, color))
            
            category_id = cursor.lastrowid
            conn.commit()
            
            return {"success": True, "id": category_id, "message": "分类添加成功"}
        except sqlite3.IntegrityError:
            return {"success": False, "message": "分类名称已存在"}
        except Exception as e:
            return {"success": False, "message": f"添加失败: {str(e)}"}
        finally:
            conn.close()
    
    def get_keywords(self, category_id: int = None, enabled_only: bool = True) -> List[Dict]:
        """获取关键词列表（可按分类筛选）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT k.*, kc.name as category_name, kc.display_name as category_display_name, kc.color as category_color
            FROM keywords k
            LEFT JOIN keyword_categories kc ON k.category_id = kc.id
            WHERE 1=1
        '''
        params = []
        
        if category_id is not None:
            query += ' AND k.category_id = ?'
            params.append(category_id)
        
        if enabled_only:
            query += ' AND k.enabled = 1'
        
        query += ' ORDER BY kc.name, k.keyword'
        
        cursor.execute(query, params)
        keywords = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return keywords
    
    def add_keyword(self, keyword: str, category_id: int = None, source: str = 'manual') -> Dict:
        """添加关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 检查是否已存在（同一分类下）
            if category_id:
                cursor.execute('SELECT id FROM keywords WHERE keyword = ? AND category_id = ?', (keyword, category_id))
            else:
                cursor.execute('SELECT id FROM keywords WHERE keyword = ? AND category_id IS NULL', (keyword,))
            
            if cursor.fetchone():
                return {"success": False, "message": "关键词已存在"}
            
            cursor.execute('''
                INSERT INTO keywords (keyword, category_id, source)
                VALUES (?, ?, ?)
            ''', (keyword, category_id, source))
            
            keyword_id = cursor.lastrowid
            conn.commit()
            
            return {"success": True, "id": keyword_id, "message": "关键词添加成功"}
        except Exception as e:
            return {"success": False, "message": f"添加失败: {str(e)}"}
        finally:
            conn.close()
    
    def update_keyword(self, keyword_id: int, **kwargs) -> Dict:
        """更新关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 构建更新语句
            allowed_fields = ['keyword', 'keyword_cn', 'category_id', 'enabled']
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f'{field} = ?')
                    params.append(value)
            
            if not updates:
                return {"success": False, "message": "没有需要更新的字段"}
            
            updates.append('updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(keyword_id)
            
            cursor.execute(f'''
                UPDATE keywords SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
            
            if cursor.rowcount > 0:
                conn.commit()
                return {"success": True, "message": "更新成功"}
            else:
                return {"success": False, "message": "关键词不存在"}
        except Exception as e:
            return {"success": False, "message": f"更新失败: {str(e)}"}
        finally:
            conn.close()
    
    def delete_keyword(self, keyword_id: int) -> Dict:
        """删除关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM keywords WHERE id = ?', (keyword_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                return {"success": True, "message": "关键词已删除"}
            else:
                return {"success": False, "message": "关键词不存在"}
        except Exception as e:
            return {"success": False, "message": f"删除失败: {str(e)}"}
        finally:
            conn.close()
    
    def batch_import_keywords(self, keywords: List[str], category_id: int = None) -> Dict:
        """批量导入关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        success_count = 0
        skip_count = 0
        
        for keyword in keywords:
            keyword = keyword.strip()
            if not keyword:
                continue
            
            try:
                # 检查是否已存在
                if category_id:
                    cursor.execute('SELECT id FROM keywords WHERE keyword = ? AND category_id = ?', (keyword, category_id))
                else:
                    cursor.execute('SELECT id FROM keywords WHERE keyword = ? AND category_id IS NULL', (keyword,))
                
                if cursor.fetchone():
                    skip_count += 1
                    continue
                
                cursor.execute('''
                    INSERT INTO keywords (keyword, category_id, source)
                    VALUES (?, ?, 'import')
                ''', (keyword, category_id))
                success_count += 1
            except:
                skip_count += 1
                continue
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "imported": success_count,
            "skipped": skip_count,
            "total": len(keywords),
            "message": f"成功导入 {success_count} 个关键词，跳过 {skip_count} 个重复项"
        }
    
    def get_keyword_stats(self) -> Dict:
        """获取关键词统计概览"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总关键词数
        cursor.execute('SELECT COUNT(*) FROM keywords')
        total_keywords = cursor.fetchone()[0]
        
        # 启用的关键词数
        cursor.execute('SELECT COUNT(*) FROM keywords WHERE enabled = 1')
        enabled_keywords = cursor.fetchone()[0]
        
        # 分类数
        cursor.execute('SELECT COUNT(*) FROM keyword_categories')
        total_categories = cursor.fetchone()[0]
        
        # 按分类统计
        cursor.execute('''
            SELECT kc.display_name, COUNT(k.id) as count
            FROM keyword_categories kc
            LEFT JOIN keywords k ON k.category_id = kc.id
            GROUP BY kc.id
            ORDER BY count DESC
        ''')
        category_stats = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        # 未分类关键词数
        cursor.execute('SELECT COUNT(*) FROM keywords WHERE category_id IS NULL')
        uncategorized = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_keywords": total_keywords,
            "enabled_keywords": enabled_keywords,
            "total_categories": total_categories,
            "category_stats": category_stats,
            "uncategorized": uncategorized
        }
    
    def search_keywords(self, query: str) -> List[Dict]:
        """搜索关键词"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT k.*, kc.name as category_name, kc.display_name as category_display_name, kc.color as category_color
            FROM keywords k
            LEFT JOIN keyword_categories kc ON k.category_id = kc.id
            WHERE k.keyword LIKE ? OR k.keyword_cn LIKE ?
            ORDER BY k.match_count DESC
            LIMIT 50
        ''', (f'%{query}%', f'%{query}%'))
        
        keywords = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return keywords
    
    def migrate_keywords_from_config(self):
        """从配置文件迁移关键词到数据库"""
        categories_config = self.config.get("geopolitical_news", {}).get("categories", {})
        
        if not categories_config:
            print("⚠ 配置中未找到关键词分类")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        total_migrated = 0
        
        for cat_name, cat_config in categories_config.items():
            if not cat_config.get("enabled", True):
                continue
            
            # 获取分类ID
            cursor.execute('SELECT id FROM keyword_categories WHERE name = ?', (cat_name,))
            row = cursor.fetchone()
            
            if not row:
                # 创建新分类
                display_names = {
                    "military": "军事",
                    "diplomacy": "外交",
                    "energy": "能源",
                    "economic": "经济"
                }
                cursor.execute('''
                    INSERT INTO keyword_categories (name, display_name)
                    VALUES (?, ?)
                ''', (cat_name, display_names.get(cat_name, cat_name)))
                category_id = cursor.lastrowid
            else:
                category_id = row[0]
            
            # 迁移关键词
            keywords = cat_config.get("keywords", [])
            for keyword in keywords:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO keywords (keyword, category_id, source)
                        VALUES (?, ?, 'migrated')
                    ''', (keyword, category_id))
                    if cursor.rowcount > 0:
                        total_migrated += 1
                except:
                    continue
        
        conn.commit()
        conn.close()
        
        print(f"  ✓ 已从配置迁移 {total_migrated} 个关键词到数据库")
    
    def toggle_keyword_category(self, category_id: int, enabled: bool) -> Dict:
        """
        启用/禁用关键词分类（同时更新该分类下所有关键词的状态）
        
        Args:
            category_id: 分类ID
            enabled: True启用，False禁用
            
        Returns:
            操作结果
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 更新分类状态
            cursor.execute('UPDATE keyword_categories SET enabled = ? WHERE id = ?', 
                         (1 if enabled else 0, category_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return {"success": False, "message": "分类不存在"}
            
            # 批量更新该分类下所有关键词的状态
            cursor.execute('UPDATE keywords SET enabled = ? WHERE category_id = ?', 
                         (1 if enabled else 0, category_id))
            
            updated_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            status = "启用" if enabled else "禁用"
            return {
                "success": True, 
                "message": f"已{status}分类及 {updated_count} 个关键词"
            }
            
        except Exception as e:
            conn.close()
            return {"success": False, "message": f"操作失败: {str(e)}"}
    
    def get_keyword_category(self, category_id: int) -> Optional[Dict]:
        """获取单个关键词分类"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT kc.*, COUNT(k.id) as keyword_count
            FROM keyword_categories kc
            LEFT JOIN keywords k ON k.category_id = kc.id
            WHERE kc.id = ?
            GROUP BY kc.id
        ''', (category_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    # ==================== 主题与关键词关联方法 ====================
    
    def get_theme_keywords(self, theme_id: int) -> List[Dict]:
        """获取主题下的所有关键词（通过关联的分类）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取主题信息
        cursor.execute('SELECT category_id FROM themes WHERE id = ?', (theme_id,))
        theme = cursor.fetchone()
        
        if not theme or not theme['category_id']:
            conn.close()
            return []
        
        category_id = theme['category_id']
        
        # 获取该分类下的所有关键词
        cursor.execute('''
            SELECT k.*, kc.display_name as category_display_name, kc.color as category_color
            FROM keywords k
            LEFT JOIN keyword_categories kc ON k.category_id = kc.id
            WHERE k.category_id = ?
            ORDER BY k.match_count DESC, k.keyword
        ''', (category_id,))
        
        keywords = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return keywords
    
    def add_keyword_to_theme_v2(self, theme_id: int, keyword: str) -> Dict:
        """向主题添加关键词（新版本，使用分类系统）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取主题的分类ID
            cursor.execute('SELECT category_id FROM themes WHERE id = ?', (theme_id,))
            theme = cursor.fetchone()
            
            if not theme:
                conn.close()
                return {"success": False, "message": "主题不存在"}
            
            category_id = theme[0]  # 元组索引，不是字典键
            
            if not category_id:
                conn.close()
                return {"success": False, "message": "主题未关联分类"}
            
            # 检查关键词是否已存在
            cursor.execute('SELECT id FROM keywords WHERE keyword = ? AND category_id = ?', (keyword, category_id))
            if cursor.fetchone():
                conn.close()
                return {"success": False, "message": "关键词已存在"}
            
            # 添加关键词
            cursor.execute('''
                INSERT INTO keywords (keyword, category_id, source)
                VALUES (?, ?, 'theme')
            ''', (keyword, category_id))
            
            conn.commit()
            
            return {"success": True, "message": "关键词添加成功"}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"添加失败: {str(e)}"}
        finally:
            conn.close()
    
    def update_theme_keyword(self, keyword_id: int, new_keyword: str) -> Dict:
        """更新主题下的关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 检查关键词是否存在
            cursor.execute('SELECT id, category_id FROM keywords WHERE id = ?', (keyword_id,))
            kw = cursor.fetchone()
            
            if not kw:
                conn.close()
                return {"success": False, "message": "关键词不存在"}
            
            # 检查新关键词是否与其他关键词冲突
            cursor.execute('SELECT id FROM keywords WHERE keyword = ? AND category_id = ? AND id != ?', 
                         (new_keyword, kw[1], keyword_id))
            if cursor.fetchone():
                conn.close()
                return {"success": False, "message": "关键词已存在"}
            
            # 更新关键词
            cursor.execute('''
                UPDATE keywords SET keyword = ?, updated_at = ?
                WHERE id = ?
            ''', (new_keyword, datetime.now().isoformat(), keyword_id))
            
            conn.commit()
            
            return {"success": True, "message": "更新成功"}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"更新失败: {str(e)}"}
        finally:
            conn.close()
    
    def delete_theme_keyword(self, keyword_id: int) -> Dict:
        """删除主题下的关键词"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM keywords WHERE id = ?', (keyword_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                return {"success": True, "message": "删除成功"}
            else:
                return {"success": False, "message": "关键词不存在"}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"删除失败: {str(e)}"}
        finally:
            conn.close()
    
    def toggle_theme(self, theme_id: int, enabled: bool) -> Dict:
        """启用/禁用主题（同时启用/禁用关联的分类和关键词）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取主题信息
            cursor.execute('SELECT category_id FROM themes WHERE id = ?', (theme_id,))
            theme = cursor.fetchone()
            
            if not theme:
                conn.close()
                return {"success": False, "message": "主题不存在"}
            
            category_id = theme[0]  # 元组索引，不是字典键
            
            # 更新主题状态
            cursor.execute('UPDATE themes SET enabled = ? WHERE id = ?', (1 if enabled else 0, theme_id))
            
            # 更新关联分类状态
            if category_id:
                cursor.execute('UPDATE keyword_categories SET enabled = ? WHERE id = ?', 
                            (1 if enabled else 0, category_id))
                
                # 更新该分类下所有关键词状态
                cursor.execute('UPDATE keywords SET enabled = ? WHERE category_id = ?', 
                            (1 if enabled else 0, category_id))
            
            conn.commit()
            
            status = "启用" if enabled else "禁用"
            return {"success": True, "message": f"主题已{status}"}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"操作失败: {str(e)}"}
        finally:
            conn.close()
    
    def get_themes_with_keywords(self) -> List[Dict]:
        """获取所有主题及其关联的关键词（用于树状展示）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取所有主题
        cursor.execute('SELECT * FROM themes ORDER BY created_at DESC')
        themes = [dict(row) for row in cursor.fetchall()]
        
        for theme in themes:
            category_id = theme.get('category_id')
            
            if category_id:
                # 获取该主题关联的关键词
                cursor.execute('''
                    SELECT k.id, k.keyword, k.match_count, k.enabled,
                           kc.display_name as category_name, kc.color as category_color
                    FROM keywords k
                    LEFT JOIN keyword_categories kc ON k.category_id = kc.id
                    WHERE k.category_id = ?
                    ORDER BY k.match_count DESC, k.keyword
                ''', (category_id,))
                
                theme['keywords'] = [dict(row) for row in cursor.fetchall()]
                theme['keyword_count'] = len(theme['keywords'])
                theme['total_matches'] = sum(k.get('match_count', 0) for k in theme['keywords'])
                
                # 获取分类颜色
                cursor.execute('SELECT color FROM keyword_categories WHERE id = ?', (category_id,))
                cat = cursor.fetchone()
                theme['color'] = cat['color'] if cat else '#00ffff'
            else:
                theme['keywords'] = []
                theme['keyword_count'] = 0
                theme['total_matches'] = 0
                theme['color'] = '#00ffff'
        
        conn.close()
        return themes


def main():
    """测试RSS管理器"""
    from news_fetcher import DataFetcher
    from ollama_analyzer import OllamaAnalyzer
    import json
    
    # 加载配置
    with open('config/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 初始化
    fetcher = DataFetcher()
    analyzer = OllamaAnalyzer()
    
    rss_manager = RSSManager(fetcher, analyzer, config)
    
    # 初始化默认订阅源
    rss_manager.init_default_feeds()
    
    # 显示订阅源
    feeds = rss_manager.get_feeds()
    print(f"\n订阅源列表 ({len(feeds)} 个):")
    for feed in feeds:
        status = "✓" if feed['enabled'] else "✗"
        print(f"  {status} {feed['name']}")
    
    # 运行一次拉取周期
    rss_manager.run_fetch_cycle()


if __name__ == "__main__":
    main()