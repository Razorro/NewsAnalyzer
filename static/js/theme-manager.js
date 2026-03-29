/**
 * NewsAnalyzer Dashboard - 主题管理模块
 */

// 全局状态
let themes = [];
let currentThemeId = null;
let aiSuggestedKeywords = [];
let selectedAIKeywords = [];
let editingKeywordId = null;
let newThemeSelectedKeywords = [];
let expandedThemes = new Set();

// 加载主题树
async function loadThemesTree() {
    try {
        const response = await fetch('/api/rss/themes/tree');
        themes = await response.json();
        renderThemeTree();
    } catch (e) {
        console.error('加载主题失败:', e);
        Utils.showToast('加载主题失败', 'error');
    }
}

// 渲染主题树
function renderThemeTree() {
    const container = document.getElementById('theme-tree');
    
    if (!themes || themes.length === 0) {
        container.innerHTML = '<div style="text-align: center; color: var(--cyber-gray); padding: 20px;">暂无主题，点击上方按钮创建</div>';
        return;
    }
    
    container.innerHTML = themes.map(theme => `
        <div class="theme-node ${theme.enabled ? 'enabled' : 'disabled'}" data-theme-id="${theme.id}">
            <div class="theme-header">
                <span class="theme-status ${theme.enabled ? 'enabled' : 'disabled'}" 
                      role="status" 
                      aria-label="主题状态: ${theme.enabled ? '已启用' : '已禁用'}"></span>
                <span class="theme-color" style="background: ${theme.color}; color: ${theme.color};" 
                      role="img" 
                      aria-label="主题颜色"></span>
                <div class="theme-info">
                    <div class="theme-name">${theme.name}</div>
                    <div class="theme-stats">
                        <span style="color: var(--cyber-green);">✓ ${theme.keyword_count}个激活</span>
                    </div>
                </div>
                <div class="theme-actions" role="group" aria-label="主题操作">
                    <button class="theme-action-btn btn-toggle" 
                            onclick="toggleTheme(${theme.id})"
                            aria-label="${theme.enabled ? '禁用主题' : '启用主题'}"
                            aria-pressed="${theme.enabled}">
                        ${theme.enabled ? '✓' : '○'}
                    </button>
                    <button class="theme-action-btn btn-expand" 
                            onclick="toggleThemeExpand(${theme.id})"
                            aria-label="${expandedThemes.has(theme.id) ? '收起关键词' : '展开关键词'}"
                            aria-expanded="${expandedThemes.has(theme.id)}">
                        ▼
                    </button>
                    <button class="theme-action-btn btn-add-kw" 
                            onclick="showAddKeyword(${theme.id})"
                            aria-label="添加关键词">+词</button>
                    <button class="theme-action-btn btn-ai-suggest" 
                            onclick="showAISuggest(${theme.id})"
                            aria-label="AI推荐关键词">🤖</button>
                    <button class="theme-action-btn btn-delete-theme" 
                            onclick="deleteTheme(${theme.id})"
                            aria-label="删除主题">×</button>
                </div>
            </div>
            <div class="keywords-container ${expandedThemes.has(theme.id) ? 'expanded' : ''}" 
                 id="keywords-${theme.id}"
                 role="region"
                 aria-label="关键词列表">
                <div class="keywords-header">
                    <span class="keywords-title">关键词列表</span>
                    <span class="keywords-count">${theme.keyword_count}个</span>
                </div>
                ${theme.keywords.map(kw => `
                    <div class="keyword-item" data-keyword-id="${kw.id}">
                        <span class="keyword-text">${kw.keyword}</span>
                        ${kw.match_count > 0 ? `<span class="keyword-matches">[${kw.match_count}]</span>` : ''}
                        <div class="keyword-actions" role="group" aria-label="关键词操作">
                            <button class="kw-action-btn btn-edit-kw" 
                                    onclick="showEditKeyword(${kw.id}, '${kw.keyword}')"
                                    aria-label="编辑关键词">✏️</button>
                            <button class="kw-action-btn btn-delete-kw" 
                                    onclick="deleteKeyword(${kw.id}, ${theme.id})"
                                    aria-label="删除关键词">×</button>
                        </div>
                    </div>
                `).join('')}
                <div class="add-keyword-inline" id="add-kw-${theme.id}" style="display: none;">
                    <input type="text" 
                           placeholder="输入关键词" 
                           id="kw-input-${theme.id}"
                           aria-label="新关键词输入">
                    <button class="btn-confirm" 
                            onclick="addKeyword(${theme.id})"
                            aria-label="确认添加">添加</button>
                    <button class="btn-cancel" 
                            onclick="hideAddKeyword(${theme.id})"
                            aria-label="取消添加">取消</button>
                </div>
            </div>
        </div>
    `).join('');
}

