import os
import re
import time
import pandas as pd
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
# Increase this number to scrape faster (e.g., 8 or 10)
# 4 is a safe start.
MAX_WORKERS = 4 
# ---

def setup_driver(is_headless=True):
    """Initializes and returns a Selenium Chrome webdriver."""
    if is_headless:
        print("Setting up HEADLESS Chrome driver (stealth mode)...")
    else:
        print("Setting up VISIBLE Chrome driver (debug mode)...")
        
    options = Options()
    
    if is_headless:
        options.add_argument("--headless") 
        
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Suppress logging
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # --- Set a 45-second timeout for all page loads ---
    driver.set_page_load_timeout(45)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def handle_cookie_banner(driver, wait):
    """Tries to find and click the 'Accept all cookies' cookie banner."""
    try:
        agree_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(., 'Accept all cookies')]")
        ))
        agree_button.click()
        time.sleep(1) # Give banner time to disappear
    except (TimeoutException, NoSuchElementException):
        print(" > Cookie banner not found or not clickable. Continuing...")
    except Exception as e:
        print(f" > An error occurred clicking the cookie button: {e}")

def scrape_master_links(driver, wait):
    """
    Part 1: Scrapes all sub-category links, then scrapes all
    company links from within each sub-category.
    """
    print("--- Starting Part 1: Master Link Collector ---")
    
    start_url = "https://www.europages.co.uk/bs/food-related-products/wines"
    try:
        driver.get(start_url)
    except Exception as e:
        print(f"Error loading start URL: {e}")
        return []

    print("Looking for cookie banner on category page...")
    handle_cookie_banner(driver, wait)

    print("Scraping sub-category links...")
    sub_category_links = []
    try:
        wait.until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Fortified wines")))
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        main_content = soup.find('main')
        if not main_content:
            main_content = soup 
        
        links = main_content.find_all('a', href=True)
        for link in links:
            href = link['href']
            if href.startswith('/companies/'): 
                full_link = f"https://www.europages.co.uk{href}"
                sub_category_links.append(full_link)
        
        sub_category_links = list(set(sub_category_links)) 
        print(f"Found {len(sub_category_links)} sub-categories to scrape.")

    except Exception as e:
        print(f"CRITICAL: Could not find sub-category links. Error: {e}")
        return []

    if not sub_category_links:
        print("No sub-category links found. Aborting.")
        return []

    print("\n--- Now scraping company links from each sub-category... ---")
    all_company_links = set()
    
    for i, sub_cat_link in enumerate(sub_category_links):
        print(f"\nProcessing Sub-Category {i+1}/{len(sub_category_links)}: {sub_cat_link}")
        try:
            driver.get(sub_cat_link)
        except Exception as e:
            print(f"  > Page load timed out for sub-category. Skipping. Error: {e}")
            continue

        page_count = 1
        while True: 
            print(f"  > Scraping company list page {page_count}...")
            try:
                wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'a[data-test="company-name"]')
                ))
                
                soup = BeautifulSoup(driver.page_source, 'lxml')
                company_cards = soup.find_all('a', {'data-test': 'company-name'})
                
                if not company_cards:
                    print("  > Found 0 company cards. Assuming empty category.")
                    break

                for card in company_cards:
                    if card.has_attr('href'):
                        href = card['href']
                        if href.startswith('/'):
                            href = f"https://www.europages.co.uk{href}"
                        all_company_links.add(href)
                
                next_button = driver.find_element(By.XPATH, "//a[.//img[@alt='Next']]")
                if 'disabled' in next_button.get_attribute('class'):
                    print("  > Next button disabled. Last page for this sub-category.")
                    break
                
                driver.execute_script("arguments[0].click();", next_button)
                page_count += 1
                time.sleep(1) 

            except (TimeoutException, NoSuchElementException):
                print("  > No company links or 'Next' button found. Assuming last page.")
                break
            except Exception as e:
                print(f"  > Error on page {page_count}: {e}")
                break
    
    final_links_list = list(all_company_links)
    try:
        df = pd.DataFrame(final_links_list, columns=['url'])
        df.to_csv('output/links_wine.csv', index=False)
        print(f"\n--- Part 1 Complete. Found {len(final_links_list)} total unique company links. ---")
        return final_links_list
    except Exception as e:
        print(f"Error saving links to CSV: {e}")
        return []

