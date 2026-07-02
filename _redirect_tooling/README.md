# 靜態轉址產生系統（Static Redirect Generator）

用途：在 GitHub Pages 網站（medatatw.com）上建立「根目錄短網址」，
例如 `medatatw.com/signup` 轉到趣開課平台，而不需要動用 Cloudflare
或另外的轉址服務。

## 架構

```
repo root
├── redirects.csv            ← 你唯一需要維護的檔案
├── signup/index.html        ← 自動產生
├── line/index.html          ← 自動產生
├── survey/index.html        ← 自動產生
└── _redirect_tooling/
    ├── redirects.csv        ← 轉址對照表（唯一資料來源）
    ├── build_redirects.py   ← 產生轉址頁 + 維護白名單
    ├── test_redirects.py    ← 驗證產出內容正確
    ├── _common.py            ← build/test 共用常數與函式（管理標記、
    │                            UTF-8 輸出、JS 跳脫邏輯）
    ├── manifest.json         ← 自動產生：本工具目前管理的路徑清單
    ├── redirects.json        ← 自動產生：redirects.csv 的 JSON 鏡像
    ├── touched_paths.json    ← 自動產生：本次新增/更新/刪除的路徑
    └── README.md（本檔）
```

每個轉址頁（例如 `/signup/index.html`）同時具備四層轉址機制：
`<meta http-equiv="refresh">`（0 秒）+ `<link rel="canonical">` +
JavaScript `location.replace()` + `<noscript>` 可點擊連結，確保
即使瀏覽器不支援 JS 或使用者手速快，都能正確跳轉。頁面帶有匯東華
品牌色（`#B82226`）的極簡過場畫面。

## 日常維護流程（唯一需要做的事）

1. 打開 `_redirect_tooling/redirects.csv`
2. 新增/修改/刪除一列，格式：`path,target,note`
   - `path`：只能是小寫英數字 + 連字號，不可有斜線（例如 `signup`、`line-2026`）
   - `target`：完整 `http(s)://` 網址
   - `note`：中文備註，會顯示在轉址過場頁上（可留空）
3. `git commit` + `git push` 到 `main` 分支
4. GitHub Actions 會自動：build → 驗證 → 若全數通過才自動 commit + push 產出
5. 幾分鐘內 `medatatw.com/{path}` 即可生效

**你完全不需要手動執行 Python，也不需要手動建立資料夾。**

## 安全機制（為什麼這套系統不會弄壞既有網站）

1. **碰撞檢查（硬阻擋）**：`build_redirects.py` 在寫入前，會先掃描 repo
   root 目前所有檔案與資料夾名稱（含 `.html` 檔案去除副檔名後的名稱），
   若 CSV 中的任何 `path` 與既有項目同名（不分大小寫），會直接印出錯誤
   並以非 0 狀態碼中止，**不會寫入或刪除任何東西**。除了實際存在的
   檔案/資料夾，也內建一份**保留字黑名單**（`index`、`assets`、`cname`、
   `robots`、`sitemap`、`404`、`.github`、`.nojekyll`、
   `_redirect_tooling`、`__system`、`__edited_images`、`_imagecache`、
   `search-index`、`pagefind`，不分大小寫），這些名稱永遠不能拿來當
   vanity path，即使當下 repo root 還沒有同名項目。

2. **manifest.json 白名單**：每次 build 只會建立/更新/刪除「manifest.json
   記錄過的路徑」。凡不在白名單內的既有檔案/資料夾，一律不會被觸碰。
   manifest.json 內每一項路徑在讀取時都會重新驗證合法性（與 CSV 的
   path 規則相同）；不合法的項目（例如遭竄改成 `../../etc` 之類的路徑
   穿越字串）會被剔除並印出警告，絕不會被用來組出 repo root 以外的
   路徑，防止任意檔案刪除。

3. **覆寫前二次確認**：即使 `path` 通過碰撞檢查（例如是上一輪已管理的
   路徑），只要該資料夾內已經有 `index.html`，寫入前都會先確認內容帶有
   本工具的管理標記（HTML 註解 `hdh-redirect-tooling:managed`）；標記
   缺失（例如被人工接手改成別的用途）就直接跳過、**不覆寫**，並印出
   警告交由人工處理。全新建立（資料夾原本不存在）不受此限制。

4. **刪除前二次確認**：當某個 `path` 從 `redirects.csv` 移除時，比照
   覆寫保護的邏輯，同樣要確認該資料夾內的 `index.html` 帶有管理標記，
   標記存在才會刪除；標記不存在則跳過刪除並印出警告，避免誤刪。

5. **大量刪除保護**：單次 build 若會刪除超過「目前已管理路徑」50%
   （且刪除數 > 1），會直接中止並列出將被刪除的 path，避免 CSV 被
   誤清空、或誤刪多列導致一次砍光大量轉址頁而沒人注意到。確認要大量
   刪除時，加上 `--allow-mass-delete` 參數重新執行才會放行。

