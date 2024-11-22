import unittest
import sqlite3
from unittest.mock import patch, MagicMock
from main import WikiParser, get_page, save_to_db, get_links_from_page, recursive_url_scrap


class TestWikiParser(unittest.TestCase):
    def setUp(self):
        self.parser = WikiParser()

    def test_handle_valid_wiki_link(self):
        """Тест обработки правильной ссылки на статью википедии"""
        self.parser.feed('<a href="/wiki/Python">Python</a>')
        self.assertEqual(self.parser.links, {'/wiki/Python'})

    def test_handle_invalid_wiki_link(self):
        """Тест обработки неправильной ссылки"""
        self.parser.feed('<a href="/wiki/Python:History">Python History</a>')
        self.assertEqual(self.parser.links, set())

    def test_handle_non_wiki_link(self):
        """Тест обработки ссылки не на википедию"""
        self.parser.feed('<a href="https://python.org">Python</a>')
        self.assertEqual(self.parser.links, set())


class TestDatabaseOperations(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_db.db"

    def test_save_to_db(self):
        """Тест сохранения URL в базу данных"""
        urls = {"https://en.wikipedia.org/wiki/Test1", "https://en.wikipedia.org/wiki/Test2"}
        save_to_db(self.db_name, urls)

        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url FROM Urls")
            saved_urls = {row[0] for row in cursor.fetchall()}

        self.assertEqual(urls, saved_urls)

    def tearDown(self):
        """Очистка после тестов"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS Urls")


class TestAsyncOperations(unittest.IsolatedAsyncioTestCase):
    async def test_get_page(self):
        """Тест получения страницы"""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b"Test content"
            mock_urlopen.return_value.__enter__.return_value = mock_response

            content = await get_page("https://en.wikipedia.org")
            self.assertEqual(content, "Test content")

    async def test_get_links_from_page(self):
        """Тест получения ссылок со страницы"""
        test_html = '<a href="/wiki/Test">Test</a>'
        with patch('main.get_page') as mock_get_page:
            mock_get_page.return_value = test_html
            base_url = "https://en.wikipedia.org"
            links = await get_links_from_page(base_url + "/wiki/Start", base_url)
            self.assertEqual(links, {base_url + "/wiki/Test"})

    async def test_recursive_url_scrap(self):
        """Тест рекурсивного обхода страниц"""
        with patch('main.get_links_from_page') as mock_get_links:
            mock_get_links.return_value = {
                "https://en.wikipedia.org/wiki/Test1",
                "https://en.wikipedia.org/wiki/Test2"
            }

            base_url = "https://en.wikipedia.org"
            start_url = base_url + "/wiki/Start"
            db_name = "test_db.db"
            visited = set()

            await recursive_url_scrap(base_url, start_url, db_name, 1, visited)

            self.assertIn(start_url, visited)
            mock_get_links.assert_called_once()


if __name__ == '__main__':
    unittest.main()
