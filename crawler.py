import argparse
import csv
import json
import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from jsonschema import validate, ValidationError
try:
    from playwright.sync_api import (
        Error as PlaywrightError,
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except ImportError:  # pragma: no cover - handled gracefully for environments without Playwright
    PlaywrightError = PlaywrightTimeoutError = None  # type: ignore
    sync_playwright = None  # type: ignore


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


class BikeCrawler:
    """Crawler for extracting bike data from 99spokes."""

    def __init__(self, base_url: str, pagination_param: str, start_page: int = 1,
                 end_page: Optional[int] = None, schema: Optional[Dict[str, Any]] = None,
                 use_browser: bool = True, browser_type: str = 'chromium', timeout: int = 15) -> None:
        self.base_url = base_url.rstrip('/')
        self.pagination_param = pagination_param
        self.start_page = start_page
        self.end_page = end_page
        self.schema = schema
        self.use_browser = use_browser
        self.browser_type = browser_type
        self.timeout = timeout
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._blocked_resource_types = {'image', 'media', 'font', 'stylesheet'}

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page and return its text."""
        if self.use_browser:
            try:
                page = self._ensure_browser_page()
                logger.debug("Navigating to URL via browser: %s", url)
                page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)
                page.wait_for_timeout(500)
                return page.content()
            except Exception as exc:  # pragma: no cover - depends on browser runtime
                logger.error("Browser fetch failed for %s: %s", url, exc)
            return None
        try:
            logger.debug("Fetching URL: %s", url)
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", url, exc)
            return None

    def _ensure_browser_page(self):
        if self._page:
            return self._page
        if not self._playwright:
            if not sync_playwright:
                raise RuntimeError('Playwright is not installed. Install the "playwright" package to enable browser crawling.')
            self._playwright = sync_playwright().start()
        launcher = getattr(self._playwright, self.browser_type, None)
        if launcher is None:
            raise ValueError(f"Unsupported browser type: {self.browser_type}")
        self._browser = launcher.launch(headless=False)
        self._context = self._browser.new_context(java_script_enabled=True)
        self._context.route('**/*', self._route_request)
        self._page = self._context.new_page()
        return self._page

    def _route_request(self, route, request) -> None:
        if request.resource_type in self._blocked_resource_types:
            route.abort()
        else:
            route.continue_()

    def close(self) -> None:
        if self._page:
            self._page.close()
            self._page = None
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def parse_price(self, text: str) -> Optional[float]:
        """Parse a price string to float."""
        if not text:
            return None
        text = text.replace('.', '').replace(',', '.').strip()
        digits = ''.join(ch for ch in text if ch.isdigit() or ch == '.')
        try:
            return float(digits)
        except ValueError:
            return None

    def parse_page(self, html: str) -> List[Dict[str, Any]]:
        """Parse HTML page and extract bike entries."""
        soup = BeautifulSoup(html, 'html.parser')
        bikes: List[Dict[str, Any]] = []

        # Try JSON-LD first
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
            except Exception:
                continue
            entries = data if isinstance(data, list) else [data]
            for item in entries:
                if item.get('@type', '').lower() in {'product', 'bike', 'bicycle'}:
                    offers = item.get('offers') or {}
                    price = self.parse_price(str(offers.get('price')))
                    availability = offers.get('availability', '')
                    bikes.append({
                        'name': item.get('name'),
                        'price': price,
                        'availability': availability,
                        'image_url': item.get('image'),
                        'detail_url': item.get('url'),
                        'specs': item.get('additionalProperty') or {}
                    })

        # Fallback: simple DOM parsing
        for card in soup.select('a[href*="/bikes/"]'):
            name = card.get_text(strip=True)
            href = card.get('href')
            detail_url = urljoin(self.base_url, href) if href else None
            image = card.find('img')
            image_url = urljoin(self.base_url, image['src']) if image and image.get('src') else None
            price_el = card.find(class_='price')
            price = self.parse_price(price_el.get_text() if price_el else '')
            if name and detail_url:
                bikes.append({
                    'name': name,
                    'price': price,
                    'availability': '',
                    'image_url': image_url,
                    'detail_url': detail_url,
                    'specs': {}
                })
        return bikes

    def is_valid(self, data: Dict[str, Any]) -> bool:
        """Validate data against schema."""
        if not self.schema:
            return True
        try:
            validate(instance=data, schema=self.schema)
            return True
        except ValidationError as exc:
            logger.warning("Validation failed for %s: %s", data.get('detail_url'), exc)
            return False

    def crawl(self) -> List[Dict[str, Any]]:
        """Run the crawling process."""
        all_bikes: List[Dict[str, Any]] = []
        page_num = self.start_page
        try:
            while True:
                if page_num == self.start_page:
                    url = self.base_url
                else:
                    url = self.base_url + self.pagination_param.format(page_num=page_num)
                html = self.fetch_page(url)
                if not html:
                    break
                bikes = self.parse_page(html)
                for bike in bikes:
                    if self.is_valid(bike):
                        all_bikes.append(bike)
                logger.info("Page %d: %d bikes", page_num, len(bikes))
                page_num += 1
                if self.end_page and page_num > self.end_page:
                    break
                if not bikes:
                    break
        finally:
            if self.use_browser:
                self.close()
        return all_bikes


def save_json(data: List[Dict[str, Any]], path: str) -> None:
    """Save list of bikes to JSON."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_csv(data: List[Dict[str, Any]], path: str) -> None:
    """Save list of bikes to CSV."""
    if not data:
        return
    fieldnames = list(data[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)


def load_json(path: str) -> Any:
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main() -> None:
    """Entry point for the crawler."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_manifest = os.path.join(script_dir, 'specs', 'manifest.json')
    default_schema = os.path.join(script_dir, 'specs', 'output_schema.json')
    default_output = os.path.join(script_dir, 'output')

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--manifest',
        default=default_manifest,
        help='Path to manifest.json (defaults to specs/manifest.json)',
    )
    parser.add_argument(
        '--schema',
        default=default_schema,
        help='Path to output_schema.json (defaults to specs/output_schema.json)',
    )
    parser.add_argument(
        '--output',
        default=default_output,
        help='Output directory (defaults to ./output)',
    )
    args = parser.parse_args()

    if not os.path.isfile(args.manifest):
        parser.error(f"Manifest file not found: {args.manifest}")
    if not os.path.isfile(args.schema):
        parser.error(f"Schema file not found: {args.schema}")

    manifest = load_json(args.manifest)
    schema = load_json(args.schema)

    crawler = BikeCrawler(
        base_url=manifest['base_url'],
        pagination_param=manifest['pagination_param'],
        start_page=manifest.get('start_page', 1),
        end_page=manifest.get('end_page'),
        schema=schema,
        use_browser=manifest.get('use_browser', True),
        browser_type=manifest.get('browser_type', 'chromium'),
        timeout=manifest.get('timeout', 15),
    )

    bikes = crawler.crawl()
    os.makedirs(args.output, exist_ok=True)
    json_path = os.path.join(args.output, 'bikes.json')
    csv_path = os.path.join(args.output, 'bikes.csv')
    save_json(bikes, json_path)
    save_csv(bikes, csv_path)
    logger.info("Saved %d bikes", len(bikes))


if __name__ == '__main__':
    main()
