#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 该脚本从文本文件读取调休上班日期（每行一个 YYYY-MM-DD 格式的日期），
# 并使用这些日期更新一个 ICS 文件 (china_adjusted_workdays.ics) 作为全天事件。
# ICS 文件中已存在的日期将被跳过以避免重复。
# 生成的 ICS 文件可以托管（例如在 GitHub 上）并在 Google 日历中订阅。

from ics import Calendar, Event
from datetime import datetime, date
import os
import re # 用于日期格式验证

# --- 配置 ---
ICS_FILENAME = "china_adjusted_workdays.ics" # 输出的 ICS 文件名
EVENT_SUMMARY = "调休上班" # 日历事件的标题
TXT_FILENAME = "adjusted_dates.txt"

# --- 配置结束 ---

def read_dates_from_file():
    """从文件中读取调休日期。
       文件格式要求:
       - UTF-8 编码
       - 每行一个日期，格式为 YYYY-MM-DD
       - 以 '#' 开头的行或空行将被忽略
    """


    parsed_dates = []
    try:
        print(f"正在尝试读取文件: '{TXT_FILENAME}'")
        line_num = 0
        invalid_lines = []
        with open(TXT_FILENAME, 'r', encoding='utf-8') as f:
            for line in f:
                line_num += 1
                line = line.strip()

                # 忽略空行和注释行
                if not line or line.startswith('#'):
                    continue

                # 验证日期格式 YYYY-MM-DD
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", line):
                    print(f"警告: 文件 '{TXT_FILENAME}' 第 {line_num} 行格式错误 '{line}'，应为 YYYY-MM-DD。已跳过。")
                    invalid_lines.append(f"L{line_num}: {line} (格式错误)")
                    continue
                try:
                    # 尝试解析日期
                    dt = datetime.strptime(line, "%Y-%m-%d").date()
                    parsed_dates.append(dt)
                except ValueError:
                    print(f"警告: 文件 '{TXT_FILENAME}' 第 {line_num} 行日期无效 '{line}' (例如，2月30日)。已跳过。")
                    invalid_lines.append(f"L{line_num}: {line} (日期无效)")
                    continue

        if not parsed_dates and not invalid_lines:
             print(f"警告: 文件 '{TXT_FILENAME}' 为空或只包含注释/空行。")
             # 让用户有机会重试
        elif not parsed_dates and invalid_lines:
             print(f"错误: 文件 '{TXT_FILENAME}' 中未找到任何有效格式的日期，仅有无效行。")
             # 让用户有机会重试
        else:
            print("-" * 20)
            print(f"从文件 '{TXT_FILENAME}' 读取到以下 {len(parsed_dates)} 个有效调休上班日期:")
            # 排序后显示，更清晰
            parsed_dates.sort()
            for dt in parsed_dates:
                print(f"- {dt.strftime('%Y-%m-%d')}")
            if invalid_lines:
                print("\n检测到以下无效或格式错误的行 (已跳过):")
                for invalid in invalid_lines:
                    print(f"- {invalid}")
            print("-" * 20)

            confirm = input("确认使用这些有效日期更新日历吗？(y/n): ").lower()
            if confirm == 'y':
                return parsed_dates # 返回成功读取并确认的日期列表
            else:
                print("操作已取消。")
                return [] # 用户取消，返回空列表

        # 如果没有成功返回日期，询问是否重试
        retry = input("是否尝试输入其他文件名？(y/n): ").lower()
        if retry != 'y':
            return [] # 用户不想重试，返回空列表
        # 否则循环将继续，要求输入新文件名

    except FileNotFoundError:
        print(f"错误: 文件 '{TXT_FILENAME}' 未找到。请确保文件与脚本在同一目录，或提供了正确的路径。")
    except Exception as e:
        print(f"读取文件 '{TXT_FILENAME}' 时发生未知错误: {e}")
        return [] # 发生其他错误，返回空列表

