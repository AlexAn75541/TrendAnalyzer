"""
Web dashboard for the PTT Forum Trend Analyzer.

Reads data from ptt_data.db (created by ptt_analyzer.py) and serves
a browser dashboard with charts, search, and post listings.

Run with: python3 web_dashboard.py
Then open: http://127.0.0.1:5000
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
import sqlite3
import os

DATA_DIR = os.environ.get("DATA_DIR", ".")
DB_PATH = os.path.join(DATA_DIR, "ptt_data.db")

app = Flask(__name__)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_exists():
    return os.path.exists(DB_PATH)

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/data/<filename>")
def serve_data_files(filename):
    return send_from_directory(DATA_DIR, filename)


@app.route("/api/summary")
def api_summary():
    """Overall counts: total posts, total comments, boards covered."""
    if not db_exists():
        return jsonify({"error": "Database not found. Run ptt_analyzer.py first."}), 404

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM posts")
    total_posts = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM comments")
    total_comments = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(DISTINCT board) AS c FROM posts")
    total_boards = cur.fetchone()["c"]

    cur.execute("SELECT AVG(sentiment) AS s FROM posts")
    avg_sentiment = cur.fetchone()["s"] or 0

    conn.close()
    return jsonify({
        "total_posts": total_posts,
        "total_comments": total_comments,
        "total_boards": total_boards,
        "avg_sentiment": round(avg_sentiment, 3),
    })


@app.route("/api/posts")
def api_posts():
    """List posts, optionally filtered by board, sorted by engagement."""
    if not db_exists():
        return jsonify({"error": "Database not found. Run ptt_analyzer.py first."}), 404

    board = request.args.get("board")
    limit = int(request.args.get("limit", 50))

    conn = get_connection()
    cur = conn.cursor()

    if board:
        cur.execute("""
            SELECT post_id, board, title, author, date, push_count, boo_count,
                   neutral_count, sentiment
            FROM posts WHERE board = ?
            ORDER BY (push_count + boo_count) DESC
            LIMIT ?
        """, (board, limit))
    else:
        cur.execute("""
            SELECT post_id, board, title, author, date, push_count, boo_count,
                   neutral_count, sentiment
            FROM posts
            ORDER BY (push_count + boo_count) DESC
            LIMIT ?
        """, (limit,))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/post/<post_id>")
def api_post_detail(post_id):
    """Full detail for a single post, including its comments."""
    if not db_exists():
        return jsonify({"error": "Database not found."}), 404

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,))
    post_row = cur.fetchone()
    if not post_row:
        conn.close()
        return jsonify({"error": "Post not found"}), 404

    cur.execute("SELECT comment_type, author, content, ip_time FROM comments WHERE post_id = ?", (post_id,))
    comments = [dict(r) for r in cur.fetchall()]

    conn.close()
    result = dict(post_row)
    result["comments"] = comments
    return jsonify(result)


@app.route("/api/search")
def api_search():
    """Full-text search over post titles and content."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    if not db_exists():
        return jsonify({"error": "Database not found."}), 404

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT posts.post_id, posts.board, posts.title, posts.author,
                   posts.push_count, posts.boo_count, posts.sentiment
            FROM posts
            JOIN posts_fts ON posts.post_id = posts_fts.post_id
            WHERE posts_fts MATCH ?
        """, (query,))
        rows = [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        # fall back to LIKE search if FTS query syntax fails
        cur.execute("""
            SELECT post_id, board, title, author, push_count, boo_count, sentiment
            FROM posts WHERE title LIKE ? OR content LIKE ?
        """, (f"%{query}%", f"%{query}%"))
        rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/keywords")
def api_keywords():
    """Top keywords by total frequency across all posts."""
    if not db_exists():
        return jsonify({"error": "Database not found."}), 404

    limit = int(request.args.get("limit", 20))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT keyword, SUM(frequency) AS total
        FROM keywords
        GROUP BY keyword
        ORDER BY total DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/board-comparison")
def api_board_comparison():
    """Average sentiment, average engagement, and post count per board."""
    if not db_exists():
        return jsonify({"error": "Database not found."}), 404

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT board,
               COUNT(*) AS post_count,
               AVG(sentiment) AS avg_sentiment,
               AVG(push_count + boo_count) AS avg_engagement
        FROM posts
        GROUP BY board
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/sentiment-distribution")
def api_sentiment_distribution():
    """Bucket all posts into positive/neutral/negative sentiment counts."""
    if not db_exists():
        return jsonify({"error": "Database not found."}), 404

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT sentiment FROM posts")
    sentiments = [r["sentiment"] for r in cur.fetchall()]
    conn.close()

    buckets = {"positive": 0, "neutral": 0, "negative": 0}
    for s in sentiments:
        if s > 0.2:
            buckets["positive"] += 1
        elif s < -0.2:
            buckets["negative"] += 1
        else:
            buckets["neutral"] += 1

    return jsonify(buckets)


@app.route("/api/top-posters")
def api_top_posters():
    """Author activity ranking by post count."""
    if not db_exists():
        return jsonify({"error": "Database not found."}), 404

    limit = int(request.args.get("limit", 10))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT author, COUNT(*) AS post_count
        FROM posts
        GROUP BY author
        ORDER BY post_count DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

if __name__ == "__main__":
    if not db_exists():
        print(f"Warning: {DB_PATH} not found.")
        print("Run python3 ptt_analyzer.py first to generate the database.")
    app.run(host="0.0.0.0", port=5000)
    
