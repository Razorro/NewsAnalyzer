/**
 * NewsAnalyzer Dashboard - 新闻流模块
 */

// 全局状态
let newsData = [];
let eventSource = null;

// 加载新闻
async function loadNews() {
    try {
        const response = await fetch('/api/rss/news?limit=30');
        newsData = await response.json();
        
        const feed = document.getElementById('news-feed');
        feed.innerHTML = '';
        
        if (newsData.length === 0) {
            feed.innerHTML = `
                <div style="text-align: center; color: var(--cyber-gray); padding: 50px;">
                    <div style="font-size: 48px; margin-bottom: 15px;">📰</div>
                    <p>暂无新闻，请等待系统拉取...</p>
                </div>
            `;
            return;
        }
        
        newsData.forEach(news => addNewsBubble(news, false));
    } catch (e) {
        console.error('加载新闻失败:', e);
        Utils.showToast('加载新闻失败', 'error');
    }
}

// 添加新闻气泡
function addNewsBubble(news, isNew = false) {
    const feed = document.getElementById('news-feed');
    
    const analysis = news.ollama_analysis || {};
    const classification = analysis.classification || {};
    const impact = analysis.impact_assessment || {};
    const entities = analysis.entities || {};
    
    const category = classification.category || 'unknown';
    const severity = impact.geopolitical_severity || 'medium';
    const oilScore = impact.oil_impact_score || 0;
    
    const categoryIcon = {
        '军事': '⚔️',
        '外交': '🤝',
        '能源': '⛽',
        '经济': '💰'
    }[category] || '📰';
    
    const bubble = document.createElement('div');
    bubble.className = `news-bubble ${isNew ? 'new' : ''}`;
    bubble.setAttribute('role', 'article');
    bubble.setAttribute('aria-label', `新闻: ${news.title}`);
    
    bubble.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
            <span style="background: rgba(0,255,255,0.2); color: var(--cyber-cyan); padding: 4px 10px; border-radius: 12px; font-size: 11px;">
                ${news.source_name || 'Unknown'}
            </span>
            <span style="color: var(--cyber-gray); font-size: 11px; margin-left: auto;">
                ${Utils.formatTime(news.published_at)}
            </span>
            <span style="background: rgba(0,255,0,0.2); color: var(--cyber-green); padding: 4px 10px; border-radius: 10px; font-size: 11px;">
                🤖 已分析
            </span>
        </div>
        
        <div style="font-size: 15px; font-weight: bold; margin-bottom: 10px; line-height: 1.4;">
            <a href="${news.url}" target="_blank" style="color: var(--cyber-text); text-decoration: none;" aria-label="查看新闻原文: ${news.title}">
                ${news.title}
            </a>
        </div>
        
        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--cyber-border);">
            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px;">
                <span style="padding: 4px 10px; border-radius: 12px; font-size: 11px; background: rgba(255,0,64,0.2); color: var(--cyber-red);">
                    ${categoryIcon} ${category}
                </span>
                <span style="padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid ${severity === 'critical' ? 'var(--cyber-red)' : severity === 'high' ? 'var(--cyber-orange)' : 'var(--cyber-yellow)'};">
                    ${severity}
                </span>
            </div>
            
            <div style="display: flex; align-items: center; gap: 10px; margin: 10px 0; padding: 8px; background: rgba(0,0,0,0.3); border-radius: 6px;">
                <span style="font-size: 11px; color: var(--cyber-gray);">🛢️ 油价影响</span>
                <div style="flex: 1; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden;">
                    <div style="height: 100%; background: linear-gradient(90deg, var(--cyber-green), var(--cyber-yellow), var(--cyber-orange), var(--cyber-red)); width: ${oilScore * 10}%; transition: width 0.5s ease;"></div>
                </div>
                <span style="font-family: 'Orbitron', sans-serif; font-weight: bold; color: var(--cyber-cyan); font-size: 14px;">
                    ${oilScore.toFixed(1)}/10
                </span>
            </div>
            
            <div style="padding: 10px; background: rgba(0,255,255,0.05); border-left: 3px solid var(--cyber-cyan); margin: 10px 0; font-size: 13px; line-height: 1.5;">
                💬 ${analysis.chinese_summary || news.summary_cn || '等待分析...'}
            </div>
            
            ${(analysis.key_insights || []).length > 0 ? `
                <div style="margin: 10px 0;">
                    ${(analysis.key_insights || []).map(insight => `
                        <div style="padding: 6px 10px; margin: 4px 0; background: rgba(255,0,255,0.05); border-left: 2px solid var(--cyber-magenta); font-size: 12px;">
                            ▸ ${insight}
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            
            ${(entities.countries || []).length > 0 ? `
                <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;">
                    ${(entities.countries || []).map(country => `
                        <span style="padding: 4px 10px; background: rgba(255,255,255,0.1); border-radius: 12px; font-size: 11px;">
                            🌍 ${country}
                        </span>
                    `).join('')}
                </div>
            ` : ''}
        </div>
        
        <a href="${news.url}" target="_blank" style="display: inline-block; margin-top: 10px; padding: 6px 12px; background: rgba(0,255,255,0.1); border: 1px solid var(--cyber-cyan); border-radius: 4px; color: var(--cyber-cyan); text-decoration: none; font-size: 12px;" aria-label="查看新闻原文">
            🔗 查看原文
        </a>
    `;
    
    if (isNew) {
        feed.insertBefore(bubble, feed.firstChild);
    } else {
        feed.appendChild(bubble);
    }
    
    // 限制显示数量
    while (feed.children.length > 50) {
        feed.removeChild(feed.lastChild);
    }
}

// SSE实时推送
function initSSE() {
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource('/api/rss/stream');
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('收到SSE消息:', data);
            handleSSEMessage(data);
        } catch (e) {
            console.error('SSE消息解析失败:', e);
        }
    };
    
    eventSource.onerror = function() {
        console.log('SSE连接断开，3秒后重连...');
        setTimeout(initSSE, 3000);
    };
    
    console.log('SSE连接已初始化');
}

// 处理SSE消息
function handleSSEMessage(message) {
    switch (message.type) {
        case 'connected':
            console.log('SSE连接成功');
            break;
        case 'news_analyzed':
            console.log('收到新新闻:', message.data);
            addNewsBubble(message.data, true);
            // 更新队列显示
            fetchQueueLength();
            break;
        case 'sentiment_updated':
            console.log('情绪数据更新');
            StatsManager.updateSentiment(message.data);
            break;
        case 'queue_updated':
            console.log('队列更新:', message.data.queue_length);
            StatsManager.updateQueueDisplay(message.data.queue_length);
            break;
        default:
            console.log('未知消息类型:', message.type);
    }
}

// 搜索新闻
function searchNews(query) {
    const feed = document.getElementById('news-feed');
    const newsBubbles = feed.querySelectorAll('.news-bubble');
    
    newsBubbles.forEach(bubble => {
        const title = bubble.querySelector('a').textContent.toLowerCase();
        const summary = bubble.querySelector('[style*="border-left: 3px solid var(--cyber-cyan)"]')?.textContent.toLowerCase() || '';
        
        if (title.includes(query.toLowerCase()) || summary.includes(query.toLowerCase())) {
            bubble.style.display = 'block';
        } else {
            bubble.style.display = 'none';
        }
    });
}

// 过滤新闻
function filterNews(category = 'all', timeRange = 'all') {
    const feed = document.getElementById('news-feed');
    const newsBubbles = feed.querySelectorAll('.news-bubble');
    
    newsBubbles.forEach(bubble => {
        let show = true;
        
        // 按类别过滤
        if (category !== 'all') {
            const categoryText = bubble.querySelector('[style*="background: rgba(255,0,64,0.2)"]')?.textContent || '';
            if (!categoryText.includes(category)) {
                show = false;
            }
        }
        
        // 按时间过滤
        if (timeRange !== 'all') {
            const timeText = bubble.querySelector('[style*="color: var(--cyber-gray)"]')?.textContent || '';
            if (timeRange === 'today' && !timeText.includes('刚刚') && !timeText.includes('分钟前') && !timeText.includes('小时前')) {
                show = false;
            } else if (timeRange === 'week' && timeText.includes('天前')) {
                const days = parseInt(timeText);
                if (days > 7) {
                    show = false;
                }
            }
        }
        
        bubble.style.display = show ? 'block' : 'none';
    });
}

// 排序新闻
function sortNews(sortBy = 'time') {
    const feed = document.getElementById('news-feed');
    const newsBubbles = Array.from(feed.querySelectorAll('.news-bubble'));
    
    newsBubbles.sort((a, b) => {
        if (sortBy === 'time') {
            const timeA = a.querySelector('[style*="color: var(--cyber-gray)"]')?.textContent || '';
            const timeB = b.querySelector('[style*="color: var(--cyber-gray)"]')?.textContent || '';
            return timeA.localeCompare(timeB);
        } else if (sortBy === 'impact') {
            const scoreA = parseFloat(a.querySelector('[style*="font-family: \'Orbitron\'"]')?.textContent || '0');
            const scoreB = parseFloat(b.querySelector('[style*="font-family: \'Orbitron\'"]')?.textContent || '0');
            return scoreB - scoreA;
        }
        return 0;
    });
    
    newsBubbles.forEach(bubble => feed.appendChild(bubble));
}

// 导出新闻数据
function exportNews(format = 'json') {
    const exportData = newsData.map(news => ({
        title: news.title,
        url: news.url,
        source: news.source_name,
        published: news.published_at,
        category: news.ollama_analysis?.classification?.category,
        severity: news.ollama_analysis?.impact_assessment?.geopolitical_severity,
        oil_score: news.ollama_analysis?.impact_assessment?.oil_impact_score,
        summary: news.ollama_analysis?.chinese_summary
    }));
    
    if (format === 'json') {
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `news-export-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
    } else if (format === 'csv') {
        const headers = ['标题', '链接', '来源', '发布时间', '类别', '严重程度', '油价评分', '摘要'];
        const csvContent = [
            headers.join(','),
            ...exportData.map(row => [
                `"${row.title}"`,
                row.url,
                row.source,
                row.published,
                row.category,
                row.severity,
                row.oil_score,
                `"${row.summary}"`
            ].join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `news-export-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    Utils.showToast(`新闻数据已导出为${format.toUpperCase()}格式`, 'success');
}

// 刷新新闻
function refreshNews() {
    loadNews();
    Utils.showToast('新闻已刷新', 'success');
}

// 导出新闻流函数
window.NewsFeed = {
    loadNews,
    addNewsBubble,
    initSSE,
    handleSSEMessage,
    searchNews,
    filterNews,
    sortNews,
    exportNews,
    refreshNews
};