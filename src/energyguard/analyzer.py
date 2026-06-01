"""
核心分析引擎 - 异常检测、统计洞察
全部使用纯统计方法 + 清晰规则，零依赖外部AI即可产生专业洞察
小白也能看懂的中文输出
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from .config import ANOMALY_ZSCORE_THRESHOLD, ANOMALY_IQR_MULTIPLIER


def compute_basic_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """计算基础统计量"""
    if df.empty:
        return {}
    kwh = df["kwh"]
    cost = df["cost_yuan"]
    stats = {
        "total_months": len(df),
        "total_kwh": float(kwh.sum()),
        "total_cost": float(cost.sum()),
        "avg_monthly_kwh": float(kwh.mean()),
        "avg_monthly_cost": float(cost.mean()),
        "median_kwh": float(kwh.median()),
        "max_kwh": float(kwh.max()),
        "min_kwh": float(kwh.min()),
        "std_kwh": float(kwh.std(ddof=0)),
        "max_cost_month": df.loc[kwh.idxmax(), "month"] if len(df) > 0 else "",
        "min_cost_month": df.loc[kwh.idxmin(), "month"] if len(df) > 0 else "",
    }
    # 季节性简单判断（中国北方常见）
    if len(df) >= 6:
        summer = df[df["month"].str[5:7].isin(["06", "07", "08"])]["kwh"]
        winter = df[df["month"].str[5:7].isin(["12", "01", "02"])]["kwh"]
        if len(summer) > 0 and len(winter) > 0:
            stats["summer_avg"] = float(summer.mean())
            stats["winter_avg"] = float(winter.mean())
            stats["season_diff"] = float(summer.mean() - winter.mean())
    return stats


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    多方法异常检测（Z-score + IQR + 同比）
    返回带 'is_anomaly', 'anomaly_reason' 列的 DataFrame
    """
    if len(df) < 3:
        df = df.copy()
        df["is_anomaly"] = False
        df["anomaly_score"] = 0.0
        df["anomaly_reason"] = ""
        return df

    result = df.copy()
    kwh = result["kwh"].values.astype(float)

    # 1. Z-score 方法
    mean = np.mean(kwh)
    std = np.std(kwh, ddof=0)
    z_scores = np.zeros_like(kwh) if std < 1e-6 else (kwh - mean) / std

    # 2. IQR 方法
    q1, q3 = np.percentile(kwh, [25, 75])
    iqr = q3 - q1
    lower = q1 - ANOMALY_IQR_MULTIPLIER * iqr
    upper = q3 + ANOMALY_IQR_MULTIPLIER * iqr

    is_anomaly = (np.abs(z_scores) > ANOMALY_ZSCORE_THRESHOLD) | (kwh < lower) | (kwh > upper)

    # 3. 简单同比（如果有上一年同月）
    yoy_flags = []
    reasons = []
    for idx, row in result.iterrows():
        m = str(row["month"])
        reason_parts = []
        if np.abs(z_scores[idx]) > ANOMALY_ZSCORE_THRESHOLD:
            direction = "显著偏高" if z_scores[idx] > 0 else "显著偏低"
            reason_parts.append(f"Z-score异常({direction} {z_scores[idx]:.1f}σ)")

        if row["kwh"] > upper:
            reason_parts.append(f"超过IQR上限({upper:.0f})")
        elif row["kwh"] < lower:
            reason_parts.append(f"低于IQR下限({lower:.0f})")

        # 同比尝试
        prev_year = None
        if len(m) >= 7:
            try:
                y = int(m[:4]) - 1
                prev_month = f"{y}-{m[5:7]}"
                prev = result[result["month"] == prev_month]
                if not prev.empty:
                    prev_kwh = float(prev.iloc[0]["kwh"])
                    change = (row["kwh"] - prev_kwh) / max(prev_kwh, 1) * 100
                    if abs(change) > 45:  # 同比变化>45% 也标记
                        is_anomaly[idx] = True
                        reason_parts.append(f"同比变化{change:+.0f}%")
            except Exception:
                pass

        yoy_flags.append(is_anomaly[idx])
        reasons.append("；".join(reason_parts) if reason_parts else "")

    result["is_anomaly"] = is_anomaly
    result["anomaly_score"] = np.round(np.abs(z_scores), 2)
    result["anomaly_reason"] = reasons
    return result


def generate_insights(df: pd.DataFrame, anomalies: pd.DataFrame) -> List[str]:
    """生成人类可读的洞察列表（中文）"""
    insights = []
    stats = compute_basic_stats(df)
    if not stats:
        return ["数据不足，无法生成洞察。"]

    avg = stats["avg_monthly_kwh"]
    total_cost = stats["total_cost"]

    insights.append(f"📊 共分析 {stats['total_months']} 个月数据，累计用电 {stats['total_kwh']:.0f} kWh，电费约 {total_cost:.0f} 元。")
    insights.append(f"📈 月均用电 {avg:.0f} kWh（约 {stats['avg_monthly_cost']:.0f} 元），中位数 {stats['median_kwh']:.0f} kWh。")

    if "summer_avg" in stats and "winter_avg" in stats:
        diff = stats["season_diff"]
        if abs(diff) > 80:
            season = "夏季" if diff > 0 else "冬季"
            insights.append(f"🌡️ 季节性明显：{season}平均比另一季节高 {abs(diff):.0f} kWh，建议针对性优化空调/取暖。")

    anomaly_count = int(anomalies["is_anomaly"].sum()) if "is_anomaly" in anomalies.columns else 0
    if anomaly_count > 0:
        insights.append(f"⚠️ 发现 {anomaly_count} 个异常月份（Z-score > {ANOMALY_ZSCORE_THRESHOLD} 或 IQR 异常），请重点查看红色标记记录。")
        # 列出异常月份
        anom_months = anomalies[anomalies["is_anomaly"]]["month"].tolist()
        insights.append(f"   异常月份: {', '.join(anom_months[:4])}{'...' if len(anom_months)>4 else ''}")
    else:
        insights.append("✅ 用电模式稳定，无明显统计异常。")

    # 趋势
    if len(df) >= 4:
        recent = df.tail(3)["kwh"].mean()
        older = df.head(3)["kwh"].mean()
        trend = (recent - older) / max(older, 1) * 100
        if abs(trend) > 15:
            direction = "上升" if trend > 0 else "下降"
            insights.append(f"📉 近期趋势：最近3个月平均较最早3个月 {direction} {abs(trend):.0f}%，请持续观察。")

    return insights
