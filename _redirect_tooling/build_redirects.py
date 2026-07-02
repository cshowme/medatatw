#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_redirects.py — 靜態轉址頁產生器（GitHub Pages 用）

用途：
    讀取 _redirect_tooling/redirects.csv，為每一列產生一個根目錄 vanity 路徑
    （例如 medatatw.com/signup -> /signup/index.html），並用 manifest.json
    白名單機制追蹤「本工具管理過的資料夾」，確保：
        1. 絕不覆蓋 / 刪除既有網站內容（碰撞檢查會直接中止）
        2. 只刪除「曾經由本工具建立、且目前已不在 redirects.csv 內」的資料夾
        3. 覆寫或刪除前都會再次驗證該資料夾的 index.html 帶有本工具的管理
           標記，避免動到被人工接手改過的頁面

用法：
    python build_redirects.py [--repo-root PATH] [--csv PATH] [--dry-run]
                               [--allow-mass-delete]

    預設 --repo-root 為本檔案所在目錄的上一層（也就是 repo 根目錄），
    --dry-run 只做驗證與列印計畫，不寫入/刪除任何檔案。

安全機制（重要）：
    - path 只允許單一層級（不含斜線），長度上限 64 字元，對應「根目錄
      vanity 路徑」設計，避免巢狀路徑造成更複雜的碰撞判斷
    - 碰撞檢查：path 不可與 repo root 既有檔案/資料夾同名（不分大小寫，
      且會比對 .html 檔案去除副檔名後的名稱），也不可使用保留字
      （見 RESERVED_NAMES），除非該名稱是本工具上一輪已經管理的資料夾
      （允許重跑/更新）
    - 覆寫保護：即使 path 通過碰撞檢查，若該資料夾已存在 index.html 但
      缺少管理標記（可能被人工接手），一律跳過不覆寫，並印出警告
    - 大量刪除保護：單次刪除超過已管理路徑 50%（且刪除數 > 1）時，
      需加上 --allow-mass-delete 才會放行，避免 CSV 誤刪/誤清空導致
      一次砍光所有轉址頁
    - manifest.json 內每一項 managed_paths 都會重新跑一次合法性檢查，
      不合法（例如被竄改成路徑穿越字串）者會被剔除並警告，不會被用來
      組出 repo_root 以外的路徑
    - 產生 touched_paths.json，紀錄本次「新增/更新/刪除」的根目錄名稱，
      供 CI 的自動 commit 步驟精準只加入這些路徑，不動到其他網站檔案
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from _common import (
    MANAGED_MARKER,
    compute_display_title,
    js_escape_target,
    reconfigure_utf8_streams,
)

reconfigure_utf8_streams()

# path 驗證規則：僅允許小寫英數字與連字號，長度 1-64，不可包含斜線
# （對應「根目錄 vanity 路徑」設計，避免巢狀路徑造成更複雜的碰撞判斷）
PATH_MAX_LENGTH = 64
PATH_PATTERN = re.compile(r"^(?=.{1,%d}$)[a-z0-9]+(?:-[a-z0-9]+)*$" % PATH_MAX_LENGTH)

# 保留字：即使碰撞檢查當下 repo root 沒有同名項目，這些名稱也一律禁止
# 拿來當 vanity path，避免未來與 GitHub Pages / repo 慣用檔案衝突
# （不分大小寫比對）。
RESERVED_NAMES = {
    "index",
    "assets",
    "cname",
    "robots",
    "sitemap",
    "404",
    ".github",
    ".nojekyll",
    "_redirect_tooling",
    "__system",
    "__edited_images",
    "_imagecache",
    "search-index",
    "pagefind",
}

# 大量刪除保護：單次刪除超過「已管理路徑」這個比例（且刪除數 > 1）時，
# 需要 --allow-mass-delete 才放行。
MASS_DELETE_RATIO = 0.5

BRAND_RED = "#B82226"

# 社群預覽（OG / Twitter Card）用的固定內容。這些是本公司自訂的靜態文案，
# 不是使用者輸入，但仍統一走 html.escape() 輸出（見 render_redirect_html），
# 避免日後這些常數被改成可參數化來源時忘記補上跳脫。
OG_SITE_NAME = "匯東華統計顧問有限公司"
OG_DESCRIPTION = "統計分析・教育培訓・數據串接・真實世界研究｜匯東華統計顧問"
TWITTER_DESCRIPTION = "統計分析・教育培訓・數據服務｜匯東華統計顧問"
OG_IMAGE_URL = "https://www.medatatw.com/assets/og-card.png"
OG_IMAGE_ALT = "匯東華統計顧問"


class ValidationError(Exception):
    """CSV 內容或環境驗證失敗時拋出，訊息會直接印給使用者看。"""


def is_valid_path(path: str) -> bool:
    return bool(PATH_PATTERN.match(path))


def is_valid_target(target: str) -> bool:
    try:
        parsed = urlparse(target)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def load_csv_rows(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        raise ValidationError(f"找不到 CSV 檔案：{csv_path}")

    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required_cols = {"path", "target", "note"}
        if reader.fieldnames is None or not required_cols.issubset(set(reader.fieldnames)):
            raise ValidationError(
                f"CSV 欄位不正確，需要 {sorted(required_cols)}，"
                f"實際讀到 {reader.fieldnames}"
            )
        for line_no, row in enumerate(reader, start=2):  # 從第 2 行開始（第 1 行是表頭）
            path = (row.get("path") or "").strip()
            target = (row.get("target") or "").strip()
            note = (row.get("note") or "").strip()
            if not path and not target:
                # 允許 CSV 尾端有空白列
                continue
            rows.append({"path": path, "target": target, "note": note, "line": line_no})
    return rows


def validate_rows(rows: list[dict]) -> None:
    errors: list[str] = []
    seen_paths: dict[str, int] = {}

    for row in rows:
        line_no = row["line"]
        path = row["path"]
        target = row["target"]

        if not path:
            errors.append(f"第 {line_no} 行：path 為空")
            continue
        if len(path) > PATH_MAX_LENGTH:
            errors.append(
                f"第 {line_no} 行：path「{path}」長度 {len(path)} 超過上限 "
                f"{PATH_MAX_LENGTH} 字元"
            )
            continue
        if not is_valid_path(path):
            errors.append(
                f"第 {line_no} 行：path「{path}」不合法"
                "（僅允許小寫英數字與連字號，不可含斜線/空白/特殊字元）"
            )
            continue

        key = path.lower()
        if key in seen_paths:
            errors.append(
                f"第 {line_no} 行：path「{path}」與第 {seen_paths[key]} 行重複"
            )
        else:
            seen_paths[key] = line_no

        if key in RESERVED_NAMES:
            errors.append(
                f"第 {line_no} 行：path「{path}」是保留字，不可使用"
            )

        if not target:
            errors.append(f"第 {line_no} 行：target 為空（path={path}）")
        elif not is_valid_target(target):
            errors.append(
                f"第 {line_no} 行：target「{target}」不是合法的 http(s) URL（path={path}）"
            )

    if errors:
        raise ValidationError("CSV 驗證失敗：\n  - " + "\n  - ".join(errors))


def load_manifest(manifest_path: Path) -> dict:
    """
    讀取 manifest.json。每一項 managed_paths 都會重新驗證是否符合
    is_valid_path（M-2 修復）：manifest.json 若被竄改或手動誤改成
    「../../etc」之類的字串，之後 repo_root / path 組出來的路徑就可能
    跑到 repo 之外，remove_stale_dir() 又會對它做 shutil.rmtree()，
    等於任意路徑刪除。不合法的項目一律剔除並印警告，絕不放進
    previously_managed，避免被用來組出 repo_root 以外的路徑。
    """
    if not manifest_path.exists():
        return {"managed_paths": []}
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValidationError(f"manifest.json 讀取失敗（可能損毀）：{e}")
    if "managed_paths" not in data or not isinstance(data["managed_paths"], list):
        raise ValidationError("manifest.json 格式不正確：缺少 managed_paths 陣列")

    valid_paths: list[str] = []
    for p in data["managed_paths"]:
        if isinstance(p, str) and is_valid_path(p):
            valid_paths.append(p)
        else:
            print(
                f"[WARN] manifest.json 內有不合法的 managed path「{p}」，"
                "已忽略（不會被用於覆寫/刪除判斷，避免路徑穿越風險）",
                file=sys.stderr,
            )
    data["managed_paths"] = valid_paths
    return data


def build_protected_names(repo_root: Path, previously_managed: set[str]) -> set[str]:
    """
    列出 repo root 目前所有「非本工具管理」的項目名稱（小寫），
    含 .html 檔案去除副檔名後的名稱，以及保留字清單，用於碰撞檢查。
    """
    protected: set[str] = {name.lower() for name in RESERVED_NAMES}
    previously_managed_lower = {p.lower() for p in previously_managed}

    for entry in repo_root.iterdir():
        name = entry.name
        name_lower = name.lower()

        # 之前由本工具建立的資料夾，允許本次重新使用（更新內容）
        if entry.is_dir() and name_lower in previously_managed_lower:
            continue

        protected.add(name_lower)

        if entry.is_file() and entry.suffix.lower() == ".html":
            protected.add(entry.stem.lower())

    return protected


def check_collisions(rows: list[dict], protected: set[str]) -> None:
    errors = []
    for row in rows:
        path_lower = row["path"].lower()
        if path_lower in protected:
            errors.append(
                f"path「{row['path']}」與 repo root 既有檔案/資料夾同名"
                "（或為保留字），為避免覆蓋既有網站內容已中止建置"
            )
    if errors:
        raise ValidationError("碰撞檢查失敗：\n  - " + "\n  - ".join(errors))


def check_mass_delete(stale_paths: list[str], previously_managed_count: int, allow: bool) -> None:
    """
    大量刪除保護（L-2）：單次刪除超過已管理路徑一半（且刪除數 > 1）時，
    需要 --allow-mass-delete 才放行，避免 CSV 被清空/誤刪導致一次砍光
    所有轉址頁而沒人注意到。
    """
    if allow or previously_managed_count == 0:
        return
    if len(stale_paths) <= 1:
        return
    if len(stale_paths) > previously_managed_count * MASS_DELETE_RATIO:
        raise ValidationError(
            "大量刪除保護觸發：本次將刪除 "
            f"{len(stale_paths)} / {previously_managed_count} "
            f"筆已管理的轉址頁（超過 {int(MASS_DELETE_RATIO * 100)}%），"
            "為避免誤刪已中止建置。\n  - 將被刪除的 path："
            + ", ".join(sorted(stale_paths, key=str.lower))
            + "\n  - 若確認要大量刪除，請加上 --allow-mass-delete 重新執行"
        )


def render_redirect_html(path: str, target: str, note: str) -> str:
    # 屬性值一律用 html.escape(quote=True)：target / note 都是 CSV 提供、
    # 不受信任的輸入，quote=True 才會把 `"` 也跳脫成 &quot;，避免在
    # content="..." / href="..." 這類屬性中提早結束引號、插入額外屬性
    # 或跑出屬性範圍（attribute breakout）。
    def esc(value: str) -> str:
        return html.escape(value, quote=True)

    safe_target_attr = esc(target)
    safe_target_text = html.escape(target, quote=False)
    safe_note = html.escape(note, quote=False) if note else ""
    # H-1 修復：<script> 內嵌的 target 必須用 JS-safe 跳脫，避免 target
    # 內含 </script> 之類字樣時提早關閉 script 區塊（context breakout）。
    js_target = js_escape_target(target)

    note_html = f'<p class="note">{safe_note}</p>' if safe_note else ""

    # 社群預覽（OG / Twitter Card）：title 用 note（CSV 第 3 欄）當頁面
    # 名稱，note 留空則回退公司名稱（compute_display_title，與
    # test_redirects.py 共用同一份邏輯，見 _common.py）。所有塞進屬性的
    # 值一律 esc()，包含公司自訂的靜態文案，避免日後改參數化來源時
    # 忘記補上跳脫。
    display_title = compute_display_title(note)
    safe_display_title = esc(display_title)
    title_text = f"{safe_display_title} ｜ 匯東華統計顧問" if note and note.strip() else safe_display_title

    safe_og_site_name = esc(OG_SITE_NAME)
    safe_og_description = esc(OG_DESCRIPTION)
    safe_twitter_description = esc(TWITTER_DESCRIPTION)
    safe_og_image = esc(OG_IMAGE_URL)
    safe_og_image_alt = esc(OG_IMAGE_ALT)

    return f"""<!DOCTYPE html>
<html lang="zh-Hant-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="0; url={safe_target_attr}">
<link rel="canonical" href="{safe_target_attr}">
<meta name="robots" content="noindex">
<title>{title_text}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="{safe_og_site_name}">
<meta property="og:title" content="{safe_display_title}">
<meta property="og:description" content="{safe_og_description}">
<meta property="og:url" content="{safe_target_attr}">
<meta property="og:image" content="{safe_og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{safe_og_image_alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_display_title}">
<meta name="twitter:description" content="{safe_twitter_description}">
<meta name="twitter:image" content="{safe_og_image}">
<!-- {MANAGED_MARKER} -->
<!-- source-path: {html.escape(path, quote=False)} -->
<style>
  html, body {{
    margin: 0;
    padding: 0;
    height: 100%;
    background: #FFFFFF;
    font-family: "Microsoft JhengHei", "PingFang TC", -apple-system, sans-serif;
  }}
  .redirect-wrap {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    text-align: center;
    padding: 24px;
    box-sizing: border-box;
  }}
  .brand {{
    color: {BRAND_RED};
    font-size: 20px;
    font-weight: bold;
    letter-spacing: 2px;
    margin-bottom: 16px;
  }}
  .spinner {{
    width: 28px;
    height: 28px;
    border: 3px solid #F0DCDD;
    border-top-color: {BRAND_RED};
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 16px;
  }}
  @keyframes spin {{
    to {{ transform: rotate(360deg); }}
  }}
  .msg {{
    color: #333333;
    font-size: 15px;
    margin: 4px 0;
  }}
  .note {{
    color: #888888;
    font-size: 13px;
    margin-top: 8px;
  }}
  a {{
    color: {BRAND_RED};
    word-break: break-all;
  }}
</style>
<script>
  location.replace({js_target});
</script>
</head>
<body>
  <div class="redirect-wrap">
    <div class="brand">匯東華統計顧問</div>
    <div class="spinner" aria-hidden="true"></div>
    <p class="msg">頁面轉址中，請稍候...</p>
    {note_html}
    <noscript>
      <p class="msg">請點擊以繼續：<a href="{safe_target_attr}">{safe_target_text}</a></p>
    </noscript>
  </div>
</body>
</html>
"""


def has_managed_marker(dir_path: Path) -> bool:
    """
    True：資料夾內的 index.html 存在且帶有本工具的管理標記（可安全覆寫/刪除）。
    False：資料夾內沒有 index.html（沒有既有內容需要保護），或
           index.html 存在但缺少管理標記（判斷為人工接手，需要保護）。

    呼叫端要自行分辨這兩種 False 的情境：
        - 資料夾/檔案根本不存在 → 通常代表「全新建立」，可放行
        - 資料夾存在但標記缺失 → 一律保護，不覆寫也不刪除
    """
    index_path = dir_path / "index.html"
    if not index_path.exists():
        return False
    try:
        content = index_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return MANAGED_MARKER in content


def write_redirect_page(repo_root: Path, path: str, target: str, note: str, dry_run: bool) -> bool:
    """
    回傳是否實際（或模擬）寫入成功；False 代表因覆寫保護而跳過。
    """
    target_dir = repo_root / path
    index_path = target_dir / "index.html"

    # M-1 修復：若資料夾已存在且已有 index.html，覆寫前必須確認帶有管理
    # 標記；若標記缺失（可能被人工接手改成別的用途），一律跳過、不得
    # 靜默覆寫，交由人工確認處理。資料夾/檔案不存在則視為全新建立，
    # 沒有既有內容需要保護，直接放行。
    if index_path.exists() and not has_managed_marker(target_dir):
        print(
            f"  [SKIP-WRITE] {index_path} 已存在但缺少管理標記，"
            "判斷可能已被人工接手修改，為安全起見不予覆寫，請手動確認後處理。"
        )
        return False

    content = render_redirect_html(path, target, note)

    if dry_run:
        print(f"  [DRY-RUN] 將寫入：{index_path}")
        return True

    target_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content, encoding="utf-8", newline="\n")
    print(f"  [WRITE] {index_path}")
    return True


def remove_stale_dir(repo_root: Path, path: str, dry_run: bool) -> bool:
    """回傳是否實際（或模擬）刪除成功。"""
    target_dir = repo_root / path
    if not target_dir.exists():
        return False

    if not has_managed_marker(target_dir):
        print(
            f"  [SKIP-DELETE] {target_dir} 已不在 redirects.csv 中，"
            "但 index.html 缺少管理標記，判斷可能已被人工接手修改，"
            "為安全起見不予刪除，請手動確認後處理。"
        )
        return False

    if dry_run:
        print(f"  [DRY-RUN] 將刪除：{target_dir}")
        return True

    shutil.rmtree(target_dir)
    print(f"  [DELETE] {target_dir}")
    return True


def write_json_artifact(path: Path, data, dry_run: bool, label: str) -> None:
    """
    共用的 JSON 產出邏輯（manifest.json / redirects.json / touched_paths.json
    都是同樣的「dry-run 只印計畫，否則寫檔並印 [WRITE]」模式，抽出來避免
    三段幾乎相同的程式碼各自重複）。
    """
    if dry_run:
        print(f"[DRY-RUN] 將寫入 {label}：{json.dumps(data, ensure_ascii=False)}")
        return
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"[WRITE] {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="靜態轉址頁產生器")
    default_script_dir = Path(__file__).resolve().parent
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=default_script_dir.parent,
        help="repo 根目錄（預設為本腳本所在目錄的上一層）",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=default_script_dir / "redirects.csv",
        help="redirects.csv 路徑",
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
        help="redirects.json 鏡像輸出路徑",
    )
    parser.add_argument(
        "--touched-paths",
        type=Path,
        default=default_script_dir / "touched_paths.json",
        help="本次異動的根目錄名稱清單輸出路徑（供 CI 精準 git add 用）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只驗證並列印計畫，不寫入/刪除任何檔案",
    )
    parser.add_argument(
        "--allow-mass-delete",
        action="store_true",
        help="允許單次刪除超過已管理路徑 50%% 的大量刪除（預設會中止並要求確認）",
    )
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    csv_path: Path = args.csv.resolve()
    manifest_path: Path = args.manifest.resolve()

    if not repo_root.is_dir():
        print(f"[ERROR] repo-root 不存在或不是資料夾：{repo_root}", file=sys.stderr)
        return 1

    try:
        rows = load_csv_rows(csv_path)
        validate_rows(rows)

        manifest = load_manifest(manifest_path)
        previously_managed: set[str] = set(manifest["managed_paths"])

        protected = build_protected_names(repo_root, previously_managed)
        check_collisions(rows, protected)

        new_paths = [row["path"] for row in rows]
        new_paths_set = {p.lower() for p in new_paths}
        stale_original = [p for p in previously_managed if p.lower() not in new_paths_set]

        check_mass_delete(stale_original, len(previously_managed), args.allow_mass_delete)
    except ValidationError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    print(f"repo-root : {repo_root}")
    print(f"csv       : {csv_path}")
    print(f"manifest  : {manifest_path}")
    print(f"dry-run   : {args.dry_run}")
    print(f"共 {len(rows)} 筆轉址設定，先前管理 {len(previously_managed)} 筆")
    print()

    touched: set[str] = set()

    # 1) 建立 / 更新
    print("== 建立/更新轉址頁 ==")
    for row in rows:
        written = write_redirect_page(repo_root, row["path"], row["target"], row["note"], args.dry_run)
        if written:
            touched.add(row["path"])

    # 2) 刪除已不在 CSV 內、且確認是本工具管理的舊資料夾
    print()
    print("== 清理已移除的轉址頁 ==")
    if not stale_original:
        print("  （無）")
    for path in stale_original:
        removed = remove_stale_dir(repo_root, path, args.dry_run)
        if removed:
            touched.add(path)

    # 3) 寫入 manifest.json（白名單）
    manifest_out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_csv": str(csv_path.relative_to(repo_root)) if csv_path.is_relative_to(repo_root) else str(csv_path),
        "managed_paths": sorted(new_paths, key=str.lower),
    }
    print()
    write_json_artifact(manifest_path, manifest_out, args.dry_run, "manifest")

    # 4) 鏡像輸出 redirects.json
    mirror = [
        {"path": row["path"], "target": row["target"], "note": row["note"]}
        for row in rows
    ]
    write_json_artifact(args.mirror_json, mirror, args.dry_run, "鏡像 JSON")

    # 5) 寫入本次異動清單（供 CI 精準 git add）
    touched_sorted = sorted(touched, key=str.lower)
    write_json_artifact(args.touched_paths, touched_sorted, args.dry_run, "異動清單")

    print()
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
