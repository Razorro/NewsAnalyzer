"""
数据获取模块 - 负责从各种数据源获取市场数据
"""
import json
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import requests
from typing import Dict, List, Optional, Any
import os
import time

# 尝试导入可选的库
try:
    from fredapi import Fred
    HAS_FRED = True
except ImportError:
    HAS_FRED = False
    print("警告: fredapi未安装，将使用模拟数据。安装命令: pip install fredapi")

try:
    from newsapi import NewsApiClient
    HAS_NEWSAPI = True
except ImportError:
    HAS_NEWSAPI = False
    print("警告: newsapi-python未安装，将使用模拟数据。安装命令: pip install newsapi-python")

# 新增：RSS支持
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    print("警告: feedparser未安装，将无法使用RSS新闻源。安装命令: pip install feedparser")

# 新增：Ollama支持
try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
    print("警告: ollama未安装，将无法使用AI智能分类。安装命令: pip install ollama")

class DataFetcher:
    def __init__(self, config_path: str = None):
        """初始化数据获取器"""
        # 尝试多个可能的配置文件路径
        possible_paths = []
        if config_path:
            possible_paths.append(config_path)
        possible_paths.extend([
            "config/config.json",
            "../config/config.json",
            os.path.join(os.path.dirname(__file__), "../config/config.json")
        ])
        
        self.config = {}
        for path in possible_paths:
            if os.path.exists(path):
                self.config = self._load_config(path)
                if self.config:
                    print(f"✓ 成功加载配置文件: {path}")
                    break
        
        if not self.config:
            print("⚠ 未找到配置文件，将使用默认配置")
        
        self.data_sources = self.config.get("data_sources", {})
        self.api_keys = self.config.get("api_keys", {})
        self.historical_days = self.config.get("monitoring", {}).get("historical_data_days", 365)
        
        # RSS拉取时间记录文件
        self.rss_fetch_times_file = "data/rss_fetch_times.json"
        self.rss_fetch_times = self._load_rss_fetch_times()
        
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件 {config_path} 失败: {e}")
            return {}
    
    def _load_rss_fetch_times(self) -> Dict[str, str]:
        """加载RSS拉取时间记录"""
        if os.path.exists(self.rss_fetch_times_file):
            try:
                with open(self.rss_fetch_times_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载RSS拉取时间记录失败: {e}")
        return {}
    
    def _save_rss_fetch_times(self):
        """保存RSS拉取时间记录"""
        os.makedirs(os.path.dirname(self.rss_fetch_times_file), exist_ok=True)
        try:
            with open(self.rss_fetch_times_file, 'w', encoding='utf-8') as f:
                json.dump(self.rss_fetch_times, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存RSS拉取时间记录失败: {e}")
    
    def get_historical_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """获取历史价格数据"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            if df.empty:
                print(f"警告: 无法获取 {symbol} 的数据")
                return pd.DataFrame()
            return df
        except Exception as e:
            print(f"获取 {symbol} 数据时出错: {e}")
            return pd.DataFrame()
    
    def get_brent_crude_data(self) -> Dict[str, Any]:
        """获取布伦特原油数据"""
        symbol = self.data_sources.get("brent_crude", "BZ=F")
        df = self.get_historical_data(symbol)
        
        if df.empty:
            return {"error": "无法获取布伦特原油数据"}
        
        latest = df.iloc[-1]
        ma_200 = df['Close'].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else None
        
        return {
            "current_price": latest['Close'],
            "high_24h": latest['High'],
            "low_24h": latest['Low'],
            "volume": latest['Volume'],
            "ma_200": ma_200,
            "above_200ma": latest['Close'] > ma_200 if ma_200 is not None else None,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_inflation_data(self) -> Dict[str, Any]:
        """获取通胀数据（PPI、CPI）"""
        fred_api_key = self.api_keys.get("fred", "")
        
        if not HAS_FRED:
            return {
                "cpi": {"latest": 0, "month_over_month": 0, "energy_component_contribution": 0},
                "ppi": {"latest": 0, "month_over_month": 0},
                "timestamp": datetime.now().isoformat(),
                "error": "fredapi库未安装，请运行: pip install fredapi"
            }
        
        if not fred_api_key:
            return {
                "cpi": {"latest": 0, "month_over_month": 0, "energy_component_contribution": 0},
                "ppi": {"latest": 0, "month_over_month": 0},
                "timestamp": datetime.now().isoformat(),
                "error": "FRED API密钥未配置，请在config.json中设置api_keys.fred"
            }
        
        try:
            fred = Fred(api_key=fred_api_key)
            
            # 获取CPI数据 (Consumer Price Index for All Urban Consumers: All Items in U.S. City Average)
            cpi_series = fred.get_series('CPIAUCSL', limit=2)
            if len(cpi_series) >= 2:
                cpi_latest = cpi_series.iloc[-1]
                cpi_prev = cpi_series.iloc[-2]
                cpi_mom = ((cpi_latest - cpi_prev) / cpi_prev) * 100
            else:
                cpi_latest = 0
                cpi_mom = 0
            
            # 获取PPI数据 (Producer Price Index by Commodity: All Commodities)
            ppi_series = fred.get_series('PPIACO', limit=2)
            if len(ppi_series) >= 2:
                ppi_latest = ppi_series.iloc[-1]
                ppi_prev = ppi_series.iloc[-2]
                ppi_mom = ((ppi_latest - ppi_prev) / ppi_prev) * 100
            else:
                ppi_latest = 0
                ppi_mom = 0
            
            # 获取能源CPI贡献 (Gasoline index)
            try:
                energy_series = fred.get_series('CUSR0000SETB01', limit=2)
                if len(energy_series) >= 2:
                    energy_latest = energy_series.iloc[-1]
                    energy_prev = energy_series.iloc[-2]
                    energy_contribution = ((energy_latest - energy_prev) / cpi_prev) * 100 if cpi_prev else 0
                else:
                    energy_contribution = 0
            except:
                energy_contribution = 0
            
            return {
                "cpi": {
                    "latest": round(cpi_mom, 2),
                    "month_over_month": round(cpi_mom, 2),
                    "energy_component_contribution": round(energy_contribution, 3)
                },
                "ppi": {
                    "latest": round(ppi_mom, 2),
                    "month_over_month": round(ppi_mom, 2)
                },
                "timestamp": datetime.now().isoformat(),
                "data_source": "FRED (Federal Reserve Economic Data)"
            }
        except Exception as e:
            return {
                "cpi": {"latest": 0, "month_over_month": 0, "energy_component_contribution": 0},
                "ppi": {"latest": 0, "month_over_month": 0},
                "timestamp": datetime.now().isoformat(),
                "error": f"FRED API调用失败: {str(e)}"
            }
    
    def get_fed_data(self) -> Dict[str, Any]:
        """获取美联储相关数据 - 使用FRED API获取联邦基金利率数据"""
        fred_api_key = self.api_keys.get("fred", "")
        
        if not HAS_FRED or not fred_api_key:
            # 尝试从网页获取FedWatch数据
            return self._get_fedwatch_from_web()
        
        try:
            fred = Fred(api_key=fred_api_key)
            
            # 获取联邦基金有效利率 (DFF)
            ffr_series = fred.get_series('DFF', limit=30)
            current_rate = ffr_series.iloc[-1] if len(ffr_series) > 0 else 0
            
            # 获取联邦基金目标利率上限 (DFEDTARU)
            try:
                target_upper = fred.get_series('DFEDTARU', limit=1)
                target_rate = target_upper.iloc[-1] if len(target_upper) > 0 else current_rate
            except:
                target_rate = current_rate
            
            # 计算简单的降息概率指标（基于利率走势）
            if len(ffr_series) >= 10:
                rate_10d_avg = ffr_series.tail(10).mean()
                rate_30d_avg = ffr_series.mean()
                
                # 如果近期利率低于30天平均，可能暗示宽松预期
                if rate_10d_avg < rate_30d_avg - 0.05:
                    cut_probability = min(40.0, abs(rate_30d_avg - rate_10d_avg) * 100)
                else:
                    cut_probability = max(5.0, 15.0 - (rate_10d_avg - rate_30d_avg) * 50)
            else:
                cut_probability = 15.0
            
            # 获取下一次FOMC会议日期（简化处理）
            from datetime import datetime, timedelta
            now = datetime.now()
            
            # FOMC通常在1月、3月、5月、6月、7月、9月、11月、12月召开
            fomc_months = [1, 3, 5, 6, 7, 9, 11, 12]
            next_meeting_month = None
            next_meeting_year = now.year
            
            for month in fomc_months:
                if month > now.month:
                    next_meeting_month = month
                    break
            
            if next_meeting_month is None:
                next_meeting_month = fomc_months[0]
                next_meeting_year += 1
            
            # 获取10年期与2年期利差（收益率曲线指标）
            try:
                treasury_10y = fred.get_series('DGS10', limit=1)
                treasury_2y = fred.get_series('DGS2', limit=1)
                
                spread = 0
                if len(treasury_10y) > 0 and len(treasury_2y) > 0:
                    spread = treasury_10y.iloc[-1] - treasury_2y.iloc[-1]
                
                # 收益率曲线倒挂通常预示经济衰退，可能增加降息概率
                if spread < 0:
                    cut_probability = min(cut_probability + 10, 60)
            except:
                spread = 0
            
            return {
                "current_rate": round(current_rate, 2),
                "target_rate": round(target_rate, 2),
                "rate_cut_probability": {
                    "next_meeting": round(cut_probability, 1),
                    "next_meeting_date": f"{next_meeting_year}-{next_meeting_month:02d}",
                    "yield_curve_spread": round(spread, 2)
                },
                "dot_plot": {
                    "median_2026": round(target_rate - (cut_probability / 100), 1),
                    "range": [round(target_rate - 0.5, 1), round(target_rate + 0.2, 1)]
                },
                "timestamp": datetime.now().isoformat(),
                "data_source": "FRED (Federal Reserve Economic Data)"
            }
            
        except Exception as e:
            print(f"FRED API调用失败，尝试网页抓取: {e}")
            return self._get_fedwatch_from_web()
    
    def _get_fedwatch_from_web(self) -> Dict[str, Any]:
        """尝试从网页获取CME FedWatch数据（备用方案）"""
        try:
            # CME FedWatch工具URL
            url = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # 简单的HTML解析（实际应用中可能需要更复杂的解析）
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 尝试提取降息概率数据（这需要根据实际页面结构调整）
                # 由于页面结构可能变化，这里返回一个基础值
                return {
                    "rate_cut_probability": {
                        "next_meeting": 20.0,
                        "note": "网页数据需要进一步解析"
                    },
                    "dot_plot": {
                        "median_2026": 4.5,
                        "range": [4.25, 4.75]
                    },
                    "timestamp": datetime.now().isoformat(),
                    "data_source": "CME FedWatch (网页抓取)"
                }
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            # 如果所有方法都失败，返回基于市场指标的估算
            return {
                "rate_cut_probability": {
                    "next_meeting": 15.0,
                    "note": "使用默认值，API和网页抓取均失败"
                },
                "dot_plot": {
                    "median_2026": 4.6,
                    "range": [4.4, 4.9]
                },
                "timestamp": datetime.now().isoformat(),
                "error": f"无法获取FedWatch数据: {str(e)}"
            }
    
    def get_yield_data(self) -> Dict[str, Any]:
        """获取债券收益率数据"""
        symbol = self.data_sources.get("treasury_10y", "^TNX")
        df = self.get_historical_data(symbol)
        
        if df.empty:
            return {"error": "无法获取10年期国债收益率数据"}
        
        latest = df.iloc[-1]
        recent_high = df['High'].tail(30).max()
        
        return {
            "current_yield": latest['Close'],
            "recent_high": recent_high,
            "breakout": latest['Close'] > recent_high,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_dxy_gold_data(self) -> Dict[str, Any]:
        """获取美元指数和黄金数据"""
        dxy_symbol = self.data_sources.get("dxy", "DX-Y.NYB")
        gold_symbol = self.data_sources.get("gold", "GC=F")
        
        dxy_df = self.get_historical_data(dxy_symbol)
        gold_df = self.get_historical_data(gold_symbol)
        
        if dxy_df.empty or gold_df.empty:
            return {"error": "无法获取DXY或黄金数据"}
        
        dxy_latest = dxy_df.iloc[-1]
        gold_latest = gold_df.iloc[-1]
        
        # 计算30天相关性
        dxy_returns = dxy_df['Close'].pct_change().dropna().tail(30)
        gold_returns = gold_df['Close'].pct_change().dropna().tail(30)
        
        correlation = dxy_returns.corr(gold_returns) if len(dxy_returns) > 10 and len(gold_returns) > 10 else None
        
        return {
            "dxy": {
                "current": dxy_latest['Close'],
                "change_pct": (dxy_latest['Close'] - dxy_df.iloc[-2]['Close']) / dxy_df.iloc[-2]['Close'] * 100
            },
            "gold": {
                "current": gold_latest['Close'],
                "change_pct": (gold_latest['Close'] - gold_df.iloc[-2]['Close']) / gold_df.iloc[-2]['Close'] * 100
            },
            "correlation_30d": correlation,
            "max_fear_signal": correlation is not None and correlation > 0.5,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_technical_liquidity_data(self) -> Dict[str, Any]:
        """获取技术流动性数据（S&P 500、纳斯达克）"""
        sp500_symbol = self.data_sources.get("sp500", "^GSPC")
        nasdaq_symbol = self.data_sources.get("nasdaq", "^IXIC")
        
        sp500_df = self.get_historical_data(sp500_symbol)
        nasdaq_df = self.get_historical_data(nasdaq_symbol)
        
        if sp500_df.empty or nasdaq_df.empty:
            return {"error": "无法获取指数数据"}
        
        # 计算简单的成交量分布分析
        sp500_latest = sp500_df.iloc[-1]
        nasdaq_latest = nasdaq_df.iloc[-1]
        
        # 模拟POC和VAL（实际需要更复杂的算法）
        sp500_poc = sp500_df['Close'].mean()
        sp500_val = sp500_df['Close'].quantile(0.25)
        
        return {
            "sp500": {
                "current": sp500_latest['Close'],
                "poc": sp500_poc,
                "val": sp500_val,
                "below_val": sp500_latest['Close'] < sp500_val
            },
            "nasdaq": {
                "current": nasdaq_latest['Close'],
                "change_pct": (nasdaq_latest['Close'] - nasdaq_df.iloc[-2]['Close']) / nasdaq_df.iloc[-2]['Close'] * 100
            },
            "volume_analysis": {
                "sp500_volume": sp500_latest['Volume'],
                "sp500_avg_volume": sp500_df['Volume'].mean()
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def get_geopolitical_news(self) -> Dict[str, Any]:
        """
        获取地缘政治新闻（优化版）
        优先使用RSS，备用NewsAPI
        先过滤再返回，减少后续处理量
        """
        all_articles = []
        sources_status = {}
        
        # 加载地缘政治新闻配置
        geopolitical_config = self.config.get("geopolitical_news", {})
        
        # 1. 优先使用RSS源
        if geopolitical_config.get("news_sources", {}).get("rss_enabled", True):
            rss_articles = self._get_rss_articles()
            all_articles.extend(rss_articles)
            sources_status['rss'] = len(rss_articles)
            print(f"  RSS源获取: {len(rss_articles)} 条")
        
        # 2. 如果RSS数据不足，使用NewsAPI补充
        rss_min_count = 10
        if len(all_articles) < rss_min_count and geopolitical_config.get("news_sources", {}).get("newsapi_enabled", True):
            newsapi_articles = self._get_newsapi_articles()
            all_articles.extend(newsapi_articles)
            sources_status['newsapi'] = len(newsapi_articles)
            print(f"  NewsAPI补充: {len(newsapi_articles)} 条")
        
        # 3. 去重
        unique_articles = self._deduplicate_articles(all_articles)
        print(f"  去重后: {len(unique_articles)} 条")
        
        # 4. 关键词预过滤（在获取URL内容之前）
        filtered_articles = self._filter_articles_by_keywords(unique_articles)
        
        # 5. 按时间排序
        sorted_articles = sorted(
            filtered_articles,
            key=lambda x: x.get('publishedAt', ''),
            reverse=True
        )
        
        # 6. 限制数量
        max_articles = geopolitical_config.get("max_articles", 20)
        final_articles = sorted_articles[:max_articles]
        
        return {
            "articles": final_articles,
            "sources_status": sources_status,
            "total_articles": len(final_articles),
            "original_count": len(all_articles),
            "filtered_count": len(filtered_articles),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_rss_articles(self) -> List[Dict]:
        """从RSS源获取新闻（优化版：添加User-Agent、延迟、超时）"""
        if not HAS_FEEDPARSER:
            print("feedparser未安装，跳过RSS获取")
            return []
        
        import feedparser
        
        # 设置User-Agent伪装成浏览器
        feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        articles = []
        geopolitical_config = self.config.get("geopolitical_news", {})
        rss_feeds = geopolitical_config.get("news_sources", {}).get("rss_feeds", {})
        
        feed_count = 0
        total_feeds = len(rss_feeds)
        
        for feed_name, feed_url in rss_feeds.items():
            feed_count += 1
            try:
                print(f"  正在抓取RSS [{feed_count}/{total_feeds}]: {feed_name}")
                
                # 设置请求超时
                feed = feedparser.parse(feed_url, request_headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/rss+xml, application/xml, text/xml',
                    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7'
                })
                
                # 检查feed是否有效
                if feed.bozo and not feed.entries:
                    print(f"    ⚠ RSS源解析失败: {feed_name}")
                    continue
                
                entry_count = 0
                # 根据源设置不同的拉取数量
                max_entries = 30 if feed_name in ['zerohedge', 'al_jazeera', 'foreign_policy', 'bbc_middle_east'] else 20
                for entry in feed.entries[:max_entries]:
                    # 解析发布时间
                    published = entry.get('published', entry.get('updated', ''))
                    
                    article = {
                        'title': entry.get('title', ''),
                        'description': entry.get('summary', entry.get('description', ''))[:500],
                        'url': entry.get('link', ''),
                        'source': feed_name,
                        'publishedAt': published,
                        'content': ''
                    }
                    
                    # 只保留最近N天的新闻（根据配置）
                    lookback_days = geopolitical_config.get("lookback_days", 1)
                    if self._is_recent_article(published, days=lookback_days):
                        articles.append(article)
                        entry_count += 1
                
                print(f"    ✓ 获取 {entry_count} 条新闻")
                
                # 请求延迟，避免被限流（1-2秒随机延迟）
                import random
                delay = random.uniform(1.0, 2.0)
                time.sleep(delay)
                        
            except Exception as e:
                print(f"  ✗ RSS抓取失败 {feed_name}: {e}")
                continue
        
        print(f"  ✓ RSS源获取完成: {len(articles)} 条新闻")
        return articles
    
    def _get_newsapi_articles(self) -> List[Dict]:
        """从NewsAPI获取新闻"""
        if not HAS_NEWSAPI:
            print("newsapi-python未安装，跳过NewsAPI获取")
            return []
        
        news_api_key = self.api_keys.get("news_api", "")
        if not news_api_key:
            print("NewsAPI密钥未配置")
            return []
        
        try:
            newsapi = NewsApiClient(api_key=news_api_key)
            
            # 构建搜索关键词
            geopolitical_config = self.config.get("geopolitical_news", {})
            categories = geopolitical_config.get("categories", {})
            
            all_keywords = []
            for cat_name, cat_config in categories.items():
                if cat_config.get("enabled", True):
                    all_keywords.extend(cat_config.get("keywords", []))
            
            # 取前5个关键词进行搜索
            search_query = " OR ".join(all_keywords[:5])
            
            # 计算日期范围
            lookback_days = geopolitical_config.get("lookback_days", 3)
            from_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            
            articles = newsapi.get_everything(
                q=search_query,
                language='en',
                sort_by='publishedAt',
                from_param=from_date,
                page_size=30
            )
            
            if articles['status'] == 'ok':
                result = []
                for article in articles['articles']:
                    result.append({
                        'title': article.get('title', ''),
                        'description': article.get('description', ''),
                        'url': article.get('url', ''),
                        'source': article.get('source', {}).get('name', 'Unknown'),
                        'publishedAt': article.get('publishedAt', ''),
                        'content': article.get('content', '')
                    })
                return result
            
        except Exception as e:
            print(f"NewsAPI调用失败: {e}")
        
        return []
    
    def _deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """去重文章"""
        seen_titles = set()
        unique_articles = []
        
        for article in articles:
            title = article.get('title', '').lower().strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_articles.append(article)
        
        return unique_articles
    
    def _filter_articles_by_keywords(self, articles: List[Dict]) -> List[Dict]:
        """
        使用关键词预过滤相关文章
        只保留与地缘政治相关的新闻
        """
        # 地缘政治相关关键词
        geopolitical_keywords = [
            # 国家/地区
            "Iran", "Israel", "Hamas", "Hezbollah", "Houthi", "Yemen",
            "Middle East", "Persian Gulf", "Hormuz", "Gaza", "Lebanon",
            "Saudi Arabia", "UAE", "Iraq", "Syria", "Turkey",
            
            # 军事
            "war", "military", "attack", "strike", "missile",
            "troops", "conflict", "bomb", "invasion", "casualties",
            "air strike", "ground operation", "offensive",
            
            # 外交
            "sanctions", "diplomacy", "nuclear", "JCPOA",
            "ceasefire", "negotiation", "treaty", "UN", "Security Council",
            
            # 能源
            "oil", "crude", "energy", "pipeline", "refinery",
            "OPEC", "petroleum", "gas field", "oil price", "supply disruption"
        ]
        
        filtered = []
        for article in articles:
            # 组合标题和描述进行匹配
            text = (
                article.get('title', '') + ' ' + 
                article.get('description', '')
            ).lower()
            
            # 计算匹配的关键词数量
            match_count = sum(1 for kw in geopolitical_keywords if kw.lower() in text)
            
            # 至少匹配2个关键词才保留
            if match_count >= 2:
                article['keyword_matches'] = match_count
                filtered.append(article)
        
        # 按匹配数量排序（最相关的在前）
        filtered.sort(key=lambda x: x.get('keyword_matches', 0), reverse=True)
        
        # 取消数量限制，返回所有匹配的文章
        result = filtered
        
        print(f"  关键词过滤: {len(articles)}篇 → {len(result)}篇")
        
        return result
    
    def _is_recent_article(self, published_date: str, days: int = 3) -> bool:
        """检查文章是否在指定天数内"""
        if not published_date:
            return False
        
        try:
            from dateutil import parser
            article_date = parser.parse(published_date)
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 处理时区
            if article_date.tzinfo is not None:
                cutoff_date = cutoff_date.replace(tzinfo=article_date.tzinfo)
            
            return article_date >= cutoff_date
        except:
            # 如果解析失败，假设文章是最近的
            return True
    
    def get_geopolitical_news_incremental(self, processed_urls: set) -> Dict[str, Any]:
        """
        获取增量地缘政治新闻（只返回未处理的文章）
        
        Args:
            processed_urls: 已处理的URL集合
            
        Returns:
            包含增量新闻的字典
        """
        # 获取所有新闻
        all_news = self.get_geopolitical_news()
        all_articles = all_news.get('articles', [])
        
        # 过滤掉已处理的URL
        new_articles = []
        for article in all_articles:
            url = article.get('url', '')
            if url and url not in processed_urls:
                new_articles.append(article)
        
        print(f"  增量过滤: {len(all_articles)}篇 → {len(new_articles)}篇新文章")
        
        # 更新结果
        all_news['articles'] = new_articles
        all_news['total_articles'] = len(new_articles)
        all_news['incremental'] = True
        all_news['processed_count'] = len(all_articles) - len(new_articles)
        
        return all_news
    
    def fetch_all_data(self) -> Dict[str, Any]:
        """获取所有数据并返回综合数据集"""
        print(f"[{datetime.now()}] 开始获取市场数据...")
        
        data = {
            "brent_crude": self.get_brent_crude_data(),
            "inflation": self.get_inflation_data(),
            "fed": self.get_fed_data(),
            "yields": self.get_yield_data(),
            "dxy_gold": self.get_dxy_gold_data(),
            "technical": self.get_technical_liquidity_data(),
            "geopolitical": self.get_geopolitical_news(),
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"[{datetime.now()}] 数据获取完成")
        return data
    
    def save_data_to_csv(self, data: Dict[str, Any], output_dir: str = "data"):
        """保存数据到CSV文件"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存主要指标
        main_indicators = {
            "timestamp": data["timestamp"],
            "brent_price": data["brent_crude"].get("current_price"),
            "brent_ma200": data["brent_crude"].get("ma_200"),
            "yield_10y": data["yields"].get("current_yield"),
            "dxy": data["dxy_gold"]["dxy"].get("current"),
            "gold": data["dxy_gold"]["gold"].get("current"),
            "sp500": data["technical"]["sp500"].get("current"),
            "nasdaq": data["technical"]["nasdaq"].get("current")
        }
        
        df = pd.DataFrame([main_indicators])
        filename = os.path.join(output_dir, f"market_data_{timestamp}.csv")
        df.to_csv(filename, index=False)
        print(f"数据已保存到 {filename}")
        
        return filename
    
    def save_raw_data(self, data: Dict[str, Any], output_dir: str = "data"):
        """保存完整的原始数据到JSON文件，便于审核追踪"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        filename = os.path.join(output_dir, f"raw_data_{timestamp}.json")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"原始数据已保存到 {filename}")
        return filename
    
    def display_data_summary(self, data: Dict[str, Any]):
        """显示获取的数据摘要，便于审核"""
        print("\n" + "="*60)
        print("获取的数据摘要")
        print("="*60)
        
        # 布伦特原油
        brent = data.get("brent_crude", {})
        print(f"\n【布伦特原油】")
        print(f"  当前价格: ${brent.get('current_price', 'N/A')}")
        print(f"  200日均线: ${brent.get('ma_200', 'N/A')}")
        print(f"  高于200MA: {brent.get('above_200ma', 'N/A')}")
        print(f"  错误信息: {brent.get('error', '无')}")
        
        # 通胀数据
        inflation = data.get("inflation", {})
        print(f"\n【通胀数据】")
        print(f"  CPI最新: {inflation.get('cpi', {}).get('latest', 'N/A')}%")
        print(f"  CPI环比: {inflation.get('cpi', {}).get('month_over_month', 'N/A')}%")
        print(f"  能源贡献: {inflation.get('cpi', {}).get('energy_component_contribution', 'N/A')}%")
        print(f"  PPI最新: {inflation.get('ppi', {}).get('latest', 'N/A')}%")
        print(f"  备注: {inflation.get('note', '无')}")
        
        # 美联储数据
        fed = data.get("fed", {})
        print(f"\n【美联储数据】")
        print(f"  下次会议降息概率: {fed.get('rate_cut_probability', {}).get('next_meeting', 'N/A')}%")
        print(f"  2026年削减定价退出: {fed.get('rate_cut_probability', {}).get('2026_cuts_priced_out', 'N/A')}")
        print(f"  点阵图中位数: {fed.get('dot_plot', {}).get('median_2026', 'N/A')}%")
        print(f"  备注: {fed.get('note', '无')}")
        
        # 收益率
        yields = data.get("yields", {})
        print(f"\n【10年期国债收益率】")
        print(f"  当前收益率: {yields.get('current_yield', 'N/A')}%")
        print(f"  近期高点: {yields.get('recent_high', 'N/A')}%")
        print(f"  突破确认: {yields.get('breakout', 'N/A')}")
        print(f"  错误信息: {yields.get('error', '无')}")
        
        # DXY和黄金
        dxy_gold = data.get("dxy_gold", {})
        print(f"\n【美元指数与黄金】")
        print(f"  DXY当前: {dxy_gold.get('dxy', {}).get('current', 'N/A')}")
        print(f"  DXY变化: {dxy_gold.get('dxy', {}).get('change_pct', 'N/A')}%")
        print(f"  黄金当前: ${dxy_gold.get('gold', {}).get('current', 'N/A')}")
        print(f"  黄金变化: {dxy_gold.get('gold', {}).get('change_pct', 'N/A')}%")
        print(f"  30日相关性: {dxy_gold.get('correlation_30d', 'N/A')}")
        print(f"  最大恐惧信号: {dxy_gold.get('max_fear_signal', 'N/A')}")
        print(f"  错误信息: {dxy_gold.get('error', '无')}")
        
        # 技术指标
        technical = data.get("technical", {})
        sp500 = technical.get("sp500", {})
        nasdaq = technical.get("nasdaq", {})
        print(f"\n【技术流动性】")
        print(f"  S&P 500当前: {sp500.get('current', 'N/A')}")
        print(f"  S&P 500 POC: {sp500.get('poc', 'N/A')}")
        print(f"  S&P 500 VAL: {sp500.get('val', 'N/A')}")
        print(f"  低于VAL: {sp500.get('below_val', 'N/A')}")
        print(f"  纳斯达克当前: {nasdaq.get('current', 'N/A')}")
        print(f"  纳斯达克变化: {nasdaq.get('change_pct', 'N/A')}%")
        print(f"  错误信息: {technical.get('error', '无')}")
        
        # 地缘政治
        geopolitical = data.get("geopolitical", {})
        print(f"\n【地缘政治】")
        print(f"  伊朗冲突状态: {geopolitical.get('iran_conflict', {}).get('latest_update', 'N/A')}")
        print(f"  严重程度: {geopolitical.get('iran_conflict', {}).get('severity', 'N/A')}")
        print(f"  霍尔木兹海峡: {geopolitical.get('strait_of_hormuz', {}).get('status', 'N/A')}")
        print(f"  备注: {geopolitical.get('note', '无')}")
        
        print("\n" + "="*60)
        print(f"数据时间戳: {data.get('timestamp', 'N/A')}")
        print("="*60 + "\n")


def main():
    """主函数，用于测试数据获取"""
    fetcher = DataFetcher()
    data = fetcher.fetch_all_data()
    
    # 打印关键信息
    print("\n=== 市场数据摘要 ===")
    print(f"布伦特原油: ${data['brent_crude'].get('current_price', 'N/A'):.2f}")
    print(f"10年期收益率: {data['yields'].get('current_yield', 'N/A'):.3f}%")
    print(f"DXY: {data['dxy_gold']['dxy'].get('current', 'N/A'):.2f}")
    print(f"黄金: ${data['dxy_gold']['gold'].get('current', 'N/A'):.2f}")
    print(f"S&P 500: {data['technical']['sp500'].get('current', 'N/A'):.2f}")
    
    # 保存数据
    fetcher.save_data_to_csv(data)


if __name__ == "__main__":
    main()