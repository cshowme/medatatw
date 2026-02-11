/**
 * 匯東華全站搜尋功能 - 自動注入版
 * 版本：v1.0 (2026-02-11)
 *
 * 使用方式：在任何頁面的 <head> 加入一行即可：
 * <script src="/pagefind-search.js"></script>
 *
 * 功能：
 * 1. 自動在導航列「聯絡我們」旁加入搜尋框
 * 2. 點擊搜尋框開啟搜尋彈窗
 * 3. 搜尋結果在新分頁開啟（不離開當前頁面）
 * 4. 品牌色 #B82226 一致呈現
 */
(function () {
    'use strict';

    var BRAND_RED = '#B82226';

    // ── 1. 動態載入 Pagefind 資源 ──────────────────────────
    function loadCSS(href) {
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        document.head.appendChild(link);
    }

    function loadJS(src, callback) {
        var script = document.createElement('script');
        script.src = src;
        script.onload = callback;
        script.onerror = function () {
            console.warn('[pagefind-search] 無法載入：' + src);
        };
        document.head.appendChild(script);
    }

    // ── 2. 注入自訂 CSS ───────────────────────────────────
    function injectStyles() {
        var style = document.createElement('style');
        style.textContent =
            /* 導航列搜尋項目 */
            '.menu_search{display:inline-block!important;vertical-align:middle;padding:0 8px!important}' +
            '#nav-search-input{' +
                'width:150px;padding:5px 12px 5px 30px;' +
                'border:2px solid ' + BRAND_RED + ';border-radius:20px;' +
                'font-size:13px;outline:none;background:#fff url("data:image/svg+xml,' +
                encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#B82226" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>') +
                '") 10px center no-repeat;' +
                'color:#333;transition:width .3s,box-shadow .3s;cursor:pointer}' +
            '#nav-search-input:focus{width:200px;box-shadow:0 0 8px rgba(184,34,38,.3)}' +
            '#nav-search-input::placeholder{color:#999}' +

            /* 搜尋彈窗遮罩 */
            '#pf-overlay{' +
                'display:none;position:fixed;top:0;left:0;right:0;bottom:0;' +
                'z-index:960000;background:rgba(0,0,0,.45);' +
                'animation:pf-fade-in .2s ease}' +
            '@keyframes pf-fade-in{from{opacity:0}to{opacity:1}}' +

            /* 搜尋彈窗主體 */
            '#pf-modal{' +
                'position:absolute;top:70px;left:50%;transform:translateX(-50%);' +
                'width:92%;max-width:680px;max-height:75vh;' +
                'background:#fff;border-radius:12px;' +
                'box-shadow:0 12px 48px rgba(0,0,0,.25);' +
                'overflow-y:auto;padding:24px 24px 16px}' +

            /* 彈窗內搜尋框品牌色 */
            '#pf-modal .pagefind-ui__search-input{' +
                'border:2px solid ' + BRAND_RED + '!important;' +
                'border-radius:8px!important;font-size:16px!important}' +
            '#pf-modal .pagefind-ui__search-input:focus{' +
                'box-shadow:0 0 8px rgba(184,34,38,.3)!important;' +
                'outline:none!important;border-color:' + BRAND_RED + '!important}' +

            /* 結果連結品牌色 */
            '#pf-modal .pagefind-ui__result-link{color:' + BRAND_RED + '!important}' +
            '#pf-modal .pagefind-ui__result-link:hover{text-decoration:underline}' +

            /* 載入更多按鈕 */
            '#pf-modal .pagefind-ui__button{' +
                'background:' + BRAND_RED + '!important;color:#fff!important;' +
                'border:none!important;border-radius:6px!important;' +
                'cursor:pointer;padding:8px 20px!important}' +

            /* 關閉按鈕 */
            '#pf-close{' +
                'position:absolute;top:10px;right:14px;' +
                'font-size:28px;cursor:pointer;color:#999;' +
                'background:none;border:none;line-height:1;' +
                'width:36px;height:36px;display:flex;align-items:center;justify-content:center;' +
                'border-radius:50%;transition:all .2s}' +
            '#pf-close:hover{color:' + BRAND_RED + ';background:#f5f5f5}' +

            /* 彈窗標題 */
            '#pf-title{' +
                'font-size:14px;color:#666;margin:0 0 12px 2px;' +
                'font-family:"Microsoft JhengHei",sans-serif}' +

            /* 響應式 */
            '@media(max-width:768px){' +
                '.menu_search{display:block!important;text-align:center;padding:8px 0!important}' +
                '#nav-search-input{width:180px}' +
                '#pf-modal{width:96%;top:50px;padding:16px}}';

        document.head.appendChild(style);
    }

    // ── 3. 建立搜尋 UI ────────────────────────────────────
    var pagefindInstance = null;
    var resultObserver = null;

    function createSearchUI() {
        // (a) 在導航列加入搜尋框
        var nav = document.querySelector('.b_menu ul');
        if (!nav) return;

        var searchLi = document.createElement('li');
        searchLi.className = 'menu_search';
        searchLi.innerHTML =
            '<input type="text" id="nav-search-input" ' +
            'placeholder="搜尋本站..." readonly>';
        nav.appendChild(searchLi);

        // (b) 建立彈窗
        var overlay = document.createElement('div');
        overlay.id = 'pf-overlay';
        overlay.innerHTML =
            '<div id="pf-modal">' +
                '<button id="pf-close" title="關閉 (Esc)">&times;</button>' +
                '<div id="pf-title">匯東華全站搜尋</div>' +
                '<div id="pf-container"></div>' +
            '</div>';
        document.body.appendChild(overlay);

        // (c) 事件綁定
        var navInput = document.getElementById('nav-search-input');

        // 點擊導航列搜尋框 → 開啟彈窗
        navInput.addEventListener('click', function () {
            openModal('');
        });

        // 關閉彈窗：X 按鈕
        document.getElementById('pf-close').addEventListener('click', closeModal);

        // 關閉彈窗：點擊遮罩
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeModal();
        });

        // 關閉彈窗：Esc 鍵
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && overlay.style.display === 'block') {
                closeModal();
            }
        });

        // 快捷鍵：Ctrl+K 或 Cmd+K 開啟搜尋
        document.addEventListener('keydown', function (e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                openModal('');
            }
        });
    }

    function openModal(initialQuery) {
        // 手機版：關閉漢堡選單（取消勾選 checkbox）
        var menuCheckbox = document.querySelector('.b_menu > input[type="checkbox"]');
        if (menuCheckbox && menuCheckbox.checked) {
            menuCheckbox.checked = false;
        }

        var overlay = document.getElementById('pf-overlay');
        overlay.style.display = 'block';
        document.body.style.overflow = 'hidden'; // 防止背景捲動

        // 首次開啟時初始化 Pagefind
        if (!pagefindInstance && typeof PagefindUI !== 'undefined') {
            pagefindInstance = new PagefindUI({
                element: '#pf-container',
                showSubResults: true,
                showImages: false,
                translations: {
                    placeholder: '搜尋課程、文章...',
                    clear_search: '清除',
                    load_more: '載入更多',
                    search_label: '搜尋本站',
                    zero_results: '找不到「[SEARCH_TERM]」的相關結果',
                    many_results: '找到 [COUNT] 個「[SEARCH_TERM]」的結果',
                    one_result: '找到 1 個「[SEARCH_TERM]」的結果'
                }
            });

            // MutationObserver：自動讓結果連結在新分頁開啟
            var container = document.getElementById('pf-container');
            resultObserver = new MutationObserver(function () {
                var links = container.querySelectorAll('a');
                for (var i = 0; i < links.length; i++) {
                    if (!links[i].hasAttribute('data-pf-processed')) {
                        links[i].setAttribute('target', '_blank');
                        links[i].setAttribute('rel', 'noopener');
                        links[i].setAttribute('data-pf-processed', '1');
                    }
                }
            });
            resultObserver.observe(container, { childList: true, subtree: true });
        }

        // 聚焦彈窗內的搜尋框
        setTimeout(function () {
            var modalInput = document.querySelector(
                '#pf-container .pagefind-ui__search-input'
            );
            if (modalInput) {
                if (initialQuery) {
                    modalInput.value = initialQuery;
                    modalInput.dispatchEvent(new Event('input'));
                }
                modalInput.focus();
            }
        }, 150);
    }

    function closeModal() {
        document.getElementById('pf-overlay').style.display = 'none';
        document.body.style.overflow = ''; // 恢復捲動
    }

    // ── 4. 啟動 ───────────────────────────────────────────
    function init() {
        loadCSS('/pagefind/pagefind-ui.css');
        injectStyles();
        loadJS('/pagefind/pagefind-ui.js', function () {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', createSearchUI);
            } else {
                createSearchUI();
            }
        });
    }

    init();
})();
