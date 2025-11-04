# Europages Lead Generation Pipeline

This project is a modular and scalable web scraping pipeline built in Python. Its objective is to gather verified contact information (Name, Country, Email) for wine producers in Europe, starting from the Europages "Wines" category.

---

## 🚀 Tech Stack

* **Python 3.12+**
* **Selenium:** For all browser automation, navigation, and page interaction.
* **BeautifulSoup4:** Used for parsing HTML content.
* **Pandas:** For structuring the final data and exporting to CSV.
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

The script is divided into two main, modular parts, just as the challenge required. This two-stage design allows the script to be re-run or modified easily.



### Part 1: The Master Link Collector (`scrape_master_links`)

This part is responsible for building the first CSV (`links_wine.csv`) and acts as a "scraper-of-scrapers."

1.  **Start:** The script starts at the correct category page (`.../bs/food-related-products/wines`), which was a key discovery for data quality.
2.  **Cookie Handling:** It first deals with the "Accept all cookies" banner to gain access to the page.
3.  **Sub-Category Scraping:** It scrapes the entire page for all sub-category links (e.g., "Fortified wines", "Wines - Apulia", "Wines - Bordeaux") by finding all `<a>` tags with an `href` starting with `/companies/`.
4.  **Deep Scraping & Pagination:** It then loops through *each* of those sub-category links and scrapes all of their company profile links. It successfully handles pagination (clicking "Next") for each one until all links are collected.
5.  **Output:** All unique company profile URLs are de-duplicated and saved to `output/links_wine.csv`.

### Part 2: The Detail Extractor (`scrape_external_details`)

This part is responsible for creating `output/emails_wine.csv`. It runs as a **single, robust process** to ensure stability and avoid bot detection.

1.  **Load Links:** It reads the `links_wine.csv` file.
2.  **Process Links (Serially):** It loops through each link one by one. For each link, it:
    * **Visits Europages:** Opens the company's profile page.
    * **Scrapes Profile:** Extracts the **Name**, **Country**, and **Website URL** from this page using robust selectors (e.g., `a.company-name`, `//span[contains(@class, 'vis-flag')]/following-sibling::span`).
    * **Finds Website:** Finds and clicks the **"Visit website"** link, opening the company's external site in a new tab.
3.  **External Site Scraping:**
    * **Resiliency (Timeout):** A **45-second page load timeout** is active. If an external site hangs or is too slow, the script gracefully catches the error, logs it, closes the tab, and moves to the next link. This prevents a single bad site from crashing the entire job.
    * **Best-Guess Logic:** It makes "best-guess" attempts to handle pop-ups (like "Are you 18?") and find "Contact" links to navigate deeper.
    * **"Smart" Email Filtering:** It scrapes all text from the landing page (and a guessed `/contact` page) and uses Regex to find all potential emails. It then filters this list:
        * **Blacklist:** Ignores junk emails (e.g., `image.png`, `user@example.com`, `user@wix.com`).
        * **Priority List:** Gives priority to emails like `info@`, `contact@`, or `sales@`.
    * **Store & Clean:** The first *valid* email is saved. The external tab is closed, and the script moves to the next link.
4.  **Final Output:** The final list of `Name, Country, Email` is de-duplicated and saved to `output/emails_wine.csv`.

---

## 🧠 Challenges Faced & Solutions

This project was a fantastic example of "real-world messy pages" as described in the challenge. The final, working script is the result of significant troubleshooting.

* **Challenge 1: Bot Detection & Shifting Selectors**
    * **Problem:** The script repeatedly failed because the site showed different HTML/selectors in headless vs. visible mode. My initial selectors for company links and "Next" buttons (`data-testid`) were incorrect in the live browser.
    * **Solution:** I used a "manual-first" debugging process. By running the browser in **visible mode** and using `input()` to pause the script, I could inspect the *actual* live HTML. This allowed me to find the stable, correct selectors:
        * **Company Link:** `a[data-test="company-name"]` (on the search page)
        * **Next Button:** `//a[.//img[@alt='Next']]` (on the search page)
        * **Profile Page Name:** `a.company-name` (on the profile page)
        * **Website Link:** `//a[.//span[contains(@class, 'website-link')]]` (on the profile page)

* **Challenge 2: Finding the Correct Starting Point**
    * **Problem:** An initial attempt using the general search URL (`/companies/wines.html`) returned thousands of irrelevant companies (e.g., box manufacturers, logistics).
    * **Solution:** I discovered that the category-specific page (`.../bs/food-related-products/wines`) was the correct, clean starting point. This required refactoring Part 1 into a "scraper-of-scrapers" that *first* finds all sub-categories (like "Wines - Apulia") and *then* scrapes the companies within them.

* **Challenge 3: External Site Timeouts**
    * **Problem:** The Part 2 scraper would frequently hang indefinitely on external company websites that were slow, broken, or ad-heavy. This would kill the entire script.
    * **Solution:** I implemented a 45-second `driver.set_page_load_timeout(45)`. This tells Selenium to "give up" on any page load that takes too long. This timeout is caught by a `try...except` block, allowing the script to log the failure and move on to the next link, making it highly resilient.

* **Challenge 4: Invalid Email Scraping**
    * **Problem:** The initial Regex grabbed junk emails like `image@2x.png` or `info@sentry.io`.
    * **Solution:** I built a "Smart" email filter with a **blacklist** (junk domains, image extensions) and a **priority list** (`info@`, `contact@`, etc.). The script now selects the *best* available email, not just the first one it finds.

---

## 💡 Future Improvements (ML/LLM)

* **Scalability (Multithreading):** The main bottleneck is running Part 2 serially. To scrape 100,000 links, I would re-introduce **multithreading** using Python's `concurrent.futures.ThreadPoolExecutor`. This would run 4-8 browser instances in parallel, dramatically cutting the runtime from 50+ hours to under 7. This approach is also *more stable*, as an `invalid session id` crash in one thread would not stop the other workers.

* **ML/LLM for Extraction:** The "best-guess" logic for finding contact links and emails is fragile. A *vastly* superior approach would be:
    1.  Scrape the raw HTML of the external contact page.
    2.  Feed that HTML to an LLM (like Gemini or a local Llama 3 model).
    3.  Use a prompt like: `"Extract the primary contact email, phone number, and physical address from this HTML. Return only a valid JSON object."`
    This approach is 100x more robust and would work on *any* website layout, removing the need for fragile regex or selectors.