#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冪等移除官網全站已過期 7/10 直播公告彈窗片段（Live26-07 存活曲線）。
雙錨點精確定位，找不到就 skip，不誤刪上下相鄰的 nlpop / footer 片段。
用法：
    python remove_annc.py --dry-run   # 預覽
    python remove_annc.py             # 正式套用
"""
import sys
import glob
import os

REPO = r"C:\Users\cshow\Desktop\medatatw_github"
ITEM_ANCHOR = "item=live-km0710"
END_MARKER = "匯東華公告彈窗片段結束（Live26-07）"

def process(text):
    """回傳 (new_text, changed_bool, note)。找不到片段回傳原文 + skip。"""
    idx_item = text.find(ITEM_ANCHOR)
    if idx_item == -1:
        return text, False, "skip: 無 item=live-km0710"
    # 以「真實公告塊」為準：annc-root 與結束 marker 必須各恰好 1 個
    # （item 註解行可能被重複注入，但只要塊本體唯一即安全）
    if text.count('id="hdh-annc-root"') != 1:
        return text, False, "SKIP-WARN: hdh-annc-root 出現次數 != 1"
    if text.count(END_MARKER) != 1:
        return text, False, "SKIP-WARN: 結束 marker 出現次數 != 1"

    # 起點：從 item 位置往前找最近的 <!--（即 @hdh-expire 註解起點）
    block_start = text.rfind("<!--", 0, idx_item)
    if block_start == -1:
        return text, False, "SKIP-WARN: 找不到起點 <!--"
    # 安全檢查：起點到 item 之間必須含 @hdh-expire（確認鎖定正確註解）
    if "@hdh-expire" not in text[block_start:idx_item]:
        return text, False, "SKIP-WARN: 起點註解非 @hdh-expire"

    # 終點：item 之後找「片段結束」marker，再找其後第一個 -->
    idx_end_marker = text.find(END_MARKER, idx_item)
    if idx_end_marker == -1:
        return text, False, "SKIP-WARN: 找不到結束 marker"
    idx_close = text.find("-->", idx_end_marker)
    if idx_close == -1:
        return text, False, "SKIP-WARN: 結束 marker 後無 -->"
    block_end = idx_close + len("-->")

    # 安全檢查：移除塊內不得含 nlpop-root / footer-root（防超刪）
    block = text[block_start:block_end]
    if "hdh-nlpop-root" in block or "hdh-footer-root" in block:
        return text, False, "SKIP-WARN: 移除塊內含 nlpop/footer root，中止防超刪"
    if "hdh-annc-root" not in block:
        return text, False, "SKIP-WARN: 移除塊內無 hdh-annc-root"

    # 吃掉緊接的一個換行（避免留白行）
    after = block_end
    if text[after:after+2] == "\r\n":
        after += 2
    elif text[after:after+1] == "\n":
        after += 1

    new_text = text[:block_start] + text[after:]
    return new_text, True, "removed"

def main():
    dry = "--dry-run" in sys.argv
    files = sorted(glob.glob(os.path.join(REPO, "*.html")))
    changed = skipped = warned = 0
    warn_list = []
    for f in files:
        base = os.path.basename(f)
        if base.startswith("_demo"):
            # 未追蹤 demo 檔，out-of-scope，不動
            continue
        with open(f, "r", encoding="utf-8") as fh:
            text = fh.read()
        new_text, ch, note = process(text)
        if ch:
            changed += 1
            if not dry:
                with open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new_text)
        else:
            if note.startswith("SKIP-WARN"):
                warned += 1
                warn_list.append((os.path.basename(f), note))
            else:
                skipped += 1
    print(f"{'[DRY-RUN] ' if dry else '[APPLIED] '}changed={changed} skipped(no-fragment)={skipped} warned={warned}")
    for name, note in warn_list:
        print(f"  WARN {name}: {note}")

if __name__ == "__main__":
    main()
