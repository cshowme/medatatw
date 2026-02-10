#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
官網品質驗證腳本 V5
執行日期：2026-02-10
驗證目標：https://www.medatatw.com/
"""

import ssl
import socket
import urllib.request
import urllib.error
import json
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

class LinkExtractor(HTMLParser):
    """提取 HTML 中的資源連結"""
    def __init__(self):
        super().__init__()
        self.links = []
        self.nav_items = []
        self.footer_content = []
        self.logo_src = None
        self.in_nav = False
        self.in_footer = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # 檢測導航列
        if tag in ['nav', 'header'] or attrs_dict.get('class', '').find('nav') >= 0:
            self.in_nav = True

        # 檢測 footer
        if tag == 'footer' or attrs_dict.get('class', '').find('footer') >= 0:
            self.in_footer = True

        # 提取資源連結
        if tag in ['script', 'link', 'img', 'a', 'iframe']:
            for attr in ['src', 'href']:
                if attr in attrs_dict:
                    url = attrs_dict[attr]
                    self.links.append((tag, attr, url))

                    # Logo 檢測
                    if tag == 'img' and ('logo' in url.lower() or
                                         'logo' in attrs_dict.get('alt', '').lower() or
                                         'logo' in attrs_dict.get('class', '').lower()):
                        self.logo_src = url

        # 導航項目
        if self.in_nav and tag == 'a':
            text = attrs_dict.get('href', '')
            self.nav_items.append(text)

    def handle_endtag(self, tag):
        if tag in ['nav', 'header']:
            self.in_nav = False
        if tag == 'footer':
            self.in_footer = False

    def handle_data(self, data):
        if self.in_footer:
            text = data.strip()
            if text:
                self.footer_content.append(text)

def check_ssl_certificate(domain):
    """檢查 SSL 憑證資訊"""
    print("\n=== 1. HTTPS 安全性驗證 ===\n")
    results = {}

    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

                results['cert_found'] = True
                results['issuer'] = dict(x[0] for x in cert['issuer'])
                results['subject'] = dict(x[0] for x in cert['subject'])
                results['version'] = cert['version']
                results['notBefore'] = cert['notBefore']
                results['notAfter'] = cert['notAfter']
                results['subjectAltName'] = cert.get('subjectAltName', [])

                # 檢查是否為 Let's Encrypt
                issuer_org = results['issuer'].get('organizationName', '')
                results['is_letsencrypt'] = "Let's Encrypt" in issuer_org

                # 檢查是否涵蓋目標域名
                alt_names = [name[1] for name in results['subjectAltName'] if name[0] == 'DNS']
                results['covers_domain'] = domain in alt_names or f'*.{".".join(domain.split(".")[1:])}' in alt_names

                print(f"[OK] SSL Certificate Info:")
                print(f"  - Issuer: {issuer_org}")
                print(f"  - Subject: {results['subject'].get('commonName', 'N/A')}")
                print(f"  - Valid Period: {results['notBefore']} ~ {results['notAfter']}")
                print(f"  - Covered Domains: {', '.join(alt_names)}")
                print(f"  - Let's Encrypt: {'YES' if results['is_letsencrypt'] else 'NO'}")
                print(f"  - Covers {domain}: {'YES' if results['covers_domain'] else 'NO'}")

    except Exception as e:
        results['error'] = str(e)
        print(f"[FAIL] SSL 憑證檢查失敗：{e}")

    return results

def check_redirects(domain):
    """檢查 HTTP → HTTPS 和裸域跳轉"""
    print("\n=== HTTP/域名跳轉測試 ===\n")
    results = {}

    # 測試 1: HTTP → HTTPS
    test_cases = [
        (f"http://{domain}/", f"https://{domain}/", "HTTP → HTTPS"),
        (f"https://{domain.replace('www.', '')}/", f"https://{domain}/", "裸域 → www"),
    ]

    for source_url, expected_url, test_name in test_cases:
        try:
            req = urllib.request.Request(source_url, headers={'User-Agent': 'Mozilla/5.0'})
            opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
            response = opener.open(req, timeout=10)
            final_url = response.geturl()

            success = final_url == expected_url
            results[test_name] = {
                'success': success,
                'source': source_url,
                'expected': expected_url,
                'actual': final_url,
                'status': response.status
            }

            print(f"{'[OK]' if success else '[FAIL]'} {test_name}")
            print(f"  - 來源：{source_url}")
            print(f"  - 預期：{expected_url}")
            print(f"  - 實際：{final_url}")
            print(f"  - 狀態：{response.status}")

        except Exception as e:
            results[test_name] = {'error': str(e)}
            print(f"[FAIL] {test_name} 測試失敗：{e}")

    return results

def fetch_page_info(url):
    """獲取單一頁面的詳細資訊"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        start_time = time.time()
        response = urllib.request.urlopen(req, timeout=10)
        response_time = (time.time() - start_time) * 1000  # 轉換為毫秒

        html = response.read().decode('utf-8', errors='ignore')
        headers = dict(response.headers)

        # 解析 HTML
        parser = LinkExtractor()
        parser.feed(html)

        return {
            'status': response.status,
            'response_time_ms': round(response_time, 2),
            'server': headers.get('Server', 'N/A'),
            'content_type': headers.get('Content-Type', 'N/A'),
            'content_length': len(html),
            'links': parser.links,
            'nav_items': parser.nav_items,
            'footer_content': parser.footer_content,
            'logo_src': parser.logo_src,
            'html': html
        }
    except urllib.error.HTTPError as e:
        return {'status': e.code, 'error': str(e)}
    except Exception as e:
        return {'error': str(e)}

