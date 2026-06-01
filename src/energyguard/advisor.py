"""
个性化节能建议生成器
核心：强大的规则引擎（始终可用） + 可选 OpenAI/Grok 润色（体验升级）
所有建议均为中文，实用可操作，针对中国家庭常见场景
"""

import os
import json
from typing import Dict, List, Any, Optional
import pandas as pd
from .analyzer import compute_basic_stats, detect_anomalies
from .predictor import simple_forecast
from .config import ENABLE_AI, AI_PROVIDER, OPENAI_API_KEY, GROK_API_KEY


def generate_rule_based_advice(df: pd.DataFrame, stats: Dict, anomalies: pd.DataFrame) -> List[str]:
    """始终可用的本地规则建议引擎（无需网络）"""
    advice = []
    avg_kwh = stats.get("avg_monthly_kwh", 300)
    total_months = stats.get("total_months", 6)

    # 基础通用建议
    advice.append("💡 基础节能（人人可做）：")
    advice.append("   • 空调夏季设定26-28℃，每升高1℃可省电6-10%")
    advice.append("   • 冰箱远离热源、留散热空间，后背每半年清理一次灰尘")
    advice.append("   • 所有电器不用时拔掉插头或用智能插座（待机功耗可达总电量5-10%）")

    # 基于数据的个性化
    if avg_kwh > 450:
        advice.append("🔥 您的月均用电偏高（>450kWh），建议优先检查：")
        advice.append("   • 老旧空调/电热水器是否能效低（建议换一级能效）")
        advice.append("   • 是否存在常亮灯具或长期待机设备")
    elif avg_kwh < 220:
        advice.append("🌱 恭喜！您的用电习惯非常节能，继续保持即可。")

    # 季节针对
    if "summer_avg" in stats and stats["summer_avg"] > stats.get("avg_monthly_kwh", 0) * 1.4:
        advice.append("❄️ 夏季高耗电优化：")
        advice.append("   • 购买/使用变频空调 + 搭配电扇，体感相同但省电30%+")
        advice.append("   • 窗帘白天拉上可降低室内5-8℃，减少空调负荷")

    if "winter_avg" in stats and stats.get("winter_avg", 0) > 380:
        advice.append("🔥 冬季取暖建议：")
        advice.append("   • 电暖器改为碳晶/石墨烯或热泵空调，长期更划算")
        advice.append("   • 晚上使用电热毯（200-500W）替代空调，省电70%+")

    # 异常针对性
    anomaly_months = anomalies[anomalies["is_anomaly"]]["month"].tolist() if "is_anomaly" in anomalies.columns else []
    if anomaly_months:
        advice.append(f"⚠️ 针对您数据中的异常月份（{', '.join(anomaly_months[:3])}）：")
        advice.append("   • 立即检查对应月份新增电器或故障设备（冰箱、热水器、空调滤网）")
        advice.append("   • 建议安装分项电表或智能插座监控大功率设备")

    # 长期趋势
    if total_months >= 6:
        recent_trend = "上升" if df.tail(3)["kwh"].mean() > df.head(3)["kwh"].mean() else "下降"
        if recent_trend == "上升":
            advice.append("📈 近期用电呈上升趋势，建议本月开始记录每日读数，定位具体增长来源。")

    # 预测结合
    try:
        fc = simple_forecast(df)
        if fc["predicted_kwh"] > avg_kwh * 1.15:
            advice.append(f"🔮 下月预测 {fc['predicted_kwh']} kWh，高于历史均值，建议提前采取节电措施。")
    except Exception:
        pass

    return advice


def enhance_with_llm(stats: Dict, anomalies: pd.DataFrame, forecast: Dict, 
                     user_note: str = "") -> Optional[str]:
    """
    使用 OpenAI 或 Grok API 生成更自然、个性化建议
    失败时静默返回 None（调用方自动降级到规则建议）
    """
    if not ENABLE_AI:
        return None

    api_key = OPENAI_API_KEY or GROK_API_KEY
    if not api_key:
        return None

    provider = "openai"
    base_url = "https://api.openai.com/v1"
    model = "gpt-4o-mini"

    if GROK_API_KEY and (AI_PROVIDER == "grok" or not OPENAI_API_KEY):
        provider = "grok"
        base_url = "https://api.x.ai/v1"
        model = "grok-2-1212"  # 或 grok-beta

    # 构建精简提示（控制 token）
    anomaly_summary = ""
    if len(anomalies) > 0:
        anom = anomalies[anomalies.get("is_anomaly", False)]
        if not anom.empty:
            anomaly_summary = "；".join([f"{r['month']}({r.get('anomaly_reason','')})" for _, r in anom.head(2).iterrows()])

    prompt = f"""你是一位资深家庭能源顾问。请用中文、亲切实用语气，给出3-5条个性化节能建议。

家庭用电数据摘要：
- 分析月份数: {stats.get('total_months', 6)}
- 月均用电: {stats.get('avg_monthly_kwh', 300):.0f} kWh
- 累计电费: {stats.get('total_cost', 2000):.0f} 元
- 最高月份: {stats.get('max_cost_month', '')} ({stats.get('max_kwh', 0):.0f}kWh)
- 异常记录: {anomaly_summary or '无'}
- 下月预测: {forecast.get('predicted_kwh', 350):.0f} kWh (置信度{forecast.get('confidence', '中')})

用户补充: {user_note or '无'}

要求：
1. 每条建议必须具体、可立即执行（带数字或明确设备）
2. 优先指出高影响低成本措施
3. 语气鼓励而非指责
4. 总字数控制在280字以内
只输出建议正文，不要前言后语。"""

    try:
        import openai
        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=450
        )
        content = resp.choices[0].message.content.strip()
        return content
    except Exception as e:
        # 静默降级，绝不让用户看到 traceback
        print(f"[Advisor] LLM 调用失败，已自动降级到规则模式: {str(e)[:80]}")
        return None


def get_comprehensive_advice(df: pd.DataFrame, user_note: str = "") -> Dict[str, Any]:
    """主入口：返回完整建议包（规则 + 可选LLM增强）"""
    stats = compute_basic_stats(df)
    anomalies = detect_anomalies(df)
    forecast = simple_forecast(df)

    rule_advice = generate_rule_based_advice(df, stats, anomalies)
    llm_text = enhance_with_llm(stats, anomalies, forecast, user_note)

    return {
        "stats": stats,
        "anomalies_count": int(anomalies["is_anomaly"].sum()) if "is_anomaly" in anomalies.columns else 0,
        "forecast": forecast,
        "rule_based": rule_advice,
        "llm_enhanced": llm_text,
        "used_ai": llm_text is not None,
        "tips": [
            "提示：配置 OPENAI_API_KEY 或 GROK_API_KEY 环境变量可获得AI润色的自然语言建议",
            "提示：数据越多（建议>8个月），分析和预测越准确"
        ]
    }
