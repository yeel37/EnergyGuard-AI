"""
EnergyGuard-AI Streamlit 图形界面
完全可交互、零基础友好
启动方式: streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# 路径处理 - 支持从项目根目录或 app/ 目录启动
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT / "src"))

from energyguard.data_loader import load_data, load_sample_data, append_manual_record, validate_data
from energyguard.analyzer import compute_basic_stats, detect_anomalies, generate_insights
from energyguard.predictor import simple_forecast, batch_forecast
from energyguard.advisor import get_comprehensive_advice
from energyguard.config import SAMPLE_DATA_PATH, STREAMLIT_PAGE_TITLE, STREAMLIT_PAGE_ICON, ENABLE_AI

# 页面配置
st.set_page_config(
    page_title=STREAMLIT_PAGE_TITLE,
    page_icon=STREAMLIT_PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS（简洁专业）
st.markdown("""
<style>
    .main .block-container { padding-top: 1.5rem; }
    .stMetric { background-color: #f8f9fa; padding: 0.8rem; border-radius: 8px; }
    .anomaly { color: #d32f2f; font-weight: 600; }
    .good { color: #2e7d32; }
    .tip-box { background: #e3f2fd; padding: 1rem; border-radius: 8px; border-left: 5px solid #1976d2; }
</style>
""", unsafe_allow_html=True)

def init_session():
    if "df" not in st.session_state:
        st.session_state.df = load_sample_data()
    if "last_advice" not in st.session_state:
        st.session_state.last_advice = None

def sidebar_controls():
    st.sidebar.header("⚙️ 数据控制")
    st.sidebar.markdown("**当前数据源**")
    source = st.sidebar.radio(
        "选择数据",
        ["内置样例数据 (推荐首次使用)", "上传我的CSV", "手动添加记录"],
        index=0
    )

    if source == "内置样例数据 (推荐首次使用)":
        if st.sidebar.button("🔄 重新加载样例", use_container_width=True):
            st.session_state.df = load_sample_data()
            st.session_state.last_advice = None
            st.rerun()

    elif source == "上传我的CSV":
        uploaded = st.sidebar.file_uploader(
            "上传CSV文件（支持UTF-8/GBK）",
            type=["csv"],
            help="列名建议：month,kwh,cost_yuan,avg_temp_c,notes"
        )
        if uploaded:
            try:
                tmp_df = pd.read_csv(uploaded)
                st.session_state.df = load_data(tmp_df)
                st.sidebar.success(f"✅ 成功导入 {len(st.session_state.df)} 条记录")
                st.session_state.last_advice = None
            except Exception as e:
                st.sidebar.error(f"导入失败: {e}")

    else:  # 手动
        with st.sidebar.form("manual_form"):
            st.write("添加单月记录")
            col1, col2 = st.columns(2)
            with col1:
                month = st.text_input("月份 (YYYY-MM)", value="2025-07")
                kwh = st.number_input("用电量 (kWh)", min_value=50.0, value=320.0, step=10.0)
            with col2:
                cost = st.number_input("电费 (元)", min_value=0.0, value=220.0, step=5.0)
                temp = st.number_input("平均气温 (℃)", value=26.0)
            notes = st.text_input("备注", value="手动添加")
            submitted = st.form_submit_button("➕ 添加到数据", use_container_width=True)
            if submitted:
                record = {"month": month, "kwh": kwh, "cost_yuan": cost, "avg_temp_c": temp, "notes": notes}
                st.session_state.df = append_manual_record(st.session_state.df, record)
                st.sidebar.success("已添加！数据已更新")
                st.session_state.last_advice = None
                st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("💡 提示：修改数据后，点击下方按钮刷新分析")
    if st.sidebar.button("🔄 重新计算全部分析", type="primary", use_container_width=True):
        st.session_state.last_advice = None
        st.rerun()

    st.sidebar.divider()
    st.sidebar.markdown("**AI 状态**")
    if ENABLE_AI:
        st.sidebar.success("✅ AI增强已启用（OpenAI/Grok）")
    else:
        st.sidebar.info("ℹ️ 当前为本地规则模式\n配置 OPENAI_API_KEY 获得更好建议")

    st.sidebar.markdown("---")
    st.sidebar.markdown("📖 [查看完整文档](https://github.com) | [GitHub](https://github.com)")


def main_dashboard():
    st.title("⚡ EnergyGuard AI")
    st.caption("家庭/个人能源消耗监测 · AI 智能分析 · 节能建议 · 零基础友好")

    init_session()
    sidebar_controls()

    df = st.session_state.df
    if df is None or df.empty:
        st.error("数据为空，请重新加载")
        return

    # 顶部关键指标
    stats = compute_basic_stats(df)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("分析月份", f"{stats['total_months']} 个月")
    col2.metric("月均用电", f"{stats['avg_monthly_kwh']:.0f} kWh", 
                delta=f"最高 {stats['max_kwh']:.0f}")
    col3.metric("累计电费", f"{stats['total_cost']:.0f} 元")
    col4.metric("异常月份", f"{len(detect_anomalies(df).query('is_anomaly==True'))} 个")

    # 主图表：历史 + 异常高亮
    st.subheader("📈 用电趋势与异常标记")
    anomalies = detect_anomalies(df)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["month"], y=df["kwh"],
        mode="lines+markers",
        name="实际用电",
        line=dict(color="#1976d2", width=3),
        marker=dict(size=8)
    ))
    # 异常点
    anom = anomalies[anomalies["is_anomaly"]]
    if not anom.empty:
        fig.add_trace(go.Scatter(
            x=anom["month"], y=anom["kwh"],
            mode="markers",
            name="异常月份",
            marker=dict(color="#d32f2f", size=14, symbol="x"),
            hovertext=anom["anomaly_reason"]
        ))
    fig.update_layout(height=420, margin=dict(l=20, r=20, t=30, b=30),
                      xaxis_title="月份", yaxis_title="用电量 (kWh)")
    st.plotly_chart(fig, use_container_width=True)

    # 洞察 + 预测
    col_left, col_right = st.columns([1.1, 1])
    with col_left:
        st.subheader("🔍 智能洞察")
        insights = generate_insights(df, anomalies)
        for i in insights:
            st.markdown(f"- {i}")

        with st.expander("查看原始数据表（可编辑）"):
            edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("保存编辑"):
                st.session_state.df = edited
                st.success("已更新！")

    with col_right:
        st.subheader("🔮 下月预测")
        fc = simple_forecast(df)
        st.metric("预测月份", fc["next_month"])
        st.metric("预计用电", f"{fc['predicted_kwh']} kWh", 
                  delta=f"区间 {fc['lower_bound']:.0f}~{fc['upper_bound']:.0f}")
        st.caption(f"方法: {fc['method']} | 置信度: {fc['confidence']}")

        # 未来3个月简单预测
        future = batch_forecast(df, 3)
        st.dataframe(future, use_container_width=True, hide_index=True)

    # 节能建议区（最核心）
    st.subheader("💡 个性化节能建议")
    user_note = st.text_input("补充说明（可选，例如：'最近买了新冰箱'）", key="user_note")

    if st.button("🚀 生成/刷新 AI 建议", type="primary", use_container_width=True):
        with st.spinner("正在分析并生成建议..."):
            st.session_state.last_advice = get_comprehensive_advice(df, user_note)

    advice = st.session_state.last_advice or get_comprehensive_advice(df, user_note)
    st.session_state.last_advice = advice

    if advice["used_ai"]:
        st.success("✨ 已使用 AI 智能生成（更自然个性化）")
        st.markdown(advice["llm_enhanced"])
    else:
        st.info("ℹ️ 当前展示本地规则建议（配置 API Key 可获得 AI 版本）")
        for line in advice["rule_based"]:
            st.markdown(line.replace("   ", "&nbsp;&nbsp;&nbsp;&nbsp;"))

    # 导出
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📥 导出当前数据 + 异常标记 CSV", use_container_width=True):
            out = ROOT / "reports" / f"energy_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            out.parent.mkdir(exist_ok=True)
            anomalies.to_csv(out, index=False, encoding="utf-8-sig")
            st.success(f"已保存到 {out.name}（可在项目根目录 reports/ 文件夹找到）")
    with c2:
        st.caption("提示：命令行运行 `python -m energyguard.cli report` 可生成更完整报告")

    # 页脚
    st.markdown("---")
    st.caption("EnergyGuard-AI v1.0.0 | 专为编程小白设计的实用开源工具 | 数据仅本地处理，永不上传")


if __name__ == "__main__":
    main_dashboard()
