"""
Modul Scraping Tokopedia
Menggunakan Selenium dan BeautifulSoup untuk mengambil data produk dari Tokopedia
dengan fitur keamanan dan validasi yang robust.
"""

import time
import random
import csv
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraping.log')
    ]
)
logger = logging.getLogger(__name__)

class TokopediaScraper:
    """
    Class untuk melakukan scraping data produk dari Tokopedia
    """
    
    def __init__(self):
        self.base_url = "https://www.tokopedia.com"
        self.search_url = "https://www.tokopedia.com/search"
        self.driver = None
        self.session = requests.Session()
        
        # User agents untuk rotasi
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        # Konfigurasi delay (dalam detik)
        self.min_delay = 2
        self.max_delay = 5
        self.page_delay = 3
        
        # Rate limiting
        self.requests_count = 0
        self.max_requests_per_minute = 30
        self.last_request_time = time.time()
        
        # Timeout dan retry configuration
        self.request_timeout = 30
        self.max_retries = 3
        self.retry_delay = 5
        
        # Monitoring variables
        self.start_time = None
        self.error_count = 0
        self.success_count = 0
        
        logger.info("🚀 TokopediaScraper initialized with enhanced monitoring")
        
    def check_internet_connection(self) -> bool:
        """Check if internet connection is available"""
        try:
            response = requests.get("https://www.google.com", timeout=5)
            logger.info("✅ Internet connection: OK")
            return response.status_code == 200
        except requests.RequestException as e:
            logger.error(f"❌ Internet connection failed: {e}")
            return False
    
    def check_website_accessibility(self) -> bool:
        """Check if Tokopedia website is accessible"""
        try:
            response = requests.get(self.base_url, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Tokopedia website: Accessible")
                return True
            else:
                logger.warning(f"⚠️ Tokopedia returned status code: {response.status_code}")
                return False
        except requests.RequestException as e:
            logger.error(f"❌ Tokopedia website not accessible: {e}")
            return False
    
    def monitor_system_resources(self):
        """Monitor CPU and memory usage"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        logger.info(f"📊 System Resources - CPU: {cpu_percent}%, Memory: {memory.percent}% ({memory.used // (1024**2)}MB used)")
        
        if cpu_percent > 80:
            logger.warning(f"⚠️ High CPU usage detected: {cpu_percent}%")
        if memory.percent > 80:
            logger.warning(f"⚠️ High memory usage detected: {memory.percent}%")
    
    def calculate_eta(self, current_count: int, total_count: int, start_time: datetime) -> str:
        """Calculate estimated time of arrival"""
        if current_count == 0:
            return "Calculating..."
        
        elapsed = datetime.now() - start_time
        rate = current_count / elapsed.total_seconds()
        remaining = total_count - current_count
        eta_seconds = remaining / rate if rate > 0 else 0
        
        eta = timedelta(seconds=int(eta_seconds))
        return str(eta)
        
    def _setup_driver(self) -> bool:
        """
        Setup Selenium WebDriver dengan konfigurasi keamanan dan retry mechanism
        """
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
                
                # Rotasi user agent
                user_agent = random.choice(self.user_agents)
                chrome_options.add_argument(f"--user-agent={user_agent}")
                logger.info(f"🎭 Using User Agent: {user_agent[:50]}...")
                
                # Headless mode untuk production
                # chrome_options.add_argument("--headless")
                
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # Set timeout untuk page load
                self.driver.set_page_load_timeout(self.request_timeout)
                
                logger.info("✅ WebDriver setup successful")
                return True
                
            except Exception as e:
                logger.error(f"❌ WebDriver setup failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"⏳ Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("❌ All WebDriver setup attempts failed")
                    return False
        
        return False
    
    def _apply_rate_limiting(self):
        """
        Implementasi rate limiting untuk menghindari blokir
        """
        current_time = time.time()
        time_diff = current_time - self.last_request_time
        
        # Reset counter setiap menit
        if time_diff >= 60:
            self.requests_count = 0
            self.last_request_time = current_time
        
        # Jika sudah mencapai limit, tunggu
        if self.requests_count >= self.max_requests_per_minute:
            wait_time = 60 - time_diff
            if wait_time > 0:
                print(f"⏳ Rate limit reached. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                self.requests_count = 0
                self.last_request_time = time.time()
        
        self.requests_count += 1
    
    def _random_delay(self):
        """
        Implementasi delay random antara request
        """
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
    
    def validate_input(self, keyword: str, max_products: int) -> Tuple[bool, str]:
        """
        Validasi input parameter
        
        Args:
            keyword: Kata kunci pencarian
            max_products: Jumlah maksimal produk
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not keyword or len(keyword.strip()) < 2:
            return False, "Keyword harus minimal 2 karakter"
        
        if not isinstance(max_products, int) or max_products < 1:
            return False, "Jumlah produk harus berupa angka positif"
        
        if max_products > 1000:
            return False, "Jumlah produk maksimal adalah 1000"
        
        # Validasi karakter berbahaya
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`']
        if any(char in keyword for char in dangerous_chars):
            return False, "Keyword mengandung karakter yang tidak diizinkan"
        
        return True, ""
    
    def _extract_product_data(self, product_element) -> Optional[Dict]:
        """
        Ekstrak data produk dari element HTML dengan logging detail
        
        Args:
            product_element: Element HTML produk
            
        Returns:
            Dictionary dengan data produk atau None jika gagal
        """
        try:
            product_data = {}
            extraction_errors = []
            
            # Nama produk
            try:
                name_element = product_element.find_element(By.CSS_SELECTOR, "[data-testid='linkProductName']")
                product_data['nama_produk'] = name_element.text.strip()
            except NoSuchElementException:
                try:
                    name_element = product_element.find_element(By.CSS_SELECTOR, ".prd_link-product-name")
                    product_data['nama_produk'] = name_element.text.strip()
                except NoSuchElementException:
                    product_data['nama_produk'] = "N/A"
                    extraction_errors.append("nama_produk")
            
            # Harga
            try:
                price_element = product_element.find_element(By.CSS_SELECTOR, "[data-testid='linkProductPrice']")
                price_text = price_element.text.strip()
                # Bersihkan format harga (hapus Rp, titik, dll)
                price_clean = re.sub(r'[^\d]', '', price_text)
                product_data['harga'] = int(price_clean) if price_clean else 0
                product_data['harga_formatted'] = price_text
            except (NoSuchElementException, ValueError) as e:
                product_data['harga'] = 0
                product_data['harga_formatted'] = "N/A"
                extraction_errors.append("harga")
            
            # Rating
            try:
                rating_element = product_element.find_element(By.CSS_SELECTOR, "[data-testid='linkProductRating']")
                rating_text = rating_element.text.strip()
                rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                product_data['rating'] = float(rating_match.group(1)) if rating_match else 0.0
            except (NoSuchElementException, ValueError):
                product_data['rating'] = 0.0
                extraction_errors.append("rating")
            
            # Jumlah review
            try:
                review_element = product_element.find_element(By.CSS_SELECTOR, "[data-testid='linkProductRating']")
                review_text = review_element.text.strip()
                # Cari pola seperti "(123)" atau "123 ulasan"
                review_match = re.search(r'\((\d+)\)|(\d+)\s*ulasan', review_text)
                if review_match:
                    product_data['jumlah_review'] = int(review_match.group(1) or review_match.group(2))
                else:
                    product_data['jumlah_review'] = 0
            except (NoSuchElementException, ValueError):
                product_data['jumlah_review'] = 0
                extraction_errors.append("jumlah_review")
            
            # Toko
            try:
                shop_element = product_element.find_element(By.CSS_SELECTOR, "[data-testid='linkShopName']")
                product_data['nama_toko'] = shop_element.text.strip()
            except NoSuchElementException:
                product_data['nama_toko'] = "N/A"
                extraction_errors.append("nama_toko")
            
            # Lokasi
            try:
                location_element = product_element.find_element(By.CSS_SELECTOR, "[data-testid='linkShopLoc']")
                product_data['lokasi'] = location_element.text.strip()
            except NoSuchElementException:
                product_data['lokasi'] = "N/A"
                extraction_errors.append("lokasi")
            
            # URL produk
            try:
                link_element = product_element.find_element(By.CSS_SELECTOR, "[data-testid='linkProductName']")
                product_data['url'] = link_element.get_attribute('href')
            except NoSuchElementException:
                product_data['url'] = "N/A"
                extraction_errors.append("url")
            
            # Timestamp
            product_data['scraped_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Log jika ada field yang gagal diekstrak
            if extraction_errors:
                logger.debug(f"⚠️ Field gagal diekstrak untuk '{product_data.get('nama_produk', 'Unknown')}': {', '.join(extraction_errors)}")
            
            # Validasi produk minimal harus punya nama
            if product_data['nama_produk'] == "N/A":
                logger.debug("❌ Produk ditolak: tidak ada nama produk")
                return None
            
            return product_data
            
        except Exception as e:
            logger.warning(f"❌ Error extracting product data: {e}")
            return None
    
    def scrape_products(self, keyword: str, max_products: int = 50, progress_callback=None) -> List[Dict]:
        """
        Scrape produk dari Tokopedia berdasarkan keyword dengan monitoring detail
        
        Args:
            keyword: Kata kunci pencarian
            max_products: Jumlah maksimal produk yang akan di-scrape
            progress_callback: Callback function untuk update progress
            
        Returns:
            List dictionary dengan data produk
        """
        # Initialize monitoring
        self.start_time = datetime.now()
        self.error_count = 0
        self.success_count = 0
        
        logger.info("="*80)
        logger.info(f"🚀 MEMULAI PROSES SCRAPING")
        logger.info(f"📝 Keyword: '{keyword}'")
        logger.info(f"🎯 Target: {max_products} produk")
        logger.info(f"⏰ Waktu mulai: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        # Validasi input
        is_valid, error_msg = self.validate_input(keyword, max_products)
        if not is_valid:
            logger.error(f"❌ Validasi input gagal: {error_msg}")
            raise ValueError(error_msg)
        
        logger.info("✅ Validasi input berhasil")
        
        # Periksa komponen sistem
        logger.info("🔍 MEMERIKSA KOMPONEN SISTEM...")
        if not self.check_internet_connection():
            raise Exception("Koneksi internet tidak tersedia")
        
        if not self.check_website_accessibility():
            raise Exception("Website Tokopedia tidak dapat diakses")
        
        # Monitor resource awal
        self.monitor_system_resources()
        
        products = []
        
        try:
            # Setup driver dengan retry
            logger.info("🔧 SETUP WEBDRIVER...")
            if not self._setup_driver():
                raise Exception("Gagal setup WebDriver setelah beberapa percobaan")
            
            if progress_callback:
                progress_callback(10, "WebDriver berhasil disetup")
            
            # Navigasi ke halaman pencarian
            search_url = f"{self.search_url}?st=product&q={keyword.replace(' ', '%20')}"
            logger.info(f"🌐 Navigasi ke: {search_url}")
            
            self._apply_rate_limiting()
            
            # Retry mechanism untuk page load
            for attempt in range(self.max_retries):
                try:
                    self.driver.get(search_url)
                    logger.info(f"✅ Halaman berhasil dimuat (attempt {attempt + 1})")
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Gagal memuat halaman (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                    else:
                        raise Exception("Gagal memuat halaman setelah beberapa percobaan")
            
            self._random_delay()
            
            if progress_callback:
                progress_callback(20, f"Mengakses halaman pencarian: {keyword}")
            
            page = 1
            products_scraped = 0
            consecutive_errors = 0
            max_consecutive_errors = 3
            
            logger.info("📊 MEMULAI EKSTRAKSI DATA...")
            
            while products_scraped < max_products:
                try:
                    logger.info(f"📄 Memproses halaman {page}...")
                    
                    # Monitor resource setiap 5 halaman
                    if page % 5 == 0:
                        self.monitor_system_resources()
                    
                    # Wait untuk produk load dengan timeout
                    try:
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='master-product-card']"))
                        )
                        logger.info("✅ Produk berhasil dimuat")
                    except TimeoutException:
                        logger.warning("⚠️ Timeout menunggu produk dimuat")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error("❌ Terlalu banyak error berturut-turut, menghentikan scraping")
                            break
                        continue
                    
                    # Scroll untuk load lazy content
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    # Ambil semua produk di halaman ini
                    product_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='master-product-card']")
                    
                    if not product_elements:
                        logger.warning("⚠️ Tidak ada produk ditemukan di halaman ini")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            break
                        continue
                    
                    logger.info(f"🔍 Ditemukan {len(product_elements)} elemen produk di halaman {page}")
                    
                    page_products = 0
                    page_errors = 0
                    
                    for i, element in enumerate(product_elements):
                        if products_scraped >= max_products:
                            break
                        
                        try:
                            product_data = self._extract_product_data(element)
                            if product_data and product_data['nama_produk'] != "N/A":
                                products.append(product_data)
                                products_scraped += 1
                                page_products += 1
                                self.success_count += 1
                                
                                # Log progress setiap 10 produk
                                if products_scraped % 10 == 0:
                                    progress_percent = (products_scraped / max_products) * 100
                                    eta = self.calculate_eta(products_scraped, max_products, self.start_time)
                                    error_rate = (self.error_count / (self.success_count + self.error_count)) * 100 if (self.success_count + self.error_count) > 0 else 0
                                    
                                    logger.info(f"📈 Progress: {products_scraped}/{max_products} ({progress_percent:.1f}%) | ETA: {eta} | Error Rate: {error_rate:.1f}%")
                                
                                if progress_callback:
                                    progress = 20 + (products_scraped / max_products) * 70
                                    progress_callback(int(progress), f"Scraped {products_scraped}/{max_products} produk")
                            else:
                                page_errors += 1
                                self.error_count += 1
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Error ekstraksi produk {i+1}: {e}")
                            page_errors += 1
                            self.error_count += 1
                    
                    # Reset consecutive errors jika halaman ini berhasil
                    if page_products > 0:
                        consecutive_errors = 0
                    
                    logger.info(f"✅ Halaman {page} selesai: {page_products} produk berhasil, {page_errors} error")
                    
                    # Cek apakah sudah cukup atau perlu ke halaman berikutnya
                    if products_scraped >= max_products:
                        logger.info(f"🎯 Target {max_products} produk tercapai!")
                        break
                    
                    # Cari tombol next page
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='btnShopProductPageNext']")
                        if next_button.is_enabled():
                            logger.info(f"➡️ Navigasi ke halaman {page + 1}")
                            self._apply_rate_limiting()
                            next_button.click()
                            time.sleep(self.page_delay)
                            page += 1
                        else:
                            logger.info("📄 Sudah mencapai halaman terakhir")
                            break
                    except NoSuchElementException:
                        logger.info("📄 Tidak ada halaman berikutnya")
                        break
                        
                except TimeoutException:
                    logger.error("⏰ Timeout waiting for products to load")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        break
                except Exception as e:
                    logger.error(f"❌ Error pada halaman {page}: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        break
            
            # Summary logging
            end_time = datetime.now()
            duration = end_time - self.start_time
            error_rate = (self.error_count / (self.success_count + self.error_count)) * 100 if (self.success_count + self.error_count) > 0 else 0
            
            logger.info("="*80)
            logger.info("📊 RINGKASAN SCRAPING")
            logger.info(f"✅ Produk berhasil: {len(products)}")
            logger.info(f"❌ Total error: {self.error_count}")
            logger.info(f"📈 Success rate: {(len(products)/(len(products)+self.error_count))*100:.1f}%")
            logger.info(f"⏱️ Durasi: {duration}")
            logger.info(f"🏁 Selesai pada: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*80)
            
            if progress_callback:
                progress_callback(100, f"Selesai! Total {len(products)} produk berhasil di-scrape")
            
            return products
            
        except Exception as e:
            logger.error(f"❌ Error critical during scraping: {e}")
            raise
        finally:
            if self.driver:
                logger.info("🔧 Menutup WebDriver...")
                self.driver.quit()
                logger.info("✅ WebDriver ditutup")
    
    def save_to_csv(self, products: List[Dict], filename: str = None) -> str:
        """
        Simpan data produk ke file CSV dengan logging detail
        
        Args:
            products: List data produk
            filename: Nama file (optional)
            
        Returns:
            Path file yang disimpan
        """
        if not products:
            logger.warning("⚠️ Tidak ada data produk untuk disimpan")
            raise ValueError("Tidak ada data produk untuk disimpan")
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tokopedia_scraping_{timestamp}.csv"
        
        # Pastikan direktori uploads ada
        uploads_dir = "uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        
        filepath = os.path.join(uploads_dir, filename)
        
        logger.info(f"💾 Menyimpan {len(products)} produk ke: {filepath}")
        
        # Kolom yang akan disimpan
        columns = [
            'nama_produk', 'harga', 'harga_formatted', 'rating', 
            'jumlah_review', 'nama_toko', 'lokasi', 'url', 'scraped_at'
        ]
        
        try:
            df = pd.DataFrame(products)
            df = df.reindex(columns=columns, fill_value='N/A')
            df.to_csv(filepath, index=False, encoding='utf-8')
            
            # Log statistik data
            logger.info("📊 STATISTIK DATA TERSIMPAN:")
            logger.info(f"   📦 Total produk: {len(df)}")
            logger.info(f"   💰 Harga rata-rata: Rp {df[df['harga'] > 0]['harga'].mean():,.0f}" if len(df[df['harga'] > 0]) > 0 else "   💰 Harga rata-rata: N/A")
            logger.info(f"   ⭐ Rating rata-rata: {df[df['rating'] > 0]['rating'].mean():.1f}" if len(df[df['rating'] > 0]) > 0 else "   ⭐ Rating rata-rata: N/A")
            logger.info(f"   🏪 Jumlah toko unik: {df['nama_toko'].nunique()}")
            logger.info(f"   📍 Jumlah lokasi unik: {df['lokasi'].nunique()}")
            
            logger.info(f"✅ Data berhasil disimpan ke: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Error saving to CSV: {e}")
            raise

def scrape_tokopedia_data(keyword: str, max_products: int = 50, progress_callback=None) -> Tuple[List[Dict], str]:
    """
    Function wrapper untuk scraping Tokopedia dengan monitoring lengkap
    
    Args:
        keyword: Kata kunci pencarian
        max_products: Jumlah maksimal produk
        progress_callback: Callback untuk progress update
        
    Returns:
        Tuple (products_data, csv_filepath)
    """
    logger.info("🎬 MEMULAI SCRAPING TOKOPEDIA")
    logger.info(f"📋 Parameter: keyword='{keyword}', max_products={max_products}")
    
    scraper = TokopediaScraper()
    
    try:
        # Scrape data dengan monitoring
        logger.info("🔄 Memulai proses scraping...")
        products = scraper.scrape_products(keyword, max_products, progress_callback)
        
        if not products:
            logger.error("❌ Tidak ada data produk yang berhasil di-scrape")
            raise Exception("Tidak ada data produk yang berhasil di-scrape")
        
        logger.info(f"✅ Scraping selesai: {len(products)} produk berhasil dikumpulkan")
        
        # Simpan ke CSV
        logger.info("💾 Menyimpan data ke CSV...")
        csv_path = scraper.save_to_csv(products)
        logger.info(f"✅ Data berhasil disimpan ke: {csv_path}")
        
        logger.info("🎉 SCRAPING TOKOPEDIA SELESAI DENGAN SUKSES!")
        return products, csv_path
        
    except Exception as e:
        logger.error(f"❌ Scraping failed: {e}")
        raise