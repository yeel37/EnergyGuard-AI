"""
用电量预测模块 - 简单但实用的统计预测
使用线性趋势 + 季节性朴素调整 + 最近均值集成
零机器学习依赖，适合小白理解和长期维护
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from .config import PREDICT_MONTHS_HISTORY


def simple_forecast(df: pd.DataFrame, months_ahead: int = 1) -> Dict[str, any]:
    """
    预测未来 N 个月用电量
    返回: {
      'next_month': '2025-07',
      'predicted_kwh': 412.3,
      'predicted_cost': 298.5,
      'confidence': '中',
      'method': '线性趋势+移动平均',
      'lower_bound': 360,
      'upper_bound': 470
    }
    """
    if len(df) < 3:
        # 数据太少，使用最后一条
        last = df.iloc[-1]
        return {
            "next_month": _next_month_str(last["month"]),
            "predicted_kwh": float(last["kwh"]),
            "predicted_cost": float(last["cost_yuan"]),
            "confidence": "低（数据不足）",
            "method": "最近值外推",
            "lower_bound": float(last["kwh"] * 0.7),
            "upper_bound": float(last["kwh"] * 1.3),
        }

    kwh = df["kwh"].values.astype(float)
    n = len(kwh)

    # 1. 线性趋势 (numpy polyfit 1阶)
    x = np.arange(n)
    try:
        slope, intercept = np.polyfit(x, kwh, 1)
    except Exception:
        slope, intercept = 0.0, np.mean(kwh)

    # 2. 最近移动平均 (平滑)
    window = min(PREDICT_MONTHS_HISTORY, n)
    ma = np.mean(kwh[-window:])

    # 3. 季节性朴素（如果有12+个月数据）
    seasonal_factor = 1.0
    if n >= 12:
        # 取同月历史平均 vs 总体平均
        last_month = str(df.iloc[-1]["month"])
        if len(last_month) >= 7:
            target_mm = last_month[5:7]
            same_months = df[df["month"].str.endswith(f"-{target_mm}")]["kwh"]
            if len(same_months) >= 1:
                seasonal_factor = float(same_months.mean() / max(ma, 1))

    # 集成预测
    trend_pred = intercept + slope * n
    base_pred = 0.55 * trend_pred + 0.45 * ma
    predicted = base_pred * seasonal_factor

    # 合理性夹紧
    hist_min, hist_max = np.min(kwh), np.max(kwh)
    predicted = max(hist_min * 0.6, min(predicted, hist_max * 1.6))

    # 简单置信区间（历史波动）
    std = np.std(kwh[-window:]) if window >= 3 else np.std(kwh)
    lower = max(50, predicted - 1.2 * std)
    upper = predicted + 1.2 * std

    next_month = _next_month_str(df.iloc[-1]["month"])

    # 成本估算（简单模型）
    avg_rate = (df["cost_yuan"] / df["kwh"]).mean()
    pred_cost = predicted * avg_rate

    # 置信度标签
    if len(df) >= 8 and abs(slope) < std * 0.15:
        conf = "高"
    elif len(df) >= 5:
        conf = "中"
    else:
        conf = "低"

    return {
        "next_month": next_month,
        "predicted_kwh": round(float(predicted), 1),
        "predicted_cost": round(float(pred_cost), 2),
        "confidence": conf,
        "method": "线性趋势 + 移动平均 + 季节调整",
        "lower_bound": round(float(lower), 1),
        "upper_bound": round(float(upper), 1),
        "trend_slope_per_month": round(float(slope), 2),
    }


def _next_month_str(current: str) -> str:
    """计算下一个月份字符串 YYYY-MM"""
    try:
        y, m = map(int, current.split("-")[:2])
        m += 1
        if m > 12:
            m = 1
            y += 1
        return f"{y}-{m:02d}"
    except Exception:
        return "2025-07"


def batch_forecast(df: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
    """生成未来 horizon 个月的预测表（用于 Streamlit 图表）"""
    forecasts = []
    current_df = df.copy()
    for i in range(horizon):
        fc = simple_forecast(current_df, 1)
        forecasts.append({
            "month": fc["next_month"],
            "kwh": fc["predicted_kwh"],
            "cost_yuan": fc["predicted_cost"],
            "type": "预测",
            "confidence": fc["confidence"]
        })
        # 追加用于下次迭代（简单）
        current_df = pd.concat([
            current_df,
            pd.DataFrame([{"month": fc["next_month"], "kwh": fc["predicted_kwh"], 
                           "cost_yuan": fc["predicted_cost"], "avg_temp_c": 25, "notes": "预测"}])
        ], ignore_index=True)
    return pd.DataFrame(forecasts)
