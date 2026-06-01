#!/usr/bin/env python3
"""
EnergyGuard-AI 命令行入口
支持：加载数据、分析、预测、生成建议、导出CSV报告
完全零基础友好，带彩色输出和详细帮助
用法示例：
  python -m energyguard.cli --help
  python -m energyguard.cli analyze --data data/sample_energy_data.csv
  python -m energyguard.cli report --output reports/my_report.csv
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# 确保可作为模块运行
try:
    from .data_loader import load_data, validate_data
    from .analyzer import compute_basic_stats, detect_anomalies, generate_insights
    from .predictor import simple_forecast, batch_forecast
    from .advisor import get_comprehensive_advice
    from .config import SAMPLE_DATA_PATH, REPORTS_DIR
except ImportError:
    # 直接脚本运行时的回退
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.energyguard.data_loader import load_data, validate_data
    from src.energyguard.analyzer import compute_basic_stats, detect_anomalies, generate_insights
    from src.energyguard.predictor import simple_forecast, batch_forecast
    from src.energyguard.advisor import get_comprehensive_advice
    from src.energyguard.config import SAMPLE_DATA_PATH, REPORTS_DIR


def print_banner():
    print("=" * 60)
    print("⚡ EnergyGuard AI - 家庭能源智能监测与分析工具 v1.0")
    print("   让每个小白都能轻松掌控家庭用电，省钱又环保")
    print("=" * 60)


def cmd_analyze(args):
    """执行分析"""
    print_banner()
    df = load_data(args.data)
    print(f"✅ 成功加载 {len(df)} 条记录（数据源: {args.data or '内置样例'}）\n")

    warnings = validate_data(df)
    for w in warnings:
        print(f"⚠️  {w}")

    stats = compute_basic_stats(df)
    anomalies = detect_anomalies(df)
    insights = generate_insights(df, anomalies)

    print("\n📊 【基础统计】")
    print(f"  分析周期: {stats['total_months']} 个月")
    print(f"  累计用电: {stats['total_kwh']:.0f} kWh | 累计电费: {stats['total_cost']:.0f} 元")
    print(f"  月均用电: {stats['avg_monthly_kwh']:.0f} kWh ({stats['avg_monthly_cost']:.0f} 元)")
    print(f"  最高月份: {stats['max_cost_month']} ({stats['max_kwh']:.0f} kWh)")

    print("\n🔍 【异常检测】")
    anom = anomalies[anomalies["is_anomaly"]]
    if not anom.empty:
        for _, row in anom.iterrows():
            print(f"  ❌ {row['month']}: {row['kwh']:.0f}kWh | 原因: {row['anomaly_reason']}")
    else:
        print("  ✅ 未发现明显异常")

    print("\n💡 【关键洞察】")
    for ins in insights:
        print(f"  {ins}")

    if args.export:
        out = Path(args.export)
        anomalies.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n📁 异常明细已导出: {out}")


def cmd_predict(args):
    """预测"""
    print_banner()
    df = load_data(args.data)
    fc = simple_forecast(df)
    print(f"\n🔮 下月 ({fc['next_month']}) 预测结果")
    print(f"  预计用电: {fc['predicted_kwh']} kWh")
    print(f"  预计电费: {fc['predicted_cost']} 元")
    print(f"  置信区间: {fc['lower_bound']} ~ {fc['upper_bound']} kWh")
    print(f"  置信度: {fc['confidence']}")
    print(f"  采用方法: {fc['method']}")


def cmd_advice(args):
    """生成建议"""
    print_banner()
    df = load_data(args.data)
    result = get_comprehensive_advice(df, args.note or "")

    print("\n🧠 【智能节能建议】")
    if result["used_ai"]:
        print("  (已使用 AI 增强生成)\n")
        print(result["llm_enhanced"])
    else:
        print("  (当前为本地规则模式，配置 OPENAI_API_KEY 可获得更好体验)\n")
        for line in result["rule_based"]:
            print(line)

    print("\n📈 预测辅助:")
    fc = result["forecast"]
    print(f"  下月预计 {fc['predicted_kwh']} kWh，建议做好 {int(fc['predicted_kwh']*0.9)} kWh 用电预算。")


def cmd_report(args):
    """生成完整报告 CSV"""
    print_banner()
    df = load_data(args.data)
    anomalies = detect_anomalies(df)
    fc = simple_forecast(df)
    advice_result = get_comprehensive_advice(df)

    # 合并预测行
    report_df = df.copy()
    report_df["type"] = "历史"
    report_df["is_anomaly"] = anomalies["is_anomaly"]
    report_df["anomaly_reason"] = anomalies["anomaly_reason"]

    pred_row = pd.DataFrame([{
        "month": fc["next_month"],
        "kwh": fc["predicted_kwh"],
        "cost_yuan": fc["predicted_cost"],
        "avg_temp_c": None,
        "notes": f"预测(置信度:{fc['confidence']})",
        "type": "预测",
        "is_anomaly": False,
        "anomaly_reason": ""
    }])
    report_df = pd.concat([report_df, pred_row], ignore_index=True)

    # 保存
    out_path = Path(args.output) if args.output else (REPORTS_DIR / f"energy_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n✅ 完整报告已生成: {out_path}")
    print(f"   包含 {len(df)} 条历史 + 1 条预测 + 异常标记")
    print("   可直接用 Excel 打开或导入其他工具。")


def main():
    parser = argparse.ArgumentParser(
        description="EnergyGuard-AI 命令行工具 - 家庭用电智能分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用内置样例数据分析
  python -m energyguard.cli analyze

  # 导入自己的CSV并预测
  python -m energyguard.cli predict --data my_bills.csv

  # 生成带AI建议的完整报告
  python -m energyguard.cli report --output my_report.csv

更多帮助: https://github.com/yeel37/EnergyGuard-AI
        """
    )
    parser.add_argument("--data", "-d", type=str, default=None,
                        help="CSV数据文件路径，默认使用内置样例")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p1 = subparsers.add_parser("analyze", help="执行异常检测与洞察分析")
    p1.add_argument("--export", type=str, default=None, help="导出异常明细CSV")
    p1.set_defaults(func=cmd_analyze)

    p2 = subparsers.add_parser("predict", help="预测下个月用电量")
    p2.set_defaults(func=cmd_predict)

    p3 = subparsers.add_parser("advice", help="生成个性化节能建议")
    p3.add_argument("--note", type=str, default="", help="补充说明（如'家里新买了电热水器'）")
    p3.set_defaults(func=cmd_advice)

    p4 = subparsers.add_parser("report", help="导出完整分析报告（含预测）")
    p4.add_argument("--output", "-o", type=str, default=None, help="输出文件路径")
    p4.set_defaults(func=cmd_report)

    args = parser.parse_args()

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n👋 已取消操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("   提示: 先运行 'python -m energyguard.cli analyze' 测试样例数据")
        sys.exit(1)


if __name__ == "__main__":
    main()
