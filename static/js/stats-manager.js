/**
 * NewsAnalyzer Dashboard - 统计管理模块
 */

// 全局状态
let countdownSeconds = 30 * 60; // 30分钟
let countdownInterval = null;
let expandedFeeds = new Set();

// 初始化倒计时
function initCountdown() {
    updateCountdownDisplay();
    startCountdown();
    loadDashboardStats();
    loadAlerts();
    loadFeeds();
    
    // 定时刷新
    setInterval(loadDashboardStats, 30000);
    setInterval(loadAlerts, 30000);
}

// 开始倒计时
function startCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
    }
    
    countdownInterval = setInterval(() => {
        countdownSeconds--;
        
        if (countdownSeconds <= 0) {
            triggerFetch();
            countdownSeconds = 30 * 60;
        }
        
        updateCountdownDisplay();
    }, 1000);
}

// 更新倒计时显示
function updateCountdownDisplay() {
    const minutes = Math.floor(countdownSeconds / 60);
    const seconds = countdownSeconds % 60;
    const display = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    
    document.getElementById('countdown-display').textContent = display;
    
    const totalSeconds = 30 * 60;
    const progress = (countdownSeconds / totalSeconds) * 100;
    document.getElementById('countdown-progress').style.width = `${progress}%`;
}

// 触发数据抓取
function triggerFetch() {
    fetch('/api/rss/fetch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('刷新任务已启动');
            countdownSeconds = 30 * 60;
            Utils.showToast('数据刷新已启动', 'success');
        } else {
            console.error('刷新失败:', data.message);
            Utils.showToast('刷新失败: ' + data.message, 'error');
        }
    })
    .catch(e => {
        console.error('刷新请求失败:', e);
        Utils.showToast('刷新请求失败', 'error');
    });
}

// 加载看板统计
async function loadDashboardStats() {
    try {
        const response = await fetch('/api/rss/dashboard-stats');
        const data = await response.json();
        updateDashboardStats(data);
    } catch (e) {
        console.error('加载看板数据失败:', e);
    }
}

// 更新看板统计
function updateDashboardStats(stats) {
    document.getElementById('today-count').textContent = stats.today_count || 0;
    document.getElementById('alert-count').textContent = stats.alert_count || 0;
    document.getElementById('active-feeds').textContent = stats.active_feeds || 0;
    
    const categories = stats.category_distribution || {};
    const total = Object.values(categories).reduce((a, b) => a + b, 0) || 1;
    
    ['military', 'energy', 'diplomacy', 'economic'].forEach(cat => {
        const key = {'military': '军事', 'energy': '能源', 'diplomacy': '外交', 'economic': '经济'}[cat];
        const count = categories[key] || 0;
        const pct = (count / total * 100).toFixed(0);
        
        document.getElementById(`cat-${cat}`).textContent = count;
        document.getElementById(`bar-${cat}`).style.width = `${pct}%`;
    });
    
    if (stats.overall_sentiment) {
        updateSentiment(stats.overall_sentiment);
    }
}

// 更新情绪数据
function updateSentiment(data) {
    const tension = data.tension_score || {};
    document.getElementById('tension-value').textContent = (tension.current || 5.0).toFixed(1);
    
    const trend = tension.trend || 'stable';
    const trendEl = document.getElementById('tension-trend');
    if (trend === 'rising') {
        trendEl.innerHTML = '↗️ 上升';
        trendEl.style.color = 'var(--cyber-red)';
    } else if (trend === 'falling') {
        trendEl.innerHTML = '↘️ 下降';
        trendEl.style.color = 'var(--cyber-green)';
    } else {
        trendEl.innerHTML = '➡️ 稳定';
        trendEl.style.color = 'var(--cyber-gray)';
    }
    
    const sentimentIndex = data.sentiment_index || {};
    const negative = sentimentIndex.negative || 50;
    const neutral = sentimentIndex.neutral || 40;
    const positive = sentimentIndex.positive || 10;
    
    document.getElementById('negative-bar').style.width = `${negative}%`;
    document.getElementById('negative-value').textContent = `${negative}%`;
    document.getElementById('neutral-bar').style.width = `${neutral}%`;
    document.getElementById('neutral-value').textContent = `${neutral}%`;
    document.getElementById('positive-bar').style.width = `${positive}%`;
    document.getElementById('positive-value').textContent = `${positive}%`;
    
    const oilOutlook = data.oil_outlook || {};
    document.getElementById('oil-direction').textContent = oilOutlook.direction || '震荡';
    document.getElementById('oil-confidence').textContent = `置信度: ${((oilOutlook.confidence || 0.5) * 100).toFixed(0)}%`;
    
    const factors = data.dominant_factors || [];
    const factorsEl = document.getElementById('dominant-factors');
    factorsEl.innerHTML = '<div style="font-size: 12px; color: var(--cyber-gray); margin-bottom: 8px;">📌 主导因素</div>';
    factors.forEach(factor => {
        const div = document.createElement('div');
        div.style.cssText = 'padding: 6px 10px; margin: 4px 0; background: rgba(255,0,255,0.05); border-left: 2px solid var(--cyber-magenta); font-size: 12px;';
        div.textContent = `· ${factor}`;
        factorsEl.appendChild(div);
    });
}

