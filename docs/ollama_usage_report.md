# Ollama模型使用情况报告

## 1. 模型配置概况

项目中配置了三种不同用途的Ollama模型：

| 模型类型 | 配置名称 | 当前模型 | 用途 | 是否启用搜索 |
|---------|---------|---------|------|-------------|
| 分析模型 | `analysis_model` | `glm-4.6:cloud` | 深度分析、危机评估 | ✅ 是 |
| 翻译模型 | `translation_model` | `gpt-oss:20b-cloud` | 快速翻译、文本处理 | ❌ 否 |
| 总结模型 | `summary_model` | `glm-4.6:cloud` | 趋势总结、综合评估 | ❌ 否 |

**配置位置**：`config/config.json` 第105-132行

```json
"ollama_settings": {
    "analysis_model": {
        "name": "glm-4.6:cloud",
        "temperature": 0.3,
        "purpose": "深度分析、危机评估",
        "enable_search": true
    },
    "translation_model": {
        "name": "gpt-oss:20b-cloud",
        "temperature": 0.3,
        "purpose": "快速翻译、文本处理",
        "enable_search": false
    },
    "summary_model": {
        "name": "glm-4.6:cloud",
        "temperature": 0.3,
        "purpose": "趋势总结、综合评估",
        "enable_search": false
    },
    "web_search": {
        "enabled": true,
        "max_results": 5
    }
}
```

## 2. 核心处理流程

### 2.1 新闻分析完整流程（已启用Tool Calling）

```
┌─────────────────────────────────────────────────────────────────┐
│                    新闻分析请求触发                                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              analyze_with_ai() 方法                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  1. 获取新闻文章完整内容                                    │   │
│  │  2. 构建分析提示词（包含所有新闻）                          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         _chat_with_tools(model, messages, use_search=True)      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  第一次调用 ollama.chat()                                 │   │
│  │  - messages: 用户问题 + 新闻内容                          │   │
│  │  - tools: [web_search工具定义]                           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  模型判断是否需要搜索  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
    ┌─────────────────┐               ┌─────────────────┐
    │  不需要搜索      │               │  需要搜索        │
    │  直接返回分析    │               │  返回tool_calls  │
    └────────┬────────┘               └────────┬────────┘
             │                                 │
             │                                 ▼
             │                    ┌─────────────────────────┐
             │                    │  执行 web_search()      │
             │                    │  - query: 搜索关键词     │
             │                    │  - 返回真实搜索结果      │
             │                    └──────────┬──────────────┘
             │                               │
             │                               ▼
             │                    ┌─────────────────────────┐
             │                    │  将搜索结果加入messages  │
             │                    │  role: "tool"           │
             │                    └──────────┬──────────────┘
             │                               │
             │                               ▼
             │                    ┌─────────────────────────┐
             │                    │  第二次调用 ollama.chat()│
             │                    │  消息列表包含：          │
             │                    │  - 用户原始问题          │
             │                    │  - 新闻内容              │
             │                    │  - 模型tool_calls请求    │
             │                    │  - 搜索结果（tool角色）  │
             │                    └──────────┬──────────────┘
             │                               │
             └───────────────┬───────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │   模型整合所有信息生成最终分析  │
              │  - 新闻原文内容               │
              │  - Web搜索最新信息            │
              │  - 综合分析报告               │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │     返回完整的分析结果         │
              │  - 危机评分                   │
              │  - 趋势判断                   │
              │  - 关键洞察                   │
              │  - 执行摘要                   │
              └─────────────────────────────┘
```

### 2.2 Tool Calling 关键代码

**调用位置**：`scripts/ollama_analyzer.py` 第358-375行

```python
# 使用带工具调用的聊天方法
ai_response = self._chat_with_tools(
    model=self.model,
    messages=[
        {
            'role': 'user',
            'content': prompt
        }
    ],
    use_search=True  # 启用搜索工具
)
```

**工具调用处理**：`scripts/ollama_analyzer.py` 第271-332行

```python
def _chat_with_tools(self, model: str, messages: List[Dict], use_search: bool = False) -> str:
    kwargs = {
        "model": model,
        "messages": messages,
        "options": {"temperature": 0.3}
    }
    
    # 仅对分析模型启用搜索工具
    if use_search and self.search_enabled and self.searcher and model == self.analysis_model:
        kwargs["tools"] = [self.searcher.get_tool_definition()]
    
    response = ollama.chat(**kwargs)
    
    # 处理工具调用
    if response.get('message', {}).get('tool_calls'):
        messages.append(response['message'])
        
        for tool_call in response['message']['tool_calls']:
            if tool_call['function']['name'] == 'web_search':
                search_results = self.searcher.search(...)
                messages.append({"role": "tool", "content": search_results})
        
        # 再次调用模型获取最终回答
        final_response = ollama.chat(model=model, messages=messages)
        return final_response['message']['content']
    
    return response['message']['content']
```

