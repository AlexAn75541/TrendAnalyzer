

| Project ID | TEC004/04 |
| ----- | :---- |
| **Project Title** | PTT Forum Trend Analyzer & Discussion Mining System |
| **Mentor** |  |
| **Project Description** |  |
| Build a Python application that crawls PTT (the largest BBS forum in Taiwan), extracts discussion threads and comments, stores them in a database, performs trend analysis and keyword mining, and visualizes discussion patterns to understand public opinion on technology topics. **Syllabus Coverage:** Directly covers the syllabus PTT Crawler topic, plus OOP design, BeautifulSoup and Selenium for scraping, JSON/CSV processing, SQLite database, Pandas for text and time-series analysis, MatPlotLib for visualization, advanced functions (decorators for rate limiting, lambda for filtering), multi-threading, and file management. **Expected Deliverables:** SP1 \- PTT Crawler: OOP-based crawler that navigates PTT boards (Gossiping, Tech\_Job, Soft\_Job), handles pagination (over-18 verification), extracts post titles, authors, dates, content, and push/boo counts. SP2 \- Data processing pipeline: Use advanced functions (map/filter/lambda) to clean posts, extract keywords, calculate sentiment from push/boo ratios. Decorator-based caching and rate limiting. SP3 \- SQLite database: Posts, Comments, Keywords, Boards tables. Full-text search capability. Historical data tracking for trend analysis. SP4 \- Trend analysis module: Pandas-based time-series analysis of posting frequency, hot topic detection, keyword co-occurrence analysis, author activity patterns. SP5 \- Visualization dashboard: MatPlotLib charts including posting activity heatmaps (hour x day), keyword trend lines, sentiment distribution, top poster rankings, board comparison charts. SP6 \- Technical report with findings on technology discussion trends in PTT. |  |
| **Project Skills** |  |
| x | Web Scraping (BeautifulSoup, requests, PTT-specific techniques) |
| x | Object-Oriented Programming (Classes, Inheritance) |
| x | Advanced Functions (Lambda, Map, Filter, Decorators) |
| x | Database Management (SQLite, full-text search) |
| x | Data Analysis (Pandas, time-series analysis) |
| x | Data Visualization (MatPlotLib) |
| x | Multi-threading (concurrent board crawling) |
| x | File I/O (JSON, CSV) |
|  **Research Component** |  |
| **(Phase 1 \- PTT Crawling):** \- Study PTT HTML structure; handle over-18 cookie verification using requests.Session. \- Design OOP classes: PTTCrawler, Post, Comment, Board with encapsulation. \- Implement BeautifulSoup parser for post listings and individual post content. \- Handle pagination (previous page navigation), extract push/boo/neutral counts. \- Create SQLite database; export raw data to JSON/CSV. \- Implement rate limiting with decorator pattern; multi-threaded board crawling. **(Phase 2 \- Text Mining & Analysis):** \- Build text processing pipeline using lambda/map/filter for keyword extraction. \- Pandas analysis: posting frequency trends, hot topic detection, sentiment calculation from push ratios. \- Time-series analysis: hourly/daily patterns, trend detection for specific keywords. \- MatPlotLib visualizations: activity heatmaps, word frequency charts, sentiment trends. \- Submit Midterm Report with PTT data collection and preliminary analysis. **(Phase 3 \- Dashboard & Insights):** \- Build comprehensive trend dashboard. \- Add real-time monitoring mode for breaking topics. \- Cross-board comparison analysis. \- Final presentation with live crawling demo and trend insights. |  |

**Syllabus Coverage Matrix**

Each project covers different combinations of syllabus topics. Together, all 5 projects ensure 100% coverage.

| Syllabus Topic | P1 | P2 | P3 | P4 | P5 |
| :---- | :---: | :---: | :---: | :---: | :---: |
| OOP (Classes, Methods, Objects) | **✓** | **✓** | **✓** | **✓** | **✓** |
| Inheritance & Abstract Classes | **✓** | **✓** | **✓** | **✓** | **✓** |
| Advanced Functions (Lambda, Map, Filter) | **✓** | **✓** | **✓** | **✓** | **✓** |
| Decorators & Closures |  | **✓** |  | **✓** | **✓** |
| JSON & CSV Processing | **✓** | **✓** | **✓** | **✓** | **✓** |
| File Management | **✓** | **✓** | **✓** | **✓** | **✓** |
| Web Scraping (BeautifulSoup) | **✓** | **✓** | **✓** | **✓** |  |
| Web Automation (Selenium) | **✓** | **✓** | **✓** |  | **✓** |
| Pandas & Data Analysis | **✓** | **✓** | **✓** | **✓** | **✓** |
| SQLite Database | **✓** | **✓** | **✓** | **✓** | **✓** |
| MatPlotLib Visualization | **✓** | **✓** | **✓** | **✓** | **✓** |
| Multi-threading | **✓** | **✓** |  | **✓** | **✓** |
| AI Application |  | **✓** |  |  | **✓** |