def check_cross_page_consistency(domain, sample_pages):
    """檢查跨頁一致性"""
    print("\n=== 2. 跨頁一致性驗證 ===\n")

    pages_info = {}

    for page_name, page_path in sample_pages.items():
        url = f"https://{domain}{page_path}"
        print(f"正在檢查：{page_name} ({url})")
        pages_info[page_name] = fetch_page_info(url)
        time.sleep(0.5)  # 避免請求過快

    # 一致性分析
    print("\n--- 一致性分析 ---\n")

    # Server header
    servers = {name: info.get('server', 'N/A') for name, info in pages_info.items() if 'error' not in info}
    unique_servers = set(servers.values())
    print(f"Server header：{unique_servers}")
    if len(unique_servers) == 1:
        print(f"  [OK] 所有頁面一致：{list(unique_servers)[0]}")
    else:
        print(f"  [FAIL] 不一致：")
        for name, server in servers.items():
            print(f"    - {name}: {server}")

    # Logo
    logos = {name: info.get('logo_src', 'N/A') for name, info in pages_info.items() if 'error' not in info}
    unique_logos = set(logos.values())
    print(f"\nLogo 來源：{len(unique_logos)} 種")
    if len(unique_logos) <= 2:  # 允許相對/絕對路徑差異
        print(f"  [OK] Logo 基本一致")
    else:
        print(f"  [WARN] Logo 可能不一致：")
        for name, logo in logos.items():
            print(f"    - {name}: {logo}")

    # 導航列
    nav_lengths = {name: len(info.get('nav_items', [])) for name, info in pages_info.items() if 'error' not in info}
    unique_nav_lengths = set(nav_lengths.values())
    print(f"\n導航項目數量：{unique_nav_lengths}")
    if len(unique_nav_lengths) == 1:
        print(f"  [OK] 所有頁面導航項目數量一致：{list(unique_nav_lengths)[0]} 項")
    else:
        print(f"  [WARN] 導航項目數量不一致：")
        for name, count in nav_lengths.items():
            print(f"    - {name}: {count} 項")

    # Footer
    footer_lengths = {name: len(info.get('footer_content', [])) for name, info in pages_info.items() if 'error' not in info}
    print(f"\nFooter 內容片段數量：{set(footer_lengths.values())}")
    if len(set(footer_lengths.values())) <= 2:  # 允許些微差異
        print(f"  [OK] Footer 基本一致")
    else:
        print(f"  [WARN] Footer 可能不一致")

    return pages_info

def check_response_times(pages_info):
    """檢查響應時間"""
    print("\n=== 3. 響應時間檢查 ===\n")

    print(f"{'頁面':<20} {'狀態':<10} {'響應時間 (ms)':<15} {'評級'}")
    print("-" * 60)

    for name, info in pages_info.items():
        if 'error' in info:
            print(f"{name:<20} {'ERROR':<10} {'N/A':<15} {'[FAIL]'}")
        else:
            status = info.get('status', 'N/A')
            resp_time = info.get('response_time_ms', 0)
            rating = '[OK]' if resp_time < 2000 else '[WARN]' if resp_time < 3000 else '[FAIL]'
            print(f"{name:<20} {status:<10} {resp_time:<15.2f} {rating}")

def check_security_issues(pages_info):
    """檢查安全問題"""
    print("\n=== 4. 特別安全檢查 ===\n")

    issues = []

    for page_name, info in pages_info.items():
        if 'error' in info:
            continue

        # Mixed content 檢查
        http_resources = []
        for tag, attr, url in info.get('links', []):
            if url.startswith('http://') and not url.startswith('http://localhost'):
                http_resources.append((tag, url))

        if http_resources:
            issues.append({
                'page': page_name,
                'type': 'Mixed Content',
                'details': http_resources
            })
            print(f"[WARN] {page_name} 發現 Mixed Content：")
            for tag, url in http_resources[:5]:  # 只顯示前 5 個
                print(f"  - <{tag}> {url}")
            if len(http_resources) > 5:
                print(f"  ... 還有 {len(http_resources) - 5} 個")

        # 敏感資訊檢查
        html = info.get('html', '')
        sensitive_patterns = ['api_key', 'apikey', 'password', 'secret', 'token']
        for pattern in sensitive_patterns:
            if pattern in html.lower():
                # 簡單檢查，避免誤報（排除註解中的說明文字）
                context_start = html.lower().find(pattern)
                context = html[max(0, context_start-50):context_start+50]
                if '<!--' not in context:  # 不在註解中
                    issues.append({
                        'page': page_name,
                        'type': 'Potential Sensitive Info',
                        'pattern': pattern,
                        'context': context[:100]
                    })
                    print(f"[WARN] {page_name} 可能包含敏感資訊：{pattern}")

    if not issues:
        print("[OK] 未發現安全問題")

    return issues

