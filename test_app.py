import json
import unittest
from app import app

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_scrape_endpoint(self):
        response = self.client.post(
            '/scrape',
            data=json.dumps({'url': 'https://example.com'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('blocks', data)
        self.assertGreater(data['total_blocks'], 0)

    def test_export_txt(self):
        self.client.post('/scrape', data=json.dumps({'url': 'https://example.com'}), content_type='application/json')
        res = self.client.get('/export/txt')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/plain')
        self.assertIn(b'MENUTECH', res.data)

    def test_export_csv_and_sheets(self):
        self.client.post('/scrape', data=json.dumps({'url': 'https://example.com'}), content_type='application/json')
        res_csv = self.client.get('/export/csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, 'text/csv')

        res_sheets = self.client.get('/export/sheets')
        self.assertEqual(res_sheets.status_code, 200)
        self.assertIn(b'ID,Tipo,Etiqueta', res_sheets.data)

    def test_export_pdf(self):
        self.client.post('/scrape', data=json.dumps({'url': 'https://example.com'}), content_type='application/json')
        res = self.client.get('/export/pdf')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'application/pdf')

    def test_export_svg(self):
        self.client.post('/scrape', data=json.dumps({'url': 'https://example.com'}), content_type='application/json')
        res = self.client.get('/export/svg')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'image/svg+xml')
        self.assertIn(b'<svg', res.data)

    def test_export_json(self):
        self.client.post('/scrape', data=json.dumps({'url': 'https://example.com'}), content_type='application/json')
        res = self.client.get('/export/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'application/json')

if __name__ == '__main__':
    unittest.main()
