/**
 * NewsAnalyzer Dashboard - 主JavaScript文件
 * 协调所有模块的工作
 */

// 全局配置
const DashboardConfig = {
    refreshInterval: 30000, // 30秒刷新一次
    animationDuration: 300,
    maxNewsItems: 50,
    apiEndpoints: {
        themes: '/api/rss/themes/tree',
        news: '/api/rss/news',
        stats: '/api/rss/dashboard-stats',
        alerts: '/api/rss/alerts',
        feeds: '/api/rss/feeds',
        stream: '/api/rss/stream'
    }
};

// 初始化应用
document.addEventListener('DOMContentLoaded', function() {
    initApp();
});

// 主初始化函数
function initApp() {
    console.log('NewsAnalyzer Dashboard 初始化中...');
    
    // 初始化各个模块
    initModules();
    
    // 设置全局事件监听器
    setupEventListeners();
    
    // 初始化SSE连接
    NewsFeed.initSSE();
    
    console.log('NewsAnalyzer Dashboard 初始化完成');
}

// 初始化各个模块
function initModules() {
    // 初始化主题管理
    ThemeManager.loadThemesTree();
    
    // 初始化新闻流
    NewsFeed.loadNews();
    
    // 初始化统计管理
    StatsManager.initCountdown();
    
    // 初始化工具函数
    Utils.formatTime(new Date().toISOString());
}

// 设置全局事件监听器
function setupEventListeners() {
    // 搜索功能
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', Utils.debounce(function(e) {
            NewsFeed.searchNews(e.target.value);
        }, 300));
    }
    
    // 过滤功能
    const categoryFilter = document.getElementById('category-filter');
    if (categoryFilter) {
        categoryFilter.addEventListener('change', function(e) {
            NewsFeed.filterNews(e.target.value, 'all');
        });
    }
    
    // 时间范围过滤
    const timeFilter = document.getElementById('time-filter');
    if (timeFilter) {
        timeFilter.addEventListener('change', function(e) {
            NewsFeed.filterNews('all', e.target.value);
        });
    }
    
    // 排序功能
    const sortSelect = document.getElementById('sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', function(e) {
            NewsFeed.sortNews(e.target.value);
        });
    }
    
    // 导出功能
    const exportJsonBtn = document.getElementById('export-json');
    if (exportJsonBtn) {
        exportJsonBtn.addEventListener('click', function() {
            NewsFeed.exportNews('json');
        });
    }
    
    const exportCsvBtn = document.getElementById('export-csv');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', function() {
            NewsFeed.exportNews('csv');
        });
    }
    
    // 刷新按钮
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            NewsFeed.refreshNews();
            Utils.showToast('正在刷新数据...', 'info');
        });
    }
    
    // 手动刷新按钮
    const manualFetchBtn = document.getElementById('manual-fetch-btn');
    if (manualFetchBtn) {
        manualFetchBtn.addEventListener('click', function() {
            StatsManager.triggerFetch();
        });
    }
    
    // 键盘快捷键
    setupKeyboardShortcuts();
    
    // 响应式设计监听
    setupResponsiveListeners();
}

// 设置键盘快捷键
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl + R: 刷新新闻
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            NewsFeed.refreshNews();
        }
        
        // Ctrl + F: 聚焦搜索框
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.focus();
            }
        }
        
        // Escape: 关闭所有弹窗
        if (e.key === 'Escape') {
            hideAllModals();
        }
        
        // Enter: 确认当前弹窗操作
        if (e.key === 'Enter') {
            const activeModal = document.querySelector('.modal.active');
            if (activeModal) {
                const confirmBtn = activeModal.querySelector('.btn-primary');
                if (confirmBtn) {
                    confirmBtn.click();
                }
            }
        }
    });
}

// 设置响应式监听器
function setupResponsiveListeners() {
    // 监听窗口大小变化
    window.addEventListener('resize', Utils.debounce(function() {
        handleResponsiveLayout();
    }, 250));
    
    // 初始化响应式布局
    handleResponsiveLayout();
}

// 处理响应式布局
function handleResponsiveLayout() {
    const width = window.innerWidth;
    const container = document.querySelector('.container');
    const leftPanel = document.querySelector('.left-panel');
    
    if (width <= 768) {
        // 移动端布局
        if (container) {
            container.style.flexDirection = 'column';
        }
        if (leftPanel) {
            leftPanel.style.width = '100%';
        }
        
        // 添加移动端菜单按钮
        addMobileMenuButton();
    } else if (width <= 1200) {
        // 平板端布局
        if (container) {
            container.style.flexDirection = 'column';
        }
        if (leftPanel) {
            leftPanel.style.width = '100%';
        }
        
        // 移除移动端菜单按钮
        removeMobileMenuButton();
    } else {
        // 桌面端布局
        if (container) {
            container.style.flexDirection = 'row';
        }
        if (leftPanel) {
            leftPanel.style.width = '450px';
        }
        
        // 移除移动端菜单按钮
        removeMobileMenuButton();
    }
}

