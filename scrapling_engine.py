import re
from urllib.parse import urljoin, urlparse
from scrapling import Fetcher, StealthyFetcher

class ScrapingEngine:
    """
    Wrapper around Scrapling library to fetch and parse structured web content.
    Supports basic HTTP fetching via Fetcher and browser/stealth fetching via StealthyFetcher.
    """

    @staticmethod
    def scrape_url(url: str, custom_selector: str = None, mode: str = "fast", timeout: int = 15) -> dict:
        """
        Scrape target URL and extract structured data blocks.

        :param url: Target website URL
        :param custom_selector: Optional CSS selector to extract specific elements
        :param mode: 'fast' using Fetcher or 'stealth' using StealthyFetcher
        :param timeout: Timeout in seconds
        :return: Dict containing page metadata and extracted blocks
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Fetch page according to requested mode
        if mode == "stealth":
            try:
                StealthyFetcher.configure(adaptive=True)
                page = StealthyFetcher.fetch(url, timeout=timeout)
            except Exception as e:
                # Fallback to standard Fetcher if StealthyFetcher encounters issue
                page = Fetcher.get(url, timeout=timeout)
        else:
            page = Fetcher.get(url, timeout=timeout)

        title = (page.css("title::text").get() or "Sin título").strip()
        domain = urlparse(url).netloc

        blocks = []
        block_id = 1

        # 1. Custom CSS selector extraction if provided
        if custom_selector and custom_selector.strip():
            selected_items = page.css(custom_selector.strip())
            for idx, item in enumerate(selected_items):
                text = (item.text or "").strip()
                html = (item.html or "").strip()
                if text or html:
                    blocks.append({
                        "id": block_id,
                        "type": "custom",
                        "tag": custom_selector.strip(),
                        "title": f"Selector Personalizado #{idx + 1}",
                        "content": text if text else html,
                        "html": html,
                        "url": url
                    })
                    block_id += 1

        # 2. Extract Headings (H1, H2, H3, H4)
        headings = page.css("h1, h2, h3, h4")
        for heading in headings:
            text = (heading.text or "").strip()
            if text:
                tag = (heading.tag or "h2").lower()
                blocks.append({
                    "id": block_id,
                    "type": "heading",
                    "tag": tag,
                    "title": f"Encabezado ({tag.upper()})",
                    "content": text,
                    "url": url
                })
                block_id += 1

        # 3. Extract Paragraphs & Text Blocks
        paragraphs = page.css("p, article p, section p")
        for p in paragraphs:
            text = (p.text or "").strip()
            if text and len(text) > 15:  # Filter noise/very short snippets
                blocks.append({
                    "id": block_id,
                    "type": "paragraph",
                    "tag": "p",
                    "title": "Párrafo de Texto",
                    "content": text,
                    "url": url
                })
                block_id += 1

        # 4. Extract Links
        links = page.css("a[href]")
        extracted_links = set()
        for link in links:
            text = (link.text or "").strip()
            href = link.attrib.get("href", "").strip() if hasattr(link, "attrib") else ""
            if href and not href.startswith("javascript:") and not href.startswith("#"):
                abs_url = urljoin(url, href)
                link_key = f"{text}|{abs_url}"
                if link_key not in extracted_links and (text or abs_url):
                    extracted_links.add(link_key)
                    blocks.append({
                        "id": block_id,
                        "type": "link",
                        "tag": "a",
                        "title": "Enlace Extraído",
                        "content": text if text else abs_url,
                        "link_url": abs_url,
                        "url": url
                    })
                    block_id += 1
                    if len(extracted_links) >= 30:  # Cap at 30 links to keep results crisp
                        break

        # 5. Extract Images
        images = page.css("img[src]")
        extracted_imgs = set()
        for img in images:
            src = img.attrib.get("src", "").strip() if hasattr(img, "attrib") else ""
            alt = (img.attrib.get("alt", "") if hasattr(img, "attrib") else "").strip()
            if src and not src.startswith("data:"):
                abs_src = urljoin(url, src)
                if abs_src not in extracted_imgs:
                    extracted_imgs.add(abs_src)
                    blocks.append({
                        "id": block_id,
                        "type": "image",
                        "tag": "img",
                        "title": "Imagen / Recurso Visual",
                        "content": alt if alt else abs_src,
                        "img_src": abs_src,
                        "url": url
                    })
                    block_id += 1
                    if len(extracted_imgs) >= 20:  # Cap images
                        break

        # 6. Extract Tables Data
        tables = page.css("table")
        for t_idx, table in enumerate(tables):
            rows = table.css("tr")
            table_data = []
            for row in rows:
                cols = [c.text.strip() for c in row.css("th, td") if c.text]
                if cols:
                    table_data.append(" | ".join(cols))
            if table_data:
                blocks.append({
                    "id": block_id,
                    "type": "table",
                    "tag": "table",
                    "title": f"Tabla de Datos #{t_idx + 1}",
                    "content": "\n".join(table_data),
                    "url": url
                })
                block_id += 1

        return {
            "status": "success",
            "url": url,
            "domain": domain,
            "title": title,
            "total_blocks": len(blocks),
            "blocks": blocks
        }