// 加载预警
async function loadAlerts() {
    try {
        const response = await fetch('/api/rss/alerts');
        const data = await response.json();
        updateAlerts(data);
    } catch (e) {
        console.error('加载预警失败:', e);
    }
}

// 更新预警
function updateAlerts(alerts) {
    const container = document.getElementById('alerts-list');
    
    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--cyber-gray); padding: 20px;">
                <div style="font-size: 24px; margin-bottom: 10px;">✓</div>
                <p>暂无预警</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = alerts.map(alert => {
        const score = alert.oil_impact_score || 0;
        const level = score >= 8 ? 'high' : 'medium';
        const borderColor = level === 'high' ? 'var(--cyber-red)' : 'var(--cyber-orange)';
        const bgColor = level === 'high' ? 'rgba(255,0,64,0.15)' : 'rgba(255,102,0,0.1)';
        
        return `
            <div style="padding: 10px; margin: 6px 0; background: ${bgColor}; border-left: 3px solid ${borderColor}; border-radius: 4px; font-size: 12px;" role="alert" aria-label="预警: ${alert.title}">
                <div style="font-weight: bold; margin-bottom: 4px;">${alert.title}</div>
                <div style="color: var(--cyber-gray);">
                    🛢️ 油价影响: ${score.toFixed(1)} · ${alert.source_name} · ${Utils.formatTime(alert.created_at)}
                </div>
            </div>
        `;
    }).join('');
}

// 获取队列长度
async function fetchQueueLength() {
    try {
        const response = await fetch('/api/rss/queue-length');
        const data = await response.json();
        const queueLength = data.queue_length || 0;
        
        updateQueueDisplay(queueLength);
    } catch (e) {
        console.error('获取队列长度失败:', e);
    }
}

// 更新队列显示
function updateQueueDisplay(queueLength) {
    const pendingEl = document.getElementById('pending-analysis');
    pendingEl.textContent = queueLength;
    
    if (queueLength > 0) {
        pendingEl.style.color = 'var(--cyber-orange)';
    } else {
        pendingEl.style.color = 'var(--cyber-cyan)';
    }
}

// 加载订阅源
async function loadFeeds() {
    try {
        const response = await fetch('/api/rss/feeds');
        const data = await response.json();
        updateFeeds(data);
    } catch (e) {
        console.error('加载订阅源失败:', e);
    }
}

