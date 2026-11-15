#!/usr/bin/env python3
"""refgrab：参照与资料抓取工具（只用标准库 + 可选 Pillow / yt-dlp / imageio-ffmpeg）。

为什么有这个工具：Agent 没有内置联网搜索时，最容易出现“搜不到用户点名的参照 → 悄悄换题”。
本工具把可用来源都接好，一条命令同时查多个源，下载的每个文件都记进 manifest.jsonl（来源、查询、时间、sha256）。

子命令（全部输出 JSON 行或可读文本，加 --json 输出 JSON）：
  refs    "Genshin Impact=原神" "Wuthering Waves=鸣潮" --topic water --out refs
                                 一键取点名参照（推荐第一条命令）：逐源尝试到够数、过滤小图/重复、拼触表、写 REFS.md
  doctor                         检查依赖和各来源当前是否可达
  web     "关键词"               网页搜索：bing(英文区)/duckduckgo/bing中文/baidu/marginalia 合并去重
  images  "关键词" [--src ...]   图片搜索：bing/baidu/wallhaven/safebooru/pixiv/artstation/openverse/commons/fandom/biligame
  video   "关键词"               视频搜索：bilibili/youtube（标题、时长、链接、封面）
  get     URL...  --out DIR      下载图片/文件（自动带 Referer，失败自动改用 curl）
  page    URL                    抓网页：正文文本 + 图片 + 链接；--js 用 Edge 无头渲染（应对前端渲染页面）
  shot    URL --out x.png        用 Edge 无头给网页截图
  vdl     URL --out DIR          下载视频（可 --section 00:30-01:10 只下一段，--height 1080）
  frames  VIDEO --out DIR        截帧：--every 2（秒）或 --scene 0.3（镜头切换）或 --at 12.5,40
  sheet   IMG... --out x.png     拼接触表（contact sheet），带文件名标注
  compare A B [C] --out x.png    并排对比图：参照 | 当前版 | 上一版，等高缩放、带标签
  wiki    SITE "关键词"          MediaWiki 站点（fandom / wiki.biligame / wikipedia / commons）搜页面或图片
  gh      "关键词"               GitHub 仓库搜索；gh-dl owner/repo --out DIR 下载源码 zip
  gh-tree owner/repo [--filter]  列仓库文件；gh-cat owner/repo 路径 读单个文件（不用下整个仓库）
  research "关键词" --out DIR    搜索并把前 N 篇正文各存一个 md，生成 index.md（查资料首选）
  subs    URL --out DIR          视频字幕 → 带时间戳文本（教程视频不用看完也能检索）
  pdf     文件或URL --out x.md   PDF 按页取文本，--images 提取插图（GDC 讲稿等）
  measure IMG                    量图：--points 取色、--regions 区域均色、--grid 4x1 色带、--palette 8 主色
  expand  作品页URL              Pixiv/HoYoLAB/米游社/B站 → 原图或视频信息
  wayback URL [--read]           web.archive.org 存档
  look    参照 当前 [上一版] --out board.png [--roi]
                                 看图板：原图|眯眼|6色分离|边缘 + 主色/明度直方图；打印饱和度、明度阶数、边缘锐度
  crops   IMG... --regions "近岸=..;远水=.." --out x.png
                                 分区对齐裁切：各图同名部位并排 + 中位色/HSV/纹理 + 相对第一张的差（比“哪里不像”）
  pick    IMG... --subject 原神 --why "…" --out refs/selected [--reject]
                                 参照登记：选入复制成 R1…并记出处和 sha256，剔除也记理由 → SELECTED.md
  motion  VIDEO --out DIR --roi  动态：时间切片图（看波速/方向）、胶片条、帧间变化、主周期（替代看原速视频）

所有下载默认写到 --out 目录，并追加记录到 <out>/manifest.jsonl。

调用方式（固定写法，不要省略 -X utf8）：
  python -X utf8 "<本 Skill 目录>\\scripts\\refgrab.py" <子命令> [参数] [--json]
--json 放在子命令前后都可以。

退出码：0 成功；1 部分失败（看 stderr 哪几项失败）；2 出错（stderr 有“失败：…”）；
        3 没有结果（换关键词/语言/来源再试）；4 refs 有点名对象参照不足（看 REFS.md 的下一步）。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util as importlib_util
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

# 用 python -I 运行时用户级 site-packages 会被屏蔽（yt-dlp / imageio-ffmpeg 装在那里），手动补回
try:
    import site
    _us = site.getusersitepackages()
    if os.path.isdir(_us) and _us not in sys.path:
        sys.path.append(_us)
except Exception:  # noqa: BLE001
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
TIMEOUT = 20

# 需要 Referer 才能取图的域名
REFERERS = {
    "i.pximg.net": "https://www.pixiv.net/",
    "hdslb.com": "https://www.bilibili.com/",
    "sinaimg.cn": "https://weibo.com/",
    "artstation.com": "https://www.artstation.com/",
    "baidu.com": "https://image.baidu.com/",
    "bdimg.com": "https://image.baidu.com/",
}

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


# --------------------------------------------------------------------------- 网络基础

def _headers(url: str, extra: dict | None = None) -> dict:
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
         "Accept": "*/*"}
    host = urllib.parse.urlsplit(url).netloc
    for dom, ref in REFERERS.items():
        if host.endswith(dom):
            h["Referer"] = ref
    if extra:
        h.update(extra)
    return h


def decode_os(b: bytes) -> str:
    """子进程输出：先按 UTF-8，不行再按系统区域编码（Windows 上 curl/schannel 的报错是 GBK）。"""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        import locale
        return b.decode(locale.getpreferredencoding(False) or "utf-8", "replace")


def _curl(url: str, headers: dict, timeout: int, retries: int = 2) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl 不可用")
    # --fail：HTTP 4xx/5xx 必须算失败，否则 404 错误页会被当成正常内容返回（如 gh-cat 把错误 JSON 当文件内容）
    cmd = [curl, "-sSL", "--fail", "--max-time", str(timeout), "--retry", str(retries)]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, timeout=timeout * (retries + 1) + 10)
    if r.returncode != 0:
        raise RuntimeError(f"curl 失败({r.returncode}): {decode_os(r.stderr)[:200]}")
    return r.stdout


# 搜索类请求“快速失败”：一个来源不通时不能拖住整条命令（实测 YouTube 不通时单次搜索 94 秒）。
# 只在 run_parallel 的工作线程里生效；下载、读页面仍用默认的较长超时和重试。
_FETCH_DEFAULTS = threading.local()
SEARCH_TIMEOUT, SEARCH_RETRIES = 12, 0


def fetch(url: str, *, headers: dict | None = None, timeout: int | None = None, retries: int | None = None) -> bytes:
    """GET，先 urllib，重试后再退到 curl（本机部分站点 Python TLS 会 EOF，curl 可通）。"""
    timeout = timeout if timeout is not None else getattr(_FETCH_DEFAULTS, "timeout", TIMEOUT)
    retries = retries if retries is not None else getattr(_FETCH_DEFAULTS, "retries", 2)
    h = _headers(url, headers)
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    data = gzip.decompress(data)
                return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (404, 410):
                # 资源确实不存在：curl 也不会拿到，直接报错，不浪费时间
                raise RuntimeError(f"{url} 取不到：HTTP Error {e.code}") from None
            if e.code in (401, 403):
                break  # 可能是针对 Python 的拦截，交给 curl 再试一次
        except Exception as e:  # noqa: BLE001 - 网络错误种类很多，统一重试
            last = e
        if i < retries:
            time.sleep(0.6 * (i + 1))
    try:
        return _curl(url, h, timeout, min(retries, 2))
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"{url} 取不到：urllib={last!r}; curl={e}") from None


def fetch_text(url: str, **kw) -> str:
    return fetch(url, **kw).decode("utf-8", "replace")


def fetch_json(url: str, **kw):
    return json.loads(fetch(url, **kw).decode("utf-8", "replace"))


def q(s: str) -> str:
    return urllib.parse.quote(s)


# --------------------------------------------------------------------------- manifest

_RECORD_LOCK = threading.Lock()


def record(out: Path, entry: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    entry.setdefault("time", time.strftime("%Y-%m-%dT%H:%M:%S"))
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _RECORD_LOCK, open(out / "manifest.jsonl", "a", encoding="utf-8") as f:
        f.write(line)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- HTML 工具

class _PageParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "pre", "figcaption"}

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.text: list[str] = []
        self.images: list[dict] = []
        self.links: list[dict] = []
        self.meta: dict = {}
        self.title = ""
        self._skip = 0
        self._in_title = False
        self._a: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.text.append("\n")
        if tag == "meta":
            k = a.get("property") or a.get("name")
            if k and a.get("content"):
                self.meta[k] = a["content"]
        if tag == "img":
            src = a.get("data-src") or a.get("data-original") or a.get("src") or ""
            srcset = a.get("srcset") or a.get("data-srcset") or ""
            if srcset:
                best = srcset.split(",")[-1].strip().split(" ")[0]
                src = best or src
            if src and not src.startswith("data:"):
                self.images.append({"src": urllib.parse.urljoin(self.base, src), "alt": a.get("alt", "")})
        if tag == "a" and a.get("href"):
            self._a = {"href": urllib.parse.urljoin(self.base, a["href"]), "text": ""}

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._a is not None:
            self._a["text"] = self._a["text"].strip()
            self.links.append(self._a)
            self._a = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._skip:
            return
        self.text.append(data)
        if self._a is not None:
            self._a["text"] += data


def parse_page(html_text: str, base: str) -> dict:
    p = _PageParser(base)
    try:
        p.feed(html_text)
    except Exception:  # noqa: BLE001 - 坏 HTML 不影响已解析部分
        pass
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.text))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    imgs, seen = [], set()
    og = p.meta.get("og:image")
    if og:
        imgs.append({"src": urllib.parse.urljoin(base, og), "alt": "og:image"})
    for im in p.images:
        if im["src"] not in seen:
            seen.add(im["src"])
            imgs.append(im)
    return {"url": base, "title": p.title.strip(), "description": p.meta.get("og:description") or p.meta.get("description", ""),
            "text": text, "images": imgs, "links": p.links}


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


# --------------------------------------------------------------------------- 网页搜索

def bing_real_url(href: str) -> str:
    """国际版 Bing 给的是 /ck/a 跳转，真实地址在 u=a1<base64url>；解不出就原样返回。"""
    if "bing.com/ck/a" not in href:
        return href
    u = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("u", [""])[0]
    if not u.startswith("a1"):
        return href
    import base64
    try:
        b = u[2:] + "=" * (-len(u[2:]) % 4)
        real = base64.urlsafe_b64decode(b).decode("utf-8", "strict")
        return real if real.startswith("http") else href
    except Exception:  # noqa: BLE001
        return href


def web_bing(query: str, n: int, cn: bool = False) -> list[dict]:
    # 英文区参数避免中文 IP 下相关性错乱（之前搜 genshin 返回自行车零件）
    url = (f"https://cn.bing.com/search?q={q(query)}&count={n}" if cn else
           f"https://www.bing.com/search?q={q(query)}&count={n}&setlang=en-US&cc=US&mkt=en-US&ensearch=1")
    s = fetch_text(url)
    out = []
    for m in re.finditer(r'<li class="b_algo"(.*?)</li>', s, re.S):
        block = m.group(1)
        a = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        snip = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        href = bing_real_url(html.unescape(a.group(1)))
        out.append({"title": strip_tags(a.group(2)), "url": href,
                    "snippet": strip_tags(snip.group(1)) if snip else ""})
    return out[:n]


def web_ddg(query: str, n: int) -> list[dict]:
    s = fetch_text(f"https://html.duckduckgo.com/html/?q={q(query)}")
    out = []
    for m in re.finditer(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>(.*?)(?=<a rel="nofollow" class="result__a"|$)', s, re.S):
        href = html.unescape(m.group(1))
        uddg = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("uddg")
        if uddg:
            href = uddg[0]
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', m.group(3), re.S)
        out.append({"title": strip_tags(m.group(2)), "url": href, "snippet": strip_tags(snip.group(1)) if snip else ""})
    return out[:n]


def web_baidu(query: str, n: int) -> list[dict]:
    s = fetch_text(f"https://www.baidu.com/s?wd={q(query)}&rn={n}")
    out = []
    for m in re.finditer(r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', s, re.S):
        out.append({"title": strip_tags(m.group(2)), "url": html.unescape(m.group(1)), "snippet": "",
                    "note": "百度跳转链接，page 子命令会自动跟随"})
    return out[:n]


def web_marginalia(query: str, n: int) -> list[dict]:
    s = fetch_text(f"https://search.marginalia.nu/search?query={q(query)}")
    out = []
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*"[^>]*>\s*<h2[^>]*>(.*?)</h2>', s, re.S):
        out.append({"title": strip_tags(m.group(2)), "url": html.unescape(m.group(1)), "snippet": ""})
    if not out:
        for m in re.finditer(r'<h2[^>]*>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', s, re.S):
            out.append({"title": strip_tags(m.group(2)), "url": html.unescape(m.group(1)), "snippet": ""})
    return out[:n]


WEB_ENGINES = {"bing": lambda qq, n: web_bing(qq, n), "ddg": web_ddg, "bingcn": lambda qq, n: web_bing(qq, n, cn=True),
               "baidu": web_baidu}
# marginalia 现已改为前端渲染，静态抓取拿不到结果，暂不接入（函数保留备用）


def short_reason(e: BaseException | str) -> str:
    """把冗长的网络错误压成一眼能懂的原因（去掉 URL）。"""
    s = str(e)
    rules = [(r"HTTP Error (\d{3})|HTTPError.*?(\d{3})|returned error: (\d{3})",
              lambda m: f"HTTP {m.group(1) or m.group(2) or m.group(3)}"),
             (r"timed out|TimeoutError|Timeout", lambda m: "超时"),
             (r"UNEXPECTED_EOF|handshake|SSLEOF|curl.*\(35\)", lambda m: "SSL 握手失败（本机网络对该域名不通）"),
             (r"CERTIFICATE_VERIFY_FAILED", lambda m: "证书校验失败"),
             (r"getaddrinfo|Name or service not known|could not resolve", lambda m: "域名解析失败"),
             (r"Connection reset|ConnectionResetError|10054", lambda m: "连接被重置"),
             (r"Connection refused|10061", lambda m: "连接被拒绝")]
    for pat, fmt in rules:
        m = re.search(pat, s, re.I)
        if m:
            return fmt(m)
    s = re.sub(r"https?://\S+", "<url>", s)
    return s[:160]


def fast_fail(f, *a):
    """在当前线程里以“快速失败”参数调用搜索函数。"""
    _FETCH_DEFAULTS.timeout, _FETCH_DEFAULTS.retries = SEARCH_TIMEOUT, SEARCH_RETRIES
    try:
        return f(*a)
    finally:
        del _FETCH_DEFAULTS.timeout, _FETCH_DEFAULTS.retries


def run_parallel(funcs: dict, query: str, n: int) -> tuple[list[dict], dict]:
    results, status = [], {}
    with cf.ThreadPoolExecutor(len(funcs)) as ex:
        futs = {ex.submit(fast_fail, f, query, n): name for name, f in funcs.items()}
        for fut in cf.as_completed(futs):
            name = futs[fut]
            try:
                items = fut.result()
                status[name] = len(items)
                for it in items:
                    it["src"] = name
                    results.append(it)
            except Exception as e:  # noqa: BLE001
                status[name] = f"失败：{short_reason(e)}"
                status.setdefault("_errors", {})[name] = str(e)[:1000]
    return results, status


def dedupe(items: list[dict], key: str) -> list[dict]:
    seen, out = set(), []
    for it in items:
        k = (it.get(key) or "").split("#")[0].rstrip("/")
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


# --------------------------------------------------------------------------- 图片搜索

def img_bing(query: str, n: int) -> list[dict]:
    out = []
    for first in range(0, max(n, 35), 35):
        s = fetch_text(f"https://www.bing.com/images/async?q={q(query)}&first={first}&count=35&mmasync=1"
                       f"&setlang=en-US&cc=US&mkt=en-US")
        for m in re.finditer(r'\sm="([^"]+)"', s):
            try:
                d = json.loads(html.unescape(m.group(1)))
            except ValueError:
                continue
            if d.get("murl"):
                out.append({"url": d["murl"], "thumb": d.get("turl", ""), "title": d.get("t", ""),
                            "page": d.get("purl", "")})
        if len(out) >= n:
            break
    return out[:n]


def img_baidu(query: str, n: int) -> list[dict]:
    d = json.loads(fetch_text(f"https://image.baidu.com/search/acjson?tn=resultjson_com&ipn=rj&word={q(query)}"
                              f"&queryWord={q(query)}&pn=0&rn={min(n, 60)}&ie=utf-8&oe=utf-8"))
    out = []
    for it in d.get("data", []):
        if not isinstance(it, dict) or not it.get("thumbURL"):
            continue
        big = ""
        for r in it.get("replaceUrl") or []:
            if r.get("ObjURL"):
                big = r["ObjURL"]
        out.append({"url": big or it.get("middleURL") or it["thumbURL"], "thumb": it["thumbURL"],
                    "title": strip_tags(it.get("fromPageTitleEnc") or it.get("fromPageTitle", "")),
                    "page": it.get("fromURLHost", ""), "size": f'{it.get("width")}x{it.get("height")}'})
    return out[:n]


def img_wallhaven(query: str, n: int) -> list[dict]:
    d = fetch_json(f"https://wallhaven.cc/api/v1/search?q={q(query)}&categories=111&purity=100&sorting=relevance")
    return [{"url": it["path"], "thumb": it["thumbs"]["small"], "title": ",".join(it.get("colors", [])),
             "page": it["url"], "size": it.get("resolution", "")} for it in d.get("data", [])][:n]


def img_safebooru(query: str, n: int) -> list[dict]:
    tags = "+".join(t for t in query.split())
    d = fetch_json(f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit={min(n, 100)}&tags={tags}")
    out = []
    for it in d or []:
        fu = it.get("file_url") or f'https://safebooru.org/images/{it["directory"]}/{it["image"]}'
        out.append({"url": fu, "thumb": it.get("preview_url", ""), "title": it.get("tags", "")[:120],
                    "page": f'https://safebooru.org/index.php?page=post&s=view&id={it["id"]}',
                    "size": f'{it.get("width")}x{it.get("height")}'})
    return out[:n]


def img_pixiv(query: str, n: int) -> list[dict]:
    d = fetch_json(f"https://www.pixiv.net/ajax/search/artworks/{q(query)}?word={q(query)}&order=popular_d&mode=safe&p=1&s_mode=s_tag",
                   headers={"Referer": "https://www.pixiv.net/"})
    out = []
    for it in d.get("body", {}).get("illustManga", {}).get("data", []):
        if not isinstance(it, dict) or not it.get("url"):
            continue
        thumb = it["url"]
        # 缩略图 → 大图（master1200），需要 Referer，get 子命令会自动加
        big = re.sub(r"/c/\d+x\d+(_\d+)?(_[a-z0-9]+)?/", "/", thumb).replace("/custom-thumb/", "/img-master/").replace("_custom1200", "_master1200").replace("_square1200", "_master1200")
        out.append({"url": big, "thumb": thumb, "title": it.get("title", ""),
                    "page": f'https://www.pixiv.net/artworks/{it["id"]}', "size": f'{it.get("width")}x{it.get("height")}'})
    return out[:n]


def img_artstation(query: str, n: int) -> list[dict]:
    d = fetch_json(f"https://www.artstation.com/api/v2/search/projects.json?query={q(query)}&page=1&per_page={min(n, 50)}&sorting=relevance")
    out = []
    for it in d.get("data", []):
        cover = it.get("smaller_square_cover_url") or (it.get("cover") or {}).get("small_square_url", "")
        big = re.sub(r"/(smaller_square|small_square|micro_square|medium)/", "/large/", cover)
        out.append({"url": big, "thumb": cover, "title": it.get("title", ""), "page": it.get("url", ""),
                    "author": (it.get("user") or {}).get("full_name", "")})
    return out[:n]


def img_openverse(query: str, n: int) -> list[dict]:
    d = fetch_json(f"https://api.openverse.org/v1/images/?q={q(query)}&page_size={min(n, 20)}", timeout=30)
    return [{"url": it["url"], "thumb": it.get("thumbnail", ""), "title": it.get("title", ""),
             "page": it.get("foreign_landing_url", ""), "license": f'{it.get("license")} {it.get("license_version", "")}'}
            for it in d.get("results", [])][:n]


def mw_images(api: str, query: str, n: int) -> list[dict]:
    d = fetch_json(f"{api}?action=query&format=json&generator=search&gsrsearch={q(query)}&gsrnamespace=6"
                   f"&gsrlimit={min(n, 50)}&prop=imageinfo&iiprop=url|size&iiurlwidth=320")
    out = []
    for p in (d.get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("url"):
            out.append({"url": ii["url"], "thumb": ii.get("thumburl", ""), "title": p.get("title", ""),
                        "page": ii.get("descriptionurl", ""), "size": f'{ii.get("width")}x{ii.get("height")}'})
    return out[:n]


WIKIS = {
    "commons": "https://commons.wikimedia.org/w/api.php",
    "wikipedia": "https://en.wikipedia.org/w/api.php",
    "zhwiki": "https://zh.wikipedia.org/w/api.php",
    "genshin": "https://genshin-impact.fandom.com/api.php",
    "zelda": "https://zelda.fandom.com/api.php",
    "wuwa": "https://wutheringwaves.fandom.com/api.php",
    "ys": "https://wiki.biligame.com/ys/api.php",          # 原神 B 站 wiki
    "mc": "https://wiki.biligame.com/wutheringwaves/api.php",  # 鸣潮 B 站 wiki
    "sr": "https://wiki.biligame.com/sr/api.php",           # 星穹铁道
    "zzz": "https://wiki.biligame.com/zzz/api.php",
}

IMG_ENGINES = {
    "bing": img_bing, "baidu": img_baidu, "wallhaven": img_wallhaven, "safebooru": img_safebooru,
    "pixiv": img_pixiv, "artstation": img_artstation, "openverse": img_openverse,
    "commons": lambda qq, n: mw_images(WIKIS["commons"], qq, n),
    "genshin": lambda qq, n: mw_images(WIKIS["genshin"], qq, n),
    "zelda": lambda qq, n: mw_images(WIKIS["zelda"], qq, n),
}
IMG_DEFAULT = ["bing", "baidu", "pixiv", "artstation", "wallhaven"]


# --------------------------------------------------------------------------- 视频搜索

def vid_bilibili(query: str, n: int) -> list[dict]:
    # 先访问首页拿 buvid3 cookie，否则搜索接口有时返回 412
    cookie = ""
    try:
        req = urllib.request.Request("https://www.bilibili.com/", headers=_headers("https://www.bilibili.com/"))
        with urllib.request.urlopen(req, timeout=10) as r:
            cookie = "; ".join(c.split(";")[0] for c in r.headers.get_all("Set-Cookie") or [])
    except Exception:  # noqa: BLE001
        pass
    d = fetch_json(f"https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={q(query)}&page=1",
                   headers={"Referer": "https://search.bilibili.com/", "Cookie": cookie})
    out = []
    for it in (d.get("data") or {}).get("result") or []:
        pic = it.get("pic", "")
        out.append({"title": strip_tags(it.get("title", "")), "url": f'https://www.bilibili.com/video/{it.get("bvid")}',
                    "duration": it.get("duration", ""), "author": it.get("author", ""),
                    "views": it.get("play"), "thumb": ("https:" + pic) if pic.startswith("//") else pic})
    return out[:n]


def vid_youtube(query: str, n: int) -> list[dict]:
    s = fetch_text(f"https://www.youtube.com/results?search_query={q(query)}&hl=en",
                   headers={"Accept-Language": "en-US,en;q=0.9"})
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", s, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))
    out = []

    def walk(o):
        if isinstance(o, dict):
            vr = o.get("videoRenderer")
            if vr and vr.get("videoId"):
                vid = vr["videoId"]
                out.append({"title": "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", [])),
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "duration": (vr.get("lengthText") or {}).get("simpleText", ""),
                            "author": "".join(r.get("text", "") for r in (vr.get("ownerText") or {}).get("runs", [])),
                            "views": (vr.get("viewCountText") or {}).get("simpleText", ""),
                            "thumb": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"})
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return out[:n]


def vid_youtube_ytdlp(query: str, n: int) -> list[dict]:
    """YouTube 页面解析失败时的退路：yt-dlp 的 ytsearch，只取列表不下载。"""
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "-J", f"ytsearch{n}:{query}", "--socket-timeout", "10"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    if r.returncode != 0:
        raise RuntimeError("yt-dlp 搜索失败：" + (r.stderr or "")[-200:])
    out = []
    for e in json.loads(r.stdout).get("entries") or []:
        vid = e.get("id")
        if not vid:
            continue
        dur = e.get("duration")
        out.append({"title": e.get("title", ""), "url": f"https://www.youtube.com/watch?v={vid}",
                    "duration": f"{int(dur) // 60}:{int(dur) % 60:02d}" if dur else "",
                    "author": e.get("channel") or e.get("uploader", ""), "views": e.get("view_count"),
                    "thumb": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"})
    return out[:n]


def vid_youtube_any(query: str, n: int) -> list[dict]:
    try:
        items = vid_youtube(query, n)
        if items:
            return items
    except Exception:  # noqa: BLE001 - 页面结构或网络问题，交给 yt-dlp
        pass
    return vid_youtube_ytdlp(query, n)


VID_ENGINES = {"bilibili": vid_bilibili, "youtube": vid_youtube_any}


# --------------------------------------------------------------------------- 下载

def guess_ext(url: str, data: bytes) -> str:
    sig = {b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg", b"GIF8": ".gif", b"%PDF": ".pdf", b"PK\x03\x04": ".zip"}
    for k, v in sig.items():
        if data.startswith(k):
            return v
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return ".avif"
    ext = os.path.splitext(urllib.parse.urlsplit(url).path)[1].lower()
    return ext if ext and len(ext) <= 5 else ".bin"


def safe_name(s: str, limit: int = 60) -> str:
    # [] 也替换：PowerShell 会把它当通配符，导致 Get-ChildItem/Get-Content 找不到文件
    s = re.sub(r'[\\/:*?"<>|\[\]\s]+', "_", s).strip("._")
    return s[:limit] or "file"


def download(url: str, out: Path, name: str | None = None, meta: dict | None = None,
             timeout: int = 40, retries: int = 2) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    data = fetch(url, timeout=timeout, retries=retries)
    if len(data) < 200:
        raise RuntimeError(f"内容过小（{len(data)} 字节），多半是防盗链或错误页")
    if data[:15].lstrip().lower().startswith((b"<!doctype", b"<html")):
        raise RuntimeError("拿到的是 HTML 页面而不是文件（防盗链/需要登录），改用 page 子命令找真实地址")
    ext = guess_ext(url, data)
    base = safe_name(name or os.path.splitext(os.path.basename(urllib.parse.urlsplit(url).path))[0] or "file")
    # 独占创建（"xb"）：并行下载同名文件时不会互相覆盖
    i = 0
    while True:
        path = out / (f"{base}_{i}{ext}" if i else base + ext)
        try:
            with open(path, "xb") as f:
                f.write(data)
            break
        except FileExistsError:
            i += 1
    entry = {"file": path.name, "url": url, "bytes": len(data), "sha256": sha256(path)}
    try:
        from PIL import Image  # 可选
        with Image.open(path) as im:
            entry["size"] = f"{im.width}x{im.height}"
    except Exception:  # noqa: BLE001
        pass
    if meta:
        entry.update(meta)
    record(out, entry)
    return entry


# --------------------------------------------------------------------------- 浏览器（Edge 无头）

def edge_path() -> str | None:
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    return shutil.which("msedge") or shutil.which("chrome")


def edge_dump(url: str, wait_ms: int = 6000) -> str:
    exe = edge_path()
    if not exe:
        raise RuntimeError("未找到 Edge/Chrome")
    r = subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-first-run", "--mute-audio",
                        f"--virtual-time-budget={wait_ms}", f"--user-agent={UA}", "--dump-dom", url],
                       capture_output=True, timeout=90)
    return r.stdout.decode("utf-8", "replace")


def edge_shot(url: str, out: Path, w: int = 1600, h: int = 900, wait_ms: int = 6000) -> Path:
    exe = edge_path()
    if not exe:
        raise RuntimeError("未找到 Edge/Chrome")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--mute-audio",
                    f"--window-size={w},{h}", f"--virtual-time-budget={wait_ms}", f"--user-agent={UA}",
                    f"--screenshot={out.resolve()}", url], capture_output=True, timeout=90)
    if not out.exists():
        raise RuntimeError("截图失败")
    record(out.parent, {"file": out.name, "url": url, "kind": "page-screenshot", "sha256": sha256(out)})
    return out


# --------------------------------------------------------------------------- 视频与帧

def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        f = shutil.which("ffmpeg")
        if f:
            return f
    raise RuntimeError("没有 ffmpeg：python -m pip install --user imageio-ffmpeg")


def video_download(url: str, out: Path, section: str | None, height: int) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    before = set(out.iterdir())
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--ffmpeg-location", ffmpeg_exe(),
           "-f", f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b", "--merge-output-format", "mp4",
           "-o", str(out / "%(title).50s_%(id)s.%(ext)s"), "--no-mtime", "--windows-filenames", "--replace-in-metadata", "title", "[\\[\\]]", "_"]
    node = shutil.which("node")
    if node:
        cmd += ["--js-runtimes", f"node:{node}"]
    if section:
        cmd += ["--download-sections", f"*{section}", "--force-keyframes-at-cuts"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if r.returncode != 0 and "--js-runtimes" in cmd:
        # 旧版 yt-dlp 不认识 --js-runtimes，去掉重试
        i = cmd.index("--js-runtimes")
        del cmd[i:i + 2]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if r.returncode != 0:
        raise RuntimeError("yt-dlp 失败：\n" + (r.stderr or r.stdout)[-1500:])
    new = [p for p in out.iterdir() if p not in before and p.suffix.lower() in (".mp4", ".webm", ".mkv")]
    for p in new:
        record(out, {"file": p.name, "url": url, "kind": "video", "section": section or "full",
                     "bytes": p.stat().st_size, "sha256": sha256(p)})
    return new


def extract_frames(video: Path, out: Path, every: float | None, scene: float | None, at: list[float] | None,
                   width: int, limit: int) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    stem = safe_name(video.stem, 40)
    ff = ffmpeg_exe()
    made: list[Path] = []
    if at:
        for t in at:
            p = out / f"{stem}_t{t:07.2f}.png"
            subprocess.run([ff, "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={width}:-2", str(p)], check=True)
            made.append(p)
    else:
        if scene is not None:
            vf = f"select='gt(scene,{scene})',scale={width}:-2"
            extra = ["-fps_mode", "vfr"]  # ffmpeg 7+ 已移除 -vsync
        else:
            vf = f"fps=1/{every or 2},scale={width}:-2"
            extra = []
        pattern = out / f"{stem}_%04d.png"
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(video), "-vf", vf, *extra,
                        "-frames:v", str(limit), str(pattern)], check=True)
        # 不用 glob：文件名里的 [] 会被当成通配字符类
        made = sorted(p for p in out.iterdir() if p.name.startswith(stem + "_") and p.suffix == ".png")
    for p in made:
        record(out, {"file": p.name, "kind": "frame", "video": str(video), "sha256": sha256(p)})
    return made


# --------------------------------------------------------------------------- 拼图

def _font(size: int):
    from PIL import ImageFont
    for f in ("msyh.ttc", "simhei.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def contact_sheet(paths: list[Path], out: Path, cols: int, cell: int) -> Path:
    from PIL import Image, ImageDraw
    ims = []
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((cell, cell))
            ims.append((p.name, im))
        except Exception:  # noqa: BLE001
            continue
    if not ims:
        raise RuntimeError("没有可读的图片")
    rows = (len(ims) + cols - 1) // cols
    lab = 22
    sheet = Image.new("RGB", (cols * cell, rows * (cell + lab)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    f = _font(14)
    for i, (name, im) in enumerate(ims):
        x, y = (i % cols) * cell, (i // cols) * (cell + lab)
        sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
        d.text((x + 4, y + cell + 3), f"{i + 1}. {name}"[:40], fill=(230, 230, 230), font=f)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def compare(paths: list[Path], labels: list[str], out: Path, height: int) -> Path:
    from PIL import Image, ImageDraw
    ims = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        w = round(im.width * height / im.height)
        ims.append(im.resize((w, height), Image.LANCZOS))
    lab = 40
    gap = 8
    total = sum(i.width for i in ims) + gap * (len(ims) - 1)
    canvas = Image.new("RGB", (total, height + lab), (18, 18, 18))
    d = ImageDraw.Draw(canvas)
    f = _font(24)
    x = 0
    for im, text in zip(ims, labels):
        canvas.paste(im, (x, lab))
        d.text((x + 10, 6), text, fill=(240, 240, 240), font=f)
        x += im.width + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


# --------------------------------------------------------------------------- 输出

def emit(args, items, status=None):
    """输出结果；返回退出码：有结果 0，无结果 3。"""
    if args.json:
        print(json.dumps({"status": status, "items": items}, ensure_ascii=False, indent=1))
        return 0 if items else 3
    if status:
        print("来源状态：" + "，".join(f"{k}={v}" for k, v in status.items() if not k.startswith("_")))
    if not items:
        print("无结果。换更短的关键词、换语言（中/英/日）、或换来源；Pixiv/ArtStation/booru 用短标签效果最好。")
    for i, it in enumerate(items, 1):
        head = f"{i:3d}. [{it.get('src', '')}] {it.get('title', '')[:90]}"
        extra = " ".join(str(it[k]) for k in ("duration", "size", "author", "license") if it.get(k))
        print(head + (f"  ({extra})" if extra else ""))
        print("     " + it.get("url", ""))
        if it.get("snippet"):
            print("     " + it["snippet"][:160])
        if it.get("page") and it.get("page") != it.get("url"):
            print("     页面: " + it["page"])
    return 0 if items else 3


# --------------------------------------------------------------------------- 子命令

DEPENDENCIES = [
    # (导入名, pip 包名, 用途, 许可/备注)
    ("PIL", "pillow", "触表、对比图、measure、图片过滤", "HPND，必需"),
    ("yt_dlp", "yt-dlp", "vdl、subs、YouTube 搜索退路", "Unlicense"),
    ("imageio_ffmpeg", "imageio-ffmpeg", "frames 截帧、vdl 合并音视频", "BSD；内含 ffmpeg（LGPL/GPL）"),
    ("pypdf", "pypdf", "pdf 文本", "BSD"),
    ("pymupdf", "pymupdf", "pdf --images 提取插图（可选）", "AGPL：只在本机研究用，不要随 Skill 包分发"),
]


def cmd_doctor(args):
    """依赖 + 各来源实时连通性。退出码：全部 ok 为 0，有来源失败为 1，缺必需依赖为 2。"""
    print(f"python {sys.version.split()[0]}   脚本：{Path(__file__).resolve()}")
    missing_required = False
    for mod, pkg, use, lic in DEPENDENCIES:
        ok = importlib_util.find_spec(mod) is not None or (mod == "pymupdf" and importlib_util.find_spec("fitz") is not None)
        if ok:
            print(f"  [ok] {pkg:15s} {use}  （{lic}）")
        else:
            print(f"  [缺] {pkg:15s} {use}  → python -m pip install --user {pkg}  （{lic}）")
            missing_required |= mod == "PIL"
    print(f"  edge: {edge_path() or '无（page --js / shot 不可用）'}   curl: {shutil.which('curl.exe') or shutil.which('curl') or '无'}"
          f"   node: {shutil.which('node') or '无'}   git: {_git_exe() or '无'}")
    try:
        print(f"  ffmpeg: {ffmpeg_exe()}")
    except RuntimeError as e:
        print(f"  ffmpeg: {e}")
    probe = "water"
    checks = {**{f"web:{k}": (lambda f=f: f(probe, 3)) for k, f in WEB_ENGINES.items()},
              **{f"img:{k}": (lambda f=f: f(probe, 3)) for k, f in IMG_ENGINES.items()},
              **{f"vid:{k}": (lambda f=f: f(probe, 3)) for k, f in VID_ENGINES.items()},
              "github:api": lambda: [gh_file("Unity-Technologies/BoatAttack", "README.md", "HEAD", SEARCH_TIMEOUT)[0][:1]]}
    with cf.ThreadPoolExecutor(16) as ex:
        futs = {ex.submit(fast_fail, f): k for k, f in checks.items()}
        res = {}
        for fut in cf.as_completed(futs):
            try:
                n = len(fut.result())
                res[futs[fut]] = f"ok({n})" if n else "无结果"
            except Exception as e:  # noqa: BLE001
                res[futs[fut]] = f"失败：{short_reason(e)}"
    for k in checks:
        print(f"  {k:16s} {res[k]}")
    bad = [k for k, v in res.items() if not v.startswith("ok")]
    if bad:
        print(f"不可用：{', '.join(bad)}。其余来源照常用；见 reference-acquisition 的来源路由换源。")
    return 2 if missing_required else (1 if bad else 0)

def cmd_web(args):
    engines = {k: WEB_ENGINES[k] for k in (args.src or ["bing", "ddg", "bingcn"])}
    query = args.query + (f" site:{args.site}" if args.site else "")
    items, status = run_parallel(engines, query, args.n)
    return emit(args, dedupe(items, "url"), status)


def cmd_images(args):
    names = args.src or IMG_DEFAULT
    engines = {k: IMG_ENGINES[k] for k in names}
    items, status = run_parallel(engines, args.query, args.n)
    items = apply_must(dedupe(items, "url"), args.must)
    rc = emit(args, items, status)
    if args.download:
        out = Path(args.download)
        ok = 0
        with cf.ThreadPoolExecutor(8) as ex:
            futs = {ex.submit(download, it["url"], out, f'{it["src"]}_{i:03d}',
                              {"query": args.query, "source": it["src"], "page": it.get("page", ""),
                               "title": it.get("title", "")}, 15, 0): it for i, it in enumerate(items, 1)}
            for fut in cf.as_completed(futs):
                it = futs[fut]
                try:
                    fut.result()
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    # 大图失败就退回缩略图，至少保证能看
                    if it.get("thumb"):
                        try:
                            download(it["thumb"], out, f'{it["src"]}_thumb', {"query": args.query, "source": it["src"],
                                                                             "page": it.get("page", ""), "fallback": "thumb"})
                            ok += 1
                            continue
                        except Exception:  # noqa: BLE001
                            pass
                    print(f"  下载失败 {it['url'][:90]}: {str(e)[:100]}", file=sys.stderr)
        print(f"已下载 {ok}/{len(items)} → {out}（记录在 manifest.jsonl）")
        if args.min_width:
            kept, notes = filter_images(out, reference_images(out), args.min_width)
            print(f"质量过滤：保留 {len(kept)}，移到 _rejected/ {len(notes)}" + (f"（{'；'.join(notes[:5])}）" if notes else ""))
        if args.sheet:
            imgs = reference_images(out)
            if imgs:
                print("触表：", contact_sheet(imgs, out / "_contact.png", 6, 260))
        if ok == 0:
            return 3
    return rc


def apply_must(items: list[dict], must: str | None) -> list[dict]:
    """标题/作者里一个必含词都没有的结果标记 offTopic 并排到最后（不删，标题可能没写作品名）。
    B 站搜“王国之泪 水面 船 实机”会混进和平精英，这样一眼能看出来。"""
    words = [w.strip().lower() for w in re.split(r"[,，|]", must or "") if w.strip()]
    if not words:
        return items
    for it in items:
        text = f"{it.get('title', '')} {it.get('author', '')} {it.get('page', '')}".lower()
        it["offTopic"] = not any(w in text for w in words)
        if it["offTopic"]:
            it["title"] = "[疑似跑题] " + it.get("title", "")
    return sorted(items, key=lambda it: it["offTopic"])


def cmd_video(args):
    engines = {k: VID_ENGINES[k] for k in (args.src or ["bilibili", "youtube"])}
    items, status = run_parallel(engines, args.query, args.n)
    items = apply_must(dedupe(items, "url"), args.must)
    if args.must and items and all(it["offTopic"] for it in items):
        print(f"注意：全部结果标题都不含 {args.must}，多半跑题；换关键词（作品名放最前、少加修饰词）或换来源", file=sys.stderr)
    return emit(args, items, status)


def cmd_get(args):
    out = Path(args.out)
    failed = 0
    for u in args.urls:
        try:
            e = download(u, out, args.name)
            print(f"ok  {e['file']}  {e.get('size', '')}  {e['bytes']}B")
        except Exception as ex:  # noqa: BLE001
            failed += 1
            print(f"失败 {u}: {ex}", file=sys.stderr)
    return 1 if failed else 0


def cmd_page(args):
    url = args.url
    raw = edge_dump(url) if args.js else fetch_text(url)
    if not args.js and len(re.sub(r"<[^>]+>", "", raw).strip()) < 300:
        print("（静态内容太少，像是前端渲染页面，自动改用 Edge 无头渲染）", file=sys.stderr)
        raw = edge_dump(url)
    if re.search(r"Just a moment|cf-chl|challenge-platform|cf_chl_opt", raw[:20000]):
        raise SystemExit("该页面有 Cloudflare 人机验证，无头浏览器过不去。改用：站点 JSON 接口（expand 子命令）、"
                         "Codex browser 插件的真实浏览器，或请用户手动保存。")
    page = parse_page(raw, url)
    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(f"# {page['title']}\n来源：{url}\n\n{page['text']}", encoding="utf-8")
    if args.json:
        print(json.dumps(page, ensure_ascii=False, indent=1))
        return
    print(f"标题：{page['title']}\n描述：{page['description']}\n")
    text = page["text"]
    print(text[:args.chars] + (f"\n…（共 {len(text)} 字，--chars 调整或 --save 保存全文）" if len(text) > args.chars else ""))
    print(f"\n图片 {len(page['images'])} 张：")
    for im in page["images"][:args.imgs]:
        print("  " + im["src"] + (f"  [{im['alt'][:40]}]" if im["alt"] else ""))
    if args.links:
        print(f"\n链接 {len(page['links'])} 个：")
        for ln in page["links"][:args.links]:
            print(f"  {ln['text'][:50]}  {ln['href']}")


def cmd_shot(args):
    print(edge_shot(args.url, Path(args.out), args.w, args.h, args.wait))


def cmd_vdl(args):
    paths = video_download(args.url, Path(args.out), args.section, args.height)
    if not paths:
        raise SystemExit("yt-dlp 没报错但目录里没有新视频文件（可能已存在同名文件）；看 --out 目录")
    if args.json:
        print(json.dumps({"paths": [str(p) for p in paths]}, ensure_ascii=False, indent=1))
        return 0
    for p in paths:
        print(p)
    return 0


def cmd_frames(args):
    at = [float(x) for x in args.at.split(",")] if args.at else None
    made = extract_frames(Path(args.video), Path(args.out), args.every, args.scene, at, args.width, args.limit)
    sheet = contact_sheet(made, Path(args.out) / "_contact.png", 5, 320) if args.sheet and made else None
    if args.json:
        print(json.dumps({"frames": [str(p) for p in made], "sheet": str(sheet) if sheet else None}, ensure_ascii=False, indent=1))
        return 0 if made else 3
    print(f"{len(made)} 帧 → {args.out}")
    if sheet:
        print("触表：", sheet)
    return 0 if made else 3


def cmd_sheet(args):
    paths = []
    for a in args.images:
        p = Path(a)
        paths += reference_images(p) if p.is_dir() else [p]
    print(contact_sheet(paths, Path(args.out), args.cols, args.cell))


def cmd_compare(args):
    labels = args.labels.split("|") if args.labels else ["参照", "当前版", "上一版"][:len(args.images)]
    print(compare([Path(p) for p in args.images], labels, Path(args.out), args.height))


def cmd_wiki(args):
    api = WIKIS.get(args.site, args.site)
    if args.images:
        items = mw_images(api, args.query, args.n)
    else:
        d = fetch_json(f"{api}?action=query&format=json&list=search&srsearch={q(args.query)}&srlimit={args.n}")
        base = api.rsplit("/", 1)[0]
        items = [{"title": r["title"], "url": f"{base}/index.php?curid={r['pageid']}", "snippet": strip_tags(r.get("snippet", ""))}
                 for r in d.get("query", {}).get("search", [])]
    for it in items:
        it["src"] = args.site
    return emit(args, items)


def cmd_gh(args):
    d = fetch_json(f"https://api.github.com/search/repositories?q={q(args.query)}&sort={args.sort}&per_page={args.n}",
                   headers={"Accept": "application/vnd.github+json"})
    items = [{"src": "github", "title": f'{r["full_name"]} ★{r["stargazers_count"]}', "url": r["html_url"],
              "snippet": (r.get("description") or "")[:150], "license": (r.get("license") or {}).get("spdx_id", "")}
             for r in d.get("items", [])]
    return emit(args, items)


def _git_exe() -> str | None:
    """系统 git；没有时找 UGit 自带的 git。"""
    g = shutil.which("git")
    if g:
        return g
    found = next(iter(Path(os.environ.get("LOCALAPPDATA", "")).glob("UGit/app-*/resources/app/git/cmd/git.exe")), None)
    return str(found) if found else None


def cmd_gh_dl(args):
    repo = args.repo.strip("/")
    out = Path(args.out)
    ref = args.ref
    if not ref:
        ref = fetch_json(f"https://api.github.com/repos/{repo}").get("default_branch", "main")
    # 本机实测：api zipball 可通，codeload 偶发 TLS EOF；都失败再用 git 浅克隆
    urls = [f"https://api.github.com/repos/{repo}/zipball/{ref}",
            f"https://codeload.github.com/{repo}/zip/refs/heads/{ref}"]
    git = _git_exe()

    def clone():
        dest = out / safe_name(repo.replace("/", "__"))
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(git), "clone", "--depth", "1", "--branch", ref, f"https://github.com/{repo}.git", str(dest)],
                       check=True, timeout=1800)
        record(out, {"file": dest.name, "repo": repo, "ref": ref, "kind": "git-clone"})
        print(f"ok {dest}")

    if args.git and git:
        clone()
        return
    for u in urls:
        try:
            e = download(u, out, safe_name(repo.replace("/", "__") + "_" + ref), {"repo": repo, "ref": ref})
            print(f"ok {out / e['file']}  {e['bytes']}B")
            return
        except Exception as ex:  # noqa: BLE001
            print(f"  {u} 失败：{short_reason(ex)}", file=sys.stderr)
    if not git:
        raise SystemExit("两个 zip 地址都失败，本机也没有 git 可做浅克隆")
    print("  zip 都失败，改用 git 浅克隆", file=sys.stderr)
    clone()


# --------------------------------------------------------------------------- 图片质量：尺寸与去重

def _pixels(im) -> list:
    """Pillow 新旧版本通用的像素列表。"""
    return list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())


def image_info(path: Path) -> tuple[int, int, int] | None:
    """返回 (宽, 高, 64 位 dHash)；读不了返回 None。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
            g = im.convert("L").resize((9, 8), Image.LANCZOS)
            px = _pixels(g)
        bits = 0
        for r in range(8):
            for c in range(8):
                bits = (bits << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
        return w, h, bits
    except Exception:  # noqa: BLE001
        return None


IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
GENERATED_STEM_SUFFIXES = ("_measure", "_slit", "_strip", "_board", "_compare")


def is_reference_image(p: Path) -> bool:
    """目录里的“参照图”：图片后缀，且不是本工具生成的触表/标注图/看图板（_contact.png、x_measure.png 等）。"""
    return (p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES and not p.name.startswith("_")
            and not p.stem.lower().endswith(GENERATED_STEM_SUFFIXES))


def reference_images(d: Path) -> list[Path]:
    return sorted(p for p in d.iterdir() if is_reference_image(p)) if d.is_dir() else []


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def filter_images(out: Path, files: list[Path], min_w: int, dup_dist: int = 12) -> tuple[list[Path], list[str]]:
    """去掉过小和近重复的图（移到 _rejected/，不删除），返回保留列表和原因。"""
    kept, seen, notes = [], [], []
    rej = out / "_rejected"
    for p in files:
        info = image_info(p)
        reason = None
        if info is None:
            reason = "无法读取"
        elif info[0] < min_w:
            reason = f"太小 {info[0]}x{info[1]}"
        else:
            for q, hsh in seen:
                if hamming(hsh, info[2]) <= dup_dist:
                    reason = f"与 {q.name} 近重复"
                    break
        if reason:
            rej.mkdir(parents=True, exist_ok=True)
            target = rej / p.name
            if target.exists():
                target.unlink()
            p.replace(target)
            notes.append(f"{p.name}: {reason}")
            record(out, {"file": p.name, "kind": "rejected", "reason": reason})
        else:
            kept.append(p)
            seen.append((p, info[2]))
    return kept, notes


# --------------------------------------------------------------------------- 一键取点名参照

TOPIC_WORDS = {
    "water": ["water", "lake", "ocean", "sea", "river", "beach", "coast", "shore", "waterfall", "pond", "水", "湖", "海", "河", "瀑布", "岸"],
    "ocean": ["ocean", "sea", "beach", "coast", "wave", "海", "浪", "岸"],
    "sky": ["sky", "cloud", "sunset", "天空", "云"],
}


def rank_by_topic(items: list[dict], topic: str, topic_zh: str) -> list[dict]:
    """标题/来源页里提到主题词的排前面（只排序不丢弃，避免误杀无标题的好图）。"""
    words = set(TOPIC_WORDS.get(topic.lower(), [topic.lower()])) | {w for w in topic_zh.split() if w}

    def hit(it):
        text = f"{it.get('title', '')} {it.get('page', '')} {it.get('url', '')}".lower()
        return sum(1 for w in words if w and w in text)
    return sorted(items, key=hit, reverse=True)


REF_ROUTES = [
    # (名称, 说明, 函数(对象英文/中文, 需要张数) -> 图片条目列表)
    ("bing-en", "Bing 图片（英文名 + 主题 + screenshot）", lambda en, zh, n: img_bing(f"{en} screenshot", n * 4)),
    ("bing-scenery", "Bing 图片（英文名 + scenery 4K）", lambda en, zh, n: img_bing(f"{en} scenery 4k", n * 3)),
    ("baidu-zh", "百度图片（中文名 + 截图）", lambda en, zh, n: img_baidu(f"{zh} 截图", n * 3)),
    ("wallhaven", "Wallhaven 壁纸", lambda en, zh, n: img_wallhaven(en, n * 2)),
    ("pixiv", "Pixiv 短标签", lambda en, zh, n: img_pixiv(zh, n * 2)),
]


STOP_WORDS = {"the", "of", "and", "a", "an", "in", "on", "to", "game", "impact"}


def subject_words(en: str, zh: str) -> list[str]:
    """作品名的识别词：中英全名，加英文里够长的单词（Zelda Tears of the Kingdom → zelda、tears、kingdom），
    中文名按空格拆开。用来判断候选图的标题/来源页有没有提到这部作品。"""
    words = {en.lower(), zh.lower()}
    words.update(w for w in re.split(r"[\s:：\-–]+", en.lower()) if len(w) >= 4 and w not in STOP_WORDS)
    words.update(w for w in zh.lower().split() if len(w) >= 2)
    return sorted(w for w in words if w)


def mentions_subject(item: dict, words: list[str]) -> bool:
    text = f"{item.get('title', '')} {item.get('page', '')} {urllib.parse.unquote(item.get('url', ''))}".lower()
    text_compact = text.replace(" ", "").replace("-", "").replace("_", "")
    return any(w in text or w.replace(" ", "") in text_compact for w in words)


def _refs_one(spec: str, args, out: Path) -> tuple[list[str], str | None]:
    """取一个点名对象的参照；返回 (报告行, 缺参照时的中文名)。"""
    en, _, zh = spec.partition("=")
    en, zh = en.strip(), (zh or en).strip()
    sub = out / safe_name(zh, 30)
    sub.mkdir(parents=True, exist_ok=True)
    kept: list[Path] = reference_images(sub)
    lines = [f"## {zh}（{en}）"]
    if kept:
        lines.append(f"- 目录里已有 {len(kept)} 张，接着补")
    tried = 0
    topic_en = f"{en} {args.topic}".strip()
    topic_zh = f"{zh} {args.topic_zh or args.topic}".strip()
    words = subject_words(en, zh)
    for name, desc, fn in REF_ROUTES:
        if len(kept) >= args.need:
            break
        tried += 1
        try:
            items = rank_by_topic(dedupe(fn(topic_en, topic_zh, args.need), "url"), args.topic, args.topic_zh)
            # 提到作品名的排前面（稳定排序，保留主题词排序）；没提到的仍可能是好图，只是要重点核
            items.sort(key=lambda it: not mentions_subject(it, words))
        except Exception as e:  # noqa: BLE001
            lines.append(f"- {desc}：失败（{short_reason(e)}）")
            continue
        # 多下 3 张给过滤留余量；不足时下一个来源会补
        want = max(args.need + 3 - len(kept), 0)
        batch = list(enumerate(items[:want]))

        def dl(pair):
            i, it = pair
            try:
                # 批量取图：一张取不到就跳过（候选很多），不重试，避免单个慢站拖住整批
                e = download(it["url"], sub, f"{name}_{i:02d}", {"query": topic_en, "source": name, "page": it.get("page", ""),
                                                                "title": it.get("title", ""), "subject": zh,
                                                                "mentionsSubject": mentions_subject(it, words)},
                             timeout=15, retries=0)
                return sub / e["file"]
            except Exception:  # noqa: BLE001
                return None
        with cf.ThreadPoolExecutor(8) as ex:
            got = [p for p in ex.map(dl, batch) if p]
        new_kept, notes = filter_images(sub, kept + got, args.min_width)
        added = len(new_kept) - len(kept)
        kept = new_kept
        lines.append(f"- {desc}：搜到 {len(items)}，下载 {len(got)}，合格新增 {added}（累计 {len(kept)}）"
                     + (f"；剔除：{'；'.join(notes[:4])}" if notes else ""))
    if kept:
        info = {}
        mf = sub / "manifest.jsonl"
        if mf.is_file():
            for row in mf.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    e = json.loads(row)
                except ValueError:
                    continue
                if "mentionsSubject" in e:
                    info[e.get("file")] = e["mentionsSubject"]
        doubtful = [p.name for p in kept if info.get(p.name) is False]
        if doubtful:
            lines.append(f"- **疑似不是{zh}**（标题和来源页都没提到作品名，触表里重点核，确认后用 pick 选入或 --reject）："
                         + "、".join(doubtful))
        contact_sheet(kept, sub / "_contact.png", 4, 320)
        lines.append(f"- 触表：{(sub / '_contact.png').as_posix()}（**必须亲眼看一遍**，剔除同人图、滤镜图、"
                     "多游戏对比拼图、不相关图；剔除后剩余不足就重跑本命令补齐）")
    missing = None
    if len(kept) < args.need:
        missing = zh
        lines.append(f"- **不足**：只有 {len(kept)} 张，已试 {tried} 个来源。下一步：`video \"{zh} 实机\"` → `vdl --section` → `frames`；"
                     "仍不足就告诉用户缺这个参照并请其提供截图/视频/链接，**不要换成别的对象**。")
    lines.append("")
    return lines, missing


def cmd_refs(args):
    """对每个点名对象（并行）依次尝试来源，直到拿到 --need 张合格图；记录全部尝试，拼触表，写 REFS.md。"""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = ["# 参照获取记录", "", f"- 时间：{time.strftime('%Y-%m-%d %H:%M')}", f"- 主题：{args.topic}",
              f"- 每个对象目标：{args.need} 张，宽度 ≥ {args.min_width}px", ""]
    with cf.ThreadPoolExecutor(min(4, len(args.subjects))) as ex:
        results = list(ex.map(lambda s: _refs_one(s, args, out), args.subjects))
    missing = [m for _, m in results if m]
    for lines, _ in results:
        report += lines
    if missing:
        report.append(f"**缺参照的对象：{'、'.join(missing)}**")
    (out / "REFS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"\n记录：{out / 'REFS.md'}")
    return 4 if missing else 0

# --------------------------------------------------------------------------- 研究：搜索 + 批量读正文

def _grab_page_text(url: str) -> dict:
    raw = fetch_text(url, timeout=25)
    if len(re.sub(r"<[^>]+>", "", raw).strip()) < 300:
        raw = edge_dump(url)
    if re.search(r"Just a moment|cf-chl|challenge-platform|cf_chl_opt", raw[:20000]):
        raise RuntimeError("Cloudflare 人机验证")
    return parse_page(raw, url)


def cmd_research(args):
    query = args.query + (f" site:{args.site}" if args.site else "")
    engines = {k: WEB_ENGINES[k] for k in (args.src or ["ddg", "bing", "bingcn"])}
    items, status = run_parallel(engines, query, max(args.n, args.pages))
    items = dedupe(items, "url")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print("来源状态：" + "，".join(f"{k}={v}" for k, v in status.items()))
    picks = [it for it in items if not re.search(r"\.(pdf|zip|mp4)(\?|$)", it["url"], re.I)][:args.pages]

    def grab(pair):
        i, it = pair
        try:
            page = _grab_page_text(it["url"])
        except Exception as e:  # noqa: BLE001
            return dict(i=i, url=it["url"], title=it.get("title", ""), error=str(e)[:120])
        name = f"{i:02d}_{safe_name(page['title'] or it.get('title', ''), 40)}.md"
        body = page["text"][:args.max_chars]
        (out / name).write_text(f"# {page['title'] or it.get('title', '')}\n\n- 来源：{it['url']}\n- 查询：{query}\n"
                                f"- 抓取：{time.strftime('%Y-%m-%d %H:%M')}\n- 正文字数：{len(page['text'])}"
                                f"{'（已截断）' if len(page['text']) > args.max_chars else ''}\n- 图片数：{len(page['images'])}\n\n"
                                f"{body}\n", encoding="utf-8")
        record(out, {"file": name, "url": it["url"], "kind": "page-text", "query": query, "chars": len(page["text"])})
        return dict(i=i, url=it["url"], title=page["title"] or it.get("title", ""), file=name, chars=len(page["text"]))

    with cf.ThreadPoolExecutor(4) as ex:
        res = sorted(ex.map(grab, enumerate(picks, 1)), key=lambda r: r["i"])
    lines = [f"# 研究：{query}", "", "| # | 标题 | 字数 | 文件 / 失败原因 | 来源 |", "|---|---|---|---|---|"]
    for r in res:
        cells = [r["title"][:50], r.get("file") or "失败：" + r["error"]]
        title, what = (c.replace("|", "\\|").replace("\n", " ") for c in cells)  # 标题里的 | 会拆坏表格
        lines.append(f"| {r['i']} | {title} | {r.get('chars', '')} | {what} | {r['url']} |")
    lines += ["", "## 其余搜索结果（未抓正文）", ""]
    lines += [f"- [{it.get('title', '')[:70]}]({it['url']})  {it.get('snippet', '')[:100]}" for it in items[len(picks):]]
    (out / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok = sum(1 for r in res if r.get("file"))
    print(f"已抓正文 {ok}/{len(res)} 篇 → {out}\\index.md（每篇一个 .md，先读 index 再挑着读）")
    for r in res:
        print(f"  {r['i']:2d}. {'ok ' if r.get('file') else '失败'} {r['title'][:60]}  {r.get('chars', r.get('error', ''))}")
    return 0 if ok else 3


# --------------------------------------------------------------------------- 字幕

def subs_to_text(raw: str) -> str:
    """VTT/SRT → 带时间戳的纯文本，去掉重复行和样式标签。"""
    out, last, ts = [], "", None
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or s.isdigit():
            continue
        if "-->" in s:
            ts = re.split(r"[.,]", s.split("-->")[0].strip())[0]
            continue
        text = html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        if not text or text == last:
            continue
        last = text
        out.append(f"[{ts}] {text}" if ts else text)
        ts = None
    return "\n".join(out)


def cmd_subs(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    before = set(out.iterdir())
    cmd = [sys.executable, "-m", "yt_dlp", "--skip-download", "--write-subs", "--write-auto-subs",
           "--sub-langs", args.lang, "--sub-format", "srt/vtt/best", "--ffmpeg-location", ffmpeg_exe(),
           "--convert-subs", "srt", "-o", str(out / "%(title).50s_%(id)s.%(ext)s"), "--windows-filenames"]
    if args.cookies_from_browser:
        cmd += ["--cookies-from-browser", args.cookies_from_browser]
    cmd.append(args.url)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    new = [p for p in out.iterdir() if p not in before and p.suffix.lower() in (".srt", ".vtt")]
    if not new:
        print("没有拿到字幕。" + ("yt-dlp 报错：" + (r.stderr or r.stdout)[-400:] if r.returncode else "该视频可能没有字幕/AI字幕。"))
        print("可选：B 站 AI 字幕常要求登录，经用户同意后加 --cookies-from-browser edge；"
              "或下载视频片段后看画面（vdl + frames），或用 expand 看简介。")
        return 3
    for p in new:
        txt = p.with_suffix(".txt")
        txt.write_text(subs_to_text(p.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        record(out, {"file": txt.name, "url": args.url, "kind": "subtitle-text", "from": p.name})
        print(f"ok {txt}  （{len(txt.read_text(encoding='utf-8').splitlines())} 行）")


# --------------------------------------------------------------------------- GitHub 单文件

def cmd_gh_tree(args):
    d = fetch_json(f"https://api.github.com/repos/{args.repo.strip('/')}/git/trees/{args.ref}?recursive=1",
                   headers={"Accept": "application/vnd.github+json"}, timeout=40)
    paths = [t["path"] for t in d.get("tree", []) if t.get("type") == "blob"]
    if args.filter:
        rx = re.compile(args.filter, re.I)
        paths = [p for p in paths if rx.search(p)]
    if args.ext:
        exts = tuple("." + e.strip().lstrip(".").lower() for e in args.ext.split(",") if e.strip())
        paths = [p for p in paths if p.lower().endswith(exts)]
    for p in paths[:args.limit]:
        print(p)
    print(f"--- {len(paths)} 个文件" + ("（仓库过大，GitHub 截断了列表，改用 gh-dl）" if d.get("truncated") else "")
          + (f"，只显示前 {args.limit} 个" if len(paths) > args.limit else ""))


def gh_file(repo: str, path: str, ref: str, timeout: int = 40) -> tuple[bytes, str]:
    """先走 GitHub API（本机实测稳定），失败再试 raw.githubusercontent.com（偶发 TLS 握手失败）。"""
    repo = repo.strip("/")
    qpath = urllib.parse.quote(path)
    api = f"https://api.github.com/repos/{repo}/contents/{qpath}" + (f"?ref={ref}" if ref and ref != "HEAD" else "")
    try:
        return fetch(api, headers={"Accept": "application/vnd.github.raw"}, timeout=timeout), api
    except Exception as e1:  # noqa: BLE001
        raw = f"https://raw.githubusercontent.com/{repo}/{ref or 'HEAD'}/{qpath}"
        try:
            return fetch(raw, timeout=timeout), raw
        except Exception as e2:  # noqa: BLE001
            raise RuntimeError(f"API 与 raw 都失败：{str(e1)[:150]} | {str(e2)[:150]}") from None


def cmd_gh_cat(args):
    data, url = gh_file(args.repo, args.path, args.ref)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        record(out.parent, {"file": out.name, "url": url, "kind": "github-file", "sha256": sha256(out)})
        print(f"ok {out}  {len(data)}B")
    else:
        print(data.decode("utf-8", "replace"))


# --------------------------------------------------------------------------- PDF

def _pymupdf():
    """可选依赖：PyMuPDF 是 AGPL 许可，只在需要提取 PDF 插图时使用。"""
    try:
        import pymupdf as fitz
        return fitz
    except ImportError:
        try:
            import fitz
            return fitz
        except ImportError:
            return None


def cmd_pdf(args):
    src = args.src
    out = Path(args.out)
    if src.startswith(("http://", "https://")):
        e = download(src, out.parent / "_pdf_src", None, {"kind": "pdf-source"})
        src = str(out.parent / "_pdf_src" / e["file"])
    try:
        from pypdf import PdfReader  # BSD 许可，默认文本提取
    except ImportError:
        raise SystemExit("需要 pypdf：python -m pip install --user pypdf")
    reader = PdfReader(src)
    total = len(reader.pages)
    first, last = 1, total
    if args.pages:
        a, _, b = args.pages.partition("-")
        first, last = int(a), int(b or a)
    last = min(last, total)
    parts = [f"# {Path(src).name}\n\n来源：{args.src}\n共 {total} 页，本次 {first}-{last}\n"]
    empty = 0
    for i in range(first - 1, last):
        text = (reader.pages[i].extract_text() or "").strip()
        empty += 0 if text else 1
        parts.append(f"\n## 第 {i + 1} 页\n\n{text}\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")
    record(out.parent, {"file": out.name, "kind": "pdf-text", "source": args.src, "pages": f"{first}-{last}"})
    msg = f"ok {out}（{last - first + 1} 页"
    msg += f"，其中 {empty} 页没有文字层，可能是扫描件/纯图，用 --images 取图后看图）" if empty else "）"
    if args.images:
        fitz = _pymupdf()
        if fitz is None:
            msg += "；--images 需要可选依赖 PyMuPDF（AGPL 许可，仅本机研究用，勿随包分发）：python -m pip install --user pymupdf"
        else:
            doc = fitz.open(src)
            img_dir = out.parent / (out.stem + "_images")
            n_img = 0
            for i in range(first - 1, last):
                for xref, *_ in doc[i].get_images(full=True):
                    info = doc.extract_image(xref)
                    if info and info.get("width", 0) >= 200:
                        img_dir.mkdir(parents=True, exist_ok=True)
                        (img_dir / f"p{i + 1:03d}_{xref}.{info['ext']}").write_bytes(info["image"])
                        n_img += 1
            msg += f"；图片 {n_img} 张 → {img_dir}"
    print(msg)
    return 0

# --------------------------------------------------------------------------- 测量（给 TARGET.md 的“怎么量”）

def _xy(token: str, w: int, h: int) -> tuple[int, int]:
    v = [float(t) for t in token.split(",")]
    if len(v) != 2:
        raise ValueError(f"点要 2 个数 x,y：{token}")
    x, y = (round(v[0] * (w - 1)) if v[0] <= 1 else int(v[0]), round(v[1] * (h - 1)) if v[1] <= 1 else int(v[1]))
    if not (0 <= x < w and 0 <= y < h):
        raise ValueError(f"点 {token} 在图外（图 {w}x{h}；≤1 的值按比例）")
    return x, y


def _box(token: str, w: int, h: int) -> list[int]:
    """"x0,y0,x1,y1"：每个值 ≤1 按比例，否则按像素；自动排序并夹在图内。"""
    v = [float(t) for t in token.split(",")]
    if len(v) != 4:
        raise ValueError(f"区域要 4 个数 x0,y0,x1,y1：{token}")
    x0, x1 = sorted((round(v[0] * w) if v[0] <= 1 else int(v[0]), round(v[2] * w) if v[2] <= 1 else int(v[2])))
    y0, y1 = sorted((round(v[1] * h) if v[1] <= 1 else int(v[1]), round(v[3] * h) if v[3] <= 1 else int(v[3])))
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        raise ValueError(f"区域太小或在图外：{token}")
    return [x0, y0, x1, y1]


def measure(path: Path, points: str | None, regions: str | None, palette: int, grid: str | None,
            roi: str | None = None) -> dict:
    """量图。roi 指定后，grid 和 palette 只在 roi 内统计（用来避开小地图、血条、字幕等游戏 UI）。
    points / regions 的坐标始终相对整张图。"""
    import colorsys
    from PIL import Image, ImageStat
    im = Image.open(path).convert("RGB")
    w, h = im.size

    def desc(rgb):
        r, g, b = (int(round(c)) for c in rgb)
        hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        return {"rgb": [r, g, b], "hex": f"#{r:02x}{g:02x}{b:02x}", "hsv": [round(hh * 360), round(ss * 100), round(vv * 100)]}

    res: dict = {"file": str(path), "size": [w, h], "warnings": []}
    area_box = _box(roi, w, h) if roi else [0, 0, w, h]
    if roi:
        res["roi"] = area_box
    elif grid or palette:
        res["warnings"].append("没有指定 --roi：色带和主色按整张图统计，会混进小地图、血条、字幕等游戏 UI 和天空/角色。"
                               "请用 --roi 框住水面区域，例如 --roi \"0.05,0.55,0.95,0.92\"，再看标注图确认框对了。")
    area = im.crop(area_box)
    aw, ah = area.size
    if points:
        res["points"] = []
        for tok in points.split(";"):
            x, y = _xy(tok, w, h)
            res["points"].append({"at": [x, y], **desc(im.getpixel((x, y)))})
    if regions:
        res["regions"] = []
        for tok in regions.split(";"):
            box = _box(tok, w, h)
            crop = im.crop(box)
            res["regions"].append({"box": box, "mean": desc(ImageStat.Stat(crop).mean),
                                   "lumaStd": round(ImageStat.Stat(crop.convert("L")).stddev[0], 1)})
    if grid:
        rows, cols = (int(v) for v in grid.lower().split("x"))
        cells = []
        for r in range(rows):
            row = []
            for c in range(cols):
                box = (c * aw // cols, r * ah // rows, (c + 1) * aw // cols, (r + 1) * ah // rows)
                row.append(desc(ImageStat.Stat(area.crop(box)).mean)["hex"])
            cells.append(row)
        res["grid"] = cells
    if palette:
        small = area.copy()
        small.thumbnail((256, 256))
        q_im = small.quantize(colors=palette, method=Image.Quantize.MEDIANCUT)
        pal = q_im.getpalette()
        counts = sorted(q_im.getcolors(), reverse=True)
        total = sum(c for c, _ in counts)
        res["palette"] = [{**desc(pal[i * 3:i * 3 + 3]), "share": round(100 * c / total, 1)} for c, i in counts]
    return res


def line_profile(path: Path, line: str, thresh: float | None = None, samples: int = 400) -> dict:
    """沿一条线取亮度剖面，找出最宽的“亮带”（如岸线泡沫），给出像素宽度和占画面高的百分比。
    line = "x0,y0,x1,y1"（≤1 为比例）。thresh 缺省取该线亮度的 (最小+最大)/2。"""
    from PIL import Image
    im = Image.open(path).convert("L")
    w, h = im.size
    x0, y0 = _xy(",".join(line.split(",")[:2]), w, h)
    x1, y1 = _xy(",".join(line.split(",")[2:4]), w, h)
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    n = max(2, min(samples, int(length)))
    pts = [(x0 + (x1 - x0) * i / (n - 1), y0 + (y1 - y0) * i / (n - 1)) for i in range(n)]
    vals = [im.getpixel((min(w - 1, round(x)), min(h - 1, round(y)))) for x, y in pts]
    lo, hi = min(vals), max(vals)
    t = thresh if thresh is not None else (lo + hi) / 2
    best, cur_start = (0, 0, 0), None
    # 线上几乎没有明暗变化（<8 灰阶）时没有“亮带”可言，不能把整条线报成亮带
    flat = thresh is None and hi - lo < 8
    for i, v in enumerate([] if flat else vals + [-1]):
        if v >= t and cur_start is None:
            cur_start = i
        elif v < t and cur_start is not None:
            if i - cur_start > best[0]:
                best = (i - cur_start, cur_start, i - 1)
            cur_start = None
    step = length / (n - 1)
    width_px = best[0] * step
    edge = lambda a, b: round(abs(vals[min(n - 1, b)] - vals[max(0, a)]), 1)  # noqa: E731
    return {"line": [x0, y0, x1, y1], "lengthPx": round(length, 1), "threshold": round(t, 1), "min": lo, "max": hi,
            "bandWidthPx": round(width_px, 1), "bandPctOfHeight": round(100 * width_px / h, 2),
            "bandStartPx": round(best[1] * step, 1), "bandEndPx": round(best[2] * step, 1),
            "edgeContrastIn": 0 if flat else edge(best[1] - 3, best[1] + 1),
            "edgeContrastOut": 0 if flat else edge(best[2] - 1, best[2] + 3),
            "flat": flat, "profile": vals[:: max(1, n // 60)]}


def annotate_measure(path: Path, res: dict, out: Path) -> Path:
    """把 roi、区域、取色点画到图上，存成标注图，方便核对“量的是不是水面”。"""
    from PIL import Image, ImageDraw
    im = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(im)
    f = _font(max(14, im.width // 80))
    lw = max(2, im.width // 400)
    if res.get("roi"):
        d.rectangle(res["roi"], outline=(255, 220, 0), width=lw)
        d.text((res["roi"][0] + 6, res["roi"][1] + 4), "ROI", fill=(255, 220, 0), font=f)
        if res.get("grid"):
            x0, y0, x1, y1 = res["roi"]
            rows = len(res["grid"])
            for r in range(1, rows):
                y = y0 + (y1 - y0) * r // rows
                d.line([x0, y, x1, y], fill=(255, 220, 0), width=1)
    for i, r in enumerate(res.get("regions", []), 1):
        d.rectangle(r["box"], outline=(0, 255, 255), width=lw)
        d.text((r["box"][0] + 4, r["box"][1] + 4), f"R{i} {r['mean']['hex']}", fill=(0, 255, 255), font=f)
    for i, ln in enumerate(res.get("lines", []), 1):
        x0, y0, x1, y1 = ln["line"]
        d.line([x0, y0, x1, y1], fill=(80, 255, 80), width=lw)
        d.text((x1 + 4, y1), f"L{i} 亮带 {ln['bandWidthPx']}px", fill=(80, 255, 80), font=f)
    for i, p in enumerate(res.get("points", []), 1):
        x, y = p["at"]
        rad = lw * 3
        d.ellipse([x - rad, y - rad, x + rad, y + rad], outline=(255, 0, 255), width=lw)
        d.text((x + rad + 3, y - rad), f"P{i} {p['hex']}", fill=(255, 0, 255), font=f)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def cmd_measure(args):
    path = Path(args.image)
    res = measure(path, args.points, args.regions, args.palette, args.grid, args.roi)
    if args.line:
        res["lines"] = [line_profile(path, tok, args.thresh) for tok in args.line.split(";")]
    if not args.no_annot and (res.get("roi") or res.get("regions") or res.get("points") or res.get("lines")):
        out = Path(args.annot) if args.annot else path.with_name(path.stem + "_measure.png")
        res["annotated"] = str(annotate_measure(path, res, out))
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    print(f"{res['file']}  {res['size'][0]}x{res['size'][1]}" + (f"  ROI {res['roi']}" if res.get("roi") else ""))
    for wmsg in res["warnings"]:
        print("  注意：" + wmsg)
    for i, p in enumerate(res.get("points", []), 1):
        print(f"  P{i} {p['at']}: {p['hex']}  HSV{tuple(p['hsv'])}")
    for i, r in enumerate(res.get("regions", []), 1):
        print(f"  R{i} {r['box']}: 均色 {r['mean']['hex']} HSV{tuple(r['mean']['hsv'])}  亮度离散 {r['lumaStd']}")
    if res.get("grid"):
        print("  网格均色（" + ("ROI 内，" if res.get("roi") else "整图，") + "上→下）：")
        for row in res["grid"]:
            print("   " + " ".join(row))
    for c in res.get("palette", []):
        print(f"  主色 {c['hex']} HSV{tuple(c['hsv'])} 占 {c['share']}%")
    for i, ln in enumerate(res.get("lines", []), 1):
        if ln.get("flat"):
            print(f"  L{i} {ln['line']}：线上明暗几乎不变（{ln['min']}–{ln['max']}），没有亮带；检查线是否横穿泡沫带")
            continue
        print(f"  L{i} {ln['line']} 长 {ln['lengthPx']}px：最宽亮带 {ln['bandWidthPx']}px（画面高的 {ln['bandPctOfHeight']}%），"
              f"阈值 {ln['threshold']}，内缘反差 {ln['edgeContrastIn']}，外缘反差 {ln['edgeContrastOut']}（反差大=硬边）")
    if res.get("annotated"):
        print(f"  标注图：{res['annotated']}（打开看一眼，确认框住的是水面）")
    return 0

# --------------------------------------------------------------------------- 看图板（帮模型用画家的方式看图）

def look_stats(im) -> dict:
    """im: PIL RGB（已按 ROI 裁好）。主色、饱和度均值、明度阶数、边缘锐度。"""
    import colorsys
    from PIL import ImageFilter, ImageStat
    small = im.copy()
    small.thumbnail((256, 256))
    q_im = small.quantize(colors=6, method=0)
    pal = q_im.getpalette()
    counts = sorted(q_im.getcolors(), reverse=True)
    total = sum(c for c, _ in counts) or 1
    colors = []
    for c, i in counts:
        r, g, b = pal[i * 3:i * 3 + 3]
        hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        colors.append({"hex": f"#{r:02x}{g:02x}{b:02x}", "rgb": [r, g, b], "share": round(100 * c / total, 1),
                       "hsv": [round(hh * 360), round(ss * 100), round(vv * 100)]})
    sat = ImageStat.Stat(small.convert("HSV")).mean[1] * 100 / 255
    # 明度阶数：占比 ≥5% 的主色按明度排序，相差 <8 的并成一阶
    vs = sorted(c["hsv"][2] for c in colors if c["share"] >= 5)
    levels = 0
    last = None
    for v in vs:
        if last is None or v - last >= 8:
            levels += 1
            last = v
    gray = small.convert("L")
    lum = _pixels(gray)
    hist = [0] * 16
    for v in lum:
        hist[v * 16 // 256] += 1
    # 边缘锐度 0–100（重模糊比较，Crété-Roffet 2007）：9 像素盒式模糊后，相邻像素差丢了多少。
    # 硬边/细碎高光一模糊就塌 → 高；本来就柔的过渡几乎不变 → 低。整图平坦（没有明度变化）记 0
    from PIL import ImageChops
    blurred = gray.filter(ImageFilter.BoxBlur(4))
    gw, gh = gray.size
    d0 = d_lost = 0
    for a, b in (((0, 1, gw, gh), (0, 0, gw, gh - 1)), ((1, 0, gw, gh), (0, 0, gw - 1, gh))):
        if a[2] <= a[0] or a[3] <= a[1]:
            continue
        di = ImageChops.difference(gray.crop(a), gray.crop(b))
        db = ImageChops.difference(blurred.crop(a), blurred.crop(b))
        d0 += sum(_pixels(di))
        d_lost += sum(_pixels(ImageChops.subtract(di, db)))
    sharp = 0.0 if d0 < gw * gh * 0.01 else 100 * d_lost / d0
    return {"colors": colors, "saturationMean": round(sat, 1), "valueLevels": levels,
            "valueRange": [min(lum), max(lum)] if lum else [0, 0],
            "edgeSharpness": round(sharp, 1),
            "lumaHistogram": [round(100 * h / max(1, len(lum)), 1) for h in hist]}


def look_board(paths: list[Path], labels: list[str], out: Path, roi: str | None, row_h: int = 260) -> tuple[Path, list[dict]]:
    """每张图一行：原图（带 ROI 框）| 眯眼（缩到 64 宽再放大）| 6 色色调分离 | 边缘图 | 主色块 + 明度直方图。"""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    rows, stats_all = [], []
    f = _font(15)
    fs = _font(12)
    rois = roi if isinstance(roi, list) else split_per_image(roi, len(paths), "--roi")
    for path, label, roi in zip(paths, labels, rois):
        im = Image.open(path).convert("RGB")
        w, h = im.size
        box = _box(roi, w, h) if roi else [0, 0, w, h]
        area = im.crop(box)
        st = look_stats(area)
        st.update(file=str(path), label=label, roi=box if roi else None)
        stats_all.append(st)
        aw = max(1, round(area.width * row_h / area.height))
        full = im.copy()
        if roi:
            ImageDraw.Draw(full).rectangle(box, outline=(255, 220, 0), width=max(2, w // 300))
        c1 = full.resize((max(1, round(w * row_h / h)), row_h), Image.LANCZOS)
        squint = area.resize((64, max(1, round(64 * area.height / area.width))), Image.LANCZOS)
        c2 = squint.resize((aw, row_h), Image.BICUBIC)
        c3 = area.quantize(colors=6, method=0).convert("RGB").resize((aw, row_h), Image.NEAREST)
        e = ImageOps.autocontrast(area.convert("L").filter(ImageFilter.FIND_EDGES), cutoff=1)
        c4 = e.convert("RGB").resize((aw, row_h), Image.LANCZOS)
        # 右侧信息栏
        side = Image.new("RGB", (230, row_h), (28, 28, 28))
        d = ImageDraw.Draw(side)
        y = 6
        for c in st["colors"]:
            d.rectangle([8, y, 38, y + 18], fill=tuple(c["rgb"]))
            d.text((44, y + 2), f"{c['hex']} {c['share']}%  S{c['hsv'][1]} V{c['hsv'][2]}", fill=(225, 225, 225), font=fs)
            y += 22
        y += 4
        d.text((8, y), f"饱和度均值 {st['saturationMean']}  明度阶数 {st['valueLevels']}", fill=(255, 220, 0), font=fs)
        y += 18
        d.text((8, y), f"边缘锐度 {st['edgeSharpness']}/100（高=硬边）", fill=(255, 220, 0), font=fs)
        y += 18
        hist_h = row_h - y - 20
        if hist_h > 20:
            peak = max(st["lumaHistogram"]) or 1
            bw = 13
            for i, v in enumerate(st["lumaHistogram"]):
                bh = round(hist_h * v / peak)
                g = i * 16 + 8
                d.rectangle([8 + i * bw, y + hist_h - bh, 8 + i * bw + bw - 2, y + hist_h], fill=(g, g, g), outline=(90, 90, 90))
            d.text((8, y + hist_h + 2), "明度直方图：暗 → 亮", fill=(160, 160, 160), font=fs)
        cols = [c1, c2, c3, c4, side]
        gap = 6
        row = Image.new("RGB", (sum(c.width for c in cols) + gap * (len(cols) - 1), row_h + 24), (16, 16, 16))
        rd = ImageDraw.Draw(row)
        x = 0
        heads = [f"{label}：原图" + ("（黄框=统计区）" if roi else ""), "眯眼看大关系", "6 色色调分离", "边缘（亮=硬边）", "主色 / 明度"]
        for col, head in zip(cols, heads):
            row.paste(col, (x, 24))
            rd.text((x + 4, 3), head, fill=(240, 240, 240), font=f)
            x += col.width + gap
        rows.append(row)
    board = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows) + 8 * (len(rows) - 1)), (10, 10, 10))
    y = 0
    for r in rows:
        board.paste(r, (0, y))
        y += r.height + 8
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out)
    return out, stats_all


def cmd_look(args):
    paths = [Path(p) for p in args.images]
    default = ["参照", "当前", "上一版"]
    labels = args.labels.split("|") if args.labels else [default[i] if i < 3 else p.stem for i, p in enumerate(paths)]
    if len(labels) < len(paths):
        labels += [p.stem for p in paths[len(labels):]]
    out, stats = look_board(paths, labels, Path(args.out), args.roi, args.row_height)
    record(out.parent, {"file": out.name, "kind": "look-board", "inputs": [str(p) for p in paths], "roi": args.roi})
    if args.json:
        print(json.dumps({"board": str(out), "images": stats}, ensure_ascii=False, indent=1))
        return 0
    for st in stats:
        main = "、".join(f"{c['hex']}({c['share']}%)" for c in st["colors"][:3])
        print(f"{st['label']}：主色 {main}；饱和度均值 {st['saturationMean']}；明度阶数 {st['valueLevels']}"
              f"（明度 {st['valueRange'][0]}–{st['valueRange'][1]}）；边缘锐度 {st['edgeSharpness']}")
    if len(stats) >= 2:
        a, b = stats[0], stats[1]
        print(f"差异（{b['label']} 相对 {a['label']}）：饱和度 {b['saturationMean'] - a['saturationMean']:+.1f}，"
              f"明度阶数 {b['valueLevels'] - a['valueLevels']:+d}，边缘锐度 {b['edgeSharpness'] - a['edgeSharpness']:+.1f}")
    if not args.roi:
        print("注意：没有 --roi，统计含天空、角色和游戏 UI；比较水体请框住水面。")
    print(f"看图板：{out}（先看第 2 列大关系，再看第 3 列色块分区，最后看第 4 列边缘软硬）")
    return 0


def split_per_image(spec: str | None, n: int, what: str) -> list[str | None]:
    """"A" → 每张图都用 A；"A|B|C" → 按顺序一张一个（构图不同的参照和当前版各框各的）。"""
    if not spec:
        return [None] * n
    parts = [s.strip() for s in spec.split("|")]
    if len(parts) == 1:
        return parts * n
    if len(parts) != n:
        raise ValueError(f"{what} 用 | 分了 {len(parts)} 段，但有 {n} 张图；要么只写一段（全部共用），要么一张一段")
    return parts


# --------------------------------------------------------------------------- 分区对齐裁切（参照和当前版同一部位并排比）

def parse_regions(spec: str) -> list[tuple[str, str]]:
    """"近岸=0.1,0.6,0.4,0.9;远水=0.5,0.3,0.9,0.5" → [(名, 框)]；不写名字的按 区1、区2 编号。"""
    out = []
    for i, tok in enumerate(t.strip() for t in spec.split(";") if t.strip()):
        name, sep, box = tok.rpartition("=")
        out.append(((name.strip() if sep else "") or f"区{i + 1}", box.strip()))
    if not out:
        raise ValueError("--regions 为空")
    names = [n for n, _ in out]
    if len(set(names)) != len(names):
        raise ValueError(f"区域名重复：{names}")
    return out


def region_stats(crop) -> dict:
    """中位色（不被零星高光带偏）+ HSV + 明度离散度（纹理多少）。"""
    import colorsys
    from PIL import ImageStat
    small = crop.copy()
    small.thumbnail((256, 256))
    med = [round(v) for v in ImageStat.Stat(small).median]
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in med))
    lum = ImageStat.Stat(small.convert("L"))
    return {"hex": "#%02x%02x%02x" % tuple(med), "rgb": med, "hsv": [round(h * 360), round(s * 100), round(v * 100)],
            "lumaMean": round(lum.mean[0], 1), "lumaStd": round(lum.stddev[0], 1)}


def hue_delta(a: int, b: int) -> int:
    d = (b - a + 180) % 360 - 180
    return d


def crops_board(paths: list[Path], labels: list[str], specs: list[str], out: Path, cell_h: int = 220) -> tuple[Path, list[dict]]:
    """第一行：原图缩略 + 全部区域框；之后每个区域一行，各图同名区域并排，下方写中位色和 HSV。"""
    from PIL import Image, ImageDraw
    per_image = [dict(parse_regions(s)) for s in specs]
    names = list(per_image[0])
    for lab, regs in zip(labels, per_image):
        if list(regs) != names:
            raise ValueError(f"{lab} 的区域名 {list(regs)} 与第一张 {names} 不一致；各图要用同一组名字、同样顺序")
    palette = [(255, 220, 0), (0, 230, 255), (255, 80, 200), (120, 255, 90), (255, 140, 40), (170, 140, 255)]
    images, boxes, stats = [], [], []
    for p, regs in zip(paths, per_image):
        im = Image.open(p).convert("RGB")
        images.append(im)
        boxes.append({n: _box(b, im.width, im.height) for n, b in regs.items()})
    cell_w = round(cell_h * 16 / 9)
    head_w, gap, lab_h, txt_h = 120, 8, 28, 40
    f, fs = _font(18), _font(13)

    def fit(im):
        im = im.copy()
        im.thumbnail((cell_w, cell_h), Image.LANCZOS)
        if im.height < cell_h * 0.6:  # 细长条放大到够看
            k = min(cell_w / im.width, cell_h / im.height)
            im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
        return im

    # 先算好每格的缩略图，行高取该行最高的一格：扁长的区域不会在图和数字之间留一大块空白
    heads = []
    for im, bx in zip(images, boxes):
        full = im.copy()
        fd = ImageDraw.Draw(full)
        lw = max(2, im.width // 250)
        for k, n in enumerate(names):
            fd.rectangle(bx[n], outline=palette[k % len(palette)], width=lw)
            fd.text((bx[n][0] + lw + 2, bx[n][1] + lw), n, fill=palette[k % len(palette)], font=_font(max(14, im.width // 60)))
        heads.append(fit(full))
    rows, tiles = [], []
    for n in names:
        row = {"region": n, "images": []}
        cells = []
        for im, lab, bx in zip(images, labels, boxes):
            crop = im.crop(bx[n])
            st = region_stats(crop)
            st.update(label=lab, box=bx[n])
            row["images"].append(st)
            cells.append(fit(crop))
        rows.append(row)
        tiles.append(cells)
    head_h = max(t.height for t in heads)
    row_hs = [max(t.height for t in cells) for cells in tiles]
    width = head_w + len(images) * (cell_w + gap)
    height = lab_h + head_h + gap + sum(h + txt_h + gap for h in row_hs)
    board = Image.new("RGB", (width, height), (16, 16, 16))
    d = ImageDraw.Draw(board)
    for c, (lab, t) in enumerate(zip(labels, heads)):
        x = head_w + c * (cell_w + gap)
        d.text((x + 4, 4), lab, fill=(240, 240, 240), font=f)
        board.paste(t, (x + (cell_w - t.width) // 2, lab_h))
    d.text((6, lab_h + 4), "原图+框", fill=(200, 200, 200), font=f)
    y = lab_h + head_h + gap
    for k, (row, cells, rh) in enumerate(zip(rows, tiles, row_hs)):
        d.text((6, y + 4), row["region"], fill=palette[k % len(palette)], font=f)
        for c, (st, t) in enumerate(zip(row["images"], cells)):
            x = head_w + c * (cell_w + gap)
            board.paste(t, (x + (cell_w - t.width) // 2, y))
            d.rectangle([x, y + rh + 4, x + 26, y + rh + 30], fill=tuple(st["rgb"]), outline=(90, 90, 90))
            d.text((x + 32, y + rh + 4), f"{st['hex']}  H{st['hsv'][0]} S{st['hsv'][1]} V{st['hsv'][2]}",
                   fill=(230, 230, 230), font=fs)
            d.text((x + 32, y + rh + 20), f"纹理(明度离散) {st['lumaStd']}", fill=(160, 160, 160), font=fs)
        y += rh + txt_h + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out)
    return out, rows


def cmd_crops(args):
    paths = [Path(p) for p in args.images]
    labels = args.labels.split("|") if args.labels else [p.stem for p in paths]
    labels += [p.stem for p in paths[len(labels):]]
    specs = split_per_image(args.regions, len(paths), "--regions")
    out, rows = crops_board(paths, labels[:len(paths)], specs, Path(args.out), args.height)
    record(out.parent, {"file": out.name, "kind": "crops-board", "inputs": [str(p) for p in paths], "regions": args.regions})
    if args.json:
        print(json.dumps({"board": str(out), "regions": rows}, ensure_ascii=False, indent=1))
        return 0
    base = labels[0]
    for row in rows:
        print(f"[{row['region']}]")
        a = row["images"][0]
        for st in row["images"]:
            line = f"  {st['label']}: {st['hex']} H{st['hsv'][0]} S{st['hsv'][1]} V{st['hsv'][2]} 纹理{st['lumaStd']}"
            if st is not a:
                line += (f"   相对{base}: 色相{hue_delta(a['hsv'][0], st['hsv'][0]):+d}° 饱和{st['hsv'][1] - a['hsv'][1]:+d}"
                         f" 明度{st['hsv'][2] - a['hsv'][2]:+d} 纹理{st['lumaStd'] - a['lumaStd']:+.1f}")
            print(line)
    print(f"对齐裁切板：{out}（先看第一行框对不对：框住的必须是同一种部位，再比下面每一行）")
    if any(st["hsv"][1] < 8 for row in rows for st in row["images"]):
        print("提示：有区域饱和度 <8，色相数值不可靠，只比明度。")
    blank = [f"{st['label']} 的 {row['region']}" for row in rows for st in row["images"]
             if st["lumaStd"] < 2 and (st["hsv"][2] < 12 or st["hsv"][2] > 97)]
    if blank:
        print(f"警告：{'、'.join(blank)} 几乎是纯黑/纯白的平块，多半框到了拼图边距、标签或天空：看第一行的框，重新框水面")
        return 1
    return 0


# --------------------------------------------------------------------------- 参照登记（选入/剔除 + 出处，可审计）

def manifest_lookup(path: Path) -> dict:
    """在图片所在目录的 manifest.jsonl 里找这张图的下载记录（来源 URL、页面、查询词）。"""
    mf = path.parent / "manifest.jsonl"
    found = {}
    if mf.is_file():
        for line in mf.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("file") == path.name and e.get("url"):
                found = e
    return found


def _md_cell(s) -> str:
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def write_selected_md(out: Path, entries: list[dict]) -> Path:
    picked = [e for e in entries if e["verdict"] == "selected"]
    rejected = [e for e in entries if e["verdict"] == "rejected"]
    lines = ["# 参照登记", "", f"更新：{time.strftime('%Y-%m-%d %H:%M')}。选入 {len(picked)} 张，剔除 {len(rejected)} 张。"
             "由 `refgrab pick` 生成，手改会被下次覆盖；改判定请重跑 pick。", ""]
    by_subject: dict[str, int] = {}
    for e in picked:
        by_subject[e["subject"]] = by_subject.get(e["subject"], 0) + 1
    if by_subject:
        lines.append("各对象张数：" + "，".join(f"{k} {v}" for k, v in by_subject.items()))
        lines.append("")
    lines += ["## 选入", "", "| ID | 对象 | 理由 | 尺寸 | 出处 | 原文件 | sha256 |", "|---|---|---|---|---|---|---|"]
    for e in picked:
        src = e.get("page") or e.get("url") or "**未知，需补**"
        lines.append("| " + " | ".join(_md_cell(x) for x in (e["id"], e["subject"], e["why"], e["size"], src,
                                                            e["original"], e["sha256"][:12])) + " |")
    if rejected:
        lines += ["", "## 剔除", "", "| 对象 | 理由 | 原文件 | 出处 |", "|---|---|---|---|"]
        for e in rejected:
            lines.append("| " + " | ".join(_md_cell(x) for x in (e["subject"], e["why"], e["original"],
                                                                e.get("page") or e.get("url") or "")) + " |")
    path = out / "SELECTED.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def cmd_pick(args):
    from PIL import Image
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    db = out / "selected.json"
    entries = json.loads(db.read_text(encoding="utf-8")) if db.is_file() else []
    used = {e["id"] for e in entries if e.get("id")}
    prefix = args.prefix
    n = 1 + max([int(m.group(1)) for i in used if (m := re.fullmatch(re.escape(prefix) + r"(\d+)", i))] or [0])
    ids = [s.strip() for s in args.ids.split(",")] if args.ids else []
    if ids and len(ids) != len(args.images):
        raise ValueError(f"--ids 给了 {len(ids)} 个，图片有 {len(args.images)} 张")
    verdict = "rejected" if args.reject else "selected"
    if not args.why.strip():
        raise ValueError("--why 不能为空：写一句为什么选入/剔除（看到了什么），以后复核靠它")
    report, unknown = [], []
    for k, raw in enumerate(args.images):
        p = Path(raw)
        if not p.is_file():
            raise ValueError(f"找不到图片：{p}")
        digest = sha256(p)
        with Image.open(p) as im:
            size = f"{im.width}x{im.height}"
        prov = manifest_lookup(p)
        # 同一张图 + 同一个对象 = 改判；同一张图登记给另一个对象（多作品拼图、对比图）是另一条登记
        old = next((e for e in entries if e["sha256"] == digest and e["subject"] == args.subject), None)
        if old is not None:
            entries.remove(old)
            if old.get("copy"):
                (out / old["copy"]).unlink(missing_ok=True)
        e = {"sha256": digest, "original": p.as_posix(), "size": size, "subject": args.subject, "verdict": verdict,
             "why": args.why.strip(), "url": args.src or prov.get("url", ""), "page": prov.get("page", ""),
             "query": prov.get("query", ""), "title": prov.get("title", ""), "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if verdict == "selected":
            rid = ids[k] if ids else (old or {}).get("id") or ""
            if not rid:
                while f"{prefix}{n}" in used:
                    n += 1
                rid = f"{prefix}{n}"
            if rid in used and (old or {}).get("id") != rid:
                raise ValueError(f"ID {rid} 已被别的图占用")
            used.add(rid)
            e["id"] = rid
            e["copy"] = rid + p.suffix.lower()
            if (out / e["copy"]).resolve() != p.resolve():
                shutil.copy2(p, out / e["copy"])
        else:
            e["id"] = ""
        entries.append(e)
        if not (e["url"] or e["page"]):
            unknown.append(p.name)
        report.append(f"{'选入 ' + e['id'] if e['id'] else '剔除'}：{p.name}（{size}）" + ("，已改判" if old else ""))
    entries.sort(key=lambda e: (e["verdict"] != "selected", e["subject"], e.get("id", "")))
    db.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    md = write_selected_md(out, entries)
    if args.json:
        print(json.dumps({"selected": md.as_posix(), "entries": entries, "unknownSource": unknown}, ensure_ascii=False, indent=1))
    else:
        print("\n".join(report))
        print(f"登记表：{md}（{sum(e['verdict'] == 'selected' for e in entries)} 选入 / "
              f"{sum(e['verdict'] == 'rejected' for e in entries)} 剔除）")
        if unknown:
            print(f"注意：{len(unknown)} 张找不到出处（不是用 refgrab 下载的）：{'、'.join(unknown[:5])}。"
                  "用 --src URL 补上，否则不能当作已核实的实机参照。")
    return 0


# --------------------------------------------------------------------------- 动态测量（模型看不了原速视频时的替代）

def _dominant_period(series_list: list[list[float]], fps: float) -> dict | None:
    """对多条时间序列做 DFT，功率相加，返回主周期。序列长度 < 8 返回 None。"""
    import cmath
    n = len(series_list[0]) if series_list else 0
    if n < 8:
        return None
    power = [0.0] * (n // 2)
    for s in series_list:
        m = sum(s) / n
        z = [v - m for v in s]
        for k in range(1, n // 2):
            acc = sum(z[t] * cmath.exp(-2j * cmath.pi * k * t / n) for t in range(n))
            power[k] += abs(acc) ** 2
    # 至少要在窗口里完整出现 2 个周期才算周期（k=1 只是整段的缓慢漂移/趋势）
    if n // 2 <= 2:
        return None
    k = max(range(2, n // 2), key=lambda i: power[i])
    total = sum(power[1:]) or 1
    return {"periodSec": round(n / (k * fps), 2), "freqHz": round(k * fps / n, 3), "powerShare": round(power[k] / total, 3),
            "trendShare": round(power[1] / total, 3)}


def _best_shift(a: list[float], b: list[float], max_shift: int) -> tuple[int, float]:
    """b 相对 a 平移多少像素最像（正数 = 向右/向下）；返回 (平移, 相关系数)。"""
    n = len(a)
    scored = []
    for s in range(-max_shift, max_shift + 1):
        xs = [(a[i], b[i + s]) for i in range(max(0, -s), min(n, n - s))]
        if len(xs) < n // 2:
            continue
        ma = sum(x for x, _ in xs) / len(xs)
        mb = sum(y for _, y in xs) / len(xs)
        num = sum((x - ma) * (y - mb) for x, y in xs)
        den = (sum((x - ma) ** 2 for x, _ in xs) * sum((y - mb) ** 2 for _, y in xs)) ** 0.5
        scored.append((s, num / den if den else 0.0))
    if not scored:
        return 0, 0.0
    top = max(r for _, r in scored)
    # 重复纹理下多个平移同样吻合（右移 2 ≈ 左移 18）：取吻合度接近最高者里位移最小的，符合逐帧小位移的物理事实
    s, r = min(((s, r) for s, r in scored if r >= top - 0.02), key=lambda sr: abs(sr[0]))
    # 抛物线插值到亚像素：整数平移在慢速时误差可达 ±0.5px/帧
    by = dict(scored)
    if s - 1 in by and s + 1 in by:
        a, c = by[s - 1], by[s + 1]
        den = a - 2 * r + c
        if den < 0:
            return s + max(-0.5, min(0.5, 0.5 * (a - c) / den)), r
    return s, r


def analyze_motion(frames: list, fps: float, roi: list[int], line: str) -> tuple[dict, object]:
    """frames: PIL RGB 图列表。返回 (统计, 时间切片图)。"""
    from PIL import Image
    x0, y0, x1, y1 = roi
    vertical = line.lower().startswith("v")
    pos = float(line[1:] or 0.5)
    rows_rgb, rows_l = [], []
    for fr in frames:
        if vertical:
            x = x0 + round(pos * (x1 - x0 - 1))
            # ROTATE_90（逆时针）把列顶放到行首：行内正向位移 = 向下。ROTATE_270 会把方向报反
            strip = fr.crop((x, y0, x + 1, y1)).transpose(Image.Transpose.ROTATE_90)
        else:
            y = y0 + round(pos * (y1 - y0 - 1))
            strip = fr.crop((x0, y, x1, y + 1))
        rows_rgb.append(strip)
        rows_l.append(_pixels(strip.convert("L").resize((min(160, strip.width), 1))))
    width = rows_rgb[0].width
    slit = Image.new("RGB", (width, len(rows_rgb)))
    for i, r in enumerate(rows_rgb):
        slit.paste(r, (0, i))
    # 帧间变化量（ROI 内）
    small = [fr.crop(roi).convert("L").resize((160, max(1, round(160 * (y1 - y0) / max(1, x1 - x0))))) for fr in frames]
    diffs = []
    for a, b in zip(small, small[1:]):
        pa, pb = _pixels(a), _pixels(b)
        diffs.append(sum(abs(p - q) for p, q in zip(pa, pb)) / len(pa))
    # 沿切片线的移动速度
    scale = width / len(rows_l[0])
    shifts = [_best_shift(a, b, max(2, len(a) // 8)) for a, b in zip(rows_l, rows_l[1:])]
    good = [s for s, r in shifts if r > 0.5]
    speed = (sum(good) / len(good)) * scale * fps if good else None
    cols = [[row[c] for row in rows_l] for c in range(0, len(rows_l[0]), max(1, len(rows_l[0]) // 48))]
    stats = {"frames": len(frames), "fps": fps, "roi": roi, "slitLine": line,
             "meanChangePerFrame": round(sum(diffs) / len(diffs), 2) if diffs else 0,
             "changeTimeline": [round(d, 1) for d in diffs[:: max(1, len(diffs) // 40)]],
             "dominantPeriod": _dominant_period(cols, fps),
             "slitSpeedPxPerSec": round(speed, 1) if speed is not None else None,
             "slitSpeedRoiWidthPerSec": round(speed / (x1 - x0 if not vertical else y1 - y0), 3) if speed is not None else None,
             "slitDirection": None if speed is None else (("向下" if speed > 0 else "向上") if vertical else ("向右" if speed > 0 else "向左")),
             "slitTrackConfidence": round(len(good) / len(shifts), 2) if shifts else 0}
    return stats, slit


def cmd_motion(args):
    from PIL import Image, ImageDraw
    import tempfile
    video = Path(args.video)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", str(args.start), "-t", str(args.dur), "-i", str(video),
                        "-vf", f"fps={args.fps},scale={args.width}:-2", str(Path(td) / "f_%05d.png")], check=True)
        files = sorted(Path(td).glob("f_*.png"))
        if len(files) < 4:
            raise RuntimeError(f"只取到 {len(files)} 帧，检查 --start/--dur 是否在视频长度内")
        frames = [Image.open(p).convert("RGB") for p in files]
    w, h = frames[0].size
    roi = _box(args.roi, w, h) if args.roi else [0, 0, w, h]
    stats, slit = analyze_motion(frames, args.fps, roi, args.line)
    stem = safe_name(video.stem, 40)
    # 时间切片图：纵向拉伸 + 每秒刻度
    rep = max(1, 360 // len(frames))
    tall = slit.resize((slit.width, slit.height * rep), Image.NEAREST)
    margin = 60
    canvas = Image.new("RGB", (tall.width + margin, tall.height + 30), (20, 20, 20))
    canvas.paste(tall, (margin, 30))
    d = ImageDraw.Draw(canvas)
    f = _font(14)
    d.text((4, 6), f"时间切片（{args.line}）：每行 = 一帧，时间向下；斜条纹的斜率 = 移动速度", fill=(230, 230, 230), font=f)
    for sec in range(int(len(frames) / args.fps) + 1):
        y = 30 + round(sec * args.fps * rep)
        d.line([margin - 8, y, margin, y], fill=(255, 220, 0))
        d.text((4, y - 8), f"{args.start + sec:.0f}s", fill=(255, 220, 0), font=f)
    slit_path = out / f"{stem}_slit.png"
    canvas.save(slit_path)
    # 胶片条：均匀取 8 帧，标时间和 ROI/切片线
    picks = [round(i * (len(frames) - 1) / 7) for i in range(8)]
    thumbs = []
    for i in picks:
        fr = frames[i].copy()
        dd = ImageDraw.Draw(fr)
        dd.rectangle(roi, outline=(255, 220, 0), width=2)
        if args.line.lower().startswith("v"):
            x = roi[0] + round(float(args.line[1:] or 0.5) * (roi[2] - roi[0] - 1))
            dd.line([x, roi[1], x, roi[3]], fill=(80, 255, 80), width=2)
        else:
            y = roi[1] + round(float(args.line[1:] or 0.5) * (roi[3] - roi[1] - 1))
            dd.line([roi[0], y, roi[2], y], fill=(80, 255, 80), width=2)
        dd.text((6, 6), f"t={args.start + i / args.fps:.2f}s", fill=(255, 255, 255), font=_font(18))
        thumbs.append(fr)
    tw, th = thumbs[0].width // 2, thumbs[0].height // 2
    strip = Image.new("RGB", (tw * 4, th * 2), (0, 0, 0))
    for k, im in enumerate(thumbs):
        strip.paste(im.resize((tw, th)), ((k % 4) * tw, (k // 4) * th))
    strip_path = out / f"{stem}_strip.png"
    strip.save(strip_path)
    stats.update(video=str(video), start=args.start, dur=args.dur, slitImage=str(slit_path), stripImage=str(strip_path))
    (out / f"{stem}_motion.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    record(out, {"file": slit_path.name, "kind": "motion", "video": str(video), "start": args.start, "dur": args.dur})
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=1))
        return 0
    p = stats["dominantPeriod"]
    print(f"{video.name}  {args.start}s 起 {args.dur}s，{stats['frames']} 帧 @ {args.fps}fps，ROI {roi}")
    print(f"  帧间平均变化：{stats['meanChangePerFrame']}（0–255 灰度；<1 几乎静止，>8 很活跃）")
    if p:
        print(f"  主周期：{p['periodSec']}s（{p['freqHz']}Hz，占能量 {p['powerShare'] * 100:.0f}%；占比 <15% 说明没有明显节奏；"
              f"整段缓慢漂移占 {p['trendShare'] * 100:.0f}%，大说明镜头在移或光在变）")
    else:
        print("  主周期：帧数太少，加长 --dur")
    if stats["slitSpeedPxPerSec"] is not None:
        print(f"  沿切片线移动：{stats['slitDirection']} {abs(stats['slitSpeedPxPerSec'])}px/s"
              f"（≈ {abs(stats['slitSpeedRoiWidthPerSec'])} 个 ROI 宽/秒，跟踪可信度 {stats['slitTrackConfidence']}；<0.4 不要采信）")
    else:
        print("  沿切片线移动：跟踪不到稳定位移（画面太乱或几乎不动），以时间切片图为准")
    print(f"  时间切片图：{slit_path}\n  胶片条：{strip_path}\n  用法：先看胶片条确认 ROI 框住水面、没有镜头移动；"
          "镜头在动时速度是“相对画面”的，不能当水的真实速度。")
    return 0


# --------------------------------------------------------------------------- 网页存档

def cmd_wayback(args):
    d = fetch_json(f"https://archive.org/wayback/available?url={q(args.url)}" + (f"&timestamp={args.at}" if args.at else ""))
    snap = (d.get("archived_snapshots") or {}).get("closest")
    if not snap:
        raise SystemExit("web.archive.org 没有该页面的存档")
    print(f"{snap['timestamp']}  {snap['url']}")
    if args.read:
        page = _grab_page_text(snap["url"])
        print(f"\n标题：{page['title']}\n\n{page['text'][:4000]}")


def expand_url(url: str) -> list[dict]:
    """作品页 → 原图列表。各站点用其公开 JSON 接口，避免解析前端页面。"""
    m = re.search(r"pixiv\.net/(?:\w+/)?artworks/(\d+)", url)
    if m:
        d = fetch_json(f"https://www.pixiv.net/ajax/illust/{m.group(1)}/pages", headers={"Referer": "https://www.pixiv.net/"})
        return [{"url": p["urls"]["original"], "thumb": p["urls"].get("regular", ""), "size": f'{p["width"]}x{p["height"]}'}
                for p in d.get("body", [])]
    m = re.search(r"hoyolab\.com/article/(\d+)", url)
    if m:
        d = fetch_json(f"https://bbs-api-os.hoyolab.com/community/post/wapi/getPostFull?post_id={m.group(1)}")
        post = d.get("data", {}).get("post", {})
        imgs = [{"url": i["url"], "size": f'{i.get("width")}x{i.get("height")}'} for i in post.get("image_list", [])]
        return imgs or [{"url": u} for u in re.findall(r'https://upload-os-bbs\.hoyolab\.com/[^"\\]+', json.dumps(post))]
    m = re.search(r"miyoushe\.com/\w+/article/(\d+)|bbs\.mihoyo\.com/\w+/article/(\d+)", url)
    if m:
        pid = m.group(1) or m.group(2)
        d = fetch_json(f"https://bbs-api.miyoushe.com/post/wapi/getPostFull?post_id={pid}", headers={"Referer": "https://www.miyoushe.com/"})
        post = d.get("data", {}).get("post", {})
        return [{"url": i["url"], "size": f'{i.get("width")}x{i.get("height")}'} for i in post.get("image_list", [])]
    m = re.search(r"bilibili\.com/video/(BV\w+)", url)
    if m:
        d = fetch_json(f"https://api.bilibili.com/x/web-interface/view?bvid={m.group(1)}")["data"]
        print(f"标题：{d['title']}\n时长：{d['duration']} 秒  UP：{d['owner']['name']}\n简介：{d['desc'][:300]}")
        return [{"url": d["pic"], "size": "cover"}]
    m = re.search(r"youtube\.com/watch\?v=([\w-]+)|youtu\.be/([\w-]+)", url)
    if m:
        vid = m.group(1) or m.group(2)
        return [{"url": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg", "size": "cover"}]
    if "artstation.com" in url:
        raise RuntimeError("ArtStation 作品详情页有 Cloudflare 人机验证，无头抓不到。"
                           "可用：① images --src artstation 拿到的 large 封面；② Codex 的 browser 插件用真实浏览器打开再取图；"
                           "③ 请用户在浏览器里打开后保存图片。")
    raise RuntimeError("暂不支持该站点，改用 page 子命令（可加 --js）找图片地址")


def cmd_expand(args):
    items = expand_url(args.url)
    for i, it in enumerate(items, 1):
        print(f"{i:3d}. {it.get('size', '')}  {it['url']}")
    if not items:
        return 3
    failed = 0
    if args.out:
        for i, it in enumerate(items, 1):
            try:
                e = download(it["url"], Path(args.out), None, {"page": args.url})
                print(f"  ok {e['file']} {e.get('size', '')}")
            except Exception as ex:  # noqa: BLE001
                failed += 1
                print(f"  失败 {it['url'][:80]}: {ex}", file=sys.stderr)
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="输出 JSON（放在子命令前后都可以）")

    def add(name, **kw):
        if "help" in kw:
            kw.setdefault("description", kw["help"])
        return sub.add_parser(name, parents=[common], formatter_class=argparse.RawDescriptionHelpFormatter, **kw)

    add("doctor", help="检查依赖和各来源此刻是否可达（每个来源最多等约 12 秒）")

    p = add("web", help="网页搜索：多个引擎并行，合并去重"); p.add_argument("query"); p.add_argument("-n", type=int, default=10)
    p.add_argument("--src", nargs="+", choices=list(WEB_ENGINES)); p.add_argument("--site", help="只搜某站，如 zhuanlan.zhihu.com")

    p = add("images", help="图片搜索；--download DIR 下载，--sheet 拼触表，--min-width 过滤小图和近重复"); p.add_argument("query"); p.add_argument("-n", type=int, default=20)
    p.add_argument("--src", nargs="+", choices=list(IMG_ENGINES))
    p.add_argument("--must", help="必含词，逗号分隔：标题/来源页都不含的标 [疑似跑题] 排到最后（下载时仍会下，挑图时注意）")
    p.add_argument("--download", metavar="DIR", help="下载到该目录"); p.add_argument("--sheet", action="store_true", help="下载后拼触表")
    p.add_argument("--min-width", type=int, default=800, help="宽度小于此值或近重复的图移到 _rejected/（0 关闭）")

    p = add("refs", help="一键取点名参照：逐个来源尝试直到够数，记录每次尝试，拼触表")
    p.add_argument("subjects", nargs="+", help='"英文名=中文名"，如 "Genshin Impact=原神" "Wuthering Waves=鸣潮"')
    p.add_argument("--topic", default="water", help="英文主题词，如 water / ocean / lake")
    p.add_argument("--topic-zh", default="水面", help="中文主题词")
    p.add_argument("--need", type=int, default=4); p.add_argument("--min-width", type=int, default=1000)
    p.add_argument("--out", required=True)

    p = add("video", help="视频搜索：bilibili / youtube（标题、时长、链接、封面）"); p.add_argument("query"); p.add_argument("-n", type=int, default=10)
    p.add_argument("--src", nargs="+", choices=list(VID_ENGINES))
    p.add_argument("--must", help="作品名等必含词，逗号分隔，如 王国之泪,塞尔达,Zelda：都不含的标 [疑似跑题] 排到最后")

    p = add("get", help="下载图片或文件到 --out（自动带 Referer，失败改用 curl）"); p.add_argument("urls", nargs="+"); p.add_argument("--out", required=True); p.add_argument("--name")

    p = add("page", help="抓网页正文 + 图片 + 链接；--js 用 Edge 无头渲染，--save 存全文"); p.add_argument("url"); p.add_argument("--js", action="store_true")
    p.add_argument("--chars", type=int, default=4000); p.add_argument("--imgs", type=int, default=30)
    p.add_argument("--links", type=int, default=0); p.add_argument("--save")

    p = add("shot", help="用 Edge 无头给网页截图"); p.add_argument("url"); p.add_argument("--out", required=True)
    p.add_argument("--w", type=int, default=1600); p.add_argument("--h", type=int, default=900); p.add_argument("--wait", type=int, default=6000)

    p = add("vdl", help="下载视频；--section 00:30-01:10 只下一段。每行打印一个文件路径（--json 给 paths）"); p.add_argument("url"); p.add_argument("--out", required=True)
    p.add_argument("--section", help="如 00:30-01:10"); p.add_argument("--height", type=int, default=1080)

    p = add("frames", help="从视频截帧：--at 12.5,40（秒）| --every 2（每 2 秒）| --scene 0.3（镜头切换）；--sheet 拼触表"); p.add_argument("video"); p.add_argument("--out", required=True)
    p.add_argument("--every", type=float); p.add_argument("--scene", type=float); p.add_argument("--at")
    p.add_argument("--width", type=int, default=1600); p.add_argument("--limit", type=int, default=60)
    p.add_argument("--sheet", action="store_true")

    p = add("sheet", help="把图片（或目录里的图片）拼成带编号的触表"); p.add_argument("images", nargs="+"); p.add_argument("--out", required=True)
    p.add_argument("--cols", type=int, default=5); p.add_argument("--cell", type=int, default=320)

    p = add("compare", help="并排对比图：参照 | 当前版 | 上一版，等高缩放、带标签"); p.add_argument("images", nargs="+"); p.add_argument("--out", required=True)
    p.add_argument("--labels", help='用 | 分隔，如 "原神参照|v3|v2"'); p.add_argument("--height", type=int, default=540)

    p = add("wiki", help="MediaWiki 站点搜页面；--images 搜图片"); p.add_argument("site", help="、".join(WIKIS) + " 或任意 api.php 地址")
    p.add_argument("query"); p.add_argument("-n", type=int, default=10); p.add_argument("--images", action="store_true")

    p = add("gh", help="GitHub 仓库搜索"); p.add_argument("query"); p.add_argument("-n", type=int, default=10)
    p.add_argument("--sort", default="stars", choices=["stars", "updated", "best-match"])

    p = add("gh-dl", help="下载 GitHub 仓库源码 zip（都失败时自动 git 浅克隆）"); p.add_argument("repo"); p.add_argument("--out", required=True); p.add_argument("--ref")
    p.add_argument("--git", action="store_true", help="用 git 浅克隆（大仓库/zip 不通时）")

    p = add("expand", help="把作品页展开成全部原图：pixiv / hoyolab / bilibili / artstation")
    p.add_argument("url"); p.add_argument("--out", help="给出则直接下载")

    p = add("research", help="搜索并把前 N 篇正文存成 md + index.md")
    p.add_argument("query"); p.add_argument("--out", required=True); p.add_argument("--pages", type=int, default=6)
    p.add_argument("-n", type=int, default=12); p.add_argument("--site"); p.add_argument("--max-chars", type=int, default=30000)
    p.add_argument("--src", nargs="+", choices=list(WEB_ENGINES))

    p = add("subs", help="下载视频字幕并转成带时间戳的文本（B 站 / YouTube 等）")
    p.add_argument("url"); p.add_argument("--out", required=True)
    p.add_argument("--lang", default="zh.*,ai-zh,en.*,ja.*")
    p.add_argument("--cookies-from-browser", help="仅在用户同意后使用，如 edge")

    p = add("gh-tree", help="列出 GitHub 仓库文件"); p.add_argument("repo")
    p.add_argument("--ref", default="HEAD"); p.add_argument("--filter", help="正则，如 \\.(shader|hlsl|cginc)$")
    p.add_argument("--limit", type=int, default=300)
    p.add_argument("--ext", help="按扩展名过滤，逗号分隔，如 shader,hlsl,cginc（免写正则，不怕 PowerShell 引号）")

    p = add("gh-cat", help="读 GitHub 仓库里的单个文件"); p.add_argument("repo"); p.add_argument("path")
    p.add_argument("--ref", default="HEAD"); p.add_argument("--out")

    p = add("pdf", help="PDF（本地或 URL）→ 按页文本，可选提取图片")
    p.add_argument("src"); p.add_argument("--out", required=True); p.add_argument("--pages", help="如 3-12")
    p.add_argument("--images", action="store_true")

    p = add("measure", help="量图：点取色、区域均色、网格色带、主色板（坐标可用 0–1 相对值）")
    p.add_argument("image"); p.add_argument("--points", help='"0.5,0.8;0.5,0.6"'); p.add_argument("--regions", help='"x0,y0,x1,y1;..."')
    p.add_argument("--grid", help="如 4x1：上下切 4 段看近中远色带"); p.add_argument("--palette", type=int, default=0)
    p.add_argument("--roi", help="只在这个框里统计 grid/palette，避开游戏 UI：x0,y0,x1,y1（≤1 为比例）")
    p.add_argument("--annot", help="标注图输出路径（默认 原名_measure.png）"); p.add_argument("--no-annot", action="store_true")
    p.add_argument("--line", help="沿线量亮带宽度（岸线泡沫等）：x0,y0,x1,y1，多条用 ; 分隔，线要横穿泡沫带")
    p.add_argument("--thresh", type=float, help="亮带阈值 0–255，缺省取线上 (最暗+最亮)/2")

    p = add("look", help="看图板：原图 | 眯眼 | 6 色分离 | 边缘，附主色和明度直方图；打印饱和度、明度阶数、边缘锐度")
    p.add_argument("images", nargs="+", help="参照 当前 [上一版] …")
    p.add_argument("--out", required=True)
    p.add_argument("--roi", help="只统计框内（如水面）：x0,y0,x1,y1（≤1 为比例）；构图不同就用 | 一张一个框")
    p.add_argument("--labels", help='用 | 分隔，默认 "参照|当前|上一版"'); p.add_argument("--row-height", type=int, default=260)

    p = add("crops", help="分区对齐裁切：各图同名部位（近岸/远水/高光…）并排，标中位色、HSV 和与第一张的差",
            epilog='例：crops ref.png v3.png v2.png --labels "参照|v3|v2" --regions "近岸=0.05,0.7,0.4,0.95;远水=0.3,0.35,0.9,0.5" --out cmp/crops.png\n'
                   '构图不同：--regions "近岸=...;远水=... | 近岸=...;远水=... | ..."（一张一段，名字和顺序一致）')
    p.add_argument("images", nargs="+"); p.add_argument("--out", required=True)
    p.add_argument("--regions", required=True, help='"名=x0,y0,x1,y1;名=..."（≤1 为比例）；用 | 给每张图各写一段')
    p.add_argument("--labels", help='用 | 分隔，如 "参照|v3|v2"'); p.add_argument("--height", type=int, default=220, help="每格高度")

    p = add("pick", help="参照登记：选入（复制成 R1、R2… 并记出处/sha256）或 --reject 剔除，生成 SELECTED.md",
            epilog='例：pick refs/genshin/bing-en_03.jpg refs/genshin/bing-en_05.jpg --subject 原神 --why "实机，水面占六成，无UI" --out refs/selected\n'
                   '    pick refs/genshin/baidu-zh_01.jpg --subject 原神 --reject --why "同人图，不是实机" --out refs/selected\n'
                   '同一张图 + 同一个对象再 pick 一次 = 改判；同一张图登记给不同对象（多作品拼图）各算一条')
    p.add_argument("images", nargs="+"); p.add_argument("--out", required=True, help="登记目录（选入的图复制到这里）")
    p.add_argument("--subject", required=True, help="点名对象，如 原神"); p.add_argument("--why", required=True, help="一句话：看到了什么所以选入/剔除")
    p.add_argument("--reject", action="store_true", help="登记为剔除（不复制）"); p.add_argument("--ids", help="自定 ID，逗号分隔，一张一个")
    p.add_argument("--prefix", default="R", help="自动编号前缀，默认 R → R1、R2…"); p.add_argument("--src", help="出处 URL 或来源标识（不是 refgrab 下载的图要补）")

    p = add("motion", help="动态测量：时间切片图（看波速/方向）、带时间戳胶片条、变化量和主周期")
    p.add_argument("video"); p.add_argument("--out", required=True)
    p.add_argument("--start", type=float, default=0); p.add_argument("--dur", type=float, default=8)
    p.add_argument("--fps", type=float, default=15); p.add_argument("--width", type=int, default=640)
    p.add_argument("--roi", help="只分析水面区域 x0,y0,x1,y1（≤1 为比例），避开 UI")
    p.add_argument("--line", default="h0.5", help="切片线：h0.5 = ROI 内高度一半处的横线；v0.3 = ROI 内宽度 30%% 处的竖线")

    p = add("wayback", help="查 web.archive.org 存档"); p.add_argument("url")
    p.add_argument("--at", help="时间，如 2023"); p.add_argument("--read", action="store_true")

    # 先于参数解析：argparse 的用法错误也要按 UTF-8 输出，否则 GBK 控制台下调用方解码会乱
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = ap.parse_args(argv)
    if getattr(args, "sort", None) == "best-match":
        args.sort = ""
    func = {"doctor": cmd_doctor, "web": cmd_web, "images": cmd_images, "video": cmd_video, "get": cmd_get, "page": cmd_page,
     "shot": cmd_shot, "vdl": cmd_vdl, "frames": cmd_frames, "sheet": cmd_sheet, "compare": cmd_compare,
     "wiki": cmd_wiki, "gh": cmd_gh, "gh-dl": cmd_gh_dl, "expand": cmd_expand, "research": cmd_research,
     "subs": cmd_subs, "gh-tree": cmd_gh_tree, "gh-cat": cmd_gh_cat, "pdf": cmd_pdf, "measure": cmd_measure,
     "wayback": cmd_wayback, "refs": cmd_refs, "motion": cmd_motion, "look": cmd_look,
     "crops": cmd_crops, "pick": cmd_pick}[args.cmd]
    try:
        rc = func(args)
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130
    except SystemExit as e:
        if isinstance(e.code, str):
            print("失败：" + e.code, file=sys.stderr)
            return 2
        return e.code or 0
    except Exception as e:  # noqa: BLE001 - 统一给出可读失败和非零退出码
        print(f"失败：{type(e).__name__}: {str(e)[:400]}", file=sys.stderr)
        return 2
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
