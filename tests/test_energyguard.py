"""
EnergyGuard-AI 基础测试
运行: pytest tests/test_energyguard.py -v
或 python -m pytest
"""

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT / "src"))

from energyguard.data_loader import load_sample_data, load_data
from energyguard.analyzer import compute_basic_stats, detect_anomalies
from energyguard.predictor import simple_forecast
from energyguard.advisor import get_comprehensive_advice


def test_sample_data_loads():
    df = load_sample_data()
    assert not df.empty
    assert "month" in df.columns
    assert "kwh" in df.columns
    assert len(df) >= 6


def test_analyzer_runs():
    df = load_sample_data()
    stats = compute_basic_stats(df)
    assert "avg_monthly_kwh" in stats
    anomalies = detect_anomalies(df)
    assert "is_anomaly" in anomalies.columns
    assert len(anomalies) == len(df)


def test_predictor_runs():
    df = load_sample_data()
    fc = simple_forecast(df)
    assert "predicted_kwh" in fc
    assert fc["predicted_kwh"] > 50


def test_advisor_runs_without_ai():
    df = load_sample_data()
    result = get_comprehensive_advice(df)
    assert "rule_based" in result
    assert len(result["rule_based"]) >= 3
    # 即使无 key，也必须返回建议
    assert result["used_ai"] is False or result["llm_enhanced"] is not None


def test_manual_append():
    df = load_sample_data()
    new = load_data({"month": "2025-08", "kwh": 999})
    assert new.iloc[0]["kwh"] == 999
    combined = pd.concat([df, new], ignore_index=True)
    assert len(combined) == len(df) + 1


if __name__ == "__main__":
    print("Running basic self-check...")
    test_sample_data_loads()
    test_analyzer_runs()
    test_predictor_runs()
    test_advisor_runs_without_ai()
    print("✅ All core tests passed!")
