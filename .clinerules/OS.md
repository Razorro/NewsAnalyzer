# .clinerules - Cline VS Code插件规则配置

## 运行环境

**操作系统**: Windows 11
**Shell**: PowerShell (C:\Program Files\PowerShell\7\pwsh.exe)
**IDE**: Visual Studio Code
**Python**: Python 3.x

## 命令执行规则

### Windows PowerShell 语法
- ❌ 不支持 `&&` 语法连接命令
- ✅ 使用 `;` 分隔多个命令
- ✅ 或者分开执行多个命令

### 示例
```powershell
# ❌ 错误写法
cd c:/Projects/OilAnalyzer && python script.py

# ✅ 正确写法
python script.py

# ✅ 或者分开执行
cd c:/Projects/OilAnalyzer
python script.py
```

## 项目信息

**项目名称**: OilAnalyzer
**工作目录**: c:/Projects/OilAnalyzer
**主要功能**: 
- 地缘政治新闻分析
- 金融市场走势分析
- 多主题Pipeline模板化

## 技术栈

- **AI模型**: Ollama (glm-4.6:cloud, gpt-oss:20b-cloud)
- **数据源**: RSS, NewsAPI, Yahoo Finance
- **输出格式**: HTML报告, JSON数据

## 注意事项

1. 所有路径使用正斜杠 `/` 或双反斜杠 `\\`
2. Python脚本直接使用 `python` 命令
3. 不需要 `cd` 到项目目录，因为当前工作目录已经是 `c:/Projects/OilAnalyzer`