import requests
import json
import re
import xml.etree.ElementTree as ET
import os
import smtplib
from email.message import EmailMessage

print("ПАРСЕР НОВОСТЕЙ И КУРСОВ ВАЛЮТ")

NEWS_URL = 'https://chr.rbc.ru/'
CBR_URL = 'https://www.cbr.ru/scripts/XML_daily.asp'
OUTPUT_FILE = 'result.json'

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 465

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


def fetch_url(url, timeout=15):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_news(html):
    news_list = []

    pattern = (
        r'<a[^>]*class="[^"]*news-line-link[^"]*"[^>]*>'
        r'.*?<span[^>]*class="[^"]*news-line-title[^"]*"[^>]*>'
        r'(.*?)</span>'
    )

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
        nominal_elem = valute.find('Nominal')

        if code_elem is None or value_elem is None:
            continue

        code = code_elem.text

        if code not in needed_codes:
            continue

        value = value_elem.text.replace(',', '.')

        if nominal_elem is not None:
            nominal = int(nominal_elem.text)

            if nominal > 1:
                value = str(float(value) / nominal)

        currencies[code] = value

    return currencies


def send_email():
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        raise ValueError(
            "Не настроены переменные EMAIL_SENDER, "
            "EMAIL_PASSWORD или EMAIL_RECEIVER."
        )

    with open(OUTPUT_FILE, "rb") as file:
        attachment = file.read()

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)

        msg = EmailMessage()
        msg["Subject"] = "Ежедневный отчёт: новости и курсы валют"
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER

        msg.set_content(
            "Здравствуйте, Сергей Дмитриевич!\n\n"
            "Во вложении находится файл result.json "
            "с актуальными новостями и курсами валют."
        )

        msg.add_attachment(
            attachment,
            maintype="application",
            subtype="json",
            filename=OUTPUT_FILE
        )

        server.send_message(msg)

        print(
            f"Почтовый сервер принял отчёт для отправки: "
            f"{msg['To']}"
        )

        notification = EmailMessage()
        notification["Subject"] = "Уведомление: отчёт отправлен"
        notification["From"] = EMAIL_SENDER
        notification["To"] = EMAIL_SENDER

        notification.set_content(
            "Почтовый сервер принял отчёт result.json "
            f"для отправки получателю: {msg['To']}.\n\n"
        )

        try:
            server.send_message(notification)
            print(
                f"Уведомление об отправке направлено на: "
                f"{EMAIL_SENDER}"
            )
        except (smtplib.SMTPException, OSError) as e:
            print(
                "Не удалось отправить уведомление об успехе: "
                f"{e}"
            )


def main():
    print("\nЗагрузка новостей с сайта РБК")

    try:
        html = fetch_url(NEWS_URL)
    except requests.RequestException as e:
        print(f"Ошибка при загрузке новостей: {e}")
        return

    if len(html) < 1000:
        print("Ошибка: полученный HTML-документ слишком короткий.")
        return

    print(f"Загружено HTML-данных: {len(html)} байт")

    news = parse_news(html)
    print(f"Найдено новостей: {len(news)}")

    print("\nЗагрузка курсов валют с сайта ЦБ РФ")

    try:
        xml_text = fetch_url(CBR_URL)
    except requests.RequestException as e:
        print(f"Ошибка при загрузке курсов валют: {e}")
        return

    if len(xml_text) < 100:
        print("Ошибка: полученный XML-документ слишком короткий.")
        return

    print(f"Загружено XML-данных: {len(xml_text)} байт")

    try:
        currencies = parse_currencies(xml_text)
    except (ET.ParseError, ValueError, AttributeError) as e:
        print(f"Ошибка при обработке курсов валют: {e}")
        return

    if not currencies:
        print("Ошибка: не удалось получить курсы нужных валют.")
        return

    result = {
        "currencies": currencies,
        "news": news
    }

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"Ошибка при сохранении файла {OUTPUT_FILE}: {e}")
        return

    print(f"\nДанные успешно сохранены в файл: {OUTPUT_FILE}")

    print("\nОтправка отчёта по электронной почте")

    try:
        send_email()
    except (smtplib.SMTPException, OSError, ValueError) as e:
        print(f"Ошибка при отправке отчёта: {e}")

    print("\nКУРСЫ ВАЛЮТ:")

    for code, value in sorted(currencies.items()):
        print(f"  {code:<6} {value:>10} руб.")

    print("\nПОСЛЕДНИЕ НОВОСТИ:")

    if news:
        for i, title in enumerate(news, 1):
            print(f"{i:>2}. {title}")
    else:
        print("Новости не найдены.")

    print(f"\nПолный отчёт сохранён в файле: {OUTPUT_FILE}")
    print("\nРабота парсера завершена.")


if __name__ == '__main__':
    main()