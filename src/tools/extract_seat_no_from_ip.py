import argparse
import ipaddress
from pathlib import Path

import pandas as pd


DEFAULT_IP_COLUMN = "考生机器ip"
DEFAULT_SEAT_COLUMN = "座位号"
DEFAULT_SUBJECT_COLUMN = "科目"
DEFAULT_GROUP_COLUMN = "组别"


def parse_args():
    parser = argparse.ArgumentParser(
        description="从 Excel 的 IP 列提取最后一位，写入座位号列。"
    )
    parser.add_argument(
        "input_file",
        help="输入 Excel 文件路径，例如 src/manager/client.xlsx"
    )
    parser.add_argument(
        "-o",
        "--output-file",
        help="输出 Excel 文件路径；不填时默认在原文件名后追加 _seat_no"
    )
    parser.add_argument(
        "--ip-column",
        default=DEFAULT_IP_COLUMN,
        help=f"IP 列名，默认: {DEFAULT_IP_COLUMN}"
    )
    parser.add_argument(
        "--seat-column",
        default=DEFAULT_SEAT_COLUMN,
        help=f"座位号列名，默认: {DEFAULT_SEAT_COLUMN}"
    )
    parser.add_argument(
        "--subject-column",
        default=DEFAULT_SUBJECT_COLUMN,
        help=f"科目列名，默认: {DEFAULT_SUBJECT_COLUMN}"
    )
    parser.add_argument(
        "--group-column",
        default=DEFAULT_GROUP_COLUMN,
        help=f"组别列名，默认: {DEFAULT_GROUP_COLUMN}"
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="直接覆盖原文件"
    )
    return parser.parse_args()


def extract_last_octet(ip_value):
    if pd.isna(ip_value):
        return None
    ip_text = str(ip_value).strip()
    if not ip_text:
        return None
    ipv4 = ipaddress.IPv4Address(ip_text)
    return int(ip_text.split(".")[-1])


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_seat_no{input_path.suffix}")


def merge_subject_and_group(subject_value, group_value):
    subject_text = "" if pd.isna(subject_value) else str(subject_value).strip()
    group_text = "" if pd.isna(group_value) else str(group_value).strip()
    if subject_text and group_text:
        return f"{subject_text}-{group_text}"
    if subject_text:
        return subject_text
    if group_text:
        return group_text
    return None


def main():
    args = parse_args()
    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    output_path = input_path if args.inplace else Path(args.output_file) if args.output_file else default_output_path(input_path)

    workbook = pd.read_excel(input_path, sheet_name=None)
    if not workbook:
        raise ValueError("Excel 中没有可处理的 sheet")

    total_rows = 0
    total_success = 0
    total_failed = 0
    processed_sheet_count = 0
    invalid_rows_by_sheet = {}

    with pd.ExcelWriter(output_path) as writer:
        for sheet_name, df in workbook.items():
            if args.ip_column not in df.columns:
                if args.subject_column in df.columns and args.group_column in df.columns:
                    df[args.subject_column] = [
                        merge_subject_and_group(subject_value, group_value)
                        for subject_value, group_value in zip(df[args.subject_column], df[args.group_column])
                    ]
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                continue

            processed_sheet_count += 1
            invalid_rows = []
            seat_values = []
            for index, ip_value in enumerate(df[args.ip_column], start=2):
                try:
                    seat_value = extract_last_octet(ip_value)
                    seat_values.append(seat_value)
                    if seat_value is None:
                        total_failed += 1
                    else:
                        total_success += 1
                except Exception:
                    invalid_rows.append((index, ip_value))
                    seat_values.append(None)
                    total_failed += 1

            total_rows += len(df)
            if invalid_rows:
                invalid_rows_by_sheet[sheet_name] = invalid_rows

            df[args.seat_column] = seat_values
            if args.subject_column in df.columns and args.group_column in df.columns:
                df[args.subject_column] = [
                    merge_subject_and_group(subject_value, group_value)
                    for subject_value, group_value in zip(df[args.subject_column], df[args.group_column])
                ]
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"处理完成: {output_path}")
    print(f"处理 sheet 数: {processed_sheet_count}/{len(workbook)}")
    print(f"总行数: {total_rows}")
    print(f"成功提取: {total_success}")
    print(f"提取失败: {total_failed}")
    if invalid_rows_by_sheet:
        print("以下 sheet 存在无法解析的 IP:")
        for sheet_name, invalid_rows in invalid_rows_by_sheet.items():
            print(f"- {sheet_name}")
            for row_no, ip_value in invalid_rows:
                print(f"  行 {row_no}: {ip_value}")


if __name__ == "__main__":
    main()
