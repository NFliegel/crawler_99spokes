import json
from pathlib import Path

import pytest
import requests
import requests_mock

from crawler import BikeCrawler, save_json, save_csv


@pytest.fixture()
def sample_html():
    return """
    <html>
    <head>
    <script type="application/ld+json">
    {
      "@context": "http://schema.org",
      "@type": "Product",
      "name": "Bike A",
      "image": "http://example.com/bike-a.jpg",
      "url": "http://example.com/bike-a",
      "offers": {"price": "1000", "availability": "InStock"}
    }
    </script>
    </head>
    <body></body>
    </html>
    """


def test_parse_page(sample_html):
    crawler = BikeCrawler(base_url="http://example.com", pagination_param="?page={page_num}", use_browser=False)
    bikes = crawler.parse_page(sample_html)
    assert len(bikes) == 1
    bike = bikes[0]
    assert bike['name'] == 'Bike A'
    assert bike['price'] == 1000.0
    assert bike['availability'] == 'InStock'


def test_crawl(tmp_path, sample_html):
    manifest = {
        'base_url': 'http://example.com',
        'pagination_param': '?page={page_num}',
        'start_page': 1,
        'end_page': 1
    }
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "price": {"type": "number"},
            "availability": {"type": "string"},
            "detail_url": {"type": "string"}
        },
        "required": ["name", "price", "availability"]
    }
    with requests_mock.Mocker() as m:
        m.get('http://example.com', text=sample_html)
        crawler = BikeCrawler(base_url=manifest['base_url'], pagination_param=manifest['pagination_param'],
                              start_page=1, end_page=1, schema=schema, use_browser=False)
        bikes = crawler.crawl()
        assert len(bikes) == 1

        json_path = tmp_path / 'bikes.json'
        csv_path = tmp_path / 'bikes.csv'
        save_json(bikes, json_path)
        save_csv(bikes, csv_path)

        assert json_path.exists() and csv_path.exists()
        data = json.loads(json_path.read_text())
        assert data[0]['name'] == 'Bike A'
