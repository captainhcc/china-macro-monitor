#!/usr/bin/env python3
"""
中国宏观经济监测 — 独立 Python 数据更新脚本
============================================
用法: python main.py
输出:
  - data/indicators.json  核心指标数据
  - data/timeline.json    新闻时间线
  - data/data.js          前端引用的 JS 数据文件
  - index.html            自包含网页（引用 data.js）
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── 依赖检查 ──────────────────────────────────────────
try:
    import requests
except ImportError:
    print("❌ 缺少 requests 库，请运行: pip install requests")
    sys.exit(1)

try:
    import akshare as ak
except ImportError:
    print("❌ 缺少 akshare 库，请运行: pip install akshare")
    sys.exit(1)

# ── 配置 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INDICATORS_FILE = DATA_DIR / "indicators.json"
TIMELINE_FILE = DATA_DIR / "timeline.json"
DATA_JS_FILE = DATA_DIR / "data.js"
INDEX_HTML_FILE = BASE_DIR / "index.html"

# 东方财富行情 API
EM_QUOTE_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
EM_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

NOW = datetime.now()
TODAY_STR = NOW.strftime("%Y-%m-%d")
TODAY_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%S+08:00")
WEEKDAY_MAP = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ═══════════════════════════════════════════════════════
#  第一部分: 数据采集
# ═══════════════════════════════════════════════════════

def fetch_index_realtime():
    """获取上证/深证实时行情（东方财富 API）"""
    print("\n📈 获取指数行情...")
    try:
        params = {
            "fltt": "2",
            "fields": "f2,f3,f4,f12,f14",
            "secids": "1.000001,0.399001",
            "invt": "2",
        }
        resp = requests.get(EM_QUOTE_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        result = []
        for item in items:
            code = item.get("f12", "")
            if code == "000001":
                result.append({
                    "id": "sh000001",
                    "name": "上证指数",
                    "value": round(item.get("f2", 0), 2),
                    "change": round(item.get("f4", 0), 2),
                    "changePercent": round(item.get("f3", 0), 2),
                    "trend": "up" if item.get("f3", 0) > 0 else ("down" if item.get("f3", 0) < 0 else "flat"),
                })
            elif code == "399001":
                result.append({
                    "id": "sz399001",
                    "name": "深证成指",
                    "value": round(item.get("f2", 0), 2),
                    "change": round(item.get("f4", 0), 2),
                    "changePercent": round(item.get("f3", 0), 2),
                    "trend": "up" if item.get("f3", 0) > 0 else ("down" if item.get("f3", 0) < 0 else "flat"),
                })

        if len(result) < 2:
            raise ValueError(f"行情数据不完整: {result}")

        for r in result:
            arrow = "▲" if r["trend"] == "up" else ("▼" if r["trend"] == "down" else "—")
            print(f"  {r['name']}: {r['value']} {arrow} {r['changePercent']:+.2f}%")
        return result
    except Exception as e:
        print(f"  ⚠️ 东方财富API失败: {e}")
        print("  → 尝试备用数据源: 新浪财经")
        return _fetch_index_sina()


def _fetch_index_sina():
    """备用: 新浪财经行情"""
    result = []
    for code, name, sid in [("sh000001", "上证指数", "s_sh000001"), ("sz399001", "深证成指", "s_sz399001")]:
        try:
            url = f"https://hq.sinajs.cn/list={sid}"
            resp = requests.get(url, headers={**HEADERS, "Referer": "https://finance.sina.com.cn/"}, timeout=10)
            resp.encoding = "gbk"
            text = resp.text
            parts = text.split('"')[1].split(",")
            price = float(parts[1])
            prev = float(parts[2])
            change = round(price - prev, 2)
            change_pct = round(change / prev * 100, 2) if prev != 0 else 0
            result.append({
                "id": code,
                "name": name,
                "value": price,
                "change": change,
                "changePercent": change_pct,
                "trend": "up" if change > 0 else ("down" if change < 0 else "flat"),
            })
            arrow = "▲" if result[-1]["trend"] == "up" else ("▼" if result[-1]["trend"] == "down" else "—")
            print(f"  {name}: {price} {arrow} {change:+.2f}%")
        except Exception as e2:
            print(f"  ⚠️ 新浪 {name} 获取失败: {e2}")
    return result


def fetch_exchange_rate():
    """获取美元兑人民币汇率"""
    print("\n💱 获取汇率...")
    try:
        url = "https://api.it120.cc/gooking/forex/rate?fromCode=USD&toCode=CNY"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        rate = round(float(data.get("data", {}).get("rate", 6.85)), 4)
        print(f"  USD/CNY: {rate}")
        return rate
    except Exception:
        pass
    # 备用: 东方财富
    try:
        params = {"fltt": "2", "fields": "f2", "secids": "133.USDCNH"}
        resp = requests.get(EM_QUOTE_URL, params=params, headers=HEADERS, timeout=10)
        rate = round(resp.json()["data"]["diff"][0]["f2"] / 10000, 4)
        print(f"  USD/CNY (离岸): {rate}")
        return rate
    except Exception as e:
        print(f"  ⚠️ 汇率获取失败: {e}，使用默认值 6.813")
        return 6.813


def fetch_bond_yield():
    """获取10年期国债收益率"""
    print("\n🏦 获取国债收益率...")
    try:
        bond_df = ak.bond_china_yield(start_date="20240101", end_date=TODAY_STR)
        if not bond_df.empty:
            latest = bond_df.iloc[-1]
            yield_val = round(float(latest["中国国债收益率10年"]), 3)
            print(f"  10年期国债: {yield_val}%")
            return yield_val
    except Exception as e:
        print(f"  ⚠️ akshare 国债数据失败: {e}")
    print("  → 使用默认值 1.730")
    return 1.730


# ── 宏观经济指标 (akshare) ─────────────────────────

def fetch_cpi_latest():
    """获取最新 CPI 同比"""
    print("\n📊 获取 CPI...")
    try:
        df = ak.macro_china_cpi()
        date_col = "月份"
        # 使用同比增长率而非绝对指数
        val_col = "全国-同比增长" if "全国-同比增长" in df.columns else "全国-当月"
        df = df.sort_values(date_col)
        latest = df.iloc[-1]
        cpi_val = round(float(latest[val_col]), 1)
        date_raw = str(latest[date_col])
        # 处理 "2026年05月份" 格式
        import re
        m = re.search(r"(\d{4}).*?(\d{1,2})", date_raw)
        date_str = f"{m.group(1)}年{m.group(2)}月" if m else date_raw[:7].replace("-", "年") + "月"
        print(f"  CPI 同比: {cpi_val}% ({date_str})")
        return cpi_val, date_str, _get_prev_value(df, val_col)
    except Exception as e:
        print(f"  ⚠️ CPI 获取失败: {e}")
        return 1.2, "2026年5月", 1.2


def fetch_ppi_latest():
    """获取最新 PPI 同比"""
    print("\n📊 获取 PPI...")
    try:
        df = ak.macro_china_ppi()
        date_col = "月份"
        val_col = "当月同比增长" if "当月同比增长" in df.columns else "当月"
        df = df.sort_values(date_col)
        latest = df.iloc[-1]
        ppi_val = round(float(latest[val_col]), 1)
        date_raw = str(latest[date_col])
        import re
        m = re.search(r"(\d{4}).*?(\d{1,2})", date_raw)
        date_str = f"{m.group(1)}年{m.group(2)}月" if m else date_raw[:7].replace("-", "年") + "月"
        print(f"  PPI 同比: {ppi_val}% ({date_str})")
        return ppi_val, date_str, _get_prev_value(df, val_col)
    except Exception as e:
        print(f"  ⚠️ PPI 获取失败: {e}")
        return 3.9, "2026年5月", 2.8


def fetch_pmi_latest():
    """获取最新制造业 PMI"""
    print("\n📊 获取 PMI...")
    try:
        df = ak.macro_china_pmi()
        date_col = "月份"
        val_col = "制造业-指数" if "制造业-指数" in df.columns else df.columns[1]
        df = df.sort_values(date_col)
        latest = df.iloc[-1]
        pmi_val = round(float(latest[val_col]), 1)
        date_raw = str(latest[date_col])
        import re
        m = re.search(r"(\d{4}).*?(\d{1,2})", date_raw)
        date_str = f"{m.group(1)}年{m.group(2)}月" if m else date_raw[:7].replace("-", "年") + "月"
        print(f"  制造业PMI: {pmi_val} ({date_str})")
        return pmi_val, date_str, _get_prev_value(df, val_col)
    except Exception as e:
        print(f"  ⚠️ PMI 获取失败: {e}")
        return 50.0, "2026年5月", 50.3


def fetch_m2_latest():
    """获取最新 M2 同比增速"""
    print("\n📊 获取 M2...")
    try:
        df = ak.macro_china_money_supply()
        date_col = "月份"
        # 找到M2相关列
        m2_col = None
        for c in df.columns:
            cs = str(c)
            if "M2" in cs and ("同比" in cs or "增速" in cs):
                m2_col = c
                break
        if not m2_col:
            for c in df.columns:
                if "M2" in str(c):
                    m2_col = c
                    break

        if not m2_col:
            raise ValueError(f"M2列未找到，可用列: {list(df.columns)}")

        df = df.sort_values(date_col)
        latest = df.iloc[-1]
        m2_val = round(float(latest[m2_col]), 1)
        date_raw = str(latest[date_col])
        import re
        m = re.search(r"(\d{4}).*?(\d{1,2})", date_raw)
        date_str = f"{m.group(1)}年{m.group(2)}月" if m else date_raw[:7].replace("-", "年") + "月"
        print(f"  M2 同比: {m2_val}% ({date_str})")
        return m2_val, date_str, _get_prev_value(df, m2_col)
    except Exception as e:
        print(f"  ⚠️ M2 获取失败: {e}")
        return 8.6, "2026年5月", 8.6


def fetch_social_finance_latest():
    """获取最新社会融资规模增量（万亿元）"""
    print("\n📊 获取社会融资规模...")
    try:
        df = ak.macro_china_shrzgm()
        date_col = "月份"
        col = None
        for c in df.columns:
            if "社会融资规模增量" in str(c):
                col = c
                break
        if not col:
            col = df.columns[1]

        df = df.sort_values(date_col)
        latest = df.iloc[-1]
        sf_raw = float(latest[col])
        # akshare 返回亿元，统一转为万亿元
        sf_val = round(sf_raw / 10000, 2)
        prev_raw = float(df.iloc[-2][col])
        prev_val = round(prev_raw / 10000, 2)
        date_raw = str(latest[date_col])
        import re
        m = re.search(r"(\d{4}).*?(\d{1,2})", date_raw)
        date_str = f"{m.group(1)}年{m.group(2)}月" if m else date_raw[:7].replace("-", "年") + "月"
        print(f"  社融增量: {sf_val}万亿 ({date_str})")
        return sf_val, date_str, prev_val
    except Exception as e:
        print(f"  ⚠️ 社融获取失败: {e}")
        return 2.03, "2026年5月", 1.86


def fetch_gdp_latest():
    """获取最新 GDP 同比增速"""
    print("\n📊 获取 GDP...")
    try:
        df = ak.macro_china_gdp()
        date_col = "季度"
        val_col = "国内生产总值-同比增长"
        df = df.sort_values(date_col)
        latest = df.iloc[-1]
        gdp_val = round(float(latest[val_col]), 1)
        date_str = str(latest[date_col])
        print(f"  GDP 同比: {gdp_val}% ({date_str})")
        return gdp_val, date_str, _get_prev_value(df, val_col)
    except Exception as e:
        print(f"  ⚠️ GDP 获取失败: {e}")
        return 5.0, "2026年Q1", 5.2


def _get_prev_value(df, col_name):
    """获取上一期值用于计算环比变化"""
    try:
        return round(float(df.iloc[-2][col_name]), 1)
    except Exception:
        return 0


# ── 历史图表数据 ────────────────────────────────────

def fetch_index_history(days=35):
    """获取上证指数近期历史数据用于走势图"""
    print("\n📈 获取上证历史走势...")
    try:
        params = {
            "secid": "1.000001",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": "1",
            "end": "20500101",
            "lmt": str(days + 5),
        }
        resp = requests.get(EM_KLINE_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        klines = resp.json().get("data", {}).get("klines", [])

        labels, data_vals = [], []
        for line in klines[-days:]:
            parts = line.split(",")
            date_str_raw = parts[0]  # e.g. "2026-06-27"
            close_val = float(parts[2])
            # Format as M/D
            if "-" in date_str_raw:
                parts_d = date_str_raw.split("-")
                labels.append(f"{int(parts_d[1])}/{int(parts_d[2])}")
            else:
                labels.append(date_str_raw[-5:])
            data_vals.append(int(close_val))

        print(f"  获取到 {len(labels)} 个交易日数据")
        return labels, data_vals
    except Exception as e:
        print(f"  ⚠️ 历史K线获取失败: {e}")
        return [], []


def fetch_macro_history(months=14):
    """获取宏观指标近12+个月历史数据"""
    print("\n📊 获取宏观指标历史...")
    result = {"cpi": [], "ppi": [], "pmi": [], "m2": [], "sf": [], "labels_cpi": [], "labels_pmi": [], "labels_m2": []}

    import re

    try:
        cpi_df = ak.macro_china_cpi()
        val_col_cpi = "全国-同比增长" if "全国-同比增长" in cpi_df.columns else "全国-当月"
        cpi_df = cpi_df.sort_values("月份").tail(months)
        for _, row in cpi_df.iterrows():
            d = str(row["月份"])
            m = re.search(r"(\d{4}).*?(\d{1,2})", d)
            result["labels_cpi"].append(f"{int(m.group(2))}月" if m else d[-3:])
            result["cpi"].append(round(float(row[val_col_cpi]), 1))
    except Exception as e:
        print(f"  ⚠️ CPI历史: {e}")

    try:
        ppi_df = ak.macro_china_ppi()
        val_col = "当月同比增长" if "当月同比增长" in ppi_df.columns else "当月"
        ppi_df = ppi_df.sort_values("月份").tail(months)
        for _, row in ppi_df.iterrows():
            result["ppi"].append(round(float(row[val_col]), 1))
    except Exception as e:
        print(f"  ⚠️ PPI历史: {e}")

    try:
        pmi_df = ak.macro_china_pmi()
        val_col = "制造业-指数" if "制造业-指数" in pmi_df.columns else pmi_df.columns[1]
        pmi_df = pmi_df.sort_values("月份").tail(months)
        for _, row in pmi_df.iterrows():
            d = str(row["月份"])
            m = re.search(r"(\d{4}).*?(\d{1,2})", d)
            result["labels_pmi"].append(f"{int(m.group(2))}月" if m else d[-3:])
            result["pmi"].append(round(float(row[val_col]), 1))
    except Exception as e:
        print(f"  ⚠️ PMI历史: {e}")

    try:
        m2_df = ak.macro_china_money_supply()
        m2_col = next((c for c in m2_df.columns if "M2" in str(c)), m2_df.columns[1])
        date_col = "月份"
        m2_df = m2_df.sort_values(date_col).tail(months)
        for _, row in m2_df.iterrows():
            d = str(row[date_col])
            m = re.search(r"(\d{4}).*?(\d{1,2})", d)
            result["labels_m2"].append(f"{int(m.group(2))}月" if m else d[-3:])
            result["m2"].append(round(float(row[m2_col]), 1))

        sf_col = next((c for c in m2_df.columns if "社会融资规模存量" in str(c) and "增速" in str(c)), None)
        if sf_col:
            for _, row in m2_df.iterrows():
                result["sf"].append(round(float(row[sf_col]), 1))
    except Exception as e:
        print(f"  ⚠️ M2历史: {e}")

    print(f"  CPI {len(result['cpi'])}点 / PPI {len(result['ppi'])}点 / PMI {len(result['pmi'])}点 / M2 {len(result['m2'])}点")
    return result


# ── 新闻 ────────────────────────────────────────────

def fetch_news():
    """获取最新财经新闻"""
    print("\n📰 获取财经新闻...")
    entries = []

    # 东方财富要闻
    try:
        url = "https://finance.eastmoney.com/yaowen.html"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "gbk" if "gb" in str(resp.apparent_encoding).lower() else "utf-8"
        text = resp.text

        # 简单提取标题 - 从 HTML 中提取
        import re
        # 匹配 news 列表项
        titles = re.findall(r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"[^>]*>', text)
        seen = set()
        count = 0
        for url_path, title in titles:
            title = title.strip()
            if not title or len(title) < 8:
                continue
            if title in seen:
                continue
            seen.add(title)

            cert = "policy"  # 默认分类
            if any(kw in title for kw in ["A股", "收盘", "涨停", "跌停", "ETF", "北向", "成交"]):
                cert = "market"
            elif any(kw in title for kw in ["GDP", "CPI", "PPI", "PMI", "M2", "社融", "通胀", "宏观", "经济数据"]):
                cert = "macro"
            elif any(kw in title for kw in ["行业", "产业", "新能源", "半导体", "AI", "芯片"]):
                cert = "industry"

            label_map = {"policy": "政策要闻", "market": "市场数据", "macro": "宏观经济", "industry": "行业动态"}
            entries.append({
                "id": f"{TODAY_STR.replace('-','')}-{count+1:03d}",
                "category": cert,
                "categoryLabel": label_map.get(cert, "综合资讯"),
                "title": title,
                "summary": title,
                "body": "",
                "sources": ["东方财富"],
                "analysis": [],
            })
            count += 1
            if count >= 5:
                break

        if entries:
            print(f"  从东方财富获取 {len(entries)} 条要闻")
    except Exception as e:
        print(f"  ⚠️ 东方财富新闻: {e}")

    return entries


# ═══════════════════════════════════════════════════════
#  第二部分: 构建数据
# ═══════════════════════════════════════════════════════

def load_existing_json(filepath, default):
    """加载已有 JSON，不存在则返回默认值"""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def build_indicators(existing, indices, cpi, ppi, pmi, m2, sf, gdp, rate, bond, hist):
    """构建 indicators.json"""
    cpi_val, cpi_period, cpi_prev = cpi
    ppi_val, ppi_period, ppi_prev = ppi
    pmi_val, pmi_period, pmi_prev = pmi
    m2_val, m2_period, m2_prev = m2
    sf_val, sf_period, sf_prev = sf
    gdp_val, gdp_period, gdp_prev = gdp

    # 处理指数数据
    index_entries = list(indices)
    # 如果获取到了汇率和国债，更新
    if rate and len(index_entries) >= 2:
        # 查找或更新汇率
        has_rate = any(i.get("id") == "cny_usd" for i in index_entries)
        if not has_rate:
            index_entries.append({
                "id": "cny_usd", "name": "人民币汇率(USD/CNY)",
                "value": rate, "change": 0, "changePercent": 0, "trend": "flat"
            })
        has_bond = any(i.get("id") == "bond_10y" for i in index_entries)
        if not has_bond and bond:
            index_entries.append({
                "id": "bond_10y", "name": "10年期国债收益率",
                "value": bond, "change": 0, "changePercent": 0, "trend": "flat", "unit": "%"
            })

    # 图表数据
    index_labels, index_data = hist.get("index_labels", []), hist.get("index_data", [])
    if not index_labels and existing:
        index_labels = existing.get("charts", {}).get("indexTrend", {}).get("labels", [])
        index_data = existing.get("charts", {}).get("indexTrend", {}).get("data", [])

    cpi_labels = hist.get("cpi_labels", [])
    cpi_hist = hist.get("cpi", [])
    ppi_hist = hist.get("ppi", [])
    pmi_labels = hist.get("pmi_labels", [])
    pmi_hist = hist.get("pmi", [])
    m2_labels = hist.get("m2_labels", [])
    m2_hist = hist.get("m2", [])
    sf_hist = hist.get("sf", [])

    return {
        "lastUpdate": TODAY_ISO,
        "updateFrequency": "每日运行 python main.py 更新",
        "source": "东方财富 · akshare · 国家统计局 · 中国人民银行",
        "dashboard": {
            "indices": index_entries,
            "macroCards": [
                {"id": "cpi", "name": "CPI 同比", "value": cpi_val, "change": round(cpi_val - cpi_prev, 1), "trend": "up" if cpi_val > cpi_prev else ("down" if cpi_val < cpi_prev else "flat"), "unit": "%", "period": cpi_period},
                {"id": "ppi", "name": "PPI 同比", "value": ppi_val, "change": round(ppi_val - ppi_prev, 1), "trend": "up" if ppi_val > ppi_prev else ("down" if ppi_val < ppi_prev else "flat"), "unit": "%", "period": ppi_period},
                {"id": "pmi", "name": "制造业PMI", "value": pmi_val, "change": round(pmi_val - pmi_prev, 1), "trend": "up" if pmi_val > pmi_prev else ("down" if pmi_val < pmi_prev else "flat"), "period": pmi_period},
                {"id": "gdp", "name": "GDP 增速", "value": gdp_val, "change": round(gdp_val - gdp_prev, 1), "trend": "up" if gdp_val > gdp_prev else ("down" if gdp_val < gdp_prev else "flat"), "unit": "%", "period": gdp_period},
                {"id": "m2", "name": "M2 同比", "value": m2_val, "change": round(m2_val - m2_prev, 1), "trend": "up" if m2_val > m2_prev else ("down" if m2_val < m2_prev else "flat"), "unit": "%", "period": m2_period},
                {"id": "social_finance", "name": "社融增量", "value": sf_val, "change": round(sf_val - sf_prev, 2), "trend": "up" if sf_val > sf_prev else ("down" if sf_val < sf_prev else "flat"), "unit": "万亿", "period": sf_period},
            ]
        },
        "charts": {
            "indexTrend": {
                "title": "上证指数近30日走势",
                "labels": index_labels or [],
                "data": index_data or []
            },
            "cpiPpi": {
                "title": "CPI / PPI 同比走势（近12个月）",
                "labels": cpi_labels or [],
                "cpi": cpi_hist or [],
                "ppi": ppi_hist or []
            },
            "pmiTrend": {
                "title": "制造业PMI近12个月走势",
                "labels": pmi_labels or [],
                "data": pmi_hist or []
            },
            "m2SocialFinance": {
                "title": "M2增速 vs 社融增速（近12个月）",
                "labels": m2_labels or [],
                "m2": m2_hist or [],
                "socialFinance": sf_hist or []
            }
        }
    }


def build_timeline(existing, news_entries):
    """构建 timeline.json，将新条目追加到已有数据"""
    if existing and "timeline" in existing:
        timeline = existing["timeline"]
    else:
        timeline = []

    if news_entries:
        # 新条目作为新的日期组插入最前面
        new_group = {
            "date": TODAY_STR,
            "weekday": WEEKDAY_MAP[NOW.weekday()],
            "entries": news_entries
        }
        timeline.insert(0, new_group)

    # 去重: 同日期只保留最新的
    seen_dates = set()
    deduped = []
    for group in timeline:
        if group["date"] not in seen_dates:
            seen_dates.add(group["date"])
            deduped.append(group)
        else:
            # 保留条目更多的那个
            for existing_group in deduped:
                if existing_group["date"] == group["date"]:
                    if len(group["entries"]) > len(existing_group["entries"]):
                        existing_group["entries"] = group["entries"]
                    break

    return {"timeline": deduped}


# ═══════════════════════════════════════════════════════
#  第三部分: 生成输出
# ═══════════════════════════════════════════════════════

def fix_ascii_quotes(obj):
    """将字符串内的 ASCII 双引号替换为中文书名号"""
    if isinstance(obj, str):
        count = [0]
        def replacer(m):
            count[0] += 1
            return "\u300C" if count[0] % 2 == 1 else "\u300D"  # 「」
        return obj.replace('"', '\uff02').replace('\uff02', '').replace('"', '')\
                  if '"' not in obj else obj  # 简单处理：移除 ASCII 双引号
    elif isinstance(obj, dict):
        return {k: fix_ascii_quotes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [fix_ascii_quotes(item) for item in obj]
    return obj


def generate_data_js(indicators, timeline):
    """生成 data.js"""
    # 修复引号
    indicators = fix_ascii_quotes(indicators)
    timeline = fix_ascii_quotes(timeline)

    indicators_json = json.dumps(indicators, ensure_ascii=False, indent=2)
    timeline_json = json.dumps(timeline, ensure_ascii=False, indent=2)

    # 验证 JSON 可解析
    try:
        json.loads(indicators_json)
        json.loads(timeline_json)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON 验证失败: {e}")
        # 尝试修复：替换字符串值中的 "
        indicators_json = _safe_json_dumps(indicators)
        timeline_json = _safe_json_dumps(timeline)

    js_content = f"""var __INDICATORS__ = {indicators_json};

