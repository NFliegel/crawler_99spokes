import requests
from bs4 import BeautifulSoup

class SpokesCrawler:
    BASE_URL = "https://www.99spokes.com"
    BIKES_PATH = "/bikes"

    def __init__(self):
        self.session = requests.Session()

    def _get(self, url):
        response = self.session.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')

    def get_years(self):
        soup = self._get(self.BASE_URL + self.BIKES_PATH)
        year_links = soup.select('a[href^="/bikes/"]')
        years = [link.get('href').split('/')[-1] for link in year_links if link.get('href').split('/')[-1].isdigit()]
        return years

    def get_brands(self, year):
        soup = self._get(f"{self.BASE_URL}{self.BIKES_PATH}/{year}")
        brand_links = soup.select('a[href^="/bikes/"]')
        brands = [link.get('href').split('/')[-1] for link in brand_links]
        return brands

    def get_models(self, year, brand):
        soup = self._get(f"{self.BASE_URL}{self.BIKES_PATH}/{year}/{brand}")
        model_links = soup.select('a[href^="/bikes/"]')
        models = [link.get('href').split('/')[-1] for link in model_links]
        return models

    def crawl(self):
        all_data = {}
        for year in self.get_years():
            all_data[year] = {}
            for brand in self.get_brands(year):
                all_data[year][brand] = self.get_models(year, brand)
        return all_data

if __name__ == "__main__":
    crawler = SpokesCrawler()
    data = crawler.crawl()
    print(data)
