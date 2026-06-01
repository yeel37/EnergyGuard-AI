"""
配置模块 - 中央配置，零基础用户无需修改
支持通过环境变量覆盖默认值
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 自动加载 .env 文件（如果存在）
load_dotenv()

# 项目根目录（支持从 src/energyguard 或直接运行）
# __file__ 在 src/energyguard/config.py → 向上3级到项目根
_project_root = Path(__file__).resolve()
for _ in range(5):
    if (_project_root / "data").exists():
        break
    _project_root = _project_root.parent
PROJECT_ROOT = _project_root

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_DATA_PATH = DATA_DIR / "sample_energy_data.csv"

# 报告输出目录
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# 默认配置
DEFAULT_CURRENCY = "元"
DEFAULT_ENERGY_UNIT = "kWh"

# AI 配置（可选）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROK_API_KEY = os.getenv("GROK_API_KEY", "") or os.getenv("XAI_API_KEY", "")
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").lower()  # openai / grok / none

# 是否启用 AI 增强（有 key 才启用）
ENABLE_AI = bool(OPENAI_API_KEY or GROK_API_KEY)

# Streamlit 页面配置
STREAMLIT_PAGE_TITLE = "EnergyGuard AI - 家庭能源智能管家"
STREAMLIT_PAGE_ICON = "⚡"

# 分析阈值
ANOMALY_ZSCORE_THRESHOLD = 2.0  # Z-score 超过此值视为异常
ANOMALY_IQR_MULTIPLIER = 1.5    # IQR 方法倍数

# 预测参数
PREDICT_MONTHS_HISTORY = 6  # 使用最近 N 个月做趋势拟合

print(f"[配置] EnergyGuard-AI v1.0.0 加载完成 | AI增强: {'已启用' if ENABLE_AI else '本地规则模式（推荐配置OPENAI_API_KEY）'}")
