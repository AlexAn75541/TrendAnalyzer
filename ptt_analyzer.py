"""
PTT Forum Trend Analyzer & Discussion Mining System
TEC004 ACP1 Group 4

This file contains:
- OOP crawler classes (PTTCrawler, Post, Comment, Board)
- Decorator-based rate limiting and caching
- Multi-threaded board crawling
- SQLite database with full-text search
- Text processing pipeline (map/filter/lambda)
- Sentiment scoring from push/boo ratios
- Pandas time-series trend analysis
- MatPlotLib visualizations

Run this file directly to crawl, process, and analyze data.
The output is a SQLite database (ptt_data.db) that web_dashboard.py reads from.
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import csv
import time
import re
import threading
import os
from functools import wraps
from datetime import datetime
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "Noto Sans CJK SC", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

DATA_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "ptt_data.db")
PTT_BASE_URL = "https://www.ptt.cc"


# ---------------------------------------------------------------------------
# Decorators: rate limiting and caching
# ---------------------------------------------------------------------------

def rate_limit(seconds=1.0):
    """Decorator that enforces a minimum delay between calls to the wrapped function."""
    def decorator(func):
        last_called = {"time": 0.0}
        lock = threading.Lock()

        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                elapsed = time.time() - last_called["time"]
                wait_time = seconds - elapsed
                if wait_time > 0:
                    time.sleep(wait_time)
                last_called["time"] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def cache_result(func):
    """Simple decorator that caches function results by argument signature."""
    cache = {}

    @wraps(func)
    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        if key in cache:
            return cache[key]
        result = func(*args, **kwargs)
        cache[key] = result
        return result
    return wrapper


# ---------------------------------------------------------------------------
# OOP domain classes
# ---------------------------------------------------------------------------

class Board:
    """Represents a PTT board (Gossiping, Tech_Job, Soft_Job)."""

    def __init__(self, name, display_name=None):
        self.name = name
        self.display_name = display_name or name
        self.posts = []

    def add_post(self, post):
        self.posts.append(post)

    def __repr__(self):
        return f"Board({self.name}, posts={len(self.posts)})"


class Comment:
    """Represents a single push/boo/neutral comment on a post."""

    VALID_TYPES = {"push", "boo", "neutral"}

    def __init__(self, comment_type, author, content, ip_time=""):
        if comment_type not in self.VALID_TYPES:
            comment_type = "neutral"
        self.comment_type = comment_type
        self.author = author
        self.content = content
        self.ip_time = ip_time

    def to_dict(self):
        return {
            "comment_type": self.comment_type,
            "author": self.author,
            "content": self.content,
            "ip_time": self.ip_time,
        }


class Post:
    """Represents a single PTT post with its metadata and comments."""

    def __init__(self, post_id, board, title, author, date, content="", url=""):
        self.post_id = post_id
        self.board = board
        self.title = title
        self.author = author
        self.date = date
        self.content = content
        self.url = url
        self.comments = []
        self.push_count = 0
        self.boo_count = 0
        self.neutral_count = 0

    def add_comment(self, comment):
        self.comments.append(comment)
        if comment.comment_type == "push":
            self.push_count += 1
        elif comment.comment_type == "boo":
            self.boo_count += 1
        else:
            self.neutral_count += 1

    def sentiment_score(self):  # mood
        """Calculate sentiment from push/boo ratio. Range -1.0 (all boo) to 1.0 (all push)."""
        total = self.push_count + self.boo_count
        if total == 0:
            return 0.0
        return (self.push_count - self.boo_count) / total

    def to_dict(self):
        return {
            "post_id": self.post_id,
            "board": self.board,
            "title": self.title,
            "author": self.author,
            "date": self.date,
            "content": self.content,
            "url": self.url,
            "push_count": self.push_count,
            "boo_count": self.boo_count,
            "neutral_count": self.neutral_count,
            "sentiment": self.sentiment_score(),
        }


class PTTCrawler:
    """
    Crawls PTT boards. Handles the over-18 cookie verification,
    pagination, and parsing of post listings and content.
    """

    def __init__(self, base_url=PTT_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.cookies.set("over18", "1")
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (PTT-Analyzer/1.0)"})

    @rate_limit(seconds=1.0)
    def fetch_page(self, url):
        """Fetch a single page. Rate limited to avoid hammering the server."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"[PTTCrawler] Failed to fetch {url}: {e}")
            return None

    def get_board_url(self, board_name, page_index=None):
        if page_index:
            return f"{self.base_url}/bbs/{board_name}/index{page_index}.html"
        return f"{self.base_url}/bbs/{board_name}/index.html"

    def parse_post_listing(self, html, board_name):
        """Parse a board index page. Returns list of dicts with basic post metadata."""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        entries = soup.select("div.r-ent")
        results = []
        for entry in entries:
            title_tag = entry.select_one("div.title a")
            if not title_tag:
                continue  # deleted post, skip
            title = title_tag.text.strip()
            link = self.base_url + title_tag["href"]
            author_tag = entry.select_one("div.author")
            author = author_tag.text.strip() if author_tag else "unknown"
            date_tag = entry.select_one("div.date")
            date = date_tag.text.strip() if date_tag else ""
            push_tag = entry.select_one("div.nrec")
            push_raw = push_tag.text.strip() if push_tag else ""
            results.append({
                "title": title,
                "url": link,
                "author": author,
                "date": date,
                "board": board_name,
                "push_raw": push_raw,
            })
        return results

    def get_previous_page_url(self, html):
        """Find the 'previous page' link for pagination."""
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("div.btn-group-paging a"):
            if "上頁" in a.text:
                href = a.get("href")
                if href and "javascript" not in href:
                    return self.base_url + href
        return None

    def parse_post_content(self, html):
        """Parse an individual post page. Returns (content_text, list_of_comment_dicts)."""
        if not html:
            return "", []
        soup = BeautifulSoup(html, "html.parser")
        main_content = soup.select_one("div#main-content")
        if not main_content:
            return "", []

        comments = []
        for push_div in main_content.select("div.push"):
            tag = push_div.select_one("span.push-tag")
            user = push_div.select_one("span.push-userid")
            content_span = push_div.select_one("span.push-content")
            ip_time = push_div.select_one("span.push-ipdatetime")

            tag_text = tag.text.strip() if tag else ""
            if "推" in tag_text:
                ctype = "push"
            elif "噓" in tag_text:
                ctype = "boo"
            else:
                ctype = "neutral"

            comments.append({
                "comment_type": ctype,
                "author": user.text.strip() if user else "unknown",
                "content": content_span.text.strip(": ").strip() if content_span else "",
                "ip_time": ip_time.text.strip() if ip_time else "",
            })
            push_div.extract()

        for meta in main_content.select("div.article-metaline, div.article-metaline-right"):
            meta.extract()

        content_text = main_content.get_text("\n").strip()
        return content_text, comments

    def crawl_board(self, board_name, max_pages=3):
        """
        Crawl a single board across max_pages of listing pages,
        then fetch each post's content and comments.
        Returns a Board object populated with Post objects.
        """
        board = Board(board_name)
        url = self.get_board_url(board_name)
        pages_crawled = 0

        while url and pages_crawled < max_pages:
            html = self.fetch_page(url)
            if html is None:
                break
            listing = self.parse_post_listing(html, board_name)

            for item in listing:
                post_html = self.fetch_page(item["url"])
                content_text, comment_dicts = self.parse_post_content(post_html)

                post_id = item["url"].split("/")[-1].replace(".html", "")
                post = Post(
                    post_id=post_id,
                    board=board_name,
                    title=item["title"],
                    author=item["author"],
                    date=item["date"],
                    content=content_text,
                    url=item["url"],
                )
                for c in comment_dicts:
                    post.add_comment(Comment(**c))
                board.add_post(post)

            url = self.get_previous_page_url(html)
            pages_crawled += 1

        return board

    def crawl_boards_multithreaded(self, board_names, max_pages=3):
        """Crawl multiple boards concurrently using one thread per board."""
        boards = {}
        lock = threading.Lock()

        def worker(name):
            result = self.crawl_board(name, max_pages=max_pages)
            with lock:
                boards[name] = result

        threads = [threading.Thread(target=worker, args=(name,)) for name in board_names]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return boards