// 展开/收起主题
function toggleThemeExpand(themeId) {
    const container = document.getElementById(`keywords-${themeId}`);
    const button = document.querySelector(`[data-theme-id="${themeId}"] .btn-expand`);
    
    container.classList.toggle('expanded');
    
    // 更新展开状态集合
    if (expandedThemes.has(themeId)) {
        expandedThemes.delete(themeId);
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-label', '展开关键词');
    } else {
        expandedThemes.add(themeId);
        button.setAttribute('aria-expanded', 'true');
        button.setAttribute('aria-label', '收起关键词');
    }
}

// 启用/禁用主题
async function toggleTheme(themeId) {
    const theme = themes.find(t => t.id === themeId);
    if (!theme) {
        Utils.showToast('主题不存在', 'error');
        return;
    }
    
    const newEnabled = !theme.enabled;
    
    try {
        const response = await fetch(`/api/rss/themes/${themeId}/toggle`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({enabled: newEnabled})
        });
        
        const result = await response.json();
        
        if (result.success) {
            loadThemesTree();
            Utils.showToast(newEnabled ? '主题已启用' : '主题已禁用', 'success');
        } else {
            Utils.showToast(result.message || '操作失败', 'error');
        }
    } catch (e) {
        console.error('切换主题状态失败:', e);
        Utils.showToast('操作失败', 'error');
    }
}

// 显示添加关键词输入框
function showAddKeyword(themeId) {
    const addKeywordDiv = document.getElementById(`add-kw-${themeId}`);
    const keywordsContainer = document.getElementById(`keywords-${themeId}`);
    
    addKeywordDiv.style.display = 'flex';
    keywordsContainer.classList.add('expanded');
    document.getElementById(`kw-input-${themeId}`).focus();
}

// 隐藏添加关键词输入框
function hideAddKeyword(themeId) {
    document.getElementById(`add-kw-${themeId}`).style.display = 'none';
}

// 添加关键词
async function addKeyword(themeId) {
    const input = document.getElementById(`kw-input-${themeId}`);
    const keyword = input.value.trim();
    
    if (!keyword) {
        Utils.showToast('请输入关键词', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/rss/themes/${themeId}/keywords`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({keyword})
        });
        
        const result = await response.json();
        if (result.success) {
            input.value = '';
            hideAddKeyword(themeId);
            loadThemesTree();
            Utils.showToast('✓ 关键词添加成功', 'success');
        } else {
            Utils.showToast(result.message || '添加失败', 'error');
        }
    } catch (e) {
        console.error('添加关键词失败:', e);
        Utils.showToast('添加失败: ' + e.message, 'error');
    }
}

// 显示编辑关键词弹窗
function showEditKeyword(keywordId, currentKeyword) {
    editingKeywordId = keywordId;
    document.getElementById('edit-keyword-input').value = currentKeyword;
    document.getElementById('edit-keyword-modal').classList.add('active');
}

// 隐藏编辑关键词弹窗
function hideEditKeywordModal() {
    document.getElementById('edit-keyword-modal').classList.remove('active');
    editingKeywordId = null;
}

// 确认编辑关键词
async function confirmEditKeyword() {
    const newKeyword = document.getElementById('edit-keyword-input').value.trim();
    if (!newKeyword || !editingKeywordId) return;
    
    try {
        const response = await fetch(`/api/rss/themes/keywords/${editingKeywordId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({keyword: newKeyword})
        });
        
        const result = await response.json();
        if (result.success) {
            hideEditKeywordModal();
            loadThemesTree();
            Utils.showToast('关键词更新成功', 'success');
        } else {
            Utils.showToast(result.message || '更新失败', 'error');
        }
    } catch (e) {
        console.error('更新关键词失败:', e);
        Utils.showToast('更新失败: ' + e.message, 'error');
    }
}

