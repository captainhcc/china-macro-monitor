# 中国宏观经济监测 — Python 本地版

独立 Python 脚本，自动采集中国宏观经济数据并生成可视化网页。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行数据更新
python main.py

# 3. 在浏览器中打开 index.html
```

## 项目结构

```
macro-monitor-py/
├── main.py              # 主脚本（数据采集 + 构建 + 输出）
├── requirements.txt     # Python 依赖
├── index.html           # 前端可视化页面
├── data/                # 自动生成
│   ├── indicators.json  # 核心指标数据
│   ├── timeline.json    # 新闻时间线
│   └── data.js          # 前端数据文件
└── README.md
```

## 数据来源

| 数据 | 来源 | 方式 |
|------|------|------|
| 上证/深证实时行情 | 东方财富 API | HTTP 请求 |
| CPI / PPI | 国家统计局 → akshare | Python 库 |
| PMI | 国家统计局 → akshare | Python 库 |
| M2 / 社融 | 中国人民银行 → akshare | Python 库 |
| GDP | 国家统计局 → akshare | Python 库 |
| 汇率 / 国债 | 东方财富 / akshare | HTTP 请求 + Python 库 |
| 财经新闻 | 东方财富要闻 | 网页解析 |

## 定时执行（可选）

Windows 任务计划程序:
```
程序: python
参数: C:\...\macro-monitor-py\main.py
触发器: 每天 8:00
```

Linux/macOS crontab:
```
0 8 * * * cd /path/to/macro-monitor-py && python main.py
```

## 与原版差异

| 特性 | 原版 (WorkBuddy) | Python 版 |
|------|-------------------|-----------|
| 数据源 | 同花顺 iFinD MCP | 东方财富 + akshare |
| 新闻质量 | AI 生成详细分析 | 标题级摘要 |
| 运行方式 | WorkBuddy 自动化 | `python main.py` |
| 依赖 | WorkBuddy 平台 | Python 3.8+ |
| 图表历史 | 逐日累积 | 每次拉取近30日/12月 |
| 手动干预 | 需要 WorkBuddy | 可直接编辑 JSON |