def load_or_create_calendar(filename):
    """加载现有的 ICS 文件或创建一个新的 Calendar 对象"""
    existing_event_dates = set()
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            # 基础检查，防止空文件或无效文件导致ics库解析错误
            if content.strip().startswith("BEGIN:VCALENDAR") and content.strip().endswith("END:VCALENDAR"):
                 c = Calendar(content)
                 print(f"已加载现有的日历文件: '{filename}'")
                 # 记录已存在的事件日期，防止重复添加
                 for event in c.events:
                     # event.begin 可能是 datetime 或 date 对象，统一转为 date
                     event_date = event.begin
                     if hasattr(event_date, 'date'): # 如果是 datetime 对象
                         event_date = event_date.date()
                     if isinstance(event_date, date):
                         # 确保只添加 EVENT_SUMMARY 匹配的事件日期，避免误删其他事件
                         if event.name == EVENT_SUMMARY:
                              existing_event_dates.add(event_date)
                 print(f"找到 {len(existing_event_dates)} 个已存在的 '{EVENT_SUMMARY}' 日期。")
                 return c, existing_event_dates
            else:
                 print(f"警告: 文件 '{filename}' 内容格式不符合 iCalendar 标准或为空，将创建新日历。")
                 return Calendar(), set()

    except FileNotFoundError:
        print(f"日历文件 '{filename}' 不存在，将创建新的文件。")
        return Calendar(), set()
    except Exception as e:
        print(f"加载或解析日历文件 '{filename}' 时发生错误: {e}")
        print("将创建一个新的空日历。")
        return Calendar(), set()

# 注意：移除了 year 参数，因为它不再从用户输入获取，而是直接来自日期对象
def add_adjustment_events(calendar, adjustment_dates, existing_event_dates):
    """将调休日期作为全天事件添加到日历对象"""
    added_count = 0
    # 排序日期以确保添加顺序一致（可选）
    adjustment_dates.sort()
    for adj_date in adjustment_dates:
        if adj_date in existing_event_dates:
            # print(f"提示: 日期 {adj_date.strftime('%Y-%m-%d')} 已存在于日历中，跳过添加。") # 可以取消注释以获得更详细的输出
            continue

        event = Event()
        event.name = EVENT_SUMMARY # 事件标题
        event.begin = adj_date     # 设置日期
        event.make_all_day()       # 设置为全天事件

        calendar.events.add(event)
        existing_event_dates.add(adj_date) # 更新内存中的已存在日期集合
        added_count += 1
        print(f"已添加事件: {EVENT_SUMMARY} - {adj_date.strftime('%Y-%m-%d')}")

    return added_count

def save_calendar(calendar, filename):
    """将 Calendar 对象写入 ICS 文件"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            # 使用 ics 库的 __str__ 方法生成标准的 VCALENDAR 输出
            f.write(str(calendar))
        print(f"\n日历已成功更新并保存到 '{filename}'")
    except IOError as e:
        print(f"错误: 无法写入文件 '{filename}'. 错误信息: {e}")
    except Exception as e:
        print(f"保存日历时发生未知错误: {e}")

def print_usage_instructions(filename):
    """打印如何使用生成的 ICS 文件的说明"""
    print("\n--- 如何在 Google 日历中使用 ---")
    print(f"1. 将更新后的 '{filename}' 文件上传/推送到您的 GitHub 仓库。")
    print(f"   - 确保仓库是公开的，或者您能获取到该文件的永久 Raw 链接。")
    print(f"2. 在 GitHub 上找到 '{filename}' 文件，点击它。")
    print(f"3. 点击文件内容右上方的 [Raw] 按钮。")
    print(f"4. 复制浏览器地址栏中显示的 URL。这个 URL 应该类似:")
    print(f"   https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPOSITORY/main/{filename}")
    print(f"5. (如果首次添加) 打开 Google 日历 (calendar.google.com)。")
    print(f"   a. 在左侧面板找到“其他日历”，点击旁边的加号 (+)。")
    print(f"   b. 选择“通过网址添加”。")
    print(f"   c. 将第 4 步复制的 Raw GitHub URL 粘贴到输入框中。")
    print(f"   d. 点击“添加日历”。")
    print(f"6. (如果已添加过) Google 日历会自动从此 URL 定期检查更新（通常每天一次）。您只需确保 GitHub 上的文件是最新版本即可。")

# --- 主程序 ---
if __name__ == "__main__":
    # 检查依赖库是否安装
    try:
        from ics import Calendar
    except ImportError:
        print("错误：缺少 'ics' 库。")
        print("请先安装: pip install ics")
        exit(1)

    # 从文件读取日期
    adjustment_dates = read_dates_from_file()

    # 只有成功读取并确认了日期才继续
    if adjustment_dates:
        calendar, existing_dates = load_or_create_calendar(ICS_FILENAME)
        added_count = add_adjustment_events(calendar, adjustment_dates, existing_dates)

        if added_count > 0:
            save_calendar(calendar, ICS_FILENAME)
            print(f"\n成功添加了 {added_count} 个新的调休上班日期。")
        else:
            print("\n没有新的调休日期被添加（可能文件中的有效日期已全部存在于日历中）。")

        print_usage_instructions(ICS_FILENAME)
    else:
        print("未能从文件获取有效日期，或操作已被用户取消。程序退出。")