# ---------------------------------------------------------------------------
# Sample data generator (in used because live crawling is rate limited or for demo/testing purposes)
# ---------------------------------------------------------------------------

def fallback_sample_data(board_names):
    """
    Build a set of Board objects with realistic sample posts.
    Use this for testing the pipeline without needing live network access to PTT.
    """
    sample_titles = {
        "Gossiping": [
            "[問卦] 台北房價會不會崩盤", "[新聞] AI 取代工程師話題再起",
            "[爆卦] 今天股市大跌", "[問卦] 大家覺得電動車如何",
            "[心情] 工作壓力好大", "[新聞] 政府宣布新政策",
        ],
        "Tech_Job": [
            "[請益] 新竹軟體工程師薪水水平", "[討論] Python 還是 Java 比較好找工作",
            "[心得] 面試心得分享 Google", "[請益] 轉職資料科學家方向",
            "[討論] 遠端工作好還是辦公室好", "[心得] 跳槽加薪經驗",
        ],
        "Soft_Job": [
            "[討論] 軟體業加班文化", "[請益] 後端工程師職涯規劃",
            "[心得] 自學程式心得", "[討論] 新創公司 vs 大公司",
            "[請益] 想轉職前端工程師", "[心得] 工作三年回顧",
        ],
    }

    keywords_pool = ["AI", "Python", "薪水", "面試", "加班", "股市", "房價", "電動車", "遠端工作", "新創"]

    boards = {}
    post_counter = 1
    for board_name in board_names:
        board = Board(board_name)
        titles = sample_titles.get(board_name, ["[討論] 一般話題"])
        for i, title in enumerate(titles):
            post_id = f"M.{1700000000 + post_counter}.A.{post_counter:03d}"
            day_offset = i % 5
            date_str = f"6/{10 + day_offset}"
            content = " ".join(
                kw for kw in keywords_pool if (post_counter + len(kw)) % 3 == 0
            ) or "一般討論內容"

            post = Post(
                post_id=post_id,
                board=board_name,
                title=title,
                author=f"user{post_counter:03d}",
                date=date_str,
                content=content,
                url=f"{PTT_BASE_URL}/bbs/{board_name}/{post_id}.html",
            )

            num_push = (post_counter * 7) % 40
            num_boo = (post_counter * 3) % 15
            num_neutral = (post_counter * 2) % 10
            for _ in range(num_push):
                post.add_comment(Comment("push", "userA", "推"))
            for _ in range(num_boo):
                post.add_comment(Comment("boo", "userB", "噓"))
            for _ in range(num_neutral):
                post.add_comment(Comment("neutral", "userC", "..."))

            board.add_post(post)
            post_counter += 1
        boards[board_name] = board

    return boards


