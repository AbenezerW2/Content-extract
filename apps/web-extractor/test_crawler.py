import unittest
from unittest.mock import Mock, patch

from crawler import (
    CrawlerError,
    Page,
    chapter_urls,
    crawl_site,
    extract,
    looks_like_verification_page,
    named_output_path,
    render_markdown,
    render_html,
    render_text,
    robots_allows,
    same_site_links,
    suggested_page_name,
    validate_public_url,
)


class ExtractTests(unittest.TestCase):
    def test_extracts_common_content(self):
        html = """<html><head><title> Demo </title><meta name="description" content="Example"></head>
        <body><h1>Hello world</h1><a href="/about">About</a>
        <img src="photo.jpg" alt="Photo"><table><tr><th>A</th></tr><tr><td>1</td></tr></table>
        <script>secret()</script></body></html>"""
        data = extract(Page("https://example.com", "https://example.com/path", 200, "text/html", html))
        self.assertEqual(data["title"], "Demo")
        self.assertEqual(data["headings"], [{"level": 1, "text": "Hello world"}])
        self.assertEqual(data["links"][0]["url"], "https://example.com/about")
        self.assertEqual(data["images"][0]["url"], "https://example.com/photo.jpg")
        self.assertEqual(data["tables"], [[['A'], ['1']]])
        self.assertNotIn("secret", data["text"])

    def test_rejects_non_http_and_credentials(self):
        for url in ("file:///etc/passwd", "https://user:pass@example.com"):
            with self.assertRaises(CrawlerError):
                validate_public_url(url)

    @patch("crawler.validate_public_url")
    @patch("crawler.requests.get")
    def test_robots_405_allows_fetch(self, mock_get, _mock_validate):
        mock_get.return_value = Mock(status_code=405)
        self.assertTrue(robots_allows("https://example.com/page", 5))

    @patch("crawler.validate_public_url")
    @patch("crawler.requests.get")
    def test_robots_403_remains_blocked(self, mock_get, _mock_validate):
        mock_get.return_value = Mock(status_code=403)
        self.assertFalse(robots_allows("https://example.com/page", 5))

    def test_builds_safe_named_output_path(self):
        path = named_output_path("PHL 218 / Chapter 7", "outputs")
        self.assertEqual(str(path), "outputs/PHL_218_Chapter_7.json")

    def test_named_output_accepts_json_extension(self):
        path = named_output_path("week-1.json", "study")
        self.assertEqual(str(path), "study/week-1.json")

    def test_named_output_uses_format_extension(self):
        self.assertEqual(
            str(named_output_path("PHL 218 - Chapter 7.json", "outputs", "markdown")),
            "outputs/PHL_218_-_Chapter_7.md",
        )
        self.assertEqual(
            str(named_output_path("Visual notes.md", "outputs", "html")),
            "outputs/Visual_notes.html",
        )

    def test_rejects_empty_named_output(self):
        with self.assertRaises(CrawlerError):
            named_output_path("...", "outputs")

    def test_detects_human_verification_page(self):
        page = Page(
            "https://example.com",
            "https://example.com",
            405,
            "text/html",
            "<title>Human Verification</title><h1>Let's confirm you are human</h1>",
        )
        self.assertTrue(looks_like_verification_page(page))

    def test_accepts_normal_rendered_page(self):
        page = Page(
            "https://example.com",
            "https://example.com",
            200,
            "text/html",
            "<title>Chapter 7</title><h1>Ethics and care</h1>",
        )
        self.assertFalse(looks_like_verification_page(page))

    def test_accepts_real_page_after_initial_405(self):
        page = Page(
            "https://example.com",
            "https://example.com/chapter",
            405,
            "text/html (rendered)",
            "<title>Chapter 7</title><h1>Ethics and care</h1><p>Study content</p>",
        )
        self.assertFalse(looks_like_verification_page(page))

    def test_renders_study_formats(self):
        data = {
            "title": "Chapter 7",
            "final_url": "https://example.com/ch7",
            "content_blocks": [
                {"type": "heading", "level": 2, "text": "Key Terms"},
                {"type": "paragraph", "text": "A useful definition."},
                {"type": "list_item", "text": "First consideration"},
            ],
        }
        markdown = render_markdown(data)
        text = render_text(data)
        self.assertIn("### Key Terms", markdown)
        self.assertIn("- First consideration", markdown)
        self.assertIn("KEY TERMS", text)
        self.assertIn("A useful definition.", text)

    def test_wordpress_archive_keeps_posts_wrapped_in_list_items(self):
        html = """<html><head><title>Blog</title></head><body><ul class="blog-grid"><li>
        <article class="post"><header><h2>First post</h2></header>
        <div class="post-content"><p>First excerpt.</p></div></article></li><li>
        <article class="post"><header><h2>Second post</h2></header>
        <div class="post-content"><p>Second excerpt.</p></div></article></li></ul></body></html>"""

        data = extract(Page("https://example.com/blog", "https://example.com/blog", 200, "text/html", html))

        self.assertEqual(
            [block["text"] for block in data["content_blocks"]],
            ["First post", "First excerpt.", "Second post", "Second excerpt."],
        )

    def test_clean_html_preserves_visual_content_and_removes_active_content(self):
        page = Page(
            "https://example.com/blog",
            "https://example.com/blog",
            200,
            "text/html",
            """<html><head><title>Visual post</title><script>bad()</script></head><body>
            <nav>Menu</nav><article><h2>Post title</h2><p>Post body.</p>
            <img src="/media/chart.png" alt="Chart"><iframe src="https://tracker.example"></iframe>
            </article></body></html>""",
        )

        result = render_html(page, "clean", embed_page_images=False)

        self.assertIn("Post title", result)
        self.assertIn("Post body.", result)
        self.assertIn('src="https://example.com/media/chart.png"', result)
        self.assertIn(".document", result)
        self.assertNotIn("bad()", result)
        self.assertNotIn("<iframe", result)
        self.assertNotIn(">Menu<", result)

    def test_snapshot_html_keeps_page_structure_and_adds_base_url(self):
        page = Page(
            "https://example.com/start",
            "https://example.com/final/",
            200,
            "text/html",
            "<html><head><title>Snapshot</title></head><body><nav>Menu</nav><script>ready()</script></body></html>",
        )

        result = render_html(page, "snapshot", embed_page_images=False)

        self.assertIn('<base href="https://example.com/final/"/>', result)
        self.assertIn("<nav>Menu</nav>", result)
        self.assertIn("<script>ready()</script>", result)

    def test_generates_book_chapter_urls(self):
        urls = chapter_urls("https://books.example/10/book/", 1, 3)
        self.assertEqual(
            urls,
            [
                "https://books.example/10/book/ch1.xhtml",
                "https://books.example/10/book/ch2.xhtml",
                "https://books.example/10/book/ch3.xhtml",
            ],
        )

    def test_chapter_urls_accepts_contents_page(self):
        urls = chapter_urls("https://books.example/10/book/contents.xhtml#top", 2, 2)
        self.assertEqual(urls, ["https://books.example/10/book/ch2.xhtml"])

    def test_rejects_invalid_chapter_range(self):
        with self.assertRaises(CrawlerError):
            chapter_urls("https://books.example/book/", 5, 2)

    def test_suggests_title_and_falls_back_to_url(self):
        self.assertEqual(suggested_page_name({"title": " Demo page "}), "Demo page")
        self.assertEqual(
            suggested_page_name({"final_url": "https://example.com/course/lesson-one"}),
            "lesson one",
        )

    def test_same_site_links_exclude_external_and_binary_urls(self):
        data = {
            "links": [
                {"url": "https://example.com/about#team"},
                {"url": "https://example.com/report.pdf"},
                {"url": "https://other.example/page"},
            ]
        }
        self.assertEqual(
            same_site_links(data, "https://example.com/start"),
            ["https://example.com/about"],
        )

    def test_site_crawl_is_breadth_first_and_bounded(self):
        pages = {
            "https://example.com": "<title>Home</title><a href='/a'>A</a><a href='/b'>B</a>",
            "https://example.com/a": "<title>A</title>",
            "https://example.com/b": "<title>B</title>",
        }

        def fetcher(url):
            return Page(url, url, 200, "text/html", pages[url])

        results = list(crawl_site("https://example.com", 2, fetcher))

        self.assertEqual([result["title"] for result in results], ["Home", "A"])


if __name__ == "__main__":
    unittest.main()
