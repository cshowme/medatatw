#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""從 HTML 提取 meta 資訊統計"""

from pathlib import Path
import re

repo = Path(r"C:/temp/medatatw")
html_files = list(repo.glob("*.html"))

# 統計
stats = {
    "total_pages": len(html_files),
    "with_charset_utf8": 0,
    "with_viewport": 0,
    "with_favicon": 0,
    "with_ga": 0,
    "with_search_related": 0,
    "external_deps": set()
}

for html_file in html_files:
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()

            # Charset
            if re.search(r'charset=["\']?utf-?8["\']?', content, re.I):
                stats["with_charset_utf8"] += 1

            # Viewport
            if re.search(r'<meta[^>]*name=["\']viewport["\']', content, re.I):
                stats["with_viewport"] += 1

            # Favicon
            if re.search(r'<link[^>]*rel=["\'](?:shortcut )?icon["\']', content, re.I):
                stats["with_favicon"] += 1

            # Google Analytics
            if re.search(r'google-?analytics|gtag\.js|G-\w+', content, re.I):
                stats["with_ga"] += 1

            # Search
            if re.search(r'search|搜尋', content, re.I):
                stats["with_search_related"] += 1

            # External dependencies
            # Google Fonts
            if 'fonts.googleapis.com' in content:
                stats["external_deps"].add("Google Fonts")
            # Facebook
            if 'facebook' in content or 'fb-' in content:
                stats["external_deps"].add("Facebook SDK")
            # Google Tag Manager
            if 'googletagmanager' in content:
                stats["external_deps"].add("Google Tag Manager")
    except Exception as e:
        pass

# 輸出
print("頁面功能元素統計")
print("=" * 60)
print(f"總頁面數: {stats['total_pages']}")
print()
print(f"UTF-8 Charset:  {stats['with_charset_utf8']:3d} / {stats['total_pages']} ({stats['with_charset_utf8']/stats['total_pages']*100:.1f}%)")
print(f"Viewport Meta:  {stats['with_viewport']:3d} / {stats['total_pages']} ({stats['with_viewport']/stats['total_pages']*100:.1f}%)")
print(f"Favicon:        {stats['with_favicon']:3d} / {stats['total_pages']} ({stats['with_favicon']/stats['total_pages']*100:.1f}%)")
print(f"Google Analytics: {stats['with_ga']:3d} / {stats['total_pages']} ({stats['with_ga']/stats['total_pages']*100:.1f}%)")
print(f"包含搜尋相關: {stats['with_search_related']:3d} / {stats['total_pages']} ({stats['with_search_related']/stats['total_pages']*100:.1f}%)")
print()
print(f"外部依賴數量: {len(stats['external_deps'])}")
for dep in sorted(stats['external_deps']):
    print(f"  - {dep}")