# ---------------------------------------------------------------------------
# Database layer: SQLite with full-text search
# ---------------------------------------------------------------------------

class Database:
    """Manages SQLite storage for boards, posts, comments, and keywords."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self):
        cur = self.conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS boards (
                name TEXT PRIMARY KEY
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY,
                board TEXT NOT NULL,
                title TEXT,
                author TEXT,
                date TEXT,
                content TEXT,
                url TEXT,
                push_count INTEGER DEFAULT 0,
                boo_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                sentiment REAL DEFAULT 0,
                crawled_at TEXT,
                FOREIGN KEY (board) REFERENCES boards(name)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                comment_type TEXT,
                author TEXT,
                content TEXT,
                ip_time TEXT,
                FOREIGN KEY (post_id) REFERENCES posts(post_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                FOREIGN KEY (post_id) REFERENCES posts(post_id)
            )
        """)

        # FTS5 virtual table for full text search over post titles and content
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
                post_id, title, content
            )
        """)

        self.conn.commit()

    def save_board(self, board):
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO boards (name) VALUES (?)", (board.name,))
        for post in board.posts:
            self.save_post(post)
        self.conn.commit()

    def save_post(self, post):
        cur = self.conn.cursor()
        d = post.to_dict()
        cur.execute("""
            INSERT OR REPLACE INTO posts
            (post_id, board, title, author, date, content, url,
             push_count, boo_count, neutral_count, sentiment, crawled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            d["post_id"], d["board"], d["title"], d["author"], d["date"],
            d["content"], d["url"], d["push_count"], d["boo_count"],
            d["neutral_count"], d["sentiment"], datetime.now().isoformat()
        ))

        cur.execute("DELETE FROM comments WHERE post_id = ?", (post.post_id,))
        for c in post.comments:
            cd = c.to_dict()
            cur.execute("""
                INSERT INTO comments (post_id, comment_type, author, content, ip_time)
                VALUES (?, ?, ?, ?, ?)
            """, (post.post_id, cd["comment_type"], cd["author"], cd["content"], cd["ip_time"]))

        cur.execute("DELETE FROM posts_fts WHERE post_id = ?", (post.post_id,))
        cur.execute("INSERT INTO posts_fts (post_id, title, content) VALUES (?, ?, ?)",
                    (post.post_id, post.title, post.content))

    def save_keywords(self, post_id, keyword_counts):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM keywords WHERE post_id = ?", (post_id,))
        for keyword, freq in keyword_counts.items():
            cur.execute("""
                INSERT INTO keywords (post_id, keyword, frequency) VALUES (?, ?, ?)
            """, (post_id, keyword, freq))
        self.conn.commit()

    def search_posts(self, query):
        """Full-text search across post titles and content."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT posts.* FROM posts
            JOIN posts_fts ON posts.post_id = posts_fts.post_id
            WHERE posts_fts MATCH ?
        """, (query,))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_all_posts(self, board=None):
        cur = self.conn.cursor()
        if board:
            cur.execute("SELECT * FROM posts WHERE board = ?", (board,))
        else:
            cur.execute("SELECT * FROM posts")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_all_keywords(self):
        cur = self.conn.cursor()
        cur.execute("SELECT keyword, SUM(frequency) as total FROM keywords GROUP BY keyword ORDER BY total DESC")
        return cur.fetchall()

    def export_json(self, path=None):
        if path is None:
            path = os.path.join(DATA_DIR, "export.json")
        posts = self.get_all_posts()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)

    def export_csv(self, path=None):
        if path is None:
            path = os.path.join(DATA_DIR, "export.csv")
        posts = self.get_all_posts()
        if not posts:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=posts[0].keys())
            writer.writeheader()
            writer.writerows(posts)

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# Text processing pipeline: map / filter / lambda
# ---------------------------------------------------------------------------

