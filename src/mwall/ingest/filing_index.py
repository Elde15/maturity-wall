"""Read an EDGAR filing's -index.htm to find its exhibits by declared type.

File names vary by filer agent (exh_102.xml, ex102.xml, wfcm2017c38_ex102.xml,
...), so we never guess from the name: we read the Type column.
"""
from __future__ import annotations

import re

from lxml import html

from mwall.ingest.sec_client import SecClient

ARCHIVES = "https://www.sec.gov/Archives/edgar/data"


def acc_nodash(accession: str) -> str:
    return accession.replace("-", "")


def filing_index_url(cik: int, accession: str) -> str:
    return f"{ARCHIVES}/{cik}/{acc_nodash(accession)}/{accession}-index.htm"


def doc_url(cik: int, accession: str, name: str) -> str:
    return f"{ARCHIVES}/{cik}/{acc_nodash(accession)}/{name}"


def parse_index_html(body: bytes) -> tuple[str | None, list[dict]]:
    tree = html.fromstring(body)
    period = None
    for head in tree.xpath('//div[@class="infoHead"]'):
        if head.text_content().strip() == "Period of Report":
            nxt = head.getnext()
            if nxt is not None:
                period = nxt.text_content().strip() or None
    docs = []
    for tr in tree.xpath('//table[contains(@class,"tableFile")]//tr'):
        tds = tr.xpath("./td")
        if len(tds) < 4:
            continue
        link = tds[2].xpath(".//a/@href")
        if not link:
            continue
        name = link[0].rsplit("/", 1)[-1]
        # inline XBRL viewer links look like /ix?doc=/Archives/...; keep the file name only
        name = re.sub(r"^.*doc=", "", name).rsplit("/", 1)[-1]
        size_txt = tds[4].text_content().strip() if len(tds) > 4 else ""
        docs.append(
            {
                "seq": tds[0].text_content().strip(),
                "description": tds[1].text_content().strip(),
                "name": name,
                "type": tds[3].text_content().strip(),
                "size": int(size_txt) if size_txt.isdigit() else None,
            }
        )
    return period, docs


def fetch_filing_docs(client: SecClient, cik: int, accession: str) -> tuple[int, str | None, list[dict]]:
    res = client.get(filing_index_url(cik, accession))
    if res.status != 200:
        return res.status, None, []
    period, docs = parse_index_html(res.content)
    return 200, period, docs


def pick(docs: list[dict], doc_type: str) -> dict | None:
    hits = [d for d in docs if d["type"].upper() == doc_type]
    if not hits:
        return None
    xml_hits = [d for d in hits if d["name"].lower().endswith(".xml")]
    return (xml_hits or hits)[0]


NS_RE = re.compile(rb"<([A-Za-z_][\w.:-]*)[^>]*?\sxmlns=\"([^\"]+)\"")


def root_namespace(head: bytes) -> tuple[str | None, str | None]:
    """Return (root tag, default namespace) from the first few KB of an XML file."""
    body = re.sub(rb"<\?xml[^>]*\?>", b"", head, count=1)
    m = NS_RE.search(body)
    if not m:
        tag = re.search(rb"<([A-Za-z_][\w.:-]*)", body)
        return (tag.group(1).decode() if tag else None), None
    return m.group(1).decode(), m.group(2).decode()
