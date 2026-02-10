#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""從 QA 執行輸出生成摘要報告"""

import sys
import re

output_file = r"C:\Users\cshow\AppData\Local\Temp\claude\D--Dropbox-00-----03------0-2026---\tasks\bb9ef8a.output"

with open(output_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 統計
css_ok = len(re.findall(r'\[OK\].*__css/', content))
css_fail = len(re.findall(r'\[FAIL\].*\.css', content))
js_ok = len(re.findall(r'\[OK\].*__js/', content))
js_fail = len(re.findall(r'\[FAIL\].*\.js', content))

# 提取外部依賴
external_match = re.search(r'外部依賴：(\d+) 個', content)
external_deps = int(external_match.group(1)) if external_match else 0

# 提取總數
total_css_match = re.search(r'CSS 檔案：(\d+) 個', content)
total_js_match = re.search(r'JS 檔案：(\d+) 個', content)
total_css = int(total_css_match.group(1)) if total_css_match else 0
total_js = int(total_js_match.group(1)) if total_js_match else 0

print("=" * 80)
print("官網前端品質驗證 V4 - 摘要報告")
print("=" * 80)
print()
print("【CSS 檔案測試】")
print(f"  總數: {total_css} 個")
print(f"  通過: {css_ok} 個")
print(f"  失敗: {css_fail} 個")
print(f"  通過率: {css_ok/total_css*100 if total_css > 0 else 0:.1f}%")
print()
print("【JS 檔案測試】")
print(f"  總數: {total_js} 個")
print(f"  通過: {js_ok} 個")
print(f"  失敗: {js_fail} 個")
print(f"  通過率: {js_ok/total_js*100 if total_js > 0 else 0:.1f}%")
print()
print("【外部資源】")
print(f"  依賴數量: {external_deps} 個")
print()

# 提取失敗項目
failed = re.findall(r'\[FAIL\] (.+?) - HTTP (\d+)', content)
if failed:
    print("【失敗項目】")
    for item, code in failed:
        print(f"  - {item} (HTTP {code})")
    print()

# 判定
total_fail = css_fail + js_fail
if total_fail == 0:
    verdict = "PASS"
    color = "綠燈"
else:
    verdict = "FAIL" if total_fail > 5 else "CONDITIONAL PASS"
    color = "紅燈" if total_fail > 5 else "黃燈"

print("=" * 80)
print(f"【最終判定】{verdict} ({color})")
print("=" * 80)
