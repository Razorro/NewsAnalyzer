/**
 * NewsAnalyzer Dashboard - 工具函数模块
 */

// Toast提示函数 - 高级感设计
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // 3秒后自动消失
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55) forwards';
        setTimeout(() => {
            if (toast.parentNode) {
                document.body.removeChild(toast);
            }
        }, 400);
    }, 3000);
}

// 带确认的Toast
function showToastWithConfirm(message, type = 'info', onConfirm = null) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove(); ${onConfirm ? onConfirm + '()' : ''}" 
                style="margin-left: 10px; background: rgba(0,0,0,0.3); border: none; color: inherit; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 11px;">
            确认
        </button>
    `;
    document.body.appendChild(toast);
    
    // 5秒后自动消失
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55) forwards';
        setTimeout(() => {
            if (toast.parentNode) {
                document.body.removeChild(toast);
            }
        }, 400);
    }, 5000);
}

// 时间格式化
function formatTime(dateStr) {
    if (!dateStr) return '未知';
    
    try {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = (now - date) / 1000;
        
        if (diff < 60) return '刚刚';
        if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
        return `${Math.floor(diff / 86400)}天前`;
    } catch (e) {
        return dateStr;
    }
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// 深拷贝
function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj);
    if (obj instanceof Array) return obj.map(item => deepClone(item));
    if (typeof obj === 'object') {
        const clonedObj = {};
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                clonedObj[key] = deepClone(obj[key]);
            }
        }
        return clonedObj;
    }
}

// 导出工具函数
window.Utils = {
    showToast,
    showToastWithConfirm,
    formatTime,
    debounce,
    throttle,
    deepClone
};