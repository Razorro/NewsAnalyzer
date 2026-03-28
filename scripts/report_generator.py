"""
报告生成器
生成竖屏赛博朋克风格的地缘政治分析报告
基于 geopolitical_report_20260322_212721.html 模板
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, List


class ReportGenerator:
    """报告生成器 - 竖屏赛博朋克风格"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.translations = {
            "escalating": "升级",
            "de-escalating": "降级",
            "stable": "稳定",
            "low": "低",
            "medium": "中等",
            "high": "高",
            "extreme": "极端",
            "military": "军事",
            "diplomacy": "外交",
            "energy": "能源"
        }
    
    def generate(self, analysis: Dict[str, Any], news_data: Dict[str, Any]) -> str:
        """
        生成竖屏赛博朋克风格HTML报告
        
        Args:
            analysis: 分析结果字典
            news_data: 新闻数据字典
            
        Returns:
            生成的HTML文件路径
        """
        crisis_score = analysis.get('crisis_score', 0)
        trend = analysis.get('trend', 'stable')
        trend_desc = analysis.get('trend_description', '')
        intensity = analysis.get('intensity_assessment', {})
        insights = analysis.get('key_insights', [])
        executive_summary = analysis.get('executive_summary', '')
        articles = news_data.get('articles', [])
        trend_summary = analysis.get('trend_summary', {})
        classification = analysis.get('classification', {})
        
        trend_icon = self._get_trend_icon(trend)
        score_color = self._get_score_color(crisis_score)
        chart_data = self._prepare_chart_data(analysis)
        
        # 生成时间线HTML（不限制数量，展示所有文章）
        timeline_html = self._generate_timeline_html(articles)
        
        # 生成趋势总评HTML
        trend_summary_html = self._generate_trend_summary_html(trend_summary)
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>威胁态势评估</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
        
        :root {{
            --cyber-bg: #0a0a0f;
            --cyber-card: #0d1117;
            --cyber-cyan: #00ffff;
            --cyber-magenta: #ff00ff;
            --cyber-green: #00ff00;
            --cyber-orange: #ff6600;
            --cyber-red: #ff0040;
            --cyber-yellow: #ffff00;
            --cyber-border: #30363d;
            --cyber-text: #e6edf3;
            --cyber-gray: #8b949e;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Share Tech Mono', monospace;
            background: var(--cyber-bg);
            min-height: 100vh;
            color: var(--cyber-text);
            line-height: 1.6;
            background-image: 
                linear-gradient(rgba(0,255,255,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,255,255,0.03) 1px, transparent 1px);
            background-size: 50px 50px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        /* 赛博朋克卡片 */
        .cyber-card {{
            background: var(--cyber-card);
            border: 1px solid var(--cyber-border);
            border-radius: 0;
            padding: 25px;
            margin-bottom: 20px;
            position: relative;
            clip-path: polygon(0 0, calc(100% - 20px) 0, 100% 20px, 100% 100%, 20px 100%, 0 calc(100% - 20px));
        }}
        
        .cyber-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--cyber-cyan), var(--cyber-magenta), var(--cyber-green));
            animation: gradient 3s ease infinite;
        }}
        
        @keyframes gradient {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}
        
        .cyber-card:hover {{
            box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
            border-color: var(--cyber-cyan);
        }}
        
        /* 头部 */
        .header {{
            text-align: center;
            padding: 50px 30px;
            background: linear-gradient(135deg, rgba(0,255,255,0.1) 0%, rgba(255,0,255,0.1) 100%);
            border: 2px solid var(--cyber-cyan);
        }}
        
        .alert-badge {{
            background: var(--cyber-red);
            color: white;
            padding: 12px 30px;
            font-weight: 900;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 3px;
            display: inline-block;
            margin-bottom: 20px;
            box-shadow: 0 0 20px rgba(255,0,64,0.5);
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
        
        .score-display {{
            margin: 30px 0;
        }}
        
        .score-number {{
            font-family: 'Orbitron', sans-serif;
            font-size: 120px;
            font-weight: 900;
            color: var(--cyber-cyan);
            text-shadow: 0 0 30px var(--cyber-cyan), 0 0 60px var(--cyber-cyan);
            animation: glow 2s ease-in-out infinite alternate;
        }}
        
        @keyframes glow {{
            from {{ text-shadow: 0 0 30px var(--cyber-cyan); }}
            to {{ text-shadow: 0 0 60px var(--cyber-cyan), 0 0 90px var(--cyber-cyan); }}
        }}
        
        .score-label {{
            font-size: 16px;
            color: var(--cyber-gray);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-top: 10px;
        }}
        
        .trend-indicator {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: {self._get_trend_color(trend)};
            color: white;
            padding: 10px 25px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 15px;
            box-shadow: 0 0 15px rgba(0,0,0,0.5);
        }}
        
        /* 图表样式 */
        .chart-container {{
            display: flex;
            justify-content: space-around;
            align-items: flex-end;
            height: 300px;
            padding: 30px 0;
            gap: 40px;
        }}
        
        .bar-wrapper {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
        }}
        
        .bar {{
            width: 80px;
            background: linear-gradient(180deg, var(--bar-color) 0%, rgba(0,0,0,0.5) 100%);
            position: relative;
            animation: growUp 1.5s ease-out forwards;
            box-shadow: 0 0 20px var(--bar-color), inset 0 0 10px rgba(255,255,255,0.2);
            border: 1px solid var(--bar-color);
        }}
        
        @keyframes growUp {{
            from {{ height: 0; }}
            to {{ height: var(--bar-height); }}
        }}
        
        .bar-value {{
            position: absolute;
            top: -40px;
            left: 50%;
            transform: translateX(-50%);
            font-family: 'Orbitron', sans-serif;
            font-weight: 700;
            font-size: 22px;
            color: var(--bar-color);
            text-shadow: 0 0 10px var(--bar-color);
        }}
        
        .bar-label {{
            margin-top: 15px;
            font-size: 12px;
            color: var(--cyber-gray);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        /* 饼图 */
        .pie-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 30px;
        }}
        
        .pie-chart {{
            width: 300px;
            height: 300px;
            border-radius: 50%;
            background: conic-gradient(
                var(--cyber-red) 0deg {chart_data.get('military_pct', 0)}deg,
                var(--cyber-cyan) {chart_data.get('military_pct', 0)}deg {chart_data.get('diplomacy_pct', 0)}deg,
                var(--cyber-orange) {chart_data.get('diplomacy_pct', 0)}deg 360deg
            );
            position: relative;
            box-shadow: 0 0 40px rgba(0,255,255,0.3), 0 0 80px rgba(255,0,255,0.2);
            animation: rotateIn 1s ease-out;
            border: 3px solid var(--cyber-border);
        }}
        
        @keyframes rotateIn {{
            from {{ transform: rotate(-90deg); opacity: 0; }}
            to {{ transform: rotate(0deg); opacity: 1; }}
        }}
        
        .pie-center {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 150px;
            height: 150px;
            background: var(--cyber-bg);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            border: 2px solid var(--cyber-cyan);
            box-shadow: 0 0 20px var(--cyber-cyan);
        }}
        
        .pie-total {{
            font-family: 'Orbitron', sans-serif;
            font-size: 36px;
            font-weight: 900;
            color: var(--cyber-cyan);
            text-shadow: 0 0 10px var(--cyber-cyan);
        }}
        
        .pie-label {{
            font-size: 12px;
            color: var(--cyber-gray);
            text-transform: uppercase;
        }}
        
        .legend {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 25px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .legend-dot {{
            width: 16px;
            height: 16px;
            border-radius: 0;
            box-shadow: 0 0 10px currentColor;
        }}
        
        /* 时间线 */
        .timeline {{
            position: relative;
            padding-left: 50px;
        }}
        
        .timeline::before {{
            content: '';
            position: absolute;
            left: 20px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: linear-gradient(180deg, var(--cyber-cyan) 0%, var(--cyber-magenta) 50%, var(--cyber-green) 100%);
            box-shadow: 0 0 10px var(--cyber-cyan);
        }}
        
        .timeline-item {{
            background: rgba(0,255,255,0.05);
            border: 1px solid var(--cyber-border);
            padding: 20px;
            margin-bottom: 15px;
            position: relative;
            transition: all 0.3s ease;
        }}
        
        .timeline-item:hover {{
            background: rgba(0,255,255,0.1);
            border-color: var(--cyber-cyan);
            box-shadow: 0 0 20px rgba(0,255,255,0.2);
        }}
        
        .timeline-item::before {{
            content: '';
            position: absolute;
            left: -38px;
            top: 25px;
            width: 12px;
            height: 12px;
            background: var(--cyber-cyan);
            box-shadow: 0 0 10px var(--cyber-cyan);
        }}
        
        .timeline-date {{
            font-size: 12px;
            color: var(--cyber-magenta);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }}
        
        .timeline-source {{
            font-size: 11px;
            color: var(--cyber-gray);
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        
        .timeline-title {{
            font-size: 14px;
            line-height: 1.5;
            color: var(--cyber-text);
        }}
        
        /* 内容卡片 */
        .content-card {{
            background: rgba(0,255,255,0.05);
            border: 1px solid var(--cyber-border);
            padding: 18px;
            margin-bottom: 12px;
            border-left: 4px solid var(--cyber-cyan);
            transition: all 0.3s ease;
        }}
        
        .content-card:hover {{
            background: rgba(0,255,255,0.1);
            border-color: var(--cyber-cyan);
            box-shadow: 0 0 15px rgba(0,255,255,0.2);
        }}
        
        .card-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            color: var(--cyber-cyan);
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        
        .card-icon {{
            margin-right: 12px;
            font-size: 20px;
        }}
        
        .summary-box {{
            background: rgba(0,255,255,0.05);
            border: 1px solid var(--cyber-cyan);
            padding: 25px;
            font-size: 14px;
            line-height: 1.8;
            box-shadow: 0 0 20px rgba(0,255,255,0.1);
        }}
        
        .footer {{
            text-align: center;
            color: var(--cyber-gray);
            font-size: 11px;
            padding: 30px;
            text-transform: uppercase;
            letter-spacing: 3px;
        }}
        
        @media (max-width: 768px) {{
            .chart-container {{ height: 200px; flex-direction: column; }}
            .bar {{ width: 60px; }}
            .pie-chart {{ width: 200px; height: 200px; }}
            .score-number {{ font-size: 80px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="cyber-card header">
            <span class="alert-badge">⚠ CYBER THREAT DETECTED</span>
            <div style="color: var(--cyber-gray); font-size: 12px; text-transform: uppercase; letter-spacing: 2px;">
                {datetime.now().strftime('%Y.%m.%d | %H:%M:%S')}
            </div>
            
            <div class="score-display">
                <div class="score-number">{crisis_score:.1f}</div>
            <div class="score-label">威胁等级 / 10</div>
            </div>
            
            <div class="trend-indicator">
                {trend_icon} {self._translate(trend).upper()}
            </div>
            <p style="margin-top: 15px; color: var(--cyber-gray); font-size: 13px;">{trend_desc}</p>
        </div>
        
        <!-- 柱状图 -->
        <div class="cyber-card">
            <div class="card-title">
                <span class="card-icon">📊</span>
                强度矩阵
            </div>
            <div class="chart-container">
                <div class="bar-wrapper">
                    <div class="bar" style="--bar-height: {intensity.get('conflict_intensity', {}).get('score', 0) * 28}px; --bar-color: #ff0040;">
                        <span class="bar-value">{intensity.get('conflict_intensity', {}).get('score', 0)}</span>
                    </div>
                    <div class="bar-label">⚔️ 军事冲突</div>
                </div>
                <div class="bar-wrapper">
                    <div class="bar" style="--bar-height: {intensity.get('diplomatic_tension', {}).get('score', 0) * 28}px; --bar-color: #00ffff;">
                        <span class="bar-value">{intensity.get('diplomatic_tension', {}).get('score', 0)}</span>
                    </div>
                    <div class="bar-label">🤝 外交紧张</div>
                </div>
                <div class="bar-wrapper">
                    <div class="bar" style="--bar-height: {intensity.get('oil_crisis', {}).get('score', 0) * 28}px; --bar-color: #ff6600;">
                        <span class="bar-value">{intensity.get('oil_crisis', {}).get('score', 0)}</span>
                    </div>
                    <div class="bar-label">⛽ 原油危机</div>
                </div>
            </div>
        </div>
        
        <!-- 饼图 -->
        <div class="cyber-card">
            <div class="card-title">
                <span class="card-icon">📈</span>
                新闻分类分布
            </div>
            <div class="pie-container">
                <div class="pie-chart">
                    <div class="pie-center">
                        <div class="pie-total">{chart_data.get('total', 0)}</div>
                        <div class="pie-label">条新闻</div>
                    </div>
                </div>
            </div>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-dot" style="background: var(--cyber-red); color: var(--cyber-red);"></div>
                    <span>军事 ({chart_data.get('military', 0)})</span>
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background: var(--cyber-cyan); color: var(--cyber-cyan);"></div>
                    <span>外交 ({chart_data.get('diplomacy', 0)})</span>
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background: var(--cyber-orange); color: var(--cyber-orange);"></div>
                    <span>能源 ({chart_data.get('energy', 0)})</span>
                </div>
            </div>
        </div>
        
        <!-- 执行摘要 -->
        <div class="cyber-card">
            <div class="card-title">
                <span class="card-icon">📝</span>
                执行摘要
            </div>
            <div class="summary-box">
                {executive_summary}
            </div>
        </div>
        
        <!-- 关键洞察 -->
        <div class="cyber-card">
            <div class="card-title">
                <span class="card-icon">⚠️</span>
                关键洞察
            </div>
            {"".join(f'<div class="content-card">{insight}</div>' for insight in insights)}
        </div>
        
        <!-- 趋势总评 -->
        {trend_summary_html}
        
        <!-- 时间线 -->
        <div class="cyber-card">
            <div class="card-title">
                <span class="card-icon">📅</span>
                事件时间线
            </div>
                <div class="timeline">
                    {timeline_html}
                </div>
        </div>
        
        <div class="footer">
            OILANALYZER CYBER THREAT INTELLIGENCE SYSTEM v2.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.output_dir, f"geopolitical_report_{timestamp}.html")
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✓ 报告已生成: {filename}")
        return filename
    
    # ============ 辅助方法 ============
    
    def _translate(self, text: str) -> str:
        if not text:
            return ""
        return self.translations.get(text.lower(), text)
    
    def _prepare_chart_data(self, analysis: Dict) -> Dict:
        classification = analysis.get('classification', {})
        military = len(classification.get('military', []))
        diplomacy = len(classification.get('diplomacy', []))
        energy = len(classification.get('energy', []))
        total = military + diplomacy + energy
        
        return {
            "military": military,
            "diplomacy": diplomacy,
            "energy": energy,
            "total": total,
            "military_pct": (military / total * 360) if total > 0 else 0,
            "diplomacy_pct": ((military + diplomacy) / total * 360) if total > 0 else 0
        }
    
    def _get_trend_icon(self, trend: str) -> str:
        icons = {"escalating": "⬆", "de-escalating": "⬇", "stable": "➡"}
        return icons.get(trend, "➡")
    
    def _get_trend_color(self, trend: str) -> str:
        colors = {"escalating": "#ff0040", "de-escalating": "#00ff00", "stable": "#ff6600"}
        return colors.get(trend, "#8b949e")
    
    def _get_score_color(self, score: float) -> str:
        if score >= 8: return "#ff0040"
        elif score >= 6: return "#ff6600"
        elif score >= 4: return "#ffff00"
        else: return "#00ff00"
    
    def _parse_date_for_sort(self, date_str: str):
        if not date_str or date_str == 'N/A':
            return datetime.min
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except Exception:
            return datetime.min
    
    def _format_date(self, date_str: str) -> str:
        if not date_str or date_str == 'N/A':
            return 'N/A'
        try:
            from dateutil import parser
            from datetime import timezone, timedelta
            
            dt = parser.parse(date_str)
            beijing_tz = timezone(timedelta(hours=8))
            dt_beijing = dt.astimezone(beijing_tz)
            return dt_beijing.strftime('%Y年%m月%d日 %H:%M')
        except Exception:
            return date_str[:16].replace('T', ' ')
    
    def _generate_timeline_html(self, articles: List[Dict]) -> str:
        """生成时间线HTML（只保留重要影响的事件）"""
        if not articles:
            return '<div class="timeline-item"><div class="timeline-title">暂无相关新闻</div></div>'
        
        # 按时间倒序排序
        sorted_articles = sorted(
            articles, 
            key=lambda x: self._parse_date_for_sort(x.get('publishedAt', '')), 
            reverse=True
        )
        
        # 过滤重要事件
        filtered_articles = self._filter_high_impact_articles(sorted_articles)
        
        timeline_items = []
        for article in filtered_articles:
            date_str = self._format_date(article.get('publishedAt', 'N/A'))
            source = article.get('source', 'Unknown').upper()
            title = article.get('summary_cn', article.get('title_cn', article.get('title', 'N/A')))
            impact_badge = self._generate_impact_badge(article.get('impact', {}))
            
            timeline_items.append(f'''
                    <div class="timeline-item">
                        <div class="timeline-date">{date_str}{impact_badge}</div>
                        <div class="timeline-source">[{source}]</div>
                        <div class="timeline-title">{title}</div>
                    </div>''')
        
        return "".join(timeline_items)
    
    def _generate_impact_badge(self, impact: Dict) -> str:
        if not impact:
            return ""
        
        military_stars = impact.get('military_stars', '')
        economic_stars = impact.get('economic_stars', '')
        
        if not military_stars and not economic_stars:
            return ""
        
        return f"""
        <span style="margin-left: 15px; font-size: 11px;">
            <span style="color: #ff0040;" title="军事冲突严重程度">⚔️{military_stars}</span>
            <span style="color: #ff6600; margin-left: 8px;" title="经济影响">⛽{economic_stars}</span>
        </span>"""
    
    def _filter_high_impact_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        筛选高影响力事件
        
        Args:
            articles: 文章列表
            
        Returns:
            筛选后的高影响力文章列表
        """
        high_impact_articles = []
        
        for article in articles:
            impact = article.get('impact', {})
            if not impact:
                continue
            
            military_score = impact.get('military_score', 0)
            economic_score = impact.get('economic_score', 0)
            
            # 只保留军事影响力 >= 4 或经济影响力 >= 4 的事件
            if military_score >= 4 or economic_score >= 4:
                high_impact_articles.append(article)
        
        # 如果没有高影响力事件，返回所有事件（避免空列表）
        if not high_impact_articles:
            return articles
        
        return high_impact_articles
    
    def _generate_trend_summary_html(self, trend_summary: Dict) -> str:
        """生成趋势总评HTML"""
        if not trend_summary:
            return ""
        
        overall = trend_summary.get('overall_assessment', '')
        confidence = trend_summary.get('confidence_level', 'medium')
        
        confidence_color = {
            'high': '#00ff00',
            'medium': '#ff6600', 
            'low': '#8b949e'
        }.get(confidence, '#8b949e')
        
        return f"""
        <div class="cyber-card">
            <div class="card-title">
                <span class="card-icon">🎯</span>
                TREND ASSESSMENT
            </div>
            <div class="summary-box">
                <div style="margin-bottom: 15px;">{overall}</div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: var(--cyber-gray);">CONFIDENCE</span>
                    <span style="background: {confidence_color}; 
                                color: black; padding: 6px 16px; font-weight: 700; text-transform: uppercase;">
                        {confidence.upper()}
                    </span>
                </div>
            </div>
        </div>
        """


def main():
    """测试报告生成器"""
    test_analysis = {
        "crisis_score": 7.5,
        "trend": "escalating",
        "trend_description": "中东局势持续升级",
        "intensity_assessment": {
            "conflict_intensity": {"level": "high", "score": 8.5},
            "diplomatic_tension": {"level": "medium", "score": 6.0},
            "oil_crisis": {"level": "high", "score": 7.5}
        },
        "classification": {
            "military": ["News 1", "News 2"],
            "diplomacy": ["News 3"],
            "energy": ["News 4"]
        },
        "key_insights": ["洞察1", "洞察2"],
        "executive_summary": "测试摘要",
        "trend_summary": {
            "overall_assessment": "测试趋势总评",
            "confidence_level": "high"
        }
    }
    
    test_news = {"articles": []}
    
    generator = ReportGenerator()
    report_path = generator.generate(test_analysis, test_news)
    print(f"报告路径: {report_path}")


if __name__ == "__main__":
    main()