def process_link(link):
    """
    Part 2: This is the function that each "worker" thread will run.
    It scrapes a SINGLE link.
    """
    
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    file_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp')
    junk_domains_list = ('example.com', 'wix.com', 'wixpress.com', 'sentry.io', 'cdn.com', 
                         'googletagmanager.com', 'domain.com', 'yourdomain.com', 'email.com', 
                         'mail.com', 'website.com', 'placeholder.com')
    priority_prefixes = ('info@', 'contact@', 'sales@', 'export@', 'office@', 
                         'admin@', 'hello@', 'enquiries@', 'support@')
    
    driver = None
    try:
        # Each thread gets its own headless driver
        driver = setup_driver(is_headless=True)
        wait = WebDriverWait(driver, 10) # 10-second wait for elements
        
        # 1. GET INFO FROM EUROPAGES PROFILE
        driver.get(link)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'a.company-name')))
        
        name = driver.find_element(By.CSS_SELECTOR, 'a.company-name').text.strip()
        country = driver.find_element(By.XPATH, "//span[contains(@class, 'vis-flag')]/following-sibling::span").text.strip()
        country = country.split(',')[0].strip()
        
        try:
            website_link_element = driver.find_element(By.XPATH, "//a[.//span[contains(@class, 'website-link')]]")
            website_url = website_link_element.get_attribute('href')
        except NoSuchElementException:
            driver.quit()
            return None

        # 2. VISIT EXTERNAL SITE
        driver.get(website_url)
        # We rely on the 45s page load timeout, not time.sleep()

        # 3. Handle Age Gate (simple version)
        age_gate_xpaths = ["//button[contains(., 'Sí')]", "//button[contains(., 'Yes')]", "//button[contains(., 'Enter')]"]
        for xpath in age_gate_xpaths:
            try:
                driver.find_element(By.XPATH, xpath).click()
                time.sleep(1) # Wait for click to register
                break
            except:
                pass

        # 4. SCRAPE FOR EMAIL (Landing Page)
        page_text = driver.page_source
        
        # 5. TRY /contact PAGE (smarter guess)
        try:
            contact_url = website_url.rstrip('/') + "/contact"
            driver.get(contact_url)
            page_text += driver.page_source # Add contact page HTML
        except Exception:
            pass # Fail silently

        # 6. Run the "Smart" Email Filter
        found_emails = set(email_pattern.findall(page_text))
        good_emails = []
        other_valid_emails = []

        for email in found_emails:
            email_low = email.lower()
            if email_low.endswith(file_extensions) or any(domain in email_low for domain in junk_domains_list):
                continue
            if email_low.startswith(priority_prefixes):
                good_emails.append(email_low)
            else:
                other_valid_emails.append(email_low)
        
        valid_email = None
        if good_emails:
            valid_email = good_emails[0]
        elif other_valid_emails:
            valid_email = other_valid_emails[0]
        
        if valid_email:
            print(f"  > SUCCESS: Found {valid_email} for {name}")
            driver.quit()
            return {'Name': name, 'Country': country, 'Email': valid_email}
        else:
            driver.quit()
            return None

    except Exception as e:
        # This will catch the 'invalid session id' or any other crash
        # and just terminate this one worker, not the whole script.
        print(f"  > THREAD FAILED for {link}: {e}")
        if driver:
            driver.quit()
        return None

def main():
    os.makedirs('output', exist_ok=True)
    print("Script started...")
    
    # --- Part 1: Scrape Links (Single Thread, VISIBLE) ---
    driver = None
    links = []
    try:
        # We use one VISIBLE driver for Part 1 to be reliable
        driver = setup_driver(is_headless=False) 
        wait = WebDriverWait(driver, 10) 
        
        links = scrape_master_links(driver, wait) 
        
    except Exception as e:
        print(f"An unexpected error occurred in Part 1: {e}")
    finally:
        if driver:
            driver.quit()
            print("Part 1 driver closed.")
    
    if not links:
        print("No links found. Stopping script.")
        print("Scraping finished.")
        return
        
    # --- Part 2: Process Links (Multi-Threaded, HEADLESS) ---
    print(f"\n--- Starting Part 2: Scraping External Details with {MAX_WORKERS} workers ---")
    all_details = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # process_link will run in parallel, each creating its own headless driver
        results = list(executor.map(process_link, links))
    
    all_details = [res for res in results if res is not None]

    if not all_details:
        print("No details were extracted. External scrapers may have failed.")
        print("Scraping finished.")
        return

    # --- Save Final Data ---
    try:
        df = pd.DataFrame(all_details)
        df.drop_duplicates(subset=['Email'], inplace=True)
        df.to_csv('output/emails_wine.csv', index=False)
        print(f"\n--- Part 2 Complete. Saved {len(df)} unique contacts to output/emails_wine.csv ---")
    except Exception as e:
        print(f"Error saving details to CSV: {e}")
        
    print("Scraping finished.")

if __name__ == "__main__":
    main()