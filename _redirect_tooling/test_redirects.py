#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_redirects.py — 驗證 build_redirects.py 的產出是否正確

用法：
    python test_redirects.py [--repo-root PATH] [--manifest PATH]

檢查項目（針對 manifest.json 內每一個 managed path）：
    1. {repo_root}/{path}/index.html 是否存在
    2. 內容是否含本工具管理標記（MANAGED_MARKER）
    3. 四種轉址機制是否都「在正確的標籤上下文內」指向 redirects.json 中
       對應的 target：
         - <meta http-equiv="refresh" content="0; url=TARGET">
         - <link rel="canonical" href="TARGET">
         - <script> 區塊內的 location.replace(JS_ESCAPED_TARGET)
           （用與 build_redirects.py 完全相同的 js_escape_target() 跳脫，
           確保這裡驗證的就是實際會被瀏覽器執行的跳脫後字串，而不是
           跳脫前的原始 target —— 否則含 </script> 的 target 會被
           build 正確跳脫，卻在這裡被誤判 FAIL）
         - <noscript> 區塊內 <a href="TARGET"> 可點擊連結
    4. 全文只出現一次「</script」字面序列（H-1 script-breakout 迴歸測試：
       若 target 未正確跳脫，含 </script> 的惡意/特殊 target 會讓這個
       字面序列出現第二次）

輸出 PASS/FAIL 表與總結，全數 PASS 才會以 exit code 0 結束
（供 CI 在自動 commit 前擋下有問題的產出）。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from _common import MANAGED_MARKER, js_escape_target, reconfigure_utf8_streams

reconfigure_utf8_streams()


def load_json(path: Path, label: str) -> object:
    if not path.exists():
        print(f"[ERROR] 找不到 {label}：{path}", file=sys.stderr)
        sys.exit(1)
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] {label} 解析失敗：{e}", file=sys.stderr)
        sys.exit(1)


def check_one(repo_root: Path, path: str, target: str) -> tuple[bool, str]:
    index_path = repo_root / path / "index.html"

    if not index_path.exists():
        return False, f"index.html 不存在（{index_path}）"

    try:
        content = index_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return False, f"讀取失敗：{e}"

    if MANAGED_MARKER not in content:
        return False, "缺少管理標記（MANAGED_MARKER），可能不是本工具產生的頁面"

    safe_target_attr = html.escape(target, quote=True)
    js_target = js_escape_target(target)

    # 四種轉址機制各自用「鎖定標籤上下文」的正則檢查，而不是單純
    # 「字串是否出現在檔案某處」，避免誤判（例如 target 字串剛好出現在
    # 別的地方、或跳脫方式不對但恰好子字串相符）。
    checks = {
        "meta refresh": re.search(
            r'<meta\s+http-equiv="refresh"\s+content="0;\s*url='
            + re.escape(safe_target_attr)
            + r'"\s*>',
            content,
        ),
        "link canonical": re.search(
            r'<link\s+rel="canonical"\s+href="' + re.escape(safe_target_attr) + r'"\s*>',
            content,
        ),
        "script location.replace": re.search(
            r"<script>.*?location\.replace\("
            + re.escape(js_target)
            + r"\).*?</script>",
            content,
            re.DOTALL,
        ),
        "noscript 連結": re.search(
            r"<noscript>.*?<a\s+href=\""
            + re.escape(safe_target_attr)
            + r"\">.*?</a>.*?</noscript>",
            content,
            re.DOTALL,
        ),
    }

    failed = [name for name, m in checks.items() if not m]
    if failed:
        return False, f"target 不一致（缺少：{', '.join(failed)}）"

    # 額外的 script-breakout 防護檢查（H-1 迴歸測試用）：
    # 確認整份文件中，「</script」這個會被 HTML 解析器辨識為關閉標籤的
    # 字面序列，只出現一次（就是合法的關閉標籤本身）。如果 target 內含
    # </script> 卻沒有正確跳脫，這裡會抓到第二次出現。
    script_close_occurrences = len(re.findall(r"</script", content, re.IGNORECASE))
    if script_close_occurrences != 1:
        return False, (
            f"偵測到 {script_close_occurrences} 次 '</script' 字樣"
            "（應恰好 1 次），疑似 target 未正確跳脫導致 script 標籤被提早關閉"
        )

    return True, "OK"


def main() -> int:
    parser = argparse.ArgumentParser(description="驗證轉址頁產出")
    default_script_dir = Path(__file__).resolve().parent
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=default_script_dir.parent,
        help="repo 根目錄（預設為本腳本所在目錄的上一層）",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_script_dir / "manifest.json",
        help="manifest.json 路徑",
    )
    parser.add_argument(
        "--mirror-json",
        type=Path,
        default=default_script_dir / "redirects.json",
        help="redirects.json 路徑（提供各 path 的 target 供比對）",
    )
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    manifest = load_json(args.manifest, "manifest.json")
    mirror = load_json(args.mirror_json, "redirects.json")

    target_by_path = {row["path"]: row["target"] for row in mirror}

    managed_paths = manifest.get("managed_paths", [])
    if not managed_paths:
        print("manifest.json 中沒有任何 managed_paths，無項目可驗證。")
        return 0

    print(f"repo-root : {repo_root}")
    print(f"共 {len(managed_paths)} 筆待驗證")
    print()
    print(f"{'狀態':<6}{'PATH':<24}說明")
    print("-" * 70)

    pass_count = 0
    fail_count = 0

    for path in managed_paths:
        target = target_by_path.get(path)
        if target is None:
            print(f"{'FAIL':<6}{path:<24}redirects.json 中找不到對應 target")
            fail_count += 1
            continue

        ok, msg = check_one(repo_root, path, target)
        status = "PASS" if ok else "FAIL"
        print(f"{status:<6}{path:<24}{msg}")
        if ok:
            pass_count += 1
        else:
            fail_count += 1

    print("-" * 70)
    print(f"總結：{pass_count} PASS / {fail_count} FAIL / 共 {len(managed_paths)} 筆")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