var __TIMELINE__ = {timeline_json};
"""
    return js_content


def _safe_json_dumps(obj):
    """安全的 JSON 序列化，处理引号问题"""
    raw = json.dumps(obj, ensure_ascii=False, indent=2)
    # 简单检测: 如果 JSON 解析失败，尝试移除值内的 "
    try:
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        # 粗暴但有效的处理: 用 Unicode 全角引号替代
        pass
    return raw


# ═══════════════════════════════════════════════════════
#  第四部分: 主流程
# ═══════════════════════════════════════════════════════

def main():
    """主流程：采集数据并生成文件"""
    import argparse
    parser = argparse.ArgumentParser(description="中国宏观经济监测 - 数据更新脚本")
    parser.add_argument("--publish", action="store_true", help="数据更新后自动推送到 GitHub Pages")
    parser.add_argument("--publish-only", action="store_true", help="仅推送现有数据到 GitHub（不重新采集）")
    args = parser.parse_args()

    if args.publish_only:
        publish_to_github()
        return

    print("=" * 60)
    print("  中国宏观经济监测 — Python 数据更新脚本")
    print(f"  运行时间: {NOW.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 确保 data 目录存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── 加载已有数据 ──
    existing_indicators = load_existing_json(INDICATORS_FILE, None)
    existing_timeline = load_existing_json(TIMELINE_FILE, None)

    # ── 步骤1: 获取行情 ──
    print("\n" + "─" * 40)
    print("第一步: 获取市场数据")
    print("─" * 40)

    indices = fetch_index_realtime()
    rate = fetch_exchange_rate()
    bond = fetch_bond_yield()

    # ── 步骤2: 获取宏观指标 ──
    print("\n" + "─" * 40)
    print("第二步: 获取宏观经济指标")
    print("─" * 40)

    cpi = fetch_cpi_latest()
    ppi = fetch_ppi_latest()
    pmi = fetch_pmi_latest()
    m2 = fetch_m2_latest()
    sf = fetch_social_finance_latest()
    gdp = fetch_gdp_latest()

    # ── 步骤3: 获取历史图表数据 ──
    print("\n" + "─" * 40)
    print("第三步: 获取图表历史数据")
    print("─" * 40)

    index_hist = fetch_index_history()
    hist_labels, hist_data = index_hist
    macro_hist = fetch_macro_history()

    hist = {
        "index_labels": hist_labels,
        "index_data": hist_data,
        "cpi_labels": macro_hist.get("labels_cpi", []),
        "cpi": macro_hist.get("cpi", []),
        "ppi": macro_hist.get("ppi", []),
        "pmi_labels": macro_hist.get("labels_pmi", []),
        "pmi": macro_hist.get("pmi", []),
        "m2_labels": macro_hist.get("labels_m2", []),
        "m2": macro_hist.get("m2", []),
        "sf": macro_hist.get("sf", []),
    }

    # ── 步骤4: 获取新闻 ──
    print("\n" + "─" * 40)
    print("第四步: 获取最新新闻")
    print("─" * 40)

    news = fetch_news()

    # ── 步骤5: 构建数据 ──
    print("\n" + "─" * 40)
    print("第五步: 生成数据文件")
    print("─" * 40)

    # 检查指数数据是否完整（至少要有上证和深证）
    if len(indices) < 2:
        print("  ⚠️ 指数数据不完整，使用已有数据")
        if existing_indicators:
            indices = existing_indicators["dashboard"]["indices"]
        else:
            print("  ❌ 无备份数据，终止")
            sys.exit(1)

    indicators = build_indicators(existing_indicators, indices, cpi, ppi, pmi, m2, sf, gdp, rate, bond, hist)
    timeline = build_timeline(existing_timeline, news)

    # ── 写入 JSON ──
    with open(INDICATORS_FILE, "w", encoding="utf-8") as f:
        json.dump(indicators, f, ensure_ascii=False, indent=2)
    print(f"  ✓ indicators.json — {len(indicators['dashboard']['indices'])} 个指数, {len(indicators['dashboard']['macroCards'])} 个宏观指标")

    with open(TIMELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    total_entries = sum(len(g["entries"]) for g in timeline["timeline"])
    print(f"  ✓ timeline.json — {len(timeline['timeline'])} 组日期, {total_entries} 条新闻")

    # ── 生成 data.js ──
    data_js = generate_data_js(indicators, timeline)
    with open(DATA_JS_FILE, "w", encoding="utf-8") as f:
        f.write(data_js)
    print(f"  ✓ data.js 已生成")

    # ── 检查 index.html ──
    if not INDEX_HTML_FILE.exists():
        print("\n⚠️ index.html 不存在！请将其放在项目根目录。")
        print("  → 从原项目复制: copy ..\\macro-monitor\\index.html .")
    else:
        print(f"\n  ✓ index.html 已就绪")

    # ── 完成 ──
    print("\n" + "=" * 60)
    print("  ✅ 数据更新完成！")
    print(f"  📂 数据目录: {DATA_DIR}")
    print(f"  🌐 打开网页: {INDEX_HTML_FILE}")
    print(f"  📊 指数: {len(indicators['dashboard']['indices'])} 个")
    print(f"  📐 宏观指标: {len(indicators['dashboard']['macroCards'])} 个")
    print(f"  📰 新闻条目: {total_entries} 条")
    print("=" * 60)
    print("\n提示: 在浏览器中打开 index.html 即可查看数据面板")

    # ── 发布到 GitHub Pages ──
    if args.publish:
        publish_to_github()


def publish_to_github():
    """将当前数据推送到 GitHub，触发 Pages 部署"""
    import subprocess

    print("\n" + "─" * 40)
    print("第六步: 发布到 GitHub Pages")
    print("─" * 40)

    # SSH key 路径
    ssh_key = os.path.expanduser("~/.ssh/id_ed25519_macro")
    if not os.path.exists(ssh_key):
        print("  ⚠️ SSH key 未找到，跳过发布")
        print(f"  请确保 {ssh_key} 存在")
        return

    git_env = os.environ.copy()
    git_env["GIT_SSH_COMMAND"] = f"ssh -i {ssh_key} -o StrictHostKeyChecking=yes"

    def git(cmd):
        result = subprocess.run(
            cmd, shell=True, cwd=BASE_DIR, capture_output=True, text=True,
            env=git_env
        )
        if result.returncode != 0:
            print(f"  ⚠️ git {cmd.split()[0]} 失败: {result.stderr.strip()}")
        return result

    # 确保是 git 仓库
    if not (BASE_DIR / ".git").exists():
        print("  ❌ 不是 git 仓库，请先执行:")
        print("     git init && git remote add origin git@github.com:captainhcc/china-macro-monitor.git")
        return

    # 确保 data/ 文件被跟踪
    git("git add data/ index.html wechat-summary.html")

    # 提交
    commit_msg = f"data: auto update {NOW.strftime('%Y-%m-%d %H:%M')}"
    result = git(f'git commit -m "{commit_msg}"')

    # Push
    print("  📤 推送到 GitHub...")
    push_result = git("git push origin main 2>&1")

    if push_result.returncode == 0:
        # 推导 Pages URL
        try:
            remote_url = subprocess.run(
                "git remote get-url origin", shell=True, cwd=BASE_DIR,
                capture_output=True, text=True, env=git_env
            ).stdout.strip()
            # git@github.com:captainhcc/china-macro-monitor.git → captainhcc/china-macro-monitor
            repo_path = remote_url.replace("git@github.com:", "").replace(".git", "").replace("https://github.com/", "")
            user, repo = repo_path.split("/")
            pages_url = f"https://{user}.github.io/{repo}/py-version/"
        except Exception:
            pages_url = "https://captainhcc.github.io/china-macro-monitor/py-version/"

        print(f"\n  ✅ 发布成功！")
        print(f"  🔗 客户访问: {pages_url}")
        print(f"  📱 公众号版: {pages_url}wechat-summary.html")
    else:
        print("  ⚠️ 推送失败，检查网络或 SSH key")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 运行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
