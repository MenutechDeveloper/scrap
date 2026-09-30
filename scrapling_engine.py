import re
import time
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
    def scrape_url(url: str, custom_selector: str = None, mode: str = "auto", timeout: int = 20) -> dict:
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
        is_google = "google." in domain.lower() or "udm=local" in url or "tbm=lcl" in url or "maps" in domain.lower() or "/maps/" in url

        html = ""
        title = ""
        blocks = []
        block_id = 1

        # Extract search query if present across different Google URL parameters or path
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        search_query = query_params.get('q', [''])[0] or query_params.get('query', [''])[0]
        if not search_query and '/maps/search/' in parsed_url.path:
            match = re.search(r'/maps/search/([^/?#]+)', parsed_url.path)
            if match:
                search_query = urllib.parse.unquote(match.group(1)).replace('+', ' ')

        # Handle Google Search / Local or stealth requests via Playwright Chromium
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

                    # Attempt 1: Try direct Google Search / Local page if it contains udm=local or tbm=lcl
                    cards = []
                    if 'udm=local' in url or 'tbm=lcl' in url:
                        try:
                            page.goto(url, timeout=timeout * 1000, wait_until='domcontentloaded')
                            page.wait_for_timeout(2000)
                            if 'sorry' not in page.url:
                                title = page.title()
                                cards = page.query_selector_all('div.VkpGBb')
                        except Exception:
                            pass

                    # Process direct Google Local business cards if available
                    if cards:
                        for i, card in enumerate(cards):
                            try:
                                name_el = card.query_selector('.OSrA4b, .oSGA3b, [role="heading"], div.dbg0pd')
                                name = name_el.inner_text().strip() if name_el else f"Negocio #{i + 1}"

                                try:
                                    card.click()
                                    page.wait_for_timeout(800)
                                except Exception:
                                    pass

                                detail_panel = page.query_selector('div.xpdopen, div.LUdaP, div[data-attrid*="location"], div#rhs, div.rhs')

                                phone = 'N/A'
                                phone_elem = detail_panel.query_selector('a[href^="tel:"]') if detail_panel else None
                                if not phone_elem:
                                    phone_elem = card.query_selector('a[href^="tel:"]')

                                if phone_elem:
                                    phone = phone_elem.get_attribute('href').replace('tel:', '').strip()
                                elif detail_panel:
                                    panel_text = detail_panel.inner_text()
                                    pm = re.search(r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', panel_text)
                                    if pm:
                                        phone = pm.group(0)

                                website = ''
                                web_elem = None
                                if detail_panel:
                                    web_elem = detail_panel.query_selector('a:has-text("Sitio web"), a:has-text("Website"), a[aria-label*="sitio web" i], a[data-aria-label*="sitio web" i], a.authority-url')
                                if not web_elem:
                                    web_elem = card.query_selector('a:has-text("Sitio web"), a:has-text("Website"), a[aria-label*="sitio web" i], a[data-aria-label*="sitio web" i]')

                                if web_elem:
                                    website = web_elem.get_attribute('href') or ''
                                    if '/url?q=' in website:
                                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(website).query)
                                        website = parsed.get('q', [''])[0]

                                address = 'N/A'
                                if detail_panel:
                                    maps_links = detail_panel.query_selector_all('a[href*="maps.google.com/maps"], a[href*="google.com/maps"], [data-dtype="d3adr"] span, span.LrzI3')
                                    for ml in maps_links:
                                        txt = ml.inner_text().strip()
                                        if txt and any(char.isdigit() for char in txt) and 'denunciar' not in txt.lower():
                                            address = txt
                                            break

                                if address == 'N/A':
                                    card_lines = [line.strip() for line in card.inner_text().split('\n') if line.strip()]
                                    for line in card_lines:
                                        if re.search(r'\d+\s+[A-Za-z0-9\s\.\,\#\-]+', line) and not 'min' in line and not '$' in line:
                                            address = line
                                            break

                                hours = 'N/A'
                                hours_elem = detail_panel.query_selector('div[data-dtype="d3oh"], div.t77a6, span.pJ33ie') if detail_panel else None
                                if not hours_elem:
                                    hours_elem = card.query_selector('div[data-dtype="d3oh"], div.t77a6, span.pJ33ie')

                                if hours_elem:
                                    hours = hours_elem.inner_text().replace('\n', ' ').strip()
                                else:
                                    for line in card.inner_text().split('\n'):
                                        if any(kw in line.lower() for kw in ['abre', 'cierra', 'open', 'closed', '24 horas']):
                                            hours = line.strip()
                                            break

                                if not website and address != 'N/A':
                                    query_str = urllib.parse.quote(f"{name} {address}")
                                    website = f"https://www.google.com/maps/search/?api=1&query={query_str}"

                                card_raw_text = card.inner_text().replace('\n', ' | ')
                                content_str = (
                                    f"Nombre: {name}\n"
                                    f"Dirección: {address}\n"
                                    f"Teléfono: {phone}\n"
                                    f"Website / Link: {website if website else 'N/A'}\n"
                                    f"Horario: {hours}\n\n"
                                    f"Detalles: {card_raw_text}"
                                )

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
                                        "website": website,
                                        "hours": hours
                                    }
                                })
                                block_id += 1
                            except Exception:
                                pass

                    # Attempt 2: Google Maps Search mode for Maps URLs or fallback if direct search failed
                    if not blocks and (is_google or search_query):
                        fallback_query = search_query if search_query else "restaurantes"
                        maps_target_url = url if ("/maps/" in url or "maps.google" in url) else f"https://www.google.com/maps/search/{urllib.parse.quote(fallback_query)}"
                        try:
                            page.goto(maps_target_url, timeout=timeout * 1000, wait_until='domcontentloaded')
                            page.wait_for_timeout(2000)
                            title = page.title()

                            pane = page.query_selector('div[role="feed"]')
                            if pane:
                                for _ in range(3):
                                    page.evaluate('(elem) => elem.scrollBy(0, 1500)', pane)
                                    page.wait_for_timeout(400)

                            place_count = len(page.query_selector_all('div.Nv2PK'))

                            for i in range(place_count):
                                try:
                                    places = page.query_selector_all('div.Nv2PK')
                                    if i >= len(places):
                                        break
                                    place = places[i]

                                    name_el = place.query_selector('div.qBF1Pd, font, div.fontHeadlineSmall')
                                    name = name_el.inner_text().strip() if name_el else f"Negocio #{i + 1}"

                                    card_text = place.inner_text()
                                    lines = [l.strip() for l in card_text.split('\n') if l.strip()]

                                    address = 'N/A'
                                    for line in lines:
                                        if re.search(r'\b\d+\s+[A-Za-z0-9\s\.\,\#\-]+', line) and not 'min' in line and not '$' in line:
                                            address = line
                                            break

                                    hours = 'N/A'
                                    for line in lines:
                                        if any(kw in line.lower() for kw in ['abierto', 'cerrado', 'abre', 'cierra', '24 horas']):
                                            hours = line
                                            break

                                    website = ''
                                    phone = 'N/A'

                                    try:
                                        place.click()
                                        page.wait_for_timeout(800)

                                        phone_el = page.query_selector('button[data-item-id*="phone"]')
                                        if phone_el:
                                            phone = phone_el.inner_text().replace('', '').replace('\n', ' ').strip()

                                        web_el = page.query_selector('a[data-item-id*="authority"]')
                                        if web_el:
                                            website = web_el.get_attribute('href') or ''

                                        addr_el = page.query_selector('button[data-item-id*="address"]')
                                        if addr_el:
                                            full_addr = addr_el.inner_text().replace('', '').replace('\n', ' ').strip()
                                            if full_addr:
                                                address = full_addr

                                        hours_el = page.query_selector('div[data-item-id*="oh"], [aria-label*="Horas" i], [aria-label*="Horario" i]')
                                        if hours_el:
                                            full_hours = hours_el.inner_text().replace('', '').replace('\n', ' ').strip()
                                            if full_hours:
                                                hours = full_hours
                                    except Exception:
                                        pass

                                    if not website and address != 'N/A':
                                        q_str = urllib.parse.quote(f"{name} {address}")
                                        website = f"https://www.google.com/maps/search/?api=1&query={q_str}"

                                    content_str = (
                                        f"Nombre: {name}\n"
                                        f"Dirección: {address}\n"
                                        f"Teléfono: {phone}\n"
                                        f"Website / Link: {website if website else 'N/A'}\n"
                                        f"Horario: {hours}\n\n"
                                        f"Detalles: {card_text.replace('\n', ' | ')}"
                                    )

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
                                            "website": website,
                                            "hours": hours
                                        }
                                    })
                                    block_id += 1
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    html = page.content()
                    browser.close()
            except Exception:
                pass

        if not blocks and not html:
            try:
                page = Fetcher.get(url, timeout=timeout)
                html = getattr(page, 'html_content', '') or getattr(page, 'text', '')
                title = title or (page.css("title::text").get() or "Sin título").strip()
            except Exception:
                pass

        soup = BeautifulSoup(html, 'html.parser') if html else None

        # Fallback extraction from soup if Playwright didn't catch business cards
        if not blocks and soup:
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

                    address = 'N/A'
                    for part in parts:
                        if re.search(r'\d+\s+[A-Za-z0-9\s\.\,\#\-]+(St|Ave|Dr|Blvd|Rd|Way|Ln|Ct|Ste|Suite|Plaza|Pkwy)', part, re.IGNORECASE):
                            address = part
                            break

                    phone = 'N/A'
                    phone_match = re.search(r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', full_text)
                    if phone_match:
                        phone = phone_match.group(0)

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
        if not blocks and soup:
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
