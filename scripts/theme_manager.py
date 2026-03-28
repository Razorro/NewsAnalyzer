"""
主题管理器 - 管理不同的分析主题
支持：中东战争、金融市场等多种主题切换
"""
import json
import os
from typing import Dict, List, Any, Optional


class ThemeManager:
    """主题管理器 - 分离公用配置和主题配置"""
    
    def __init__(self, config_dir: str = "config", themes_dir: str = "templates/themes"):
        self.config_dir = config_dir
        self.themes_dir = themes_dir
        
        # 加载公用配置
        self.common_config = self._load_common_config()
        
        # 加载当前主题
        self.active_theme_id = None
        self.theme_config = None
        self._load_active_theme()
    
    def _load_common_config(self) -> Dict:
        """加载公用配置"""
        config_file = os.path.join(self.config_dir, 'config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _load_active_theme(self):
        """加载当前激活的主题"""
        active_file = os.path.join(self.config_dir, 'active_theme.json')
        if os.path.exists(active_file):
            with open(active_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.active_theme_id = data.get('theme_id', 'geopolitical_war')
        
        if not self.active_theme_id:
            self.active_theme_id = 'geopolitical_war'
        
        self.load_theme(self.active_theme_id)
    
    def load_theme(self, theme_id: str) -> bool:
        """加载指定主题"""
        theme_dir = os.path.join(self.themes_dir, theme_id)
        theme_file = os.path.join(theme_dir, 'theme.json')
        
        if not os.path.exists(theme_file):
            print(f"⚠ 主题不存在: {theme_id}")
            return False
        
        with open(theme_file, 'r', encoding='utf-8') as f:
            self.theme_config = json.load(f)
            self.theme_config['theme_dir'] = theme_dir
        
        print(f"✓ 已加载主题: {self.theme_config.get('theme_name')}")
        return True
    
    def switch_theme(self, theme_id: str) -> bool:
        """切换主题"""
        if self.load_theme(theme_id):
            # 保存激活主题
            os.makedirs(self.config_dir, exist_ok=True)
            active_file = os.path.join(self.config_dir, 'active_theme.json')
            with open(active_file, 'w', encoding='utf-8') as f:
                json.dump({'theme_id': theme_id}, f, indent=2, ensure_ascii=False)
            
            self.active_theme_id = theme_id
            print(f"✓ 已切换到主题: {theme_id}")
            return True
        return False
    
    # ========== 公用配置访问 ==========
    
    def get_api_keys(self) -> Dict:
        """获取API密钥"""
        return self.common_config.get('api_keys', {})
    
    def get_ollama_settings(self) -> Dict:
        """获取Ollama设置"""
        return self.common_config.get('ollama_settings', {})
    
    def get_news_sources(self) -> Dict:
        """获取新闻源配置"""
        return self.common_config.get('news_sources', {})
    
    def get_data_sources(self) -> Dict:
        """获取数据源配置"""
        return self.common_config.get('data_sources', {})
    
    def get_debug_config(self) -> Dict:
        """获取调试配置"""
        return self.common_config.get('debug', {})
    
    def get_geopolitical_config(self) -> Dict:
        """获取地缘政治配置（向后兼容）"""
        return self.common_config.get('geopolitical_news', {})
    
    # ========== 主题配置访问 ==========
    
    def get_keywords(self) -> Dict:
        """获取当前主题的关键词"""
        if not self.theme_config:
            return {}
        
        theme_dir = self.theme_config.get('theme_dir')
        keywords_file = os.path.join(theme_dir, self.theme_config['files']['keywords'])
        
        if os.path.exists(keywords_file):
            with open(keywords_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def get_analysis_prompt(self) -> str:
        """获取分析提示词"""
        if not self.theme_config:
            return ""
        
        theme_dir = self.theme_config.get('theme_dir')
        prompt_file = os.path.join(theme_dir, self.theme_config['files']['analysis_prompt'])
        
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def get_trend_prompt(self) -> str:
        """获取趋势总评提示词"""
        if not self.theme_config:
            return ""
        
        theme_dir = self.theme_config.get('theme_dir')
        prompt_file = os.path.join(theme_dir, self.theme_config['files']['trend_prompt'])
        
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def get_report_template(self) -> str:
        """获取报告HTML模板"""
        if not self.theme_config:
            return ""
        
        theme_dir = self.theme_config.get('theme_dir')
        template_file = os.path.join(theme_dir, self.theme_config['files']['report_template'])
        
        if os.path.exists(template_file):
            with open(template_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def get_analysis_settings(self) -> Dict:
        """获取分析设置"""
        if not self.theme_config:
            return {}
        return self.theme_config.get('analysis_settings', {})
    
    def get_report_style(self) -> Dict:
        """获取报告样式配置"""
        if not self.theme_config:
            return {}
        return self.theme_config.get('report_style', {})
    
    def get_data_extraction_config(self) -> Dict:
        """获取数据提取配置"""
        if not self.theme_config:
            return {}
        return self.theme_config.get('data_extraction', {})
    
    # ========== 工具方法 ==========
    
    def list_themes(self) -> List[Dict]:
        """列出所有可用主题"""
        themes = []
        if os.path.exists(self.themes_dir):
            for item in os.listdir(self.themes_dir):
                theme_dir = os.path.join(self.themes_dir, item)
                theme_file = os.path.join(theme_dir, 'theme.json')
                if os.path.isdir(theme_dir) and os.path.exists(theme_file):
                    with open(theme_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        themes.append({
                            'id': item,
                            'name': config.get('theme_name'),
                            'description': config.get('description')
                        })
        return themes
    
    def get_current_theme_id(self) -> str:
        """获取当前主题ID"""
        return self.active_theme_id or 'geopolitical_war'
    
    def get_full_config(self) -> Dict:
        """获取完整配置（公用 + 主题）"""
        return {
            'common': self.common_config,
            'theme': self.theme_config
        }
    
    def format_analysis_prompt(self, articles: List[Dict], **kwargs) -> str:
        """
        格式化分析提示词
        
        Args:
            articles: 文章列表
            **kwargs: 其他变量
            
        Returns:
            格式化后的提示词
        """
        prompt_template = self.get_analysis_prompt()
        
        # 准备文章内容
        article_texts = []
        for i, article in enumerate(articles[:15], 1):
            article_texts.append(f"""
--- 文章{i} ---
标题: {article.get('title', 'N/A')}
来源: {article.get('source', 'Unknown')}
日期: {article.get('publishedAt', '')[:10]}
URL: {article.get('url', '')}
内容: {article.get('full_content', article.get('description', ''))}
""")
        
        # 默认变量
        format_vars = {
            'article_count': len(articles),
            'articles': '\n'.join(article_texts),
        }
        
        # 合并用户提供的变量
        format_vars.update(kwargs)
        
        try:
            return prompt_template.format(**format_vars)
        except KeyError as e:
            print(f"⚠ 提示词模板变量缺失: {e}")
            return prompt_template
    
    def format_trend_prompt(self, articles: List[Dict], analysis: Dict, **kwargs) -> str:
        """
        格式化趋势总评提示词
        
        Args:
            articles: 文章列表
            analysis: 分析结果
            **kwargs: 其他变量
            
        Returns:
            格式化后的提示词
        """
        prompt_template = self.get_trend_prompt()
        
        # 准备新闻摘要
        news_summary_parts = []
        for i, article in enumerate(articles[:15], 1):
            title = article.get('title', 'N/A')
            source = article.get('source', 'Unknown')
            news_summary_parts.append(f"{i}. [{source}] {title}")
        
        # 默认变量
        format_vars = {
            'article_count': len(articles),
            'news_summary': '\n'.join(news_summary_parts),
            'crisis_score': analysis.get('crisis_score', 'N/A'),
            'trend': analysis.get('trend', 'N/A'),
            'conflict_intensity': analysis.get('intensity_assessment', {}).get('conflict_intensity', {}).get('score', 'N/A'),
            'diplomatic_tension': analysis.get('intensity_assessment', {}).get('diplomatic_tension', {}).get('score', 'N/A'),
            'oil_crisis': analysis.get('intensity_assessment', {}).get('oil_crisis', {}).get('score', 'N/A'),
        }
        
        # 合并用户提供的变量
        format_vars.update(kwargs)
        
        try:
            return prompt_template.format(**format_vars)
        except KeyError as e:
            print(f"⚠ 趋势提示词模板变量缺失: {e}")
            return prompt_template


def main():
    """测试主题管理器"""
    print("=" * 60)
    print("🎨 主题管理器测试")
    print("=" * 60)
    
    # 初始化
    theme_manager = ThemeManager()
    
    # 列出可用主题
    themes = theme_manager.list_themes()
    print(f"\n可用主题: {len(themes)}")
    for theme in themes:
        print(f"  - {theme['id']}: {theme['name']}")
    
    # 当前主题
    print(f"\n当前主题: {theme_manager.get_current_theme_id()}")
    
    # 获取关键词
    keywords = theme_manager.get_keywords()
    print(f"\n关键词分类: {list(keywords.keys())}")
    
    # 获取分析设置
    settings = theme_manager.get_analysis_settings()
    print(f"分析设置: {settings}")
    
    # 切换主题
    print("\n" + "-" * 60)
    if theme_manager.switch_theme('financial_market'):
        print(f"切换后主题: {theme_manager.get_current_theme_id()}")
        keywords = theme_manager.get_keywords()
        print(f"新关键词分类: {list(keywords.keys())}")


if __name__ == "__main__":
    main()