// 删除关键词
async function deleteKeyword(keywordId, themeId) {
    if (!confirm('确定删除此关键词？')) return;
    
    try {
        const response = await fetch(`/api/rss/themes/keywords/${keywordId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        if (result.success) {
            loadThemesTree();
            Utils.showToast('关键词已删除', 'success');
        } else {
            Utils.showToast(result.message || '删除失败', 'error');
        }
    } catch (e) {
        console.error('删除关键词失败:', e);
        Utils.showToast('删除失败: ' + e.message, 'error');
    }
}

// 显示AI推荐
async function showAISuggest(themeId) {
    currentThemeId = themeId;
    selectedAIKeywords = [];
    document.getElementById('ai-suggest-modal').classList.add('active');
    await loadAISuggestions(themeId);
}

// 隐藏AI推荐弹窗
function hideAISuggestModal() {
    document.getElementById('ai-suggest-modal').classList.remove('active');
    currentThemeId = null;
}

// 加载AI推荐
async function loadAISuggestions(themeId) {
    const grid = document.getElementById('ai-keywords-grid');
    grid.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>AI正在思考中...</p></div>';
    
    try {
        const response = await fetch(`/api/rss/themes/${themeId}/suggest`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success && result.keywords) {
            aiSuggestedKeywords = result.keywords;
            renderAIKeywords();
        } else {
            grid.innerHTML = `<div style="color: var(--cyber-red);">推荐失败: ${result.message || '未知错误'}</div>`;
        }
    } catch (e) {
        grid.innerHTML = `<div style="color: var(--cyber-red);">推荐失败: ${e.message}</div>`;
    }
}

// 渲染AI推荐关键词
function renderAIKeywords() {
    const grid = document.getElementById('ai-keywords-grid');
    grid.innerHTML = aiSuggestedKeywords.map(kw => `
        <div class="ai-keyword-chip ${selectedAIKeywords.includes(kw) ? 'selected' : ''}" 
             onclick="toggleAIKeyword('${kw}')"
             role="checkbox"
             aria-checked="${selectedAIKeywords.includes(kw)}"
             tabindex="0">
            ${kw}
        </div>
    `).join('');
}

// 切换AI关键词选择
function toggleAIKeyword(keyword) {
    const index = selectedAIKeywords.indexOf(keyword);
    if (index > -1) {
        selectedAIKeywords.splice(index, 1);
    } else {
        selectedAIKeywords.push(keyword);
    }
    renderAIKeywords();
}

// 重新生成关键词
async function regenerateKeywords() {
    if (currentThemeId) {
        await loadAISuggestions(currentThemeId);
    }
}

// 导入选中的关键词
async function importSelectedKeywords() {
    if (selectedAIKeywords.length === 0) {
        Utils.showToast('请先选择关键词', 'warning');
        return;
    }
    
    if (!currentThemeId) {
        Utils.showToast('主题ID无效', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/rss/themes/${currentThemeId}/import`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({keywords: selectedAIKeywords})
        });
        
        const result = await response.json();
        if (result.success) {
            Utils.showToast(`成功导入 ${result.imported} 个关键词`, 'success');
            hideAISuggestModal();
            loadThemesTree();
        } else {
            Utils.showToast(result.message || '导入失败', 'error');
        }
    } catch (e) {
        console.error('导入关键词失败:', e);
        Utils.showToast('导入失败: ' + e.message, 'error');
    }
}

