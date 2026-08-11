import requests
import json
import re
import xml.etree.ElementTree as ET

print("RBC PARSER")
NEWS_URL = 'https://chr.rbc.ru/'
CBR_URL = 'https://www.cbr.ru/scripts/XML_daily.asp'
OUTPUT_FILE = 'result.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}

def fetch_url(url, timeout=15):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.encoding = 'utf-8'
    return response.text

def parse_news(html):
    news_list = []

    pattern = r'<a[^>]*class="[^"]*news-line-link[^"]*"[^>]*>.*?<span[^>]*class="[^"]*news-line-title[^"]*"[^>]*>(.*?)<\/span>'
    matches = re.findall(pattern, html, re.DOTALL)

    seen = set()
    for title in matches:
        title = re.sub(r'<[^>]*>', '', title)
        title = re.sub(r'^\s+|\s+$', '', title)
        title = re.sub(r'\s+', ' ', title)

        if len(title) < 15:
            continue
        if title in seen:
            continue
        if re.search(r'Реклама', title, re.I):
            continue
        if re.match(r'^[\d.,\s]+$', title):
            continue

        seen.add(title)
        news_list.append(title)
        if len(news_list) >= 10:
            break

    return news_list


def parse_currencies(xml_text):
    currencies = {}
    needed_codes = {'USD', 'EUR', 'CNY', 'GBP', 'JPY'}

    root = ET.fromstring(xml_text)

    for valute in root.findall('Valute'):
        code_elem = valute.find('CharCode')
        value_elem = valute.find('Value')

        if code_elem is None or value_elem is None:
            continue

        code = code_elem.text
        if code not in needed_codes:
            continue

        value = value_elem.text.replace(',', '.')
        currencies[code] = value

    return currencies


def main():
    print("Loading news from chr.rbc.ru")
    html = fetch_url(NEWS_URL)
    if len(html) < 1000:
        print("Error")
        return
    print(f"  Loaded {len(html)} bytes\n")

    news = parse_news(html)
    print("Loading currency rates from cbr.ru")
    xml_text = fetch_url(CBR_URL)
    if len(xml_text) < 100:
        print("Error")
        return
    print(f"  Loaded {len(xml_text)} bytes")

    currencies = parse_currencies(xml_text)
    result = {
        "currencies": currencies,
        "news": news
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved to {OUTPUT_FILE}")
    print("CURRENCIES:")
    for code, value in sorted(currencies.items()):
        print(f"  {code:<6} {value:>10} RUB")

    print(f"\nNews:")
    for i, title in enumerate(news, 1):
        print(f"{i:>2}. {title}")

    print(f"\nFull JSON: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()