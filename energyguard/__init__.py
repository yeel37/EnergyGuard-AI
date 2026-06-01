"""
兼容入口：支持在项目根目录直接运行 `python -m energyguard.cli`。

实际源码仍保存在 src/energyguard，便于后续发布到 PyPI 或继续维护。
"""

from pathlib import Path


SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "energyguard"
__path__.append(str(SRC_PACKAGE))

__version__ = "1.0.0"
__author__ = "EnergyGuard Team"
__description__ = "实用家庭/个人能源消耗监测和 AI 智能分析工具"
