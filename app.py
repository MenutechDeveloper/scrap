import io
import csv
import json
from flask import Flask, render_template, request, jsonify, send_file, Response
from fpdf import FPDF
from scrapling_engine import ScrapingEngine

app = Flask(__name__)

# Temporary in-memory cache for export generation
LATEST_SCRAPE_RESULTS = {}

class PDFExport(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(249, 115, 22) # MENUTECH Brand Accent Color
        self.cell(0, 10, 'MENUTECH - Reporte de Extracción', border=False, new_x='LMARGIN', new_y='NEXT', align='L')
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(148, 163, 184)
        self.cell(0, 5, 'Generado con Extractor Web MENUTECH', border=False, new_x='LMARGIN', new_y='NEXT', align='L')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Página {self.page_no()}', border=False, new_x='LMARGIN', new_y='NEXT', align='C')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    custom_selector = data.get('selector', '').strip()
    mode = data.get('mode', 'auto')

    if not url:
        return jsonify({"status": "error", "message": "Por favor proporciona una URL válida."}), 400

    try:
        results = ScrapingEngine.scrape_url(url, custom_selector=custom_selector, mode=mode)
        global LATEST_SCRAPE_RESULTS
        LATEST_SCRAPE_RESULTS = results
        return jsonify(results)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error durante el scraping: {str(e)}"}), 500


@app.route('/export/<fmt>', methods=['GET', 'POST'])
def export_file(fmt):
    global LATEST_SCRAPE_RESULTS

    if request.method == 'POST':
        data = request.get_json() or {}
    else:
        data = LATEST_SCRAPE_RESULTS

    if not data or 'blocks' not in data:
        return jsonify({"status": "error", "message": "No hay datos disponibles para exportar."}), 400

    url = data.get('url', 'desconocido')
    domain = data.get('domain', 'sitio')
    blocks = data.get('blocks', [])

    # Export TXT
    if fmt == 'txt':
        lines = [
            "==================================================",
            f"  MENUTECH - RESULTADOS DE SCRAPING",
            "==================================================",
            f"URL: {url}",
            f"Dominio: {domain}",
            f"Total de Bloques: {len(blocks)}",
            "--------------------------------------------------\n"
        ]
        for b in blocks:
            lines.append(f"[{b['id']}] {b['title'].upper()}")
            lines.append(f"Tipo: {b['type']} | Etiqueta: {b.get('tag', 'N/A')}")
            lines.append(f"Contenido:\n{b['content']}")
            if b.get('link_url'):
                lines.append(f"Enlace: {b['link_url']}")
            if b.get('img_src'):
                lines.append(f"Imagen SRC: {b['img_src']}")
            lines.append("\n" + "-"*40 + "\n")

        output = "\n".join(lines)
        return Response(
            output,
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment;filename=menutech_{domain}.txt"}
        )

    # Export CSV / Google Sheets
    elif fmt in ['csv', 'sheets']:
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(["ID", "Tipo", "Etiqueta", "Título", "Contenido", "URL Enlace / Imagen", "URL Origen"])
        for b in blocks:
            extra_url = b.get('link_url') or b.get('img_src') or ''
            cw.writerow([
                b['id'],
                b['type'],
                b.get('tag', ''),
                b['title'],
                b['content'],
                extra_url,
                b.get('url', url)
            ])

        output = si.getvalue()
        filename = f"menutech_google_sheets_{domain}.csv" if fmt == 'sheets' else f"menutech_{domain}.csv"
        return Response(
            output,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    # Export JSON
    elif fmt == 'json':
        output = json.dumps(data, indent=2, ensure_ascii=False)
        return Response(
            output,
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment;filename=menutech_{domain}.json"}
        )

    # Export PDF
    elif fmt == 'pdf':
        pdf = PDFExport()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"URL extraída: {url[:70]}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Total de elementos estructurados: {len(blocks)}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        for b in blocks:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_fill_color(241, 245, 249)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 7, f" #{b['id']} - {b['title']} [{b['type']}]", fill=True, new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(51, 65, 85)
            content_text = b['content'].encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, content_text)

            if b.get('link_url'):
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(249, 115, 22)
                pdf.cell(0, 5, f"Link: {b['link_url'][:80]}", new_x="LMARGIN", new_y="NEXT")

            pdf.ln(3)

        pdf_bytes = io.BytesIO(pdf.output())
        return send_file(
            pdf_bytes,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"menutech_{domain}.pdf"
        )

    # Export SVG Summary Card
    elif fmt == 'svg':
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 {250 + len(blocks)*40}" width="800" height="{250 + len(blocks)*40}">
  <style>
    .bg {{ fill: #0f172a; }}
    .card {{ fill: #1e293b; rx: 12px; stroke: #334155; stroke-width: 1; }}
    .header-title {{ fill: #ffffff; font-family: sans-serif; font-weight: bold; font-size: 22px; }}
    .subtitle {{ fill: #94a3b8; font-family: sans-serif; font-size: 13px; }}
    .badge {{ fill: #f97316; rx: 4px; }}
    .badge-text {{ fill: #ffffff; font-family: sans-serif; font-weight: bold; font-size: 11px; }}
    .block-title {{ fill: #f97316; font-family: sans-serif; font-weight: bold; font-size: 14px; }}
    .block-text {{ fill: #cbd5e1; font-family: sans-serif; font-size: 12px; }}
  </style>
  <rect width="100%" height="100%" class="bg" />

  <!-- Header Card -->
  <rect x="20" y="20" width="760" height="100" class="card" />
  <text x="40" y="55" class="header-title">MENUTECH - Resumen de Extracción</text>
  <text x="40" y="80" class="subtitle">URL: {url[:70]}</text>
  <text x="40" y="98" class="subtitle">Total Bloques: {len(blocks)} | MENUTECH Web Engine</text>

  <!-- Blocks -->
'''
        y_offset = 140
        for b in blocks[:15]:
            clean_content = b['content'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')[:80]
            svg_content += f'''
  <rect x="20" y="{y_offset}" width="760" height="35" class="card" />
  <text x="35" y="{y_offset + 22}" class="block-title">#{b['id']} [{b['type'].upper()}]</text>
  <text x="160" y="{y_offset + 22}" class="block-text">{clean_content}</text>
'''
            y_offset += 42

        svg_content += '\n</svg>'
        return Response(
            svg_content,
            mimetype="image/svg+xml",
            headers={"Content-Disposition": f"attachment;filename=menutech_{domain}.svg"}
        )

    return jsonify({"status": "error", "message": "Formato no soportado."}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