// 更新订阅源
function updateFeeds(feeds) {
    const container = document.getElementById('feeds-list');
    
    if (!feeds || feeds.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: var(--cyber-gray); padding: 20px;">暂无订阅源</div>';
        return;
    }
    
    container.innerHTML = feeds.map(feed => `
        <div class="feed-node" data-feed-id="${feed.id}">
            <div class="feed-header">
                <input type="checkbox" 
                       class="feed-checkbox" 
                       ${feed.enabled ? 'checked' : ''} 
                       onchange="StatsManager.toggleFeed(${feed.id}, this.checked)"
                       aria-label="启用订阅源: ${feed.name}">
                <span class="feed-name">${feed.name}</span>
                <span class="feed-stats">${feed.article_count || 0}篇</span>
                <div class="feed-actions" role="group" aria-label="订阅源操作">
                    <button class="feed-action-btn btn-feed-expand" 
                            onclick="StatsManager.toggleFeedExpand(${feed.id})"
                            aria-label="${expandedFeeds.has(feed.id) ? '收起详情' : '展开详情'}"
                            aria-expanded="${expandedFeeds.has(feed.id)}">
                        ${expandedFeeds.has(feed.id) ? '▲' : '▼'}
                    </button>
                    <button class="feed-action-btn btn-feed-delete" 
                            onclick="StatsManager.deleteFeed(${feed.id})"
                            aria-label="删除订阅源">×</button>
                </div>
            </div>
            <div class="feed-details ${expandedFeeds.has(feed.id) ? 'expanded' : ''}" 
                 id="feed-details-${feed.id}"
                 role="region"
                 aria-label="订阅源详情">
                <div class="feed-detail-item">
                    <span class="feed-detail-icon">📎</span>
                    <span class="feed-detail-label">URL:</span>
                    <span class="feed-detail-value url">${feed.url}</span>
                </div>
                <div class="feed-detail-item">
                    <span class="feed-detail-icon">🕐</span>
                    <span class="feed-detail-label">最后拉取:</span>
                    <span class="feed-detail-value">${feed.last_fetched ? Utils.formatTime(feed.last_fetched) : '从未拉取'}</span>
                </div>
                <div class="feed-detail-item">
                    <span class="feed-detail-icon">📅</span>
                    <span class="feed-detail-label">创建时间:</span>
                    <span class="feed-detail-value">${Utils.formatTime(feed.created_at)}</span>
                </div>
            </div>
        </div>
    `).join('');
}

// 展开/收起订阅源详情
function toggleFeedExpand(feedId) {
    const details = document.getElementById(`feed-details-${feedId}`);
    const button = document.querySelector(`[data-feed-id="${feedId}"] .btn-feed-expand`);
    
    details.classList.toggle('expanded');
    
    // 更新展开状态集合
    if (expandedFeeds.has(feedId)) {
        expandedFeeds.delete(feedId);
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-label', '展开详情');
        button.textContent = '▼';
    } else {
        expandedFeeds.add(feedId);
        button.setAttribute('aria-expanded', 'true');
        button.setAttribute('aria-label', '收起详情');
        button.textContent = '▲';
    }
}

// 添加订阅源
async function addFeed() {
    const nameInput = document.getElementById('feed-name');
    const urlInput = document.getElementById('feed-url');
    
    const name = nameInput.value.trim();
    const url = urlInput.value.trim();
    
    if (!name || !url) {
        Utils.showToast('请填写订阅源名称和URL', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/rss/feeds', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, url})
        });
        
        const result = await response.json();
        
        if (result.success) {
            nameInput.value = '';
            urlInput.value = '';
            loadFeeds();
            Utils.showToast('订阅源添加成功', 'success');
        } else {
            Utils.showToast(result.message || '添加失败', 'error');
        }
    } catch (e) {
        console.error('添加订阅源失败:', e);
        Utils.showToast('添加失败: ' + e.message, 'error');
    }
}

// 删除订阅源
async function deleteFeed(feedId) {
    if (!confirm('确定删除此订阅源？')) return;
    
    try {
        const response = await fetch(`/api/rss/feeds/${feedId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            loadFeeds();
            Utils.showToast('订阅源已删除', 'success');
        } else {
            Utils.showToast(result.message || '删除失败', 'error');
        }
    } catch (e) {
        console.error('删除订阅源失败:', e);
        Utils.showToast('删除失败: ' + e.message, 'error');
    }
}

// 切换订阅源状态
async function toggleFeed(feedId, enabled) {
    try {
        await fetch(`/api/rss/feeds/${feedId}/toggle`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({enabled})
        });
        
        Utils.showToast(enabled ? '订阅源已启用' : '订阅源已禁用', 'success');
    } catch (e) {
        console.error('切换状态失败:', e);
        Utils.showToast('切换状态失败', 'error');
    }
}

// 导出统计管理函数
window.StatsManager = {
    initCountdown,
    startCountdown,
    updateCountdownDisplay,
    triggerFetch,
    loadDashboardStats,
    updateDashboardStats,
    updateSentiment,
    loadAlerts,
    updateAlerts,
    fetchQueueLength,
    updateQueueDisplay,
    loadFeeds,
    updateFeeds,
    toggleFeedExpand,
    addFeed,
    deleteFeed,
    toggleFeed
};