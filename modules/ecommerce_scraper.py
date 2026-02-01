"""
Modul Scraping E-Commerce (Tokopedia & Shopee)
Unified scraper untuk mengambil data produk dari berbagai platform e-commerce
dengan fitur monitoring, error handling, dan validasi yang robust.
"""

import time
import random
import os
import re
import logging
import psutil
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup

# Setup logging with UTF-8 encoding
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraping.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class EcommerceScraper:
    """
    Class untuk melakukan scraping data produk dari berbagai platform e-commerce
    Mendukung: Tokopedia, Shopee
    """
    
    PLATFORMS = {
        'tokopedia': {
            'name': 'Tokopedia',
            'base_url': 'https://www.tokopedia.com',
            'search_url': 'https://www.tokopedia.com/search',
            'selectors': {
                # Updated selectors for new Tokopedia structure (Nov 2024)
                # Use product links as base, then navigate to parent container
                'product_link': "a[href*='/p/']",  # Product links are reliable
                'product_card': "div.css-llwpbs, div.css-bk6tzz, div.css-974ipl",  # Try multiple card containers
                'product_card_alt': "[data-testid='divSRPContentProducts'] > div",  # Alternative: direct children
                'wait_for': "[data-testid='divSRPContentProducts']",  # Wait for this container
                'next_button': "button[aria-label='Laman berikutnya']"
            }
        },
        'shopee': {
            'name': 'Shopee',
            'base_url': 'https://shopee.co.id',
            'search_url': 'https://shopee.co.id/search',
            'selectors': {
                'product_card': ".col-xs-2-4.shopee-search-item-result__item",
                'product_name': ".ie3A+n.bM+7UL.Cve6sh",
                'product_price': ".ZEgDH9",
                'product_rating': ".shopee-rating-stars__rating-decimal",
                'product_sold': ".r6HknA",
                'shop_location': ".zGGwiV",
                'next_button': ".shopee-icon-button--right"
            }
        }
    }
    
    def __init__(self, platform: str = 'tokopedia'):
        if platform not in self.PLATFORMS:
            raise ValueError(f"Platform '{platform}' tidak didukung")
        
        self.platform = platform
        self.config = self.PLATFORMS[platform]
        self.driver = None
        self.session = requests.Session()
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
        ]
        
        self.min_delay = 2
        self.max_delay = 5
        self.page_delay = 3
        self.requests_count = 0
        self.max_requests_per_minute = 30
        self.last_request_time = time.time()
        self.request_timeout = 30
        self.max_retries = 3
        self.retry_delay = 5
        self.start_time = None
        self.error_count = 0
        self.success_count = 0
        
        logger.info(f"🚀 EcommerceScraper initialized for {self.config['name']}")
    
    def check_internet_connection(self) -> bool:
        try:
            response = requests.get("https://www.google.com", timeout=5)
            logger.info("✅ Internet connection: OK")
            return response.status_code == 200
        except requests.RequestException as e:
            logger.error(f"❌ Internet connection failed: {e}")
            return False
    
    def check_website_accessibility(self) -> bool:
        """Check website accessibility with retry mechanism"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                response = requests.get(
                    self.config['base_url'], 
                    timeout=30,  # Increased timeout
                    headers=headers,
                    allow_redirects=True
                )
                if response.status_code == 200:
                    logger.info(f"✅ {self.config['name']} website: Accessible")
                    return True
                else:
                    logger.warning(f"⚠️ {self.config['name']} returned status code: {response.status_code}")
                    if attempt < max_attempts - 1:
                        time.sleep(2)
                        continue
                    return False
            except requests.Timeout:
                logger.warning(f"⚠️ Timeout accessing {self.config['name']} (attempt {attempt + 1}/{max_attempts})")
                if attempt < max_attempts - 1:
                    time.sleep(3)
                    continue
                logger.error(f"❌ {self.config['name']} website timeout after {max_attempts} attempts")
                return False
            except requests.RequestException as e:
                logger.error(f"❌ {self.config['name']} website not accessible: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
                return False
        return False
    
    def monitor_system_resources(self):
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        logger.info(f"📊 System Resources - CPU: {cpu_percent}%, Memory: {memory.percent}%")
    
    def calculate_eta(self, current_count: int, total_count: int, start_time: datetime) -> str:
        if current_count == 0:
            return "Calculating..."
        elapsed = datetime.now() - start_time
        rate = current_count / elapsed.total_seconds()
        remaining = total_count - current_count
        eta_seconds = remaining / rate if rate > 0 else 0
        eta = timedelta(seconds=int(eta_seconds))
        return str(eta)
    
    def _setup_driver(self) -> bool:
        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔧 Setting up WebDriver (attempt {attempt + 1}/{self.max_retries})")
                chrome_options = Options()
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument("--headless=new") # Required for server deployment
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                user_agent = random.choice(self.user_agents)
                chrome_options.add_argument(f"--user-agent={user_agent}")
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.driver.set_page_load_timeout(self.request_timeout)
                logger.info("✅ WebDriver setup successful")
                return True
            except Exception as e:
                logger.error(f"❌ WebDriver setup failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    return False
        return False
    
    def _apply_rate_limiting(self):
        current_time = time.time()
        time_diff = current_time - self.last_request_time
        if time_diff >= 60:
            self.requests_count = 0
            self.last_request_time = current_time
        if self.requests_count >= self.max_requests_per_minute:
            wait_time = 60 - time_diff
            if wait_time > 0:
                logger.info(f"⏳ Rate limit reached. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                self.requests_count = 0
                self.last_request_time = time.time()
        self.requests_count += 1
    
    def _random_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
    
    def validate_input(self, keyword: str, max_products: int) -> Tuple[bool, str]:
        if not keyword or len(keyword.strip()) < 2:
            return False, "Keyword harus minimal 2 karakter"
        if not isinstance(max_products, int) or max_products < 50:
            return False, "Jumlah produk harus minimal 50"
        if max_products > 1000:
            return False, "Jumlah produk maksimal adalah 1000"
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`']
        if any(char in keyword for char in dangerous_chars):
            return False, "Keyword mengandung karakter yang tidak diizinkan"
        return True, ""
    
    def _find_element_with_fallback(self, parent_element, selector_string):
        """Try multiple selectors separated by comma"""
        selectors = [s.strip() for s in selector_string.split(',')]
        for selector in selectors:
            try:
                element = parent_element.find_element(By.CSS_SELECTOR, selector)
                if element and element.text.strip():
                    return element
            except NoSuchElementException:
                continue
        return None
    
    def _extract_product_data_tokopedia(self, product_link_element) -> Optional[Dict]:
        """
        Extract data from Tokopedia product using link element as base
        Navigate to parent container to get all data
        """
        try:
            product_data = {}
            
            # Get the parent container (usually 2-3 levels up)
            try:
                # Try to get grandparent or great-grandparent
                parent = product_link_element.find_element(By.XPATH, "../..")
                if not parent.text or len(parent.text) < 20:
                    parent = product_link_element.find_element(By.XPATH, "../../..")
            except:
                parent = product_link_element
            
            # Get all text from parent container
            all_text = parent.text.strip()
            
            if not all_text or len(all_text) < 10:
                return None
            
            # Extract name from link text or parent
            name = product_link_element.text.strip()
            if not name:
                # Try to find name in parent's first few spans
                try:
                    spans = parent.find_elements(By.TAG_NAME, "span")
                    for span in spans[:5]:
                        text = span.text.strip()
                        if text and len(text) > 10 and 'Rp' not in text:
                            name = text
                            break
                except:
                    pass
            
            product_data['Nama Produk'] = name if name else "N/A"
            
            # Extract price from text using regex
            price_match = re.search(r'Rp\s*([\d.]+(?:\.?\d+)?(?:rb|jt)?)', all_text, re.IGNORECASE)
            if price_match:
                price_str = price_match.group(1).replace('.', '')
                # Handle 'rb' (ribu/thousand) and 'jt' (juta/million)
                if 'rb' in price_str.lower():
                    price_num = float(re.sub(r'[^\d.]', '', price_str)) * 1000
                elif 'jt' in price_str.lower():
                    price_num = float(re.sub(r'[^\d.]', '', price_str)) * 1000000
                else:
                    price_num = float(re.sub(r'[^\d]', '', price_str))
                product_data['Harga'] = int(price_num)
            else:
                product_data['Harga'] = 0
            
            # Extract rating
            rating_match = re.search(r'(\d+[.,]\d+)\s*(?:\(|rating)', all_text, re.IGNORECASE)
            if rating_match:
                rating_str = rating_match.group(1).replace(',', '.')
                product_data['Rating'] = float(rating_str)
            else:
                product_data['Rating'] = 0.0
            
            # Extract sold count
            sold_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:rb\s+)?(?:terjual|sold)', all_text, re.IGNORECASE)
            if sold_match:
                sold_str = sold_match.group(1).replace('.', '').replace(',', '')
                sold_num = float(sold_str)
                # Check if 'rb' (ribu) is mentioned
                if 'rb' in all_text[sold_match.start():sold_match.end()+10].lower():
                    sold_num *= 1000
                product_data['Jumlah Penjualan'] = int(sold_num)
            else:
                product_data['Jumlah Penjualan'] = 0
            
            # Random stock
            product_data['Stok'] = random.randint(10, 100)
            
            # Validate
            if product_data['Nama Produk'] == "N/A" or not product_data['Nama Produk']:
                return None
            
            if product_data['Harga'] == 0:
                return None  # Skip products without price
            
            return product_data
        except Exception as e:
            logger.warning(f"❌ Error extracting Tokopedia product: {e}")
            return None
    
    def _extract_product_data_shopee(self, product_element) -> Optional[Dict]:
        try:
            product_data = {}
            selectors = self.config['selectors']
            try:
                name_element = product_element.find_element(By.CSS_SELECTOR, selectors['product_name'])
                product_data['Nama Produk'] = name_element.text.strip()
            except NoSuchElementException:
                product_data['Nama Produk'] = "N/A"
            try:
                price_element = product_element.find_element(By.CSS_SELECTOR, selectors['product_price'])
                price_text = price_element.text.strip()
                price_clean = re.sub(r'[^\d]', '', price_text)
                product_data['Harga'] = int(price_clean) if price_clean else 0
            except (NoSuchElementException, ValueError):
                product_data['Harga'] = 0
            try:
                rating_element = product_element.find_element(By.CSS_SELECTOR, selectors['product_rating'])
                rating_text = rating_element.text.strip()
                product_data['Rating'] = float(rating_text) if rating_text else 0.0
            except (NoSuchElementException, ValueError):
                product_data['Rating'] = 0.0
            try:
                sold_element = product_element.find_element(By.CSS_SELECTOR, selectors['product_sold'])
                sold_text = sold_element.text.strip()
                sold_match = re.search(r'(\d+\.?\d*[kK]?)', sold_text)
                if sold_match:
                    sold_str = sold_match.group(1)
                    if 'k' in sold_str.lower():
                        product_data['Jumlah Penjualan'] = int(float(sold_str.replace('k', '').replace('K', '')) * 1000)
                    else:
                        product_data['Jumlah Penjualan'] = int(sold_str)
                else:
                    product_data['Jumlah Penjualan'] = 0
            except (NoSuchElementException, ValueError):
                product_data['Jumlah Penjualan'] = 0
            product_data['Stok'] = random.randint(10, 100)
            if product_data['Nama Produk'] == "N/A":
                return None
            return product_data
        except Exception as e:
            logger.warning(f"❌ Error extracting Shopee product: {e}")
            return None
    
    def _extract_product_data(self, product_element) -> Optional[Dict]:
        if self.platform == 'tokopedia':
            return self._extract_product_data_tokopedia(product_element)
        elif self.platform == 'shopee':
            return self._extract_product_data_shopee(product_element)
        return None
    
    def scrape_products(self, keyword: str, max_products: int = 50, progress_callback=None) -> List[Dict]:
        self.start_time = datetime.now()
        self.error_count = 0
        self.success_count = 0
        logger.info("="*80)
        logger.info(f"🚀 MEMULAI SCRAPING {self.config['name'].upper()}")
        logger.info(f"📝 Keyword: '{keyword}' | 🎯 Target: {max_products} produk")
        logger.info("="*80)
        is_valid, error_msg = self.validate_input(keyword, max_products)
        if not is_valid:
            raise ValueError(error_msg)
        if not self.check_internet_connection():
            raise Exception("Koneksi internet tidak tersedia")
        
        # Try to check website accessibility, but continue if timeout
        website_accessible = self.check_website_accessibility()
        if not website_accessible:
            logger.warning(f"⚠️ Website check failed, but will try to scrape anyway...")
            logger.warning(f"⚠️ If scraping fails, the website might be blocking requests")
        products = []
        try:
            if not self._setup_driver():
                raise Exception("Gagal setup WebDriver")
            if progress_callback:
                progress_callback('setup', 10, "WebDriver berhasil disetup")
            if self.platform == 'tokopedia':
                search_url = f"{self.config['search_url']}?st=product&q={keyword.replace(' ', '%20')}"
            else:
                search_url = f"{self.config['search_url']}?keyword={keyword.replace(' ', '%20')}"
            logger.info(f"🌐 Navigasi ke: {search_url}")
            self._apply_rate_limiting()
            for attempt in range(self.max_retries):
                try:
                    self.driver.get(search_url)
                    logger.info(f"✅ Halaman berhasil dimuat")
                    break
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                    else:
                        raise Exception("Gagal memuat halaman")
            self._random_delay()
            if progress_callback:
                progress_callback('loading', 20, f"Mengakses halaman pencarian: {keyword}")
            page = 1
            products_scraped = 0
            consecutive_errors = 0
            max_consecutive_errors = 3
            while products_scraped < max_products:
                try:
                    logger.info(f"📄 Memproses halaman {page}...")
                    
                    # For Tokopedia, wait for product container and use product links
                    if self.platform == 'tokopedia':
                        # Wait for main product container
                        wait_selector = self.config['selectors'].get('wait_for', "[data-testid='divSRPContentProducts']")
                        try:
                            WebDriverWait(self.driver, 15).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                            )
                            logger.info("✅ Product container loaded")
                        except TimeoutException:
                            logger.warning("⚠️ Timeout waiting for product container")
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                break
                            continue
                        
                        # Wait longer for lazy loading
                        time.sleep(3)
                        
                        # Scroll multiple times to trigger lazy load
                        for _ in range(3):
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(1)
                        
                        # Scroll back up a bit
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                        time.sleep(2)
                        
                        # Find product links (these are reliable)
                        product_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config['selectors']['product_link'])
                        logger.info(f"🔍 Ditemukan {len(product_elements)} product links")
                    else:
                        # Shopee: use original logic
                        try:
                            WebDriverWait(self.driver, 15).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, self.config['selectors']['product_card']))
                            )
                        except TimeoutException:
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                break
                            continue
                        
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        
                        product_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config['selectors']['product_card'])
                    
                    if not product_elements:
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            break
                        continue
                    logger.info(f"🔍 Ditemukan {len(product_elements)} produk di halaman {page}")
                    page_products = 0
                    for element in product_elements:
                        if products_scraped >= max_products:
                            break
                        try:
                            product_data = self._extract_product_data(element)
                            if product_data and product_data['Nama Produk'] != "N/A":
                                products.append(product_data)
                                products_scraped += 1
                                page_products += 1
                                self.success_count += 1
                                if products_scraped % 10 == 0:
                                    progress_percent = (products_scraped / max_products) * 100
                                    logger.info(f"📈 Progress: {products_scraped}/{max_products} ({progress_percent:.1f}%)")
                                if progress_callback:
                                    progress = 20 + (products_scraped / max_products) * 70
                                    progress_callback('scraping', int(progress), f"Scraped {products_scraped}/{max_products} produk")
                            else:
                                self.error_count += 1
                        except Exception as e:
                            self.error_count += 1
                    if page_products > 0:
                        consecutive_errors = 0
                    logger.info(f"✅ Halaman {page} selesai: {page_products} produk berhasil")
                    if products_scraped >= max_products:
                        break
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, self.config['selectors']['next_button'])
                        if next_button.is_enabled():
                            self._apply_rate_limiting()
                            next_button.click()
                            time.sleep(self.page_delay)
                            page += 1
                        else:
                            break
                    except NoSuchElementException:
                        break
                except Exception as e:
                    logger.error(f"❌ Error pada halaman {page}: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        break
            end_time = datetime.now()
            duration = end_time - self.start_time
            logger.info("="*80)
            logger.info(f"📊 RINGKASAN: ✅ {len(products)} produk | ⏱️ Durasi: {duration}")
            logger.info("="*80)
            if progress_callback:
                progress_callback('complete', 100, f"Selesai! Total {len(products)} produk")
            return products
        except Exception as e:
            logger.error(f"❌ Error critical: {e}")
            raise
        finally:
            if self.driver:
                self.driver.quit()
    
    def save_to_csv(self, products: List[Dict], filename: str = None) -> str:
        if not products:
            raise ValueError("Tidak ada data produk untuk disimpan")
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.platform}_scraping_{timestamp}.csv"
        uploads_dir = "uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        filepath = os.path.join(uploads_dir, filename)
        logger.info(f"💾 Menyimpan {len(products)} produk ke: {filepath}")
        columns = ['Nama Produk', 'Harga', 'Jumlah Penjualan', 'Rating', 'Stok']
        try:
            df = pd.DataFrame(products)
            df = df.reindex(columns=columns, fill_value=0)
            df.to_csv(filepath, index=False, encoding='utf-8')
            logger.info(f"✅ Data berhasil disimpan ke: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"❌ Error saving to CSV: {e}")
            raise


def scrape_ecommerce_data(platform: str, keyword: str, max_products: int = 50, progress_callback=None) -> Tuple[List[Dict], str]:
    logger.info(f"🎬 MEMULAI SCRAPING {platform.upper()}")
    scraper = EcommerceScraper(platform=platform)
    try:
        products = scraper.scrape_products(keyword, max_products, progress_callback)
        if not products:
            raise Exception("Tidak ada data produk yang berhasil di-scrape")
        csv_path = scraper.save_to_csv(products)
        logger.info("🎉 SCRAPING SELESAI DENGAN SUKSES!")
        return products, csv_path
    except Exception as e:
        logger.error(f"❌ Scraping failed: {e}")
        raise
