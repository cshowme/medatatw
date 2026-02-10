#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
官網前端品質驗證 V4
檢查 https://www.medatatw.com/ 的 CSS、JavaScript 和頁面功能完整性
日期：2026-02-10
作者：CSX
"""

import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from collections import defaultdict
import json

# 設定
REPO_PATH = Path(r"C:/temp/medatatw")
BASE_URL = "https://www.medatatw.com"
TIMEOUT = 10

# 結果統計
results = {
    "css_files": {},
    "js_files": {},
    "external_deps": [],
    "page_checks": {},
    "issues": [],
    "summary": {}
}

def extract_resources_from_html(html_path):
    """從 HTML 檔案中提取 CSS 和 JS 引用"""
    css_refs = []
    js_refs = []
    external_refs = []

    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

            # 提取 CSS
            css_pattern = r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']'
            css_refs = re.findall(css_pattern, content, re.IGNORECASE)

            # 提取 JS
            js_pattern = r'<script[^>]*src=["\']([^"\']+)["\']'
            js_refs = re.findall(js_pattern, content, re.IGNORECASE)

            # 檢查外部依賴（CDN、其他網域）
            all_refs = css_refs + js_refs
            for ref in all_refs:
                if ref.startswith('http') and 'medatatw.com' not in ref:
                    external_refs.append(ref)
                elif 'mawebcenters.com' in ref:
                    external_refs.append(ref)
                    results["issues"].append(f"❌ {html_path.name}: 引用舊網域 {ref}")

            # 檢查頁面元素
            page_info = {
                "charset": bool(re.search(r'<meta[^>]*charset=["\']?utf-8["\']?', content, re.IGNORECASE)),
                "viewport": bool(re.search(r'<meta[^>]*name=["\']viewport["\']', content, re.IGNORECASE)),
                "favicon": bool(re.search(r'<link[^>]*rel=["\'](?:icon|shortcut icon)["\']', content, re.IGNORECASE)),
                "google_analytics": bool(re.search(r'google-analytics\.com|gtag\.js|ga\.js', content)),
                "has_search": bool(re.search(r'search|搜尋', content, re.IGNORECASE))
            }
            results["page_checks"][html_path.name] = page_info

    except Exception as e:
        results["issues"].append(f"❌ 讀取 {html_path.name} 失敗: {str(e)}")

    return css_refs, js_refs, external_refs

def test_url(url):
    """測試 URL 是否可訪問，返回 (status_code, content_type, error)"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            status = response.getcode()
            content_type = response.headers.get('Content-Type', '')
            cache_control = response.headers.get('Cache-Control', '')
            return status, content_type, cache_control, None
    except urllib.error.HTTPError as e:
        return e.code, '', '', str(e)
    except urllib.error.URLError as e:
        return 0, '', '', str(e)
    except Exception as e:
        return 0, '', '', str(e)

def normalize_url(ref, base_url=BASE_URL):
    """標準化 URL"""
    if ref.startswith('http'):
        return ref
    elif ref.startswith('//'):
        return 'https:' + ref
    elif ref.startswith('/'):
        return base_url + ref
    else:
        return base_url + '/' + ref

