"""
数据加载模块 - 支持 CSV 导入、手动输入、样例数据
针对小白设计：自动容错、编码检测、列映射、友好错误提示
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import sys

from .config import SAMPLE_DATA_PATH, DATA_DIR


def load_csv_data(file_path: Union[str, Path], 
                  encoding: str = "utf-8") -> pd.DataFrame:
    """
    健壮的 CSV 加载器
    自动处理常见中文编码问题（utf-8 / gbk / gb2312）
    自动识别常见列名变体（kwh / 用电量 / electricity 等）
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到文件: {path}。请检查路径是否正确。")

    # 尝试多种编码
    encodings_to_try = [encoding, "utf-8", "gbk", "gb2312", "gb18030", "latin1"]
    df = None
    last_error = None

    for enc in encodings_to_try:
        try:
            df = pd.read_csv(path, encoding=enc)
            if len(df.columns) > 0:
                break
        except Exception as e:
            last_error = e
            continue

    if df is None or df.empty:
        raise ValueError(f"无法读取CSV文件（已尝试多种编码）。错误: {last_error}。建议使用UTF-8编码保存CSV。")

    # 标准化列名（小白常犯的列名不规范问题）
    df = _normalize_columns(df)
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """智能列名标准化，将用户常见输入映射到标准内部列"""
    col_map = {
        # 月份/日期
        "month": "month", "月份": "month", "date": "month", "日期": "month", "时间": "month",
        "year-month": "month", "ym": "month",
        # 用电量
        "kwh": "kwh", "用电量": "kwh", "kwh用量": "kwh", "consumption": "kwh",
        "电量": "kwh", "usage": "kwh", "electricity": "kwh",
        # 费用
        "cost": "cost_yuan", "费用": "cost_yuan", "电费": "cost_yuan", "cost_yuan": "cost_yuan",
        "金额": "cost_yuan", "yuan": "cost_yuan", "rmb": "cost_yuan",
        # 温度（可选）
        "temp": "avg_temp_c", "温度": "avg_temp_c", "avg_temp": "avg_temp_c",
        "平均温度": "avg_temp_c", "temp_c": "avg_temp_c",
        # 备注
        "notes": "notes", "备注": "notes", "说明": "notes", "note": "notes", "描述": "notes"
    }

    # 构建实际映射
    rename_dict = {}
    for col in df.columns:
        col_lower = str(col).strip().lower().replace(" ", "").replace("_", "")
        if col_lower in col_map:
            rename_dict[col] = col_map[col_lower]
        elif col_lower in ["kwh", "cost", "costyuan"]:
            rename_dict[col] = "cost_yuan" if "cost" in col_lower else "kwh"

    if rename_dict:
        df = df.rename(columns=rename_dict)

    # 确保必要列存在
    required = ["month", "kwh"]
    missing = [r for r in required if r not in df.columns]
    if missing:
        # 尝试从第一列猜测
        if len(df.columns) >= 2:
            df = df.rename(columns={df.columns[0]: "month", df.columns[1]: "kwh"})
        else:
            raise ValueError(f"CSV缺少必要列: {missing}。请确保包含 'month' 和 'kwh' 列（或中文等价列名）。")

    # 强制类型转换 + 清洗
    df["kwh"] = pd.to_numeric(df["kwh"], errors="coerce")
    if "cost_yuan" in df.columns:
        df["cost_yuan"] = pd.to_numeric(df["cost_yuan"], errors="coerce")
    else:
        # 估算电费（简单模型，0.6元/kWh + 基础费）
        df["cost_yuan"] = (df["kwh"] * 0.62 + 35).round(2)

    if "avg_temp_c" not in df.columns:
        df["avg_temp_c"] = np.nan

    if "notes" not in df.columns:
        df["notes"] = ""

    df = df.dropna(subset=["month", "kwh"])
    df["month"] = df["month"].astype(str).str.strip()

    # 排序
    try:
        df = df.sort_values("month").reset_index(drop=True)
    except Exception:
        pass

    return df[["month", "kwh", "cost_yuan", "avg_temp_c", "notes"]]


def load_sample_data() -> pd.DataFrame:
    """加载内置模拟真实数据（首次运行必备 fallback）"""
    if not SAMPLE_DATA_PATH.exists():
        # 紧急回退：生成极简数据（防止任何情况下首次运行失败）
        print("警告: 样例文件丢失，正在生成最小回退数据集...")
        months = [f"2024-{m:02d}" for m in range(1, 13)] + [f"2025-{m:02d}" for m in range(1, 7)]
        kwhs = [320, 380, 290, 275, 310, 580, 510, 490, 265, 300, 285, 410,
                395, 415, 470, 280, 290, 505]
        df = pd.DataFrame({
            "month": months,
            "kwh": kwhs,
            "cost_yuan": [round(k*0.65 + 40, 2) for k in kwhs],
            "avg_temp_c": [6, 9, 12, 18, 23, 27, 29, 28, 22, 15, 8, 3] * 1 + [5,7,11,16,21,26],
            "notes": [""] * 18
        })
        return df
    return load_csv_data(SAMPLE_DATA_PATH)


def load_data(source: Optional[Union[str, Path, pd.DataFrame, Dict]] = None) -> pd.DataFrame:
    """
    统一数据入口
    source 可以是:
      - None -> 自动使用样例
      - str/Path -> CSV 文件路径
      - DataFrame -> 直接使用
      - dict -> 手动单条记录（用于 Streamlit 表单追加）
    """
    if source is None:
        return load_sample_data()

    if isinstance(source, (str, Path)):
        return load_csv_data(source)

    if isinstance(source, pd.DataFrame):
        return _normalize_columns(source.copy())

    if isinstance(source, dict):
        # 手动输入一条
        row = {
            "month": source.get("month", "2025-07"),
            "kwh": float(source.get("kwh", 350)),
            "cost_yuan": float(source.get("cost_yuan", source.get("kwh", 350)*0.62 + 35)),
            "avg_temp_c": float(source.get("avg_temp_c", 25.0)),
            "notes": str(source.get("notes", "手动输入"))
        }
        df = pd.DataFrame([row])
        return _normalize_columns(df)

    raise TypeError(f"不支持的数据源类型: {type(source)}")


def append_manual_record(existing_df: pd.DataFrame, record: Dict[str, Any]) -> pd.DataFrame:
    """追加手动记录，返回新 DataFrame"""
    new_row = load_data(record)
    combined = pd.concat([existing_df, new_row], ignore_index=True)
    # 去重保留最新
    combined = combined.drop_duplicates(subset=["month"], keep="last")
    return combined.sort_values("month").reset_index(drop=True)


def validate_data(df: pd.DataFrame) -> List[str]:
    """数据质量检查，返回警告列表（小白友好）"""
    warnings = []
    if df.empty:
        warnings.append("数据为空！")
        return warnings
    if len(df) < 3:
        warnings.append("数据量过少（少于3条），分析结果可能不准，建议至少导入6个月数据。")
    if df["kwh"].min() < 50:
        warnings.append("检测到极低用电量记录，请确认单位是否为kWh。")
    if (df["kwh"] > 2000).any():
        warnings.append("存在单月超过2000kWh的记录，可能是商业用电或数据错误。")
    missing_months = df["month"].isna().sum()
    if missing_months > 0:
        warnings.append(f"有 {missing_months} 条记录月份为空，已自动跳过。")
    return warnings