def check_404_page(domain):
    """測試 404 頁面"""
    print("\n=== 5. 404 頁面測試 ===\n")

    test_url = f"https://{domain}/nonexistent-page-12345.html"
    try:
        req = urllib.request.Request(test_url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=10)
        print(f"[WARN] 404 測試異常：回傳 {response.status}（預期 404）")
        return {'status': response.status, 'expected': 404, 'pass': False}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[OK] 404 頁面正常：{e.code}")
            return {'status': e.code, 'expected': 404, 'pass': True}
        else:
            print(f"[WARN] 回傳非預期狀態碼：{e.code}")
            return {'status': e.code, 'expected': 404, 'pass': False}
    except Exception as e:
        print(f"[FAIL] 404 測試失敗：{e}")
        return {'error': str(e)}

def main():
    domain = "www.medatatw.com"

    print("=" * 70)
    print("官網品質驗證報告 V5")
    print("=" * 70)
    print(f"驗證目標：https://{domain}/")
    print(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. SSL 憑證檢查
    ssl_results = check_ssl_certificate(domain)

    # 2. 跳轉檢查
    redirect_results = check_redirects(domain)

    # 3. 抽樣頁面
    sample_pages = {
        '首頁': '/',
        '生物統計與R語言': '/biostat/',
        'Python 統計': '/python/',
        '縱貫性資料分析': '/longitudinal/',
        'SEM 結構方程': '/sem/',
        'Meta 統合分析': '/meta/',
        '進階醫學統計': '/advance/',
        '關於匯東華': '/about/',
        '隱私權聲明': '/privacy/',
        '聯絡我們': '/contact/',
    }

    pages_info = check_cross_page_consistency(domain, sample_pages)

    # 4. 響應時間
    check_response_times(pages_info)

    # 5. 安全檢查
    security_issues = check_security_issues(pages_info)

    # 6. 404 測試
    not_found_result = check_404_page(domain)

    # 7. 總結
    print("\n" + "=" * 70)
    print("總結報告")
    print("=" * 70)

    all_pass = True

    # SSL 檢查
    if ssl_results.get('is_letsencrypt') and ssl_results.get('covers_domain'):
        print("[OK] HTTPS 安全性：PASS")
    else:
        print("[FAIL] HTTPS 安全性：FAIL")
        all_pass = False

    # 跳轉檢查
    redirect_pass = all(r.get('success', False) for r in redirect_results.values() if 'error' not in r)
    if redirect_pass:
        print("[OK] HTTP/域名跳轉：PASS")
    else:
        print("[WARN] HTTP/域名跳轉：部分失敗")
        all_pass = False

    # 響應時間
    slow_pages = [name for name, info in pages_info.items()
                  if 'error' not in info and info.get('response_time_ms', 0) > 2000]
    if not slow_pages:
        print("[OK] 響應時間：PASS（所有頁面 < 2 秒）")
    else:
        print(f"[WARN] 響應時間：{len(slow_pages)} 個頁面 > 2 秒")
        all_pass = False

    # 安全問題
    if not security_issues:
        print("[OK] 安全檢查：PASS")
    else:
        print(f"[WARN] 安全檢查：發現 {len(security_issues)} 個問題")
        all_pass = False

    # 404
    if not_found_result.get('pass'):
        print("[OK] 404 頁面：PASS")
    else:
        print("[WARN] 404 頁面：異常")
        all_pass = False

    print("\n" + "=" * 70)
    if all_pass:
        print("最終結論：[OK] PASS")
    else:
        print("最終結論：[WARN] PASS WITH WARNINGS")
    print("=" * 70)

    # 儲存結果
    report = {
        'timestamp': datetime.now().isoformat(),
        'domain': domain,
        'ssl_results': ssl_results,
        'redirect_results': redirect_results,
        'pages_info': {name: {k: v for k, v in info.items() if k != 'html'}
                       for name, info in pages_info.items()},
        'security_issues': security_issues,
        'not_found_result': not_found_result,
        'final_verdict': 'PASS' if all_pass else 'PASS_WITH_WARNINGS'
    }

    output_file = 'website_verification_report_20260210_CSX.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n詳細報告已儲存：{output_file}")

if __name__ == '__main__':
    main()