def main():
    import sys
    import io
    # 強制使用 UTF-8 輸出
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=" * 80)
    print("官網前端品質驗證 V4")
    print("=" * 80)
    print()

    # Step 1: 掃描所有 HTML 檔案
    print("【Step 1】掃描本地 HTML 檔案...")
    html_files = list(REPO_PATH.glob("*.html"))
    print(f"[OK] 找到 {len(html_files)} 個 HTML 檔案")
    print()

    all_css = set()
    all_js = set()
    all_external = set()

    for html_file in html_files:
        css, js, ext = extract_resources_from_html(html_file)
        all_css.update(css)
        all_js.update(js)
        all_external.update(ext)

    # 只保留本站資源
    local_css = [c for c in all_css if not c.startswith('http') or 'medatatw.com' in c]
    local_js = [j for j in all_js if not j.startswith('http') or 'medatatw.com' in j]

    print(f"[OK] 統計完成：")
    print(f"  - CSS 檔案：{len(local_css)} 個")
    print(f"  - JS 檔案：{len(local_js)} 個")
    print(f"  - 外部依賴：{len(all_external)} 個")
    print()

    # Step 2: 測試 CSS 檔案可訪問性
    print("【Step 2】測試 CSS 檔案可訪問性...")
    for css_ref in sorted(set(local_css)):
        url = normalize_url(css_ref)
        status, content_type, cache_control, error = test_url(url)

        results["css_files"][css_ref] = {
            "url": url,
            "status": status,
            "content_type": content_type,
            "cache_control": cache_control,
            "ok": status == 200
        }

        if status == 200:
            print(f"[OK] {css_ref}")
        else:
            print(f"[FAIL] {css_ref} - HTTP {status}")
            results["issues"].append(f"❌ CSS 無法訪問: {css_ref} (HTTP {status})")
    print()

    # Step 3: 測試 JS 檔案可訪問性
    print("【Step 3】測試 JS 檔案可訪問性...")
    for js_ref in sorted(set(local_js)):
        url = normalize_url(js_ref)
        status, content_type, cache_control, error = test_url(url)

        results["js_files"][js_ref] = {
            "url": url,
            "status": status,
            "content_type": content_type,
            "cache_control": cache_control,
            "ok": status == 200
        }

        if status == 200:
            print(f"[OK] {js_ref}")
        else:
            print(f"[FAIL] {js_ref} - HTTP {status}")
            results["issues"].append(f"❌ JS 無法訪問: {js_ref} (HTTP {status})")
    print()

    # Step 4: 外部資源清單
    print("【Step 4】外部資源依賴清單...")
    results["external_deps"] = sorted(list(all_external))
    if all_external:
        for ext in sorted(all_external):
            print(f"  - {ext}")
    else:
        print("  [OK] 無外部依賴（良好）")
    print()

    # Step 5: 頁面功能元素統計
    print("【Step 5】頁面功能元素統計...")
    charset_ok = sum(1 for p in results["page_checks"].values() if p["charset"])
    viewport_ok = sum(1 for p in results["page_checks"].values() if p["viewport"])
    favicon_ok = sum(1 for p in results["page_checks"].values() if p["favicon"])
    ga_ok = sum(1 for p in results["page_checks"].values() if p["google_analytics"])
    search_pages = sum(1 for p in results["page_checks"].values() if p["has_search"])

    total_pages = len(results["page_checks"])
    print(f"  - UTF-8 Charset: {charset_ok}/{total_pages} ({charset_ok/total_pages*100:.1f}%)")
    print(f"  - Viewport Meta: {viewport_ok}/{total_pages} ({viewport_ok/total_pages*100:.1f}%)")
    print(f"  - Favicon: {favicon_ok}/{total_pages} ({favicon_ok/total_pages*100:.1f}%)")
    print(f"  - Google Analytics: {ga_ok}/{total_pages} ({ga_ok/total_pages*100:.1f}%)")
    print(f"  - 包含搜尋功能: {search_pages}/{total_pages}")
    print()

    # Step 6: 測試首頁 Response Headers
    print("【Step 6】測試首頁 Response Headers...")
    home_url = BASE_URL + "/index.html"
    status, content_type, cache_control, error = test_url(home_url)
    print(f"  URL: {home_url}")
    print(f"  Status: {status}")
    print(f"  Content-Type: {content_type}")
    print(f"  Cache-Control: {cache_control}")
    print()

    # 生成總結
    css_pass = sum(1 for v in results["css_files"].values() if v["ok"])
    css_total = len(results["css_files"])
    js_pass = sum(1 for v in results["js_files"].values() if v["ok"])
    js_total = len(results["js_files"])

    results["summary"] = {
        "css_pass_rate": f"{css_pass}/{css_total} ({css_pass/css_total*100:.1f}%)" if css_total > 0 else "N/A",
        "js_pass_rate": f"{js_pass}/{js_total} ({js_pass/js_total*100:.1f}%)" if js_total > 0 else "N/A",
        "total_issues": len(results["issues"]),
        "verdict": "PASS" if len(results["issues"]) == 0 and css_pass == css_total and js_pass == js_total else "FAIL"
    }

    # 輸出報告
    print("=" * 80)
    print("【驗證結果總結】")
    print("=" * 80)
    print(f"CSS 檔案測試: {results['summary']['css_pass_rate']}")
    print(f"JS 檔案測試: {results['summary']['js_pass_rate']}")
    print(f"外部資源依賴: {len(results['external_deps'])} 個")
    print(f"總問題數: {results['summary']['total_issues']}")
    print()

    if results["issues"]:
        print("【問題清單】")
        for issue in results["issues"]:
            print(issue)
        print()

    print("=" * 80)
    print(f"最終判定: {results['summary']['verdict']}")
    print("=" * 80)
    print()

    # 儲存 JSON 報告
    report_file = REPO_PATH / f"official_website_qa_v4_report_{Path(__file__).stem.split('_')[-1]}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[OK] 詳細報告已儲存: {report_file}")

if __name__ == "__main__":
    main()
