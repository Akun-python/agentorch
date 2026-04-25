#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量下载 cas-sc-template-zh.tex 中 thebibliography 的参考文献。

功能目标：
1. 按文献顺序编号下载到 `参考文献\\编号下载`；
2. 优先下载 PDF；
3. 无法直下 PDF 时，回退保存来源页面 HTML；
4. 生成 manifest 与 CSV 结果，便于人工复核。
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import requests


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 12
MAX_PDF_CANDIDATES = 15


@dataclass
class ReferenceItem:
    index: int
    key: str
    body: str
    url: str


def parse_references(tex_path: Path) -> list[ReferenceItem]:
    text = tex_path.read_text(encoding="utf-8")
    block_match = re.search(
        r"\\begin\{thebibliography\}\{00\}(?P<block>.*?)\\end\{thebibliography\}",
        text,
        flags=re.S,
    )
    if not block_match:
        raise RuntimeError("未找到 thebibliography 区块。")

    block = block_match.group("block")
    pattern = re.compile(
        r"\\bibitem\[[^\]]+\]\{(?P<key>[^}]+)\}\s*(?P<body>.*?)(?=(?:\n\\bibitem\[)|\Z)",
        flags=re.S,
    )
    refs: list[ReferenceItem] = []
    for idx, m in enumerate(pattern.finditer(block), start=1):
        key = m.group("key").strip()
        body = " ".join(m.group("body").strip().split())
        url_match = re.search(r"\\url\{(?P<url>[^}]+)\}", body)
        if not url_match:
            # 没有 URL 的条目保留，后续写入 manifest 便于人工补全。
            url = ""
        else:
            url = url_match.group("url").strip()
        refs.append(ReferenceItem(index=idx, key=key, body=body, url=url))
    return refs


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


def looks_like_pdf(content: bytes) -> bool:
    return content[:5] == b"%PDF-"


def is_pdf_response(resp: requests.Response) -> bool:
    ctype = resp.headers.get("Content-Type", "").lower()
    if "application/pdf" in ctype:
        return True
    return looks_like_pdf(resp.content[:2048])


def fetch(url: str) -> requests.Response:
    return requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )


def extract_html_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if not m:
        return ""
    return " ".join(m.group(1).split())


def unique_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if not v:
            continue
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def build_special_candidates(url: str) -> list[str]:
    candidates: list[str] = []
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path

    # ACL Anthology: 条目页 -> 论文 PDF
    if "aclanthology.org" in host and not path.endswith(".pdf"):
        candidates.append(url.rstrip("/") + ".pdf")

    # OpenReview: forum -> pdf
    if "openreview.net" in host and parsed.path == "/forum":
        q = parse_qs(parsed.query)
        paper_id = q.get("id", [""])[0]
        if paper_id:
            candidates.append(f"https://openreview.net/pdf?id={paper_id}")

    # NeurIPS Abstract 页面 -> 直接 PDF
    m = re.search(
        r"/paper/(?P<year>\d{4})/hash/(?P<hash>[0-9a-f]+)-Abstract\.html$",
        path,
        flags=re.I,
    )
    if m:
        year = m.group("year")
        hash_code = m.group("hash")
        candidates.append(
            f"https://proceedings.neurips.cc/paper_files/paper/{year}/file/{hash_code}-Paper.pdf"
        )

    # PMLR 页面 -> 直接 PDF
    # 例: /v267/gutierrez25a.html -> /v267/gutierrez25a/gutierrez25a.pdf
    m_pmlr = re.search(r"/v(?P<vol>\d+)/(?P<name>[^/]+)\.html$", path, flags=re.I)
    if "proceedings.mlr.press" in host and m_pmlr:
        vol = m_pmlr.group("vol")
        name = m_pmlr.group("name")
        candidates.append(f"https://proceedings.mlr.press/v{vol}/{name}/{name}.pdf")

    return candidates


def extract_pdf_links_from_html(base_url: str, html: str) -> list[str]:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    pdf_links: list[str] = []
    for href in hrefs:
        if ".pdf" in href.lower() or "/pdf?" in href.lower():
            pdf_links.append(urljoin(base_url, href))
    return unique_keep_order(pdf_links)[:MAX_PDF_CANDIDATES]


def find_existing_download(base_stem: str, out_dir: Path) -> Path | None:
    for ext in (".pdf", ".html", ".txt"):
        p = out_dir / f"{base_stem}{ext}"
        if p.exists():
            return p
    return None