6. **JS 內嵌跳脫（防 script 標籤被提早關閉）**：`<script>` 區塊內的
   `location.replace(...)` 會把 target 中的 `<`、`>`、`&` 轉成 Unicode
   escape（`<` `>` `&`）再嵌入。若 target 剛好含
   `</script>` 字樣（不論是巧合或惡意輸入），瀏覽器的 HTML 解析器都不會
   把它誤判為標籤結束，避免 script 區塊被提早關閉、後續內容被當成新
   HTML/JS 執行的風險。`test_redirects.py` 會用相同的跳脫函式驗證，並
   額外檢查全文只出現一次合法的 `</script` 字面序列。

7. **CI 自動 commit 只加入本次異動的路徑**：`touched_paths.json` 精準記錄
   本次新增/更新/刪除了哪些根目錄名稱，`.github/workflows/redirects.yml`
   只會對這些路徑加上 `git add -A`，加上 `manifest.json` /
   `redirects.json` / `touched_paths.json` 三個 tooling 自己的追蹤檔，
   **絕不會用 `git add -A` 之類的全域指令**，不會誤動到網站其他既有內容。

8. **build 前必先驗證再寫入**：CSV 格式、path 合法性（含長度上限 64
   字元）、target 合法性、重複 path、保留字等，全部在動筆寫檔之前完成
   檢查；任何一項失敗就整批中止（不會「部分成功」導致狀態不一致）。

9. **CI 寫入前必先跑 `test_redirects.py`**：build 完成後，workflow 會先
   執行驗證腳本確認每個轉址頁內容正確，全數 PASS 才會進到自動 commit
   步驟；只要有一筆 FAIL，workflow 就會直接失敗、不會 push 任何東西。

10. **concurrency 保護**：workflow 設定 `concurrency: {group: redirects,
    cancel-in-progress: false}`，避免短時間內連續修改 CSV 觸發多次
    run 交錯執行 commit/push；後一次會排隊等前一次完全跑完，而不是
    取消進行中的那次（取消寫到一半的 commit/push 可能留下不一致狀態）。

## 手動測試（本機）

```bash
# 只做驗證與列印計畫，不寫入/刪除任何檔案
python _redirect_tooling/build_redirects.py --dry-run

# 實際產生（會寫入 repo root）
python _redirect_tooling/build_redirects.py

# 驗證產出內容
python _redirect_tooling/test_redirects.py
```

也可以用 `--repo-root` 指向一個暫存資料夾做隔離測試，不會動到正式網站：

```bash
python _redirect_tooling/build_redirects.py --repo-root /path/to/scratch --csv _redirect_tooling/redirects.csv
```

若確認要執行會刪除大量（超過已管理路徑 50%）轉址頁的變更，需明確加上：

```bash
python _redirect_tooling/build_redirects.py --allow-mass-delete
```

## 常見問題

**Q: 我想要的 path 跟現有某個頁面同名怎麼辦？**
A: build 會直接報錯中止，不會覆蓋。請改用其他 path，或先確認、調整既有
頁面後再處理。

**Q: 我想要的 path 是保留字（例如 `sitemap`、`pagefind`）怎麼辦？**
A: 這些名稱一律禁止使用，即使目前 repo root 還沒有同名檔案/資料夾也一樣
會被擋下，請換一個 path。

**Q: 可以用巢狀路徑嗎（例如 `promo/2026`）？**
A: 目前設計僅支援單層根目錄路徑（例如 `promo-2026`），刻意不支援斜線，
以簡化碰撞檢查、降低誤刪風險。如未來有巢狀需求，建議另開任務評估。

**Q: 一次刪掉/清空好幾列，build 卻直接報錯中止？**
A: 這是「大量刪除保護」在運作：單次刪除超過已管理路徑一半（且刪除數
大於 1）時，預設會中止並列出將被刪除的 path，避免誤清空/誤刪 CSV
導致一次砍光大量轉址頁。確認是有意的大量刪除，加上
`--allow-mass-delete` 重新執行即可。

**Q: 某個轉址頁的 index.html 被我手動改過內容，重跑 build 會不會被蓋掉？**
A: 不會。只要該資料夾的 index.html 沒有本工具的管理標記（HTML 註解
`hdh-redirect-tooling:managed`），build 一律跳過不覆寫並印出警告。
如果要讓工具重新接管這個 path，需要手動刪除該資料夾（或還原成帶有
管理標記的內容）後再重跑。

**Q: 誤刪了怎麼辦？**
A: 由於整個網站都在 git 版本控制下，任何一次自動 commit 都可以用
`git revert` 復原；此外「刪除前二次確認」與「大量刪除保護」機制本身
就會阻擋大部分誤刪情境。
