#!/usr/bin/env python3
"""
便捷启动脚本（小白推荐）
直接双击或 python run_cli.py 即可运行 CLI 演示
"""

import sys
from pathlib import Path

# 确保导入正确
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    from energyguard.cli import main
    main()