def download_one(ref: ReferenceItem, out_dir: Path) -> dict:
    base_stem = f"{ref.index:03d}_{safe_name(ref.key)}"
    existing = find_existing_download(base_stem, out_dir)
    if existing is not None:
        return {
            "index": ref.index,
            "key": ref.key,
            "source_url": ref.url,
            "status": "skipped_existing",
            "saved_as": str(existing),
            "final_url": "",
            "http_status": "",
            "note": "already_exists",
        }

    result = {
        "index": ref.index,
        "key": ref.key,
        "source_url": ref.url,
        "status": "failed",
        "saved_as": "",
        "final_url": "",
        "http_status": "",
        "note": "",
    }

    if not ref.url:
        txt_path = out_dir / f"{base_stem}.txt"
        txt_path.write_text(
            f"[{ref.index}] {ref.key}\n原始条目缺少 URL，需人工补充下载源。\n",
            encoding="utf-8",
        )
        result["status"] = "no_url"
        result["saved_as"] = str(txt_path)
        result["note"] = "missing_url"
        return result

    try:
        primary = fetch(ref.url)
    except Exception as exc:
        txt_path = out_dir / f"{base_stem}.txt"
        txt_path.write_text(
            f"[{ref.index}] {ref.key}\n请求失败：{exc}\nURL: {ref.url}\n",
            encoding="utf-8",
        )
        result["status"] = "request_error"
        result["saved_as"] = str(txt_path)
        result["note"] = str(exc)
        return result

    result["final_url"] = primary.url
    result["http_status"] = primary.status_code

    # 1) 首次响应就是 PDF，直接保存
    if primary.status_code == 200 and is_pdf_response(primary):
        pdf_path = out_dir / f"{base_stem}.pdf"
        pdf_path.write_bytes(primary.content)
        result["status"] = "pdf"
        result["saved_as"] = str(pdf_path)
        return result

    html = primary.text if primary.text else ""
    title = extract_html_title(html)

    # 2) 组合候选 PDF 链接逐一尝试
    candidates = []
    candidates.extend(build_special_candidates(ref.url))
    candidates.extend(build_special_candidates(primary.url))
    if html:
        candidates.extend(extract_pdf_links_from_html(primary.url, html))
    candidates = unique_keep_order(candidates)

    for cand in candidates[:MAX_PDF_CANDIDATES]:
        try:
            r = fetch(cand)
        except Exception:
            continue
        if r.status_code == 200 and is_pdf_response(r):
            pdf_path = out_dir / f"{base_stem}.pdf"
            pdf_path.write_bytes(r.content)
            result["status"] = "pdf"
            result["saved_as"] = str(pdf_path)
            result["final_url"] = r.url
            result["http_status"] = r.status_code
            result["note"] = f"resolved_from={cand}"
            return result

    # 3) 回退保存 HTML（表示已下载到源页面，但无公开 PDF 或受限）
    if primary.status_code == 200 and html:
        html_path = out_dir / f"{base_stem}.html"
        html_path.write_text(html, encoding="utf-8", errors="ignore")
        result["status"] = "html_fallback"
        result["saved_as"] = str(html_path)
        result["note"] = title or "no_pdf_found"
        return result

    # 4) 最终失败，保存文本说明
    txt_path = out_dir / f"{base_stem}.txt"
    txt_path.write_text(
        "\n".join(
            [
                f"[{ref.index}] {ref.key}",
                f"请求状态: {primary.status_code}",
                f"URL: {ref.url}",
                f"Final URL: {primary.url}",
                f"Title: {title}",
                "未能获取 PDF，可能因权限限制或站点防护。",
            ]
        ),
        encoding="utf-8",
    )
    result["status"] = "failed_saved_note"
    result["saved_as"] = str(txt_path)
    result["note"] = title or "failed"
    return result


def main() -> int:
    root = Path.cwd()
    tex_path = root / "cas-sc-template-zh.tex"
    out_root = root / "参考文献"
    out_dir = out_root / "编号下载"
    out_dir.mkdir(parents=True, exist_ok=True)

    refs = parse_references(tex_path)
    results = [download_one(ref, out_dir) for ref in refs]

    manifest = {
        "source_tex": str(tex_path),
        "target_dir": str(out_dir),
        "total_references": len(refs),
        "results": results,
    }

    manifest_path = out_root / "download_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = out_root / "download_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "index",
                "key",
                "status",
                "http_status",
                "saved_as",
                "source_url",
                "final_url",
                "note",
            ],
        )
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    pdf_count = sum(1 for r in results if r["status"] == "pdf")
    html_count = sum(1 for r in results if r["status"] == "html_fallback")
    fail_count = len(results) - pdf_count - html_count

    print(f"总文献数: {len(results)}")
    print(f"PDF 下载成功: {pdf_count}")
    print(f"HTML 回退保存: {html_count}")
    print(f"失败/仅说明文件: {fail_count}")
    print(f"清单: {manifest_path}")
    print(f"汇总: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