## 3. 所有Ollama调用点

### 3.1 分析模型 (`analysis_model` = `glm-4.6:cloud`)

| 调用位置 | 方法 | 功能 | 是否启用搜索 |
|---------|------|------|-------------|
| `ollama_analyzer.py:358` | `analyze_with_ai()` | 新闻深度分析 | ✅ **是** |
| `ollama_analyzer.py:486` | `_generate_news_summaries()` | 批量生成摘要 | ❌ 否 |
| `ollama_analyzer.py:973` | `analyze_event_impact()` | 事件影响力分析 | ❌ 否 |
| `ollama_analyzer.py:1078` | `batch_analyze_events()` | 批量事件分析 | ❌ 否 |
| `rss_manager.py:752` | `_call_ollama_analysis()` | RSS新闻分析 | ❌ 否 |
| `rss_manager.py:882` | `_update_overall_sentiment()` | 更新整体情绪 | ❌ 否 |

### 3.2 翻译模型 (`translation_model` = `gpt-oss:20b-cloud`)

| 调用位置 | 方法 | 功能 | 是否启用搜索 |
|---------|------|------|-------------|
| `ollama_analyzer.py:389` | `_translate_titles()` | 翻译新闻标题 | ❌ 否 |
| `rss_manager.py:789` | `_call_ollama_analysis()` | RSS新闻分析（使用翻译模型） | ❌ 否 |

### 3.3 总结模型 (`summary_model` = `glm-4.6:cloud`)

| 调用位置 | 方法 | 功能 | 是否启用搜索 |
|---------|------|------|-------------|
| `ollama_analyzer.py:334` | `_generate_trend_summary()` | 生成趋势总评 | ❌ 否 |

## 4. 核心模块说明

### 4.1 `scripts/ollama_analyzer.py` - 核心分析模块

**主要方法**：
- `analyze_with_ai()`: 全权分析新闻（**已启用tool calling**）
- `_chat_with_tools()`: 带工具调用的聊天
- `_translate_titles()`: 翻译新闻标题
- `_generate_trend_summary()`: 生成趋势总评
- `_generate_news_summaries()`: 批量生成摘要
- `batch_analyze_events()`: 批量分析事件影响力

**新增功能**：
- `check_model_health()`: 检查模型健康状态
- `validate_models()`: 验证所有配置的模型是否可用

### 4.2 `scripts/web_searcher.py` - 网页搜索工具

**主要方法**：
- `search()`: 执行DuckDuckGo搜索
- `search_and_format_for_prompt()`: 搜索并格式化结果
- `get_tool_definition()`: 获取Ollama工具定义

### 4.3 `scripts/rss_manager.py` - RSS管理器

**Ollama相关方法**：
- `_call_ollama_analysis()`: 调用Ollama分析单条新闻
- `_update_overall_sentiment()`: 使用Ollama更新整体情绪

## 5. 配置说明

### 5.1 启用/禁用搜索

在 `config/config.json` 中：

```json
"web_search": {
    "enabled": true,  // 设置为false禁用搜索
    "max_results": 5  // 最大搜索结果数
}
```

### 5.2 为特定模型启用搜索

```json
"analysis_model": {
    "name": "glm-4.6:cloud",
    "enable_search": true  // 为该模型启用搜索
}
```

### 5.3 更换模型

修改 `config/config.json` 中的模型名称：

```json
"analysis_model": {
    "name": "your-model-name",  // 更换为其他模型
    "temperature": 0.3,
    "purpose": "深度分析、危机评估",
    "enable_search": true
}
```

## 6. Pipeline调整建议

### 6.1 如果需要禁用Tool Calling

在 `scripts/ollama_analyzer.py` 第358-375行，将：

```python
ai_response = self._chat_with_tools(
    model=self.model,
    messages=[{'role': 'user', 'content': prompt}],
    use_search=True  # 改为 False 可禁用搜索
)
```

### 6.2 如果需要调整搜索结果数量

在 `config/config.json` 中：

```json
"web_search": {
    "enabled": true,
    "max_results": 3  // 减少到3条，或增加到10条
}
```

### 6.3 如果需要为其他模型启用搜索

在 `config/config.json` 中：

```json
"summary_model": {
    "name": "glm-4.6:cloud",
    "enable_search": true  // 为总结模型也启用搜索
}
```

## 7. 依赖说明

新增依赖：
```
duckduckgo-search>=6.0.0
```

安装命令：
```bash
pip install duckduckgo-search
```

---

**报告更新时间**：2026年4月3日 18:42
**最新修改内容**：
1. ✅ `analyze_with_ai()` 已启用 tool calling
2. ✅ 添加完整的处理流程图
3. ✅ 记录所有Ollama调用点
4. ✅ 添加Pipeline调整建议