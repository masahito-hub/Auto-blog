#!/usr/bin/env python3
"""
商品リンク切れ検知（refs Auto-blog#8）

WordPress の全公開記事から外部リンク・画像URLを抽出し、到達性を検査する。

背景:
  2026-08-01 のケトブログ調査で、確認した商品リンク3件が全て壊れていた。
  いずれも自動検知の仕組みがなく、偶然発見されたもの。

検知する障害:
  1. 画像404          : 画像URLが取得できない
  2. 商品ページ消滅   : 404、または「トップページへのリダイレクト」
  3. 到達不能         : DNS/接続エラー

  ⚠️ 2が重要。楽天は商品が消えると404ではなくトップへ302するため、
     HTTPステータスだけでは正常に見える。最終URLの比較が必須。

使い方:
  python3 scripts/check_product_links.py
  python3 scripts/check_product_links.py --self-test
  終了コード 0=正常 / 1=異常あり
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


WP_API = "https://guide.ketogenic.press/wp-json/wp/v2/posts"
UA = ("Mozilla/5.0 (compatible; LinkChecker/1.0; "
      "+https://guide.ketogenic.press/)")
TIMEOUT = 20
SLEEP = 0.7

# 検査対象ホスト。ASP・商品ページ・商品画像を網羅する。
# ⚠️ 追加漏れがあると「検知できない障害」が生まれる（#8）
TARGET_HOSTS = (
    # もしもアフィリエイト
    "af.moshimo.com", "i.moshimo.com",
    # バリューコマース / A8.net
    "ck.jp.ap.valuecommerce.com",
    "px.a8.net", "www13.a8.net", "www24.a8.net",
    # 楽天（a.r10.to は短縮URL。商品消滅でトップへ飛ぶ）
    "a.r10.to",
    "item.rakuten.co.jp", "search.rakuten.co.jp",
    "thumbnail.image.rakuten.co.jp",
    # Yahoo!ショッピング
    "shopping.yahoo.co.jp", "store.shopping.yahoo.co.jp",
    "item-shopping.c.yimg.jp",
    # Amazon
    "www.amazon.co.jp", "amzn.to", "amzn.asia",
    "images-fe.ssl-images-amazon.com", "m.media-amazon.com",
)

# 商品が消えるとここへ飛ぶ。最終URLがこれなら商品消滅とみなす（#8 中核判定）
TOP_PAGE_PATHS = ("", "/", "/index.html")

# 転送が正常動作であるASP・短縮URLのホスト。
# 別ドメインへ飛んでも異常としない。
# ⚠️ ただしトップページ判定はこれより先に行うため、
#    ASP経由でも商品消滅は検知される（#8）
REDIRECTOR_HOSTS = (
    "af.moshimo.com", "i.moshimo.com",
    "ck.jp.ap.valuecommerce.com",
    "px.a8.net", "www13.a8.net", "www24.a8.net",
    "a.r10.to", "amzn.to", "amzn.asia",
)

# ホスト別の最小アクセス間隔（秒）。
# Amazonは短時間の連続アクセスで503を返すため厚めに取る（#8）
HOST_INTERVAL = {
    "www.amazon.co.jp": 4.0,
    "amzn.to": 4.0,
    "amzn.asia": 4.0,
}
DEFAULT_INTERVAL = 0.7
_last_access = {}


def polite_wait(url):
    """同一ホストへの連続アクセスを避ける"""
    host = urllib.parse.urlparse(url).netloc.lower()
    wait = HOST_INTERVAL.get(host, DEFAULT_INTERVAL)
    prev = _last_access.get(host)
    now = time.time()
    if prev is not None:
        rest = wait - (now - prev)
        if rest > 0:
            time.sleep(rest)
    _last_access[host] = time.time()


def fetch_posts():
    """公開記事を全件取得する（ページング対応）"""
    posts, page = [], 1
    while True:
        url = ("%s?per_page=100&page=%d&status=publish"
               "&_fields=id,link,title,content" % (WP_API, page))
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                batch = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 400:
                break
            raise
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return posts


def extract_urls(html):
    """href / src から検査対象ホストのURLだけを抜き出す"""
    found = []
    for m in re.finditer(r'(?:href|src)=["\']([^"\']+)["\']', html):
        u = m.group(1).strip()
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            continue
        host = urllib.parse.urlparse(u).netloc.lower()
        if host in TARGET_HOSTS:
            found.append(u)
    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def is_top_page(url):
    """URLがサイトのトップページ相当か（楽天の商品消滅検知に使う）"""
    p = urllib.parse.urlparse(url)
    return p.path in TOP_PAGE_PATHS and not p.query


def classify(original, final_url, status, err=None):
    """検査結果を分類する。戻り値: (OK/NG/WARN, 理由)"""
    if err:
        return "NG", "到達不能: %s" % err
    if status is None:
        return "NG", "応答なし"
    if status in (404, 410):
        return "NG", "HTTP %d（ページ消滅）" % status
    if status >= 500:
        return "WARN", "HTTP %d（サーバ側の一時障害の可能性）" % status
    if status >= 400:
        return "WARN", "HTTP %d" % status
    if final_url and final_url != original:
        o = urllib.parse.urlparse(original)
        f = urllib.parse.urlparse(final_url)
        if is_top_page(final_url) and not is_top_page(original):
            return "NG", "トップページへリダイレクト（商品消滅の疑い）→ %s" % final_url
        if o.netloc in REDIRECTOR_HOSTS:
            # ASPの計測リンクは転送が正常動作。別ドメイン遷移を異常としない
            return "OK", "HTTP %d（ASP経由 → %s）" % (status, f.netloc)
        if o.netloc != f.netloc:
            return "WARN", "別ドメインへリダイレクト → %s" % f.netloc
    return "OK", "HTTP %d" % status


def check_url(url):
    """HEADを試し、拒否されたらGETへフォールバック"""
    hdr = {"User-Agent": UA, "Accept": "*/*"}
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return {"status": r.status, "final": r.url,
                        "ctype": r.headers.get("Content-Type", ""),
                        "err": None}
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return {"status": e.code, "final": getattr(e, "url", url),
                    "ctype": "", "err": None}
        except Exception as e:
            if method == "HEAD":
                continue
            return {"status": None, "final": None, "ctype": "",
                    "err": "%s: %s" % (type(e).__name__, str(e)[:60])}
    return {"status": None, "final": None, "ctype": "", "err": "検査不能"}


def is_image_url(url):
    return bool(re.search(r'\.(jpe?g|png|gif|webp)(\?|$)', url, re.I)) \
        or "thumbnail.image.rakuten" in url \
        or "item-shopping.c.yimg.jp" in url \
        or "images-amazon.com" in url \
        or "media-amazon.com" in url


def self_test():
    """回帰テスト。2026-08-01 に実際に壊れていたURLを検証データに使う"""
    fails = []
    for url, expect in [
        ("https://www.rakuten.co.jp/", True),
        ("https://www.rakuten.co.jp", True),
        ("https://item.rakuten.co.jp/shop/item123/", False),
        ("https://www.amazon.co.jp/dp/B0CRR7FM52", False),
    ]:
        if is_top_page(url) != expect:
            fails.append(("is_top_page", url, expect))

    # 今日の実障害パターン
    for orig, final, st, err, expect in [
        # 商品消滅でトップへリダイレクト（旧ケトスキャンmini）
        ("https://item.rakuten.co.jp/onayamihonpo/wjbcb-xmng3088l/",
         "https://www.rakuten.co.jp/", 200, None, "NG"),
        # 画像404（旧かんたんリンクの楽天画像）
        ("https://thumbnail.image.rakuten.co.jp/@0_mall/x/y.jpg",
         None, 404, None, "NG"),
        # 正常な商品ページ
        ("https://www.amazon.co.jp/dp/B0CRR7FM52",
         "https://www.amazon.co.jp/dp/B0CRR7FM52", 200, None, "OK"),
        ("https://example.invalid/x", None, None, "DNSエラー", "NG"),
        # 一時障害は WARN（誤って NG にしない）
        ("https://item.rakuten.co.jp/a/b/", None, 503, None, "WARN"),
        # ASP経由の通常遷移は正常（誤検知を出さない）
        ("https://af.moshimo.com/af/c/click?url=x",
         "https://www.amazon.co.jp/dp/B0X", 200, None, "OK"),
        # ★ASP経由でも商品消滅は検知する（トップ判定が先に効く）
        ("https://a.r10.to/abcdef",
         "https://www.rakuten.co.jp/", 200, None, "NG"),
    ]:
        level, _ = classify(orig, final, st, err)
        if level != expect:
            fails.append(("classify", orig[:40], "%s≠%s" % (level, expect)))

    html = ('<a href="https://af.moshimo.com/af/c/click?x=1">A</a>'
            '<a href="https://guide.ketogenic.press/practice/x/">内部</a>'
            '<img src="//thumbnail.image.rakuten.co.jp/@0_mall/a/b.jpg">'
            '<a href="https://example.com/">外部</a>')
    if len(extract_urls(html)) != 2:
        fails.append(("extract_urls", "対象2件のはず", len(extract_urls(html))))

    total = 12
    if fails:
        for f in fails:
            print("FAIL %s | %s | %s" % f)
        print("\n%d/%d 失敗" % (len(fails), total))
        return 1
    print("OK 回帰テスト %d/%d 通過" % (total, total))
    return 0


def run_check(json_out=None, limit=None):
    posts = fetch_posts()
    print("記事数: %d" % len(posts))
    results, ng, warn, checked = [], 0, 0, 0
    for p in posts:
        urls = extract_urls(p.get("content", {}).get("rendered", ""))
        if limit:
            urls = urls[:limit]
        for u in urls:
            polite_wait(u)
            r = check_url(u)
            level, reason = classify(u, r["final"], r["status"], r["err"])
            if level == "OK" and is_image_url(u) and r["ctype"] \
                    and not r["ctype"].startswith("image/"):
                level, reason = "NG", "画像だがCT=%s" % r["ctype"]
            checked += 1
            if level != "OK":
                results.append({"post": p["link"], "url": u,
                                "level": level, "reason": reason})
                ng += 1 if level == "NG" else 0
                warn += 1 if level == "WARN" else 0
                print("%s %s\n    記事: %s\n    理由: %s"
                      % (level, u[:88], p["link"], reason))
    print("\n検査 %d件 / NG %d件 / WARN %d件" % (checked, ng, warn))
    if json_out:
        with open(json_out, "w") as f:
            json.dump({"checked": checked, "ng": ng, "warn": warn,
                       "items": results}, f, ensure_ascii=False, indent=2)
        print("結果を %s へ出力" % json_out)
    return 1 if ng else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--limit", type=int, help="記事あたりの検査上限")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    return run_check(a.json, a.limit)


if __name__ == "__main__":
    sys.exit(main())
