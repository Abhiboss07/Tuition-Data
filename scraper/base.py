"""
Base scraper class with common functionality
"""
import os
import time
import random
from typing import Optional, Dict, List
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from utils.logger import logger
from utils.classifier import classify_role, extract_subjects, extract_location, extract_experience


class BaseScraper:
    """Base class for all scrapers with common functionality"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        # Allow tuning via env
        env_retries = os.getenv("SCRAPER_MAX_RETRIES")
        self.max_retries = int(env_retries) if env_retries and env_retries.isdigit() else max_retries
        self.ua = UserAgent()
        self.session = requests.Session()
        # Per-host pacing to avoid bursts
        self._last_request_ts: Dict[str, float] = {}
        min_interval_ms = os.getenv("REQUEST_MIN_INTERVAL_MS")
        self._min_interval = (int(min_interval_ms) / 1000.0) if (min_interval_ms and min_interval_ms.isdigit()) else 0.5
        # Optional proxies rotation (comma-separated in WEBSHARE_PROXIES)
        self._proxies_pool = [p.strip() for p in os.getenv("WEBSHARE_PROXIES", "").split(",") if p.strip()]
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get rotating user agent headers
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _pick_request_proxies(self) -> Optional[Dict[str, str]]:
        if not self._proxies_pool:
            return None
        proxy = random.choice(self._proxies_pool)
        # requests expects scheme keys
        if not proxy.startswith("http"):
            proxy = f"http://{proxy}"
        return {"http": proxy, "https": proxy}

    def _pace_host(self, host: str):
        now = time.time()
        last = self._last_request_ts.get(host, 0)
        delta = now - last
        wait = self._min_interval - delta
        if wait > 0:
            # small jitter to de-sync
            time.sleep(wait + random.uniform(0, 0.1))
        self._last_request_ts[host] = time.time()

    def fetch_page(self, url: str, retry_count: int = 0) -> Optional[str]:
        """
        Fetch page content with retry logic
        
        Args:
            url: URL to fetch
            retry_count: Current retry attempt
        
        Returns:
            Page HTML content or None if failed
        """
        try:
            host = urlparse(url).netloc
            self._pace_host(host)
            response = self.session.get(
                url,
                headers=self.get_headers(),
                timeout=self.timeout,
                allow_redirects=True,
                proxies=self._pick_request_proxies() or None,
            )
            
            if response.status_code == 200:
                return response.text
            # Handle common throttling/temporary errors
            if response.status_code in (429, 503, 502, 500):
                if retry_count < self.max_retries:
                    backoff = min(30, (2 ** retry_count)) + random.uniform(0, 1.0)
                    logger.warning(f"[yellow]HTTP {response.status_code} for {host}. Backing off {backoff:.1f}s (retry {retry_count+1}/{self.max_retries})[/yellow]")
                    time.sleep(backoff)
                    return self.fetch_page(url, retry_count + 1)
                logger.warning(f"[yellow]Giving up after {self.max_retries} retries for {host}[/yellow]")
                return None
            else:
                logger.warning(f"[yellow]Status {response.status_code} for {url}[/yellow]")
                return None
        
        except requests.exceptions.Timeout:
            logger.warning(f"[yellow]Timeout for {url}[/yellow]")
            if retry_count < self.max_retries:
                backoff = min(15, (2 ** retry_count)) + random.uniform(0, 0.5)
                time.sleep(backoff)
                return self.fetch_page(url, retry_count + 1)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[red]Request error for {url}: {e}[/red]")
            if retry_count < self.max_retries:
                backoff = min(15, (2 ** retry_count)) + random.uniform(0, 0.5)
                time.sleep(backoff)
                return self.fetch_page(url, retry_count + 1)
        
        return None
    
    def parse_profile(self, data: Dict) -> Dict:
        """
        Parse and classify profile data
        
        Args:
            data: Raw profile data
        
        Returns:
            Processed profile data
        """
        # Combine text for classification
        combined_text = f"{data.get('name', '')} {data.get('description', '')} {data.get('title', '')}"
        
        # Classify role
        role = classify_role(combined_text)
        
        # Extract subjects
        subjects = extract_subjects(combined_text)
        
        # Extract location if not already present
        if not data.get('location'):
            data['location'] = extract_location(combined_text)
        
        # Extract experience if not already present
        if not data.get('experience'):
            data['experience'] = extract_experience(combined_text)
        
        # Add role and subjects
        data['role'] = role
        data['subjects'] = ', '.join(subjects) if subjects else 'N/A'
        
        return data
    
    def random_delay(self, min_delay: float = 1.0, max_delay: float = 3.0):
        """
        Add random delay between requests to avoid detection
        
        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
        """
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def scrape(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Main scrape method to be implemented by subclasses
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of profile dictionaries
        """
        raise NotImplementedError("Subclasses must implement scrape method")