// 删除主题
async function deleteTheme(themeId) {
    if (!confirm('确定删除此主题？')) return;
    
    try {
        const response = await fetch(`/api/rss/themes/${themeId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        if (result.success) {
            loadThemesTree();
            Utils.showToast('主题已删除', 'success');
        } else {
            Utils.showToast(result.message || '删除失败', 'error');
        }
    } catch (e) {
        console.error('删除主题失败:', e);
        Utils.showToast('删除失败: ' + e.message, 'error');
    }
}

// 显示新建主题弹窗
function showCreateThemeModal() {
    document.getElementById('new-theme-name').value = '';
    document.getElementById('new-theme-desc').value = '';
    document.getElementById('manual-keywords').value = '';
    document.getElementById('selected-keywords-preview').style.display = 'none';
    newThemeSelectedKeywords = [];
    document.getElementById('create-theme-modal').classList.add('active');
}

// 隐藏新建主题弹窗
function hideCreateThemeModal() {
    document.getElementById('create-theme-modal').classList.remove('active');
}

// 为新主题显示AI推荐
async function showAISuggestForNewTheme() {
    const name = document.getElementById('new-theme-name').value.trim();
    const desc = document.getElementById('new-theme-desc').value.trim();
    
    if (!name) {
        Utils.showToast('请先输入主题名称', 'warning');
        return;
    }
    
    document.getElementById('ai-suggest-modal').classList.add('active');
    
    const grid = document.getElementById('ai-keywords-grid');
    grid.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>AI正在思考中...</p></div>';
    
    try {
        // 临时创建一个主题来获取推荐
        const tempResponse = await fetch('/api/rss/themes', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, description: desc})
        });
        
        const tempResult = await tempResponse.json();
        
        if (!tempResult.success) {
            grid.innerHTML = `<div style="color: var(--cyber-red);">创建临时主题失败: ${tempResult.message}</div>`;
            return;
        }
        
        const tempThemeId = tempResult.id;
        
        // 获取AI推荐
        const suggestResponse = await fetch(`/api/rss/themes/${tempThemeId}/suggest`, {
            method: 'POST'
        });
        
        const suggestResult = await suggestResponse.json();
        
        if (suggestResult.success && suggestResult.keywords) {
            aiSuggestedKeywords = suggestResult.keywords;
            currentThemeId = tempThemeId;
            renderAIKeywords();
        } else {
            grid.innerHTML = `<div style="color: var(--cyber-red);">推荐失败: ${suggestResult.message || '未知错误'}</div>`;
        }
        
    } catch (e) {
        grid.innerHTML = `<div style="color: var(--cyber-red);">推荐失败: ${e.message}</div>`;
    }
}

// 更新已选关键词预览
function updateSelectedKeywordsPreview() {
    const manualKeywords = document.getElementById('manual-keywords').value
        .split('\n')
        .map(k => k.trim())
        .filter(k => k);
    
    const allKeywords = [...manualKeywords, ...newThemeSelectedKeywords];
    
    const preview = document.getElementById('selected-keywords-preview');
    const list = document.getElementById('selected-keywords-list');
    
    if (allKeywords.length === 0) {
        preview.style.display = 'none';
        return;
    }
    
    preview.style.display = 'block';
    list.innerHTML = allKeywords.map(kw => `
        <span class="selected-kw-chip">
            ${kw}
            <span class="remove" onclick="removeSelectedKeyword('${kw}')" role="button" aria-label="移除关键词">×</span>
        </span>
    `).join('');
}

// 移除已选关键词
function removeSelectedKeyword(keyword) {
    const index = newThemeSelectedKeywords.indexOf(keyword);
    if (index > -1) {
        newThemeSelectedKeywords.splice(index, 1);
    }
    updateSelectedKeywordsPreview();
}

// 创建主题
async function createTheme() {
    const name = document.getElementById('new-theme-name').value.trim();
    const description = document.getElementById('new-theme-desc').value.trim();
    const manualKeywords = document.getElementById('manual-keywords').value
        .split('\n')
        .map(k => k.trim())
        .filter(k => k);
    
    if (!name) {
        Utils.showToast('请输入主题名称', 'error');
        return;
    }
    
    const allKeywords = [...manualKeywords, ...newThemeSelectedKeywords];
    
    try {
        const response = await fetch('/api/rss/themes', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name,
                description,
                keywords: allKeywords
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            Utils.showToast('主题创建成功！', 'success');
            hideCreateThemeModal();
            loadThemesTree();
        } else {
            Utils.showToast(result.message || '创建失败', 'error');
        }
    } catch (e) {
        console.error('创建主题失败:', e);
        Utils.showToast('创建失败: ' + e.message, 'error');
    }
}

// 监听手动输入变化
document.getElementById('manual-keywords').addEventListener('input', updateSelectedKeywordsPreview);

// 导出主题管理函数
window.ThemeManager = {
    loadThemesTree,
    renderThemeTree,
    toggleThemeExpand,
    toggleTheme,
    showAddKeyword,
    hideAddKeyword,
    addKeyword,
    showEditKeyword,
    hideEditKeywordModal,
    confirmEditKeyword,
    deleteKeyword,
    showAISuggest,
    hideAISuggestModal,
    loadAISuggestions,
    renderAIKeywords,
    toggleAIKeyword,
    regenerateKeywords,
    importSelectedKeywords,
    deleteTheme,
    showCreateThemeModal,
    hideCreateThemeModal,
    showAISuggestForNewTheme,
    updateSelectedKeywordsPreview,
    removeSelectedKeyword,
    createTheme
};