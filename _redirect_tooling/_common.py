#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_common.py — build_redirects.py 與 test_redirects.py 共用的常數與函式。

放在這裡的東西必須是「兩支腳本都要用、且必須保持完全一致」的邏輯：
    - MANAGED_MARKER：build 寫入時用來標記「本工具管理」，test 驗證時
      也要用同一個字串去檢查，兩邊如果各自硬編碼一份、日後很容易改一邊
      忘了改另一邊，造成誤判。
    - reconfigure_utf8_streams()：Windows 主控台編碼修正，兩支腳本都需要。
    - js_escape_target()：寫入 <script> 內的 target 字串跳脫規則。
      build 用它「寫」，test 用它「驗證寫得對不對」，必須是同一份函式，
      不能各寫一份，否則其中一邊改了跳脫規則、另一邊沒跟著改，
      驗證就會失去意義（誤判 PASS 或誤判 FAIL）。

用法：
    import 前，兩支腳本檔案必須跟本檔放在同一個目錄
    （_redirect_tooling/）。Python 執行 `python _redirect_tooling/build_redirects.py`
    時，直譯器會自動把「腳本所在目錄」加進 sys.path[0]，
    所以 `import _common` 不需要額外處理 sys.path 就能解析，
    不論目前工作目錄（cwd）是 repo root 還是別的地方都一樣。
"""

from __future__ import annotations

import json
import sys

# 本工具產生的 index.html 一律帶這個管理標記；覆寫/刪除舊資料夾前都要先
# 檢查此標記是否存在，才允許覆寫/刪除，避免動到被人工接手改過的頁面。
MANAGED_MARKER = "hdh-redirect-tooling:managed"


def reconfigure_utf8_streams() -> None:
    """
    Windows 主控台預設可能是 cp950 等非 UTF-8 編碼，中文輸出會亂碼。
    這裡盡量把 stdout/stderr 重新設為 UTF-8；失敗也不影響檔案寫入本身
    （所有檔案一律以 encoding="utf-8" 明確寫入，不受此設定影響）。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def js_escape_target(target: str) -> str:
    """
    產生可安全內嵌在 <script>...</script> 區塊中的 JS 字串常值。

    背景（安全性修復 H-1）：json.dumps() 預設不會跳脫 `<` `>` `&`，
    若 target 內含 `</script>` 字樣（例如 target 剛好帶有這段查詢字串
    或惡意輸入 https://x.example/</script><script>alert(1)</script>），
    瀏覽器的 HTML 解析器會在「解析 JS 之前」就依字面尋找 `</script`
    來結束 <script> 區塊，導致 script 提早關閉、後面的內容被當成新的
    HTML/JS 執行 —— 這是典型的 script context breakout。

    做法：先用 json.dumps() 產生標準 JSON 字串常值（含跳脫引號、反斜線等），
    再把其中的 `<` `>` `&` 換成 Unicode escape（\\u003c \\u003e \\u0026）。
    這在 JS 字串常值語法中是完全合法、值不變的寫法，但輸出的原始位元組
    不再包含 `<` `>` `&`，瀏覽器的 HTML 解析器就不可能誤判為標籤邊界。
    """
    encoded = json.dumps(target)
    encoded = encoded.replace("<", "\\u003c")
    encoded = encoded.replace(">", "\\u003e")
    encoded = encoded.replace("&", "\\u0026")
    return encoded
