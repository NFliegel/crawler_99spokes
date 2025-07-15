# crawler_99spokes

This repository contains a simple crawler that fetches bike models from 99spokes.com. It traverses the site by year, brand, and model to gather information.

## Usage

1. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the crawler:
   ```bash
   python crawler.py
   ```

Note: Network access is required to fetch data from the website. The script uses `requests` and `BeautifulSoup` to parse the pages.
