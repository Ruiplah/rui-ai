#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地 AI 联网搜索外挂服务
监听 127.0.0.1:8081，提供：
  GET /api/search?q=关键词&n=数量  -> 搜索网页，返回 [{title,url,snippet}]
  GET /api/fetch?url=网页地址      -> 抓取网页正文文本，返回 {title,text}
  GET /health                      -> 健康检查
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser

HOST = "127.0.0.1"
PORT = 8081
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def http_get(url, timeout=20, binary=False):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if binary:
            return data
        charset = r.headers.get_content_charset()
        if not charset:
            ct = (r.headers.get("Content-Type") or "").lower()
            charset = "utf-8" if "gb" not in ct else "gbk"
        try:
            return data.decode(charset, errors="replace")
        except Exception:
            return data.decode("utf-8", errors="replace")


def strip_html(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;?", " ", s)
    s = re.sub(r"&amp;?", "&", s)
    s = re.sub(r"&lt;?", "<", s)
    s = re.sub(r"&gt;?", ">", s)
    s = re.sub(r"&quot;?", '"', s)
    s = re.sub(r"&#39;?", "'", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def search_bing(q, n=6):
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(q) + "&count=" + str(n) + "&setlang=zh-CN"
    html = http_get(url)
    results = []
    blocks = re.findall(r'<li class="b_algo".*?</li>', html, re.S | re.I)
    if not blocks:
        # 兜底：Bing 有时用 <li class="b_algo" ...> 不同结构，宽泛匹配 h2>a
        blocks = re.findall(r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h2>\s*(?:<p[^>]*>(.*?)</p>)?', html, re.S | re.I)
        for url_t, title, snippet in blocks:
            if not url_t.startswith("http"):
                continue
            results.append({"title": strip_html(title), "url": url_t, "snippet": strip_html(snippet or "")})
            if len(results) >= n:
                break
        return results
    for item in blocks:
        hm = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', item, re.S | re.I)
        if not hm:
            continue
        url_t = hm.group(1)
        if not url_t.startswith("http"):
            continue
        title = strip_html(hm.group(2))
        pm = re.search(r"<p[^>]*>(.*?)</p>", item, re.S | re.I)
        snippet = strip_html(pm.group(1)) if pm else ""
        results.append({"title": title, "url": url_t, "snippet": snippet})
        if len(results) >= n:
            break
    return results


def search_duckduckgo(q, n=6):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
    html = http_get(url)
    results = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        url_t = m.group(1)
        title = strip_html(m.group(2))
        if url_t.startswith("//duckduckgo.com/l/?uddg="):
            url_t = urllib.parse.unquote(re.search(r"uddg=([^&]+)", url_t).group(1)) if "uddg=" in url_t else url_t
        snippet = ""
        sm = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html[m.start():m.start()+3000], re.S | re.I)
        if sm:
            snippet = strip_html(sm.group(1))
        results.append({"title": title, "url": url_t, "snippet": snippet})
        if len(results) >= n:
            break
    return results


def search(q, n=6):
    try:
        r = search_bing(q, n)
        if r:
            return r
    except Exception:
        pass
    try:
        return search_duckduckgo(q, n)
    except Exception:
        return []


def fetch_text(url, max_len=6000):
    html = http_get(url)
    # 提取 title
    tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = strip_html(tm.group(1)) if tm else ""
    # 提取正文：优先 main/article，否则全文
    body = ""
    mm = re.search(r"<article.*?</article>", html, re.S | re.I)
    if mm:
        body = mm.group(0)
    else:
        mm = re.search(r'<main.*?</main>', html, re.S | re.I)
        if mm:
            body = mm.group(0)
        else:
            mm = re.search(r'<body.*?</body>', html, re.S | re.I)
            if mm:
                body = mm.group(0)
    text = strip_html(body)
    if len(text) > max_len:
        text = text[:max_len] + "……（内容过长已截断）"
    return {"title": title, "text": text}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == "/health":
                return self._send(200, {"ok": True})
            if parsed.path == "/api/search":
                qs = urllib.parse.parse_qs(parsed.query)
                q = (qs.get("q") or [""])[0].strip()
                n = int((qs.get("n") or ["6"])[0])
                if not q:
                    return self._send(400, {"error": "缺少参数 q"})
                results = search(q, max(1, min(n, 10)))
                return self._send(200, {"query": q, "results": results})
            if parsed.path == "/api/fetch":
                qs = urllib.parse.parse_qs(parsed.query)
                url = (qs.get("url") or [""])[0].strip()
                if not url:
                    return self._send(400, {"error": "缺少参数 url"})
                if not url.startswith(("http://", "https://")):
                    return self._send(400, {"error": "非法 URL"})
                info = fetch_text(url)
                return self._send(200, info)
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"搜索服务已启动: http://{HOST}:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
