import sys
import urllib.request
import urllib.parse
import sqlite3
import asyncio
from html.parser import HTMLParser
from typing import Set, List
from re import match
import urllib.error


class WikiParser(HTMLParser):
    """
    Парсер HTML-страниц, извлекающий ссылки на статьи Википедии
    """

    def __init__(self):
        super().__init__()
        self.links: Set[str] = set()

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str]]) -> None:
        """
        Обрабатывает теги <a>, извлекая значения из аттрибутов href, которые являются ссылками на статьи
        """
        if tag == "a":
            for attr in attrs:
                if (
                    attr[0] == "href"
                    and attr[1].startswith("/wiki")
                    and ":" not in attr[1]
                ):
                    self.links.add(attr[1])


async def get_page(url: str) -> str:
    """
    Загружает содержимое страницы по указанному URL
    """
    try:
        url = urllib.parse.quote(url, safe=":/?&=")
        await asyncio.sleep(0.3)
        with urllib.request.urlopen(url) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"Ошибка HTTP {e.code} для URL: {url}")
        return ""
    except urllib.error.URLError as e:
        print(f"Ошибка URL: {e.reason} для URL: {url}")
        return ""


def save_to_db(db_name: str, urls: Set[str]) -> None:
    """
    Сохраняет ссылки в БД, используя режим WAL для избежания ошибок блокировки
    """
    with sqlite3.connect(db_name) as connection:
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE
            )
        """
        )
        for url in urls:
            cursor.execute("INSERT OR IGNORE INTO Urls (url) VALUES (?)", (url,))
        connection.commit()


async def get_links_from_page(url: str, base_url: str) -> Set[str]:
    """
    Извлекает ссылки на статьи Википедии с указанной страницы
    """
    html = await get_page(url)
    if not html:
        return set()  # Если страница не загружена, возвращаем пустое множество
    parser = WikiParser()
    parser.feed(html)
    return {
        urllib.parse.urljoin(base_url, urllib.parse.unquote(link))
        for link in parser.links
    }


async def recursive_url_scrap(
    base_url: str, current_url: str, db_name: str, depth: int, visited: Set[str]
) -> None:
    """
    Рекурсивно обходит страницы Википедии до заданной глубины, сохраняя ссылки в БД
    """
    if depth == 0 or current_url in visited:
        return

    visited.add(current_url)

    try:
        links = await get_links_from_page(current_url, base_url)
        save_to_db(db_name, links)
        for link in links:
            await recursive_url_scrap(base_url, link, db_name, depth - 1, visited)
    except Exception as e:
        print(f"Ошибка обработки URL {current_url} на глубине {depth}: {e}")


async def shutdown(loop):
    """
    Завершает все асинхронные задачи и останавливает цикл событий
    """
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


async def main() -> None:
    try:
        if len(sys.argv) < 2:
            print(f"Использование: python {sys.argv[0]} <url статьи Википедии>")
            sys.exit(1)

        current_url = sys.argv[1]
        pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        if match(pattern, current_url) is None:
            print("Введите валидный URL")
            sys.exit(1)

        parse_url = urllib.parse.urlparse(current_url)
        base_url = parse_url.scheme + "://" + parse_url.netloc
        db_name = "url_storage.db"

        depth = 6  # Глубина поиска

        # Очистка базы данных перед запуском
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS Urls")
            conn.commit()

        # Запуск рекурсивного обхода
        await recursive_url_scrap(base_url, current_url, db_name, depth, set())
    finally:
        loop = asyncio.get_running_loop()
        await shutdown(loop)


if __name__ == "__main__":
    asyncio.run(main())
