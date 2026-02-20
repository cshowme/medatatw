#!/usr/bin/env python3
"""
medatatw_repo HTML 品質守門員
用途：pre-commit hook 或手動執行，檢查 HTML 頁面是否符合遷移規範。
建立日期：2026-02-20
依據：官網維護防呆小組會議決議 A1

使用方式：
  手動全站掃描：python scripts/check_html_quality.py --all
  只掃 staged 檔：python scripts/check_html_quality.py --staged
  掃指定檔案：  python scripts/check_html_quality.py file1.html file2.html
"""
import re, sys, os, subprocess, glob

# === 設定 ===
P_PREFIX = "P%3DMW800%2CMH800%2CF%2CBFFFFFF/"

IMAGES_NEEDING_P = [
    "%E7%B5%B1%E5%90%88%E5%88%86%E6%9E%90%E7%A0%94%E7%A9%B6%E5%B7%A5%E4%BD%9C%E5%9D%8A%E8%AA%B2%E7%A8%8B%E6%83%85%E5%BD%A21.png",
    "%E7%B5%B1%E5%90%88%E5%88%86%E6%9E%90%E7%A0%94%E7%A9%B6%E5%B7%A5%E4%BD%9C%E5%9D%8A%E8%AA%B2%E7%A8%8B%E6%83%85%E5%BD%A22.png",
    "%E7%B5%B1%E5%90%88%E5%88%86%E6%9E%90%E7%A0%94%E7%A9%B6%E5%B7%A5%E4%BD%9C%E5%9D%8A%E8%AC%9B%E7%BE%A9.png",
]


def check_file(filepath):
    """檢查單一 HTML 檔案，回傳錯誤列表"""
    errors = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (FileNotFoundError, UnicodeDecodeError) as e:
        return [f"{filepath}: 無法讀取 ({e})"]

    basename = os.path.basename(filepath)

    # 規則 1：禁止 margin:50px widget
    if '__iv_dynamic_widget" style="margin: 50px"' in content:
        errors.append(f"{basename}: __iv_dynamic_widget 未改為 display:none（仍為 margin:50px）")

    # 規則 2：必須有 pagefind-search.js
    if "pagefind-search.js" not in content:
        errors.append(f"{basename}: 缺少 pagefind-search.js 引入")

    # 規則 3：F26 頁面輪播圖路徑檢查
    if re.search(r"[fF]26", basename):
        for img_name in IMAGES_NEEDING_P:
            old_path = f'data-lazy="_imagecache/{img_name}"'
            new_path = f'data-lazy="_imagecache/{P_PREFIX}{img_name}"'
            if old_path in content and new_path not in content:
                short_name = img_name[-25:]
                errors.append(f"{basename}: 輪播圖缺 P= 前綴（...{short_name}）")

    return errors


def get_staged_html():
    """取得本次 commit 異動的 HTML 檔"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, check=True
        )
        return [f for f in result.stdout.strip().splitlines() if f.endswith(".html")]
    except subprocess.CalledProcessError:
        return []


def main():
    args = sys.argv[1:]

    if not args or "--staged" in args:
        # Pre-commit 模式：只掃 staged 檔案
        html_files = get_staged_html()
        mode = "staged"
    elif "--all" in args:
        # 全站掃描模式
        html_files = glob.glob("*.html")
        mode = "all"
    else:
        # 指定檔案模式
        html_files = [f for f in args if f.endswith(".html")]
        mode = "specified"

    if not html_files:
        if mode == "staged":
            # 沒有 HTML 檔案被修改，直接通過
            sys.exit(0)
        else:
            print("未找到任何 HTML 檔案")
            sys.exit(0)

    all_errors = []
    for f in html_files:
        errors = check_file(f)
        all_errors.extend(errors)

    if all_errors:
        print(f"\n[BLOCK] 官網頁面品質檢查失敗（{len(all_errors)} 個問題）：")
        for e in all_errors:
            print(f"  FAIL: {e}")
        print(f"\n提示：執行 python batch_fix_pages_20260220.py 修正後重新 stage。")
        print(f"參考：~/.claude/knowledge/website_page_migration_sop.md")
        sys.exit(1)
    else:
        print(f"[PASS] {len(html_files)} 個 HTML 檔通過品質檢查（模式：{mode}）")
        sys.exit(0)


if __name__ == "__main__":
    main()
