import re
import urllib.parse
from patchright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from scrapling import Fetcher, Selector

class ScrapingEngine:
    """
    Wrapper around Scrapling and Patchright Playwright engine to fetch and parse structured web content.
    Automatically handles Google Search/Local queries and Javascript-rendered pages.
    """

    @staticmethod
    def scrape_url(url: str, custom_selector: str = None, mode: str = "auto", timeout: int = 15) -> dict:
        """
        Scrape target URL and extract structured data blocks.

        :param url: Target website URL
        :param custom_selector: Optional CSS selector
        :param mode: Extraction mode ('auto', 'fast', 'stealth')
        :param timeout: Timeout in seconds
        :return: Dict containing page metadata and extracted blocks
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        domain = urllib.parse.urlparse(url).netloc
        is_google = "google." in domain.lower()

        html = ""
        title = ""

        # Google Search/Local or stealth requests use Playwright Chromium for full JavaScript rendering and stealth bypass
        if is_google or mode in ["stealth", "playwright"]:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                        locale='es-ES',
                        viewport={'width': 1280, 'height': 800}
                    )
                    page = context.new_page()
                    page.goto(url, timeout=timeout * 1000, wait_until='domcontentloaded')

                    if is_google:
                        try:
                            page.wait_for_selector('div.dbg0pd, div.VkpGBb, .rllt__content', timeout=8000)
                        except Exception:
                            pass
                    page.wait_for_timeout(1500)
                    title = page.title()
                    html = page.content()
                    browser.close()
            except Exception:
                page = Fetcher.get(url, timeout=timeout)
                html = getattr(page, 'html_content', '') or getattr(page, 'text', '')
                title = (page.css("title::text").get() or "Sin título").strip()
        else:
            try:
                page = Fetcher.get(url, timeout=timeout)
                html = getattr(page, 'html_content', '') or getattr(page, 'text', '')
                title = (page.css("title::text").get() or "Sin título").strip()
                # If Google consent redirect or blocked response detected, fallback to Playwright
                if "sorry/index" in html or "retry/enablejs" in html or ("Google" in title and len(html) < 100000):
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        context = browser.new_context(
                            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                            locale='es-ES',
                            viewport={'width': 1280, 'height': 800}
                        )
                        pg = context.new_page()
                        pg.goto(url, timeout=timeout * 1000, wait_until='domcontentloaded')
                        pg.wait_for_timeout(1500)
                        title = pg.title()
                        html = pg.content()
                        browser.close()
            except Exception:
                pass

        soup = BeautifulSoup(html, 'html.parser')
        blocks = []
        block_id = 1

        # Extract Google Local / Business Cards if present
        dbg_elements = soup.select('div.dbg0pd')
        if dbg_elements or 'udm=local' in url:
            seen_names = set()
            for name_el in dbg_elements:
                name = name_el.get_text(strip=True)
                if not name or name in seen_names:
                    continue

                container = name_el
                for _ in range(8):
                    if container.parent and container.parent.name != 'body':
                        container = container.parent
                        classes = container.get('class') or []
                        if any(cls in classes for cls in ['VkpGBb', 'vwVdIc', 'cXedhc', 'rllt__content']):
                            break

                full_text = container.get_text(separator=' | ', strip=True)
                parts = [p.strip() for p in full_text.split('|') if p.strip()]

                # Address extraction
                address = 'N/A'
                for part in parts:
                    if re.search(r'\d+\s+[A-Za-z0-9\s\.\,\#\-]+(St|Ave|Dr|Blvd|Rd|Way|Ln|Ct|Ste|Suite|Plaza|Pkwy)', part, re.IGNORECASE):
                        address = part
                        break

                # Phone extraction
                phone = 'N/A'
                phone_match = re.search(r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', full_text)
                if phone_match:
                    phone = phone_match.group(0)

                # Website link extraction
                website = ''
                for a in container.find_all('a', href=True):
                    href = a['href']
                    if 'url?q=' in href:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        target_url = parsed.get('q', [''])[0]
                        if target_url and not any(g in target_url for g in ['google.com', 'google.es', 'google.co']):
                            website = target_url
                            break
                    elif href.startswith('http') and not any(g in href for g in ['google.com', 'google.es', 'gstatic.com']):
                        website = href
                        break

                # Fallback to direct Google Maps search link if no external website is embedded
                if not website and address != 'N/A':
                    query_str = urllib.parse.quote(f"{name} {address}")
                    website = f"https://www.google.com/maps/search/?api=1&query={query_str}"

                content_str = f"Nombre: {name}\nTeléfono: {phone}\nDirección: {address}\nWebsite / Link: {website if website else 'N/A'}\n\nDetalles: {full_text}"

                seen_names.add(name)
                blocks.append({
                    "id": block_id,
                    "type": "business",
                    "tag": "negocio",
                    "title": f"Negocio: {name}",
                    "content": content_str,
                    "link_url": website if website else None,
                    "url": url,
                    "business_data": {
                        "name": name,
                        "phone": phone,
                        "address": address,
                        "website": website
                    }
                })
                block_id += 1

        # Extract standard web blocks if no business cards found
        if not blocks:
            # Custom selector if provided
            if custom_selector and custom_selector.strip():
                sel = Selector(html)
                selected_items = sel.css(custom_selector.strip())
                for idx, item in enumerate(selected_items):
                    text = (item.text or "").strip()
                    if text:
                        blocks.append({
                            "id": block_id,
                            "type": "custom",
                            "tag": custom_selector.strip(),
                            "title": f"Selector Personalizado #{idx + 1}",
                            "content": text,
                            "url": url
                        })
                        block_id += 1

            # Headings
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
            for heading in headings:
                text = heading.get_text(strip=True)
                if text and len(text) > 2:
                    blocks.append({
                        "id": block_id,
                        "type": "heading",
                        "tag": heading.name,
                        "title": f"Encabezado ({heading.name.upper()})",
                        "content": text,
                        "url": url
                    })
                    block_id += 1

            # Paragraphs
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    blocks.append({
                        "id": block_id,
                        "type": "paragraph",
                        "tag": "p",
                        "title": "Párrafo de Texto",
                        "content": text,
                        "url": url
                    })
                    block_id += 1

            # Links
            extracted_links = set()
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                href = link['href'].strip()
                if href and not href.startswith(('javascript:', '#')):
                    abs_url = urllib.parse.urljoin(url, href)
                    if abs_url not in extracted_links and text:
                        extracted_links.add(abs_url)
                        blocks.append({
                            "id": block_id,
                            "type": "link",
                            "tag": "a",
                            "title": "Enlace Extraído",
                            "content": text,
                            "link_url": abs_url,
                            "url": url
                        })
                        block_id += 1
                        if len(extracted_links) >= 30:
                            break

            # Images
            extracted_imgs = set()
            for img in soup.find_all('img', src=True):
                src = img['src'].strip()
                alt = img.get('alt', '').strip()
                if src and not src.startswith('data:'):
                    abs_src = urllib.parse.urljoin(url, src)
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
                        if len(extracted_imgs) >= 20:
                            break

            # Tables
            tables = soup.find_all('table')
            for t_idx, table in enumerate(tables, 1):
                rows = table.find_all('tr')
                table_data = []
                for row in rows:
                    cols = [c.get_text(strip=True) for c in row.find_all(['th', 'td']) if c.get_text(strip=True)]
                    if cols:
                        table_data.append(" | ".join(cols))
                if table_data:
                    blocks.append({
                        "id": block_id,
                        "type": "table",
                        "tag": "table",
                        "title": f"Tabla de Datos #{t_idx}",
                        "content": "\n".join(table_data),
                        "url": url
                    })
                    block_id += 1

        return {
            "status": "success",
            "url": url,
            "domain": domain,
            "title": title or domain,
            "total_blocks": len(blocks),
            "blocks": blocks
        }
