#!/usr/bin/env python3
"""
FIT File Merger - 将两个 Garmin FIT 文件合并为一个。

使用方法:
    python entrypoint.py file1.fit file2.fit -o merged.fit

所有中间文件使用临时目录管理，脚本结束后自动清理。
"""

import os
import sys
import re
import argparse
import subprocess
import tempfile

import pandas as pd


# ---------------------------------------------------------------------------
# 工具定位与环境检查
# ---------------------------------------------------------------------------

def find_fit_csv_tool():
    """在常见路径中搜索 FitCSVTool.jar"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(script_dir, "FitSDK", "java", "FitCSVTool.jar"),
        "FitSDK/java/FitCSVTool.jar",
        "../FitSDK/java/FitCSVTool.jar",
        "./FitCSVTool.jar",
        os.path.expanduser("~/FitSDK/java/FitCSVTool.jar"),
        "/opt/FitSDK/java/FitCSVTool.jar",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


def check_java():
    """检查 Java 是否可用"""
    try:
        result = subprocess.run(
            ["java", "-version"], capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# FIT <-> CSV 转换（通过 FitCSVTool.jar）
# ---------------------------------------------------------------------------

def convert_fit_to_csv(fit_path, csv_path, tool_jar):
    """调用 FitCSVTool.jar 将 FIT 文件转换为官方 CSV 格式"""
    print(f"  [FIT->CSV] {os.path.basename(fit_path)}")
    cmd = ["java", "-jar", tool_jar, "-b", fit_path, csv_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FIT->CSV 转换失败: {os.path.basename(fit_path)}\n{result.stderr}"
        )
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"FIT->CSV 转换后未生成文件: {csv_path}"
        )
    line_count = sum(1 for _ in open(csv_path)) - 1
    print(f"           -> {os.path.basename(csv_path)} ({line_count} 行)")
    return csv_path


def convert_csv_to_fit(csv_path, fit_path, tool_jar):
    """调用 FitCSVTool.jar 将 CSV 文件转换回 FIT 格式"""
    print(f"  [CSV->FIT] {os.path.basename(csv_path)}")
    cmd = ["java", "-jar", tool_jar, "-c", csv_path, fit_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"CSV->FIT 转换失败:\n{result.stderr}"
        )
    if not os.path.exists(fit_path):
        raise FileNotFoundError(
            f"CSV->FIT 转换后未生成文件: {fit_path}"
        )
    size = os.path.getsize(fit_path)
    print(f"           -> {os.path.basename(fit_path)} ({size} bytes)")
    return fit_path


# ---------------------------------------------------------------------------
# CSV 合并逻辑
# ---------------------------------------------------------------------------

def _extract_timestamp(row):
    """从官方 CSV 的 Field/Value 列中提取 timestamp 值"""
    for i in range(1, 60):
        field_col = f"Field {i}"
        value_col = f"Value {i}"
        if field_col in row.index and value_col in row.index:
            if pd.notna(row[field_col]) and row[field_col] == "timestamp":
                if pd.notna(row[value_col]):
                    try:
                        return int(str(row[value_col]).split("|")[0])
                    except (ValueError, IndexError):
                        return 0
                return 0
    return 0


def merge_csv_files(csv1_path, csv2_path, output_path):
    """
    合并两个 Garmin 官方格式的 CSV 文件。

    - 按消息类型优先级排序
    - 同类型消息按 timestamp 排序
    - 去除重复的 record 消息（基于 timestamp）
    """
    print("  [合并CSV]")

    df1 = pd.read_csv(csv1_path)
    df2 = pd.read_csv(csv2_path)
    print(f"    文件1: {len(df1)} 行  |  文件2: {len(df2)} 行")

    merged = pd.concat([df1, df2], ignore_index=True)

    # --- 排序 ---
    type_priority = {
        "file_id": 0,
        "file_creator": 1,
        "device_info": 2,
        "event": 3,
        "record": 4,
        "lap": 5,
        "segment_lap": 6,
        "session": 7,
        "activity": 8,
    }

    def sort_key(row):
        msg = row.get("Message", "")
        priority = type_priority.get(msg, 999)
        ts = _extract_timestamp(row)
        return (priority, ts)

    merged["_sort"] = merged.apply(sort_key, axis=1)
    merged = merged.sort_values("_sort").drop(columns=["_sort"])

    # --- 去重（仅对 record 消息按 timestamp 去重）---
    dup_count = 0
    record_mask = merged["Message"] == "record"
    record_rows = merged[record_mask]

    if len(record_rows) > 1:
        seen = set()
        drop_indices = []
        for idx, row in record_rows.iterrows():
            ts = _extract_timestamp(row)
            if ts in seen:
                drop_indices.append(idx)
                dup_count += 1
            else:
                seen.add(ts)
        if drop_indices:
            merged = merged.drop(drop_indices)

    merged.to_csv(output_path, index=False)
    print(f"    合并后: {len(merged)} 行 (去重 {dup_count} 条)")
    return output_path


# ---------------------------------------------------------------------------
# CSV 格式修复（pandas 输出 -> Garmin 官方格式）
# ---------------------------------------------------------------------------

def fix_csv_format(input_path, output_path):
    """
    修复 pandas 写出的 CSV，使其符合 FitCSVTool 要求：
    - 去除浮点数尾部 .0
    - 去除尾部多余逗号
    - 去除 Unnamed 列
    """
    print("  [格式修复]")

    with open(input_path, "r") as f:
        content = f.read()

    # 去除整数的 .0 后缀
    content = re.sub(r"\b(\d+)\.0\b", r"\1", content)

    lines = content.split("\n")
    fixed = []
    for line in lines:
        if not line.strip():
            continue
        # 去除尾部空逗号
        while line.endswith(","):
            line = line[:-1]
        # 去除 Unnamed 列
        if "Unnamed:" in line:
            parts = line.split(",")
            parts = [p for p in parts if not p.startswith("Unnamed:") and p.strip()]
            line = ",".join(parts)
        fixed.append(line)

    with open(output_path, "w") as f:
        f.write("\n".join(fixed))

    print(f"    已修复 -> {os.path.basename(output_path)}")
    return output_path


# ---------------------------------------------------------------------------
# 主合并流程
# ---------------------------------------------------------------------------

def merge_fit_files(fit1, fit2, output, tool_jar):
    """
    完整的 FIT 合并流程：
    1. FIT -> CSV (临时)
    2. 合并两个 CSV
    3. 修复 CSV 格式
    4. CSV -> FIT (输出到目标路径)
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(os.path.abspath(output))
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="fit_merge_") as tmpdir:
        print(f"临时目录: {tmpdir}\n")

        # Step 1: FIT -> CSV
        print("Step 1/4: 转换 FIT 为 CSV")
        csv1 = os.path.join(tmpdir, "file1.csv")
        csv2 = os.path.join(tmpdir, "file2.csv")
        convert_fit_to_csv(fit1, csv1, tool_jar)
        convert_fit_to_csv(fit2, csv2, tool_jar)

        # Step 2: 合并 CSV
        print("\nStep 2/4: 合并 CSV 文件")
        merged_csv = os.path.join(tmpdir, "merged.csv")
        merge_csv_files(csv1, csv2, merged_csv)

        # Step 3: 修复格式
        print("\nStep 3/4: 修复 CSV 格式")
        fixed_csv = os.path.join(tmpdir, "merged_fixed.csv")
        fix_csv_format(merged_csv, fixed_csv)

        # Step 4: CSV -> FIT
        print("\nStep 4/4: 转换 CSV 为 FIT")
        convert_csv_to_fit(fixed_csv, output, tool_jar)

    # TemporaryDirectory 已自动清理
    print(f"\n{'='*50}")
    print(f"合并完成！输出文件: {output}")
    print(f"文件大小: {os.path.getsize(output)} bytes")
    print(f"临时文件已自动清理。")
    return output


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="合并两个 Garmin FIT 文件为一个",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python entrypoint.py ride1.fit ride2.fit -o merged.fit\n"
            "  python entrypoint.py a.fit b.fit --tool-path /path/to/FitCSVTool.jar\n"
        ),
    )
    parser.add_argument("fit1", help="第一个 FIT 文件路径")
    parser.add_argument("fit2", help="第二个 FIT 文件路径")
    parser.add_argument(
        "-o", "--output",
        default="merged_output.fit",
        help="输出 FIT 文件路径 (默认: merged_output.fit)",
    )
    parser.add_argument(
        "-t", "--tool-path",
        default=None,
        help="FitCSVTool.jar 路径 (未指定时自动搜索)",
    )

    args = parser.parse_args()

    # --- 校验输入 ---
    for path in [args.fit1, args.fit2]:
        if not os.path.isfile(path):
            print(f"错误: 文件不存在 - {path}")
            sys.exit(1)
        if not path.lower().endswith(".fit"):
            print(f"警告: {path} 可能不是 FIT 文件")

    # --- 检查 Java ---
    if not check_java():
        print("错误: 未检测到 Java，请先安装 Java Runtime。")
        sys.exit(1)

    # --- 定位 FitCSVTool.jar ---
    tool_jar = args.tool_path or find_fit_csv_tool()
    if not tool_jar or not os.path.isfile(tool_jar):
        print("错误: 找不到 FitCSVTool.jar")
        print("请通过 --tool-path 参数指定路径，或将其放在以下位置之一:")
        print("  - FitSDK/java/FitCSVTool.jar")
        print("  - ./FitCSVTool.jar")
        sys.exit(1)

    print(f"FitCSVTool: {tool_jar}")
    print(f"输入文件1: {args.fit1}")
    print(f"输入文件2: {args.fit2}")
    print(f"输出文件:  {args.output}")
    print(f"{'='*50}\n")

    # --- 执行合并 ---
    try:
        merge_fit_files(args.fit1, args.fit2, args.output, tool_jar)
    except Exception as e:
        print(f"\n合并失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