STOPWORDS = {"的", "了", "在", "是", "我", "你", "他", "她", "也", "都", "就", "和", "與", "to", "the", "a", "is"}


def clean_post_text(text):
    """Remove punctuation and extra whitespace from a block of text."""
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return text.strip()


def extract_keywords_from_posts(posts):
    """
    Use map/filter/lambda to clean post titles and pull out keyword candidates.
    Returns a dict of {post_id: Counter(keyword -> frequency)}.
    """
    # map: clean every post's title+content into a single text blob
    cleaned = list(map(lambda p: (p["post_id"], clean_post_text(p["title"] + " " + p["content"])), posts))

    keyword_map = {}
    for post_id, text in cleaned:
        tokens = text.split()
        # filter: drop stopwords and short tokens
        tokens = list(filter(lambda t: t.lower() not in STOPWORDS and len(t) > 1, tokens))
        keyword_map[post_id] = Counter(tokens)

    return keyword_map


def calculate_sentiment_for_posts(posts):
    """Recompute sentiment using lambda over a list of post dicts."""
    sentiment_fn = lambda p: (p["push_count"] - p["boo_count"]) / max(p["push_count"] + p["boo_count"], 1)
    return {p["post_id"]: sentiment_fn(p) for p in posts}


# ---------------------------------------------------------------------------
# Trend analysis: Pandas time-series and keyword co-occurrence
# ---------------------------------------------------------------------------

class TrendAnalyzer:
    """Runs Pandas-based trend analysis over posts pulled from the database."""

    def __init__(self, db):
        self.db = db

    def posts_dataframe(self, board=None):
        posts = self.db.get_all_posts(board=board)
        df = pd.DataFrame(posts)
        if df.empty:
            return df
        df["crawled_at"] = pd.to_datetime(df["crawled_at"])
        return df

    def posting_frequency(self, board=None):
        """Number of posts per board."""
        df = self.posts_dataframe(board=board)
        if df.empty:
            return pd.Series(dtype="int64")
        return df.groupby("board")["post_id"].count().rename("post_count")

    def hot_topics(self, top_n=10):
        """Detect hot topics: posts ranked by total engagement (push + boo)."""
        df = self.posts_dataframe()
        if df.empty:
            return pd.DataFrame()
        df["engagement"] = df["push_count"] + df["boo_count"]
        return df.sort_values("engagement", ascending=False).head(top_n)[
            ["post_id", "board", "title", "engagement", "sentiment"]
        ]

    def sentiment_distribution(self, board=None):
        """Bucket posts into positive/neutral/negative sentiment categories."""
        df = self.posts_dataframe(board=board)
        if df.empty:
            return pd.Series(dtype="int64")

        def bucket(s):
            if s > 0.2:
                return "positive"
            if s < -0.2:
                return "negative"
            return "neutral"

        df["bucket"] = df["sentiment"].apply(bucket)
        return df["bucket"].value_counts()

    def top_posters(self, top_n=10):
        """Author activity ranking by post count."""
        df = self.posts_dataframe()
        if df.empty:
            return pd.Series(dtype="int64")
        return df.groupby("author")["post_id"].count().sort_values(ascending=False).head(top_n)

    def board_comparison(self):
        """Compare average sentiment and engagement across boards."""
        df = self.posts_dataframe()
        if df.empty:
            return pd.DataFrame()
        df["engagement"] = df["push_count"] + df["boo_count"]
        return df.groupby("board").agg(
            avg_sentiment=("sentiment", "mean"),
            avg_engagement=("engagement", "mean"),
            post_count=("post_id", "count"),
        )

    def keyword_cooccurrence(self, keyword_map, top_n=10):
        """
        Given {post_id: Counter(keyword)} from extract_keywords_from_posts,
        compute which keyword pairs co-occur most often in the same post.
        """
        pair_counts = Counter()
        for counter in keyword_map.values():
            keywords = list(counter.keys())
            for i in range(len(keywords)):
                for j in range(i + 1, len(keywords)):
                    pair = tuple(sorted((keywords[i], keywords[j])))
                    pair_counts[pair] += 1
        return pair_counts.most_common(top_n)

    def activity_heatmap_data(self):
        """
        Build hour x day posting activity matrix.
        Since PTT dates from listing pages don't include hour, this uses
        crawled_at as a proxy timestamp for demo purposes.
        """
        df = self.posts_dataframe()
        if df.empty:
            return pd.DataFrame()
        df["hour"] = df["crawled_at"].dt.hour
        df["day"] = df["crawled_at"].dt.day_name()
        pivot = df.pivot_table(index="day", columns="hour", values="post_id", aggfunc="count", fill_value=0)
        return pivot


# ---------------------------------------------------------------------------
# Visualization: MatPlotLib
# ---------------------------------------------------------------------------

class Visualizer:
    """Generates MatPlotLib charts and saves them as PNG files."""

    def __init__(self, analyzer, output_dir="."):
        self.analyzer = analyzer
        self.output_dir = output_dir or DATA_DIR

    def plot_posting_activity_heatmap(self, filename="heatmap.png"):
        pivot = self.analyzer.activity_heatmap_data()
        if pivot.empty:
            return None
        fig, ax = plt.subplots(figsize=(10, 4))
        im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_xlabel("Hour of day")
        ax.set_title("Posting activity heatmap (hour x day)")
        fig.colorbar(im, ax=ax, label="Post count")
        path = f"{self.output_dir}/{filename}"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def plot_keyword_trend(self, keyword_counts, filename="keyword_trend.png"):
        if not keyword_counts:
            return None
        keywords, counts = zip(*keyword_counts.most_common(10))
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.barh(keywords, counts, color="#3b6e9e")
        ax.set_xlabel("Frequency")
        ax.set_title("Top keyword frequency")
        ax.invert_yaxis()
        path = f"{self.output_dir}/{filename}"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def plot_sentiment_distribution(self, filename="sentiment.png"):
        dist = self.analyzer.sentiment_distribution()
        if dist.empty:
            return None
        fig, ax = plt.subplots(figsize=(6, 4))
        colors = {"positive": "#3aa657", "neutral": "#9aa0a6", "negative": "#d9534f"}
        ax.bar(dist.index, dist.values, color=[colors.get(i, "#888") for i in dist.index])
        ax.set_title("Sentiment distribution")
        ax.set_ylabel("Post count")
        path = f"{self.output_dir}/{filename}"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def plot_top_posters(self, filename="top_posters.png"):
        top = self.analyzer.top_posters()
        if top.empty:
            return None
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(top.index, top.values, color="#6a4fb5")
        ax.set_title("Top poster rankings")
        ax.set_ylabel("Post count")
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        path = f"{self.output_dir}/{filename}"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def plot_board_comparison(self, filename="board_comparison.png"):
        comparison = self.analyzer.board_comparison()
        if comparison.empty:
            return None
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(comparison.index, comparison["avg_sentiment"], color="#3b6e9e")
        ax.set_title("Board comparison: average sentiment")
        ax.set_ylabel("Average sentiment")
        path = f"{self.output_dir}/{filename}"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(boards_to_crawl=("Gossiping", "Tech_Job", "Soft_Job"), use_sample_data=True, max_pages=2):
    """
    Run the full pipeline: crawl, store, process, analyze, visualize.
    Set use_sample_data=False to attempt a live crawl of PTT
    (note: live crawling depends on network access and PTT's current HTML structure).
    """
    db = Database()

    print("Step 1: Crawling boards...")
    if use_sample_data:
        boards = fallback_sample_data(boards_to_crawl)
    else:
        crawler = PTTCrawler()
        boards = crawler.crawl_boards_multithreaded(boards_to_crawl, max_pages=max_pages)

    print("Step 2: Saving to database...")
    for board in boards.values():
        db.save_board(board)

    print("Step 3: Extracting keywords...")
    all_posts = db.get_all_posts()
    keyword_map = extract_keywords_from_posts(all_posts)
    for post_id, counter in keyword_map.items():
        db.save_keywords(post_id, counter)

    print("Step 4: Running trend analysis...")
    analyzer = TrendAnalyzer(db)
    print(analyzer.posting_frequency())
    print(analyzer.sentiment_distribution())

    print("Step 5: Generating visualizations...")
    viz = Visualizer(analyzer)
    overall_keywords = Counter()
    for counter in keyword_map.values():
        overall_keywords.update(counter)

    viz.plot_posting_activity_heatmap()
    viz.plot_keyword_trend(overall_keywords)
    viz.plot_sentiment_distribution()
    viz.plot_top_posters()
    viz.plot_board_comparison()

    print("Step 6: Exporting raw data...")
    db.export_json()
    db.export_csv()

    print("Pipeline complete. Database saved to:", DB_PATH)
    db.close()


if __name__ == "__main__":
    run_pipeline()