// 添加移动端菜单按钮
function addMobileMenuButton() {
    const existingBtn = document.getElementById('mobile-menu-btn');
    if (existingBtn) return;
    
    const header = document.querySelector('.header');
    if (header) {
        const menuBtn = document.createElement('button');
        menuBtn.id = 'mobile-menu-btn';
        menuBtn.innerHTML = '☰ 菜单';
        menuBtn.style.cssText = `
            position: absolute;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(0,255,255,0.2);
            border: 1px solid var(--cyber-cyan);
            color: var(--cyber-cyan);
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-family: inherit;
        `;
        
        menuBtn.addEventListener('click', toggleMobileMenu);
        header.style.position = 'relative';
        header.appendChild(menuBtn);
    }
}

// 移除移动端菜单按钮
function removeMobileMenuButton() {
    const menuBtn = document.getElementById('mobile-menu-btn');
    if (menuBtn) {
        menuBtn.remove();
    }
}

// 切换移动端菜单
function toggleMobileMenu() {
    const leftPanel = document.querySelector('.left-panel');
    if (leftPanel) {
        leftPanel.classList.toggle('mobile-visible');
        
        if (leftPanel.classList.contains('mobile-visible')) {
            leftPanel.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 1000;
                background: var(--cyber-bg);
                overflow-y: auto;
                padding: 20px;
            `;
            
            // 添加关闭按钮
            const closeBtn = document.createElement('button');
            closeBtn.id = 'close-menu-btn';
            closeBtn.innerHTML = '× 关闭';
            closeBtn.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: var(--cyber-red);
                border: none;
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                cursor: pointer;
                z-index: 1001;
            `;
            
            closeBtn.addEventListener('click', toggleMobileMenu);
            document.body.appendChild(closeBtn);
        } else {
            leftPanel.style.cssText = '';
            
            const closeBtn = document.getElementById('close-menu-btn');
            if (closeBtn) {
                closeBtn.remove();
            }
        }
    }
}

// 隐藏所有弹窗
function hideAllModals() {
    const modals = document.querySelectorAll('.modal.active');
    modals.forEach(modal => {
        modal.classList.remove('active');
    });
}

// 全局函数导出
window.Dashboard = {
    config: DashboardConfig,
    init: initApp,
    hideAllModals: hideAllModals,
    toggleMobileMenu: toggleMobileMenu
};

// 兼容性处理：将模块函数暴露到全局作用域
// 这样HTML中的onclick事件仍然可以正常工作
window.toggleTheme = ThemeManager.toggleTheme;
window.toggleThemeExpand = ThemeManager.toggleThemeExpand;
window.showAddKeyword = ThemeManager.showAddKeyword;
window.hideAddKeyword = ThemeManager.hideAddKeyword;
window.addKeyword = ThemeManager.addKeyword;
window.showEditKeyword = ThemeManager.showEditKeyword;
window.hideEditKeywordModal = ThemeManager.hideEditKeywordModal;
window.confirmEditKeyword = ThemeManager.confirmEditKeyword;
window.deleteKeyword = ThemeManager.deleteKeyword;
window.showAISuggest = ThemeManager.showAISuggest;
window.hideAISuggestModal = ThemeManager.hideAISuggestModal;
window.regenerateKeywords = ThemeManager.regenerateKeywords;
window.importSelectedKeywords = ThemeManager.importSelectedKeywords;
window.deleteTheme = ThemeManager.deleteTheme;
window.showCreateThemeModal = ThemeManager.showCreateThemeModal;
window.hideCreateThemeModal = ThemeManager.hideCreateThemeModal;
window.showAISuggestForNewTheme = ThemeManager.showAISuggestForNewTheme;
window.updateSelectedKeywordsPreview = ThemeManager.updateSelectedKeywordsPreview;
window.removeSelectedKeyword = ThemeManager.removeSelectedKeyword;
window.createTheme = ThemeManager.createTheme;

window.loadNews = NewsFeed.loadNews;
window.addNewsBubble = NewsFeed.addNewsBubble;
window.searchNews = NewsFeed.searchNews;
window.filterNews = NewsFeed.filterNews;
window.sortNews = NewsFeed.sortNews;
window.exportNews = NewsFeed.exportNews;
window.refreshNews = NewsFeed.refreshNews;

window.triggerFetch = StatsManager.triggerFetch;
window.addFeed = StatsManager.addFeed;
window.toggleFeedExpand = StatsManager.toggleFeedExpand;
window.deleteFeed = StatsManager.deleteFeed;
window.toggleFeed = StatsManager.toggleFeed;

console.log('NewsAnalyzer Dashboard 主脚本加载完成');