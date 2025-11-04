# Europages Lead Generation Pipeline

This project is a modular and scalable web scraping pipeline built in Python. Its objective is to gather verified contact information (Name, Country, Email) for wine producers in Europe, starting from the Europages "Wines" category.

The pipeline is built to be **fast** and **resilient**, using a hybrid approach: a stable, single-browser process for initial link gathering, followed by a high-speed, parallel process for external data extraction.

---

## 🚀 Tech Stack

* **Python 3.12+**
* **Selenium:** For all browser automation, navigation, and page interaction.
* **BeautifulSoup4:** Used for parsing HTML content.
* **Pandas:** For structuring the final data and exporting to CSV.
* **Concurrent.futures:** For high-speed, parallel scraping using a `ThreadPoolExecutor`.
* **Regex (re):** For pattern-based extraction and "smart" filtering of email addresses.
* **Webdriver Manager:** To automatically manage the Chrome driver.

---

## 🛠️ How to Run

1.  **Clone this repository:**
    ```bash
    git clone https://github.com/jordialt/europages-scraper.git
    cd europages-scraper
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    
    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required packages:**
    (A `requirements.txt` file should be included with the project)
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the main script:**
    ```bash
    python main.py
    ```

5.  **Find the results:**
    The script will create an `output` folder and place the final, clean CSV files inside:
    * `output/links_wine.csv`
    * `output/emails_wine.csv`

---

## 🤖 Pipeline Approach

The script is divided into two main, modular parts. It uses a **hybrid execution model** to maximize stability and speed.



### Part 1: The Master Link Collector (`scrape_master_links`)

This part runs first, using **one visible browser**. This was a deliberate choice, as a single, visible instance is the most reliable way to handle initial bot detection and cookie banners.

1.  **Start:** The script starts at the correct category page (`.../bs/food-related-products/wines`), which was a key discovery for data quality.
2.  **Cookie Handling:** It reliably clicks the "Accept all cookies" banner to gain access to the page.
3.  **Sub-Category Scraping:** It scrapes the page for all sub-category links (e.g., "Fortified wines", "Wines - Apulia") by finding all `<a>` tags with an `href` starting with `/companies/`.
4.  **Deep Scraping & Pagination:** It then loops through *each* sub-category and scrapes all company profile links using the `a[data-test="company-name"]` selector. It handles pagination by clicking the "Next" button (`//a[.//img[@alt='Next']]`) until it's disabled.
5.  **Output:** All unique company profile URLs are saved to `output/links_wine.csv`.

### Part 2: The Parallel Detail Extractor (`process_link`)

This part is built for **speed and resilience**. It reads the list from Part 1 and processes it in parallel.

1.  **Parallel Workers:** It uses a `ThreadPoolExecutor` to launch **4 (or more) workers**. Each worker is its own **independent, headless browser instance**.
2.  **Process Link:** Each worker grabs a link from the list and:
    * **Visits Europages:** Opens the company's profile page.
    * **Scrapes Profile:** Extracts the **Name**, **Country**, and **Website URL** using the robust selectors we found (e.g., `a.company-name`, `//a[.//span[contains(@class, 'website-link')]]`).
    * **Visits External Site:** Opens the company's own site.
3.  **Resilient Scraping:**
    * **Timeout:** A **45-second page load timeout** is active. If an external site hangs, the worker catches the error, quits, and moves on, *without* crashing the whole script.
    * **"Smart" Email Filtering:** It scrapes all text from the landing page (and a guessed `/contact` page) and uses Regex to find all potential emails. It then filters this list:
        * **Blacklist:** Ignores junk emails (e.g., `image.png`, `user@example.com`).
        * **Priority List:** Gives priority to emails like `info@`, `contact@`, or `sales@`.
4.  **Final Output:** All valid results from all workers are collected, de-duplicated, and saved to `output/emails_wine.csv`.

---

## 🧠 Challenges Faced & Solutions

This project was a fantastic example of "real-world messy pages" as described in the challenge. The final, hybrid solution was a direct result of overcoming several key challenges.

* **Challenge 1: Speed & Stability (The Core Problem)**
    * **Problem:** A single-threaded approach was far too slow (estimated 50+ hours) and extremely fragile. A single browser crash (`invalid session id`) would kill the entire job.
    * **Solution:** I implemented a **multithreaded worker pool** for Part 2. This solved both problems at once:
        1.  **Speed:** It cuts the 50+ hour runtime to under 14 hours (with 4 workers).
        2.  **Resiliency:** If one of the 4 browser workers crashes, it only affects that single link. The thread terminates, but the other workers (and the main script) continue running. This makes the pipeline truly fault-tolerant.

* **Challenge 2: Bot Detection & Shifting Selectors**
    * **Problem:** The script repeatedly failed to find any links. I discovered the site was showing different HTML in headless vs. visible mode. My initial selectors were wrong.
    * **Solution:** I used a "manual-first" debugging process. By running the browser in **visible mode** and using `input()` to pause the script, I could **live-inspect** the HTML. This was the only way to find the stable, correct selectors that work in the final script.

* **Challenge 3: Finding the Correct Starting Point**
    * **Problem:** An initial attempt using the general search URL returned thousands of irrelevant companies (e.g., box manufacturers, logistics).
    * **Solution:** I discovered that the category-specific page (`.../bs/food-related-products/wines`) was the correct, clean starting point. This required refactoring Part 1 into a "scraper-of-scrapers" that *first* finds all sub-categories and *then* scrapes the companies within them.

* **Challenge 4: Invalid Email Scraping**
    * **Problem:** The initial Regex grabbed junk emails like `image@2x.png` or `info@sentry.io`.
    * **Solution:** I built a "Smart" email filter with a **blacklist** (junk domains, image extensions) and a **priority list** (`info@`, `contact@`, etc.). The script now selects the *best* available email, not just the first one it finds.

---

## 💡 Future Improvements (ML/LLM)

* **Scalability:** The `MAX_WORKERS` variable can be increased from `4` to `8` or `12` on a more powerful machine or server to further decrease the runtime.
* **ML/LLM for Extraction:** The "best-guess" logic for finding emails on external sites is the script's most fragile part. A vastly superior approach would be:
    1.  Have each worker scrape the raw HTML of the external contact page.
    2.  Feed that HTML to an LLM (like Gemini or a local Llama 3 model).
    3.  Use a prompt like: `"Extract the primary contact email from this HTML. Return only a valid JSON object with 'email' as the key."`
    This approach is 100x more robust and would work on *any* website layout, removing the need for fragile regex or selectors.