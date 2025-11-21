"""
Google Custom Search API scraper for real tutor/student data
"""
import os
import time
import random
import requests
from typing import List, Dict, Optional, Tuple
import threading
from dotenv import load_dotenv
from scraper.base import BaseScraper
from utils.logger import logger

load_dotenv()


class GoogleAPISearcher(BaseScraper):
    """
    Scraper using Google Custom Search API (more reliable than HTML scraping)
    
    Setup:
    1. Get API key: https://developers.google.com/custom-search/v1/introduction
    2. Create Search Engine: https://programmablesearchengine.google.com/
    3. Add to .env:
       GOOGLE_API_KEY=your_api_key
       GOOGLE_SEARCH_ENGINE_ID=your_cx_id
    """
    
    # Global throttle across all instances
    _GLOBAL_SEM: Optional[threading.Semaphore] = None
    _GLOBAL_LAST_CALL: float = 0.0

    def __init__(self):
        super().__init__()
        # Support multiple API keys (comma-separated)
        api_keys_str = os.getenv('GOOGLE_API_KEY', '')
        self.api_keys = [key.strip() for key in api_keys_str.split(',') if key.strip()]
        
        # Support multiple search engine IDs (comma-separated)
        cx_ids_str = os.getenv('GOOGLE_SEARCH_ENGINE_ID', '')
        self.search_engine_ids = [cx.strip() for cx in cx_ids_str.split(',') if cx.strip()]
        
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.current_key_index = 0
        self.key_usage = {i: 0 for i in range(len(self.api_keys))}
        # Optional default site restriction to reduce irrelevant results
        self.default_site = os.getenv('GOOGLE_SEARCH_SITE', '').strip()  # e.g., "site:superprof.co.in OR site:urbanpro.com"
        # Backoff tracking per key
        self._key_backoff_until: Dict[int, float] = {}
        # Deep fetch settings to extract experience/location from profile pages
        # Default disabled for performance; enable via env if needed
        self.deep_fetch = os.getenv('GOOGLE_API_DEEP_FETCH', 'false').strip().lower() in ('1', 'true', 'yes')
        try:
            self.deep_fetch_per_page = max(0, int(os.getenv('GOOGLE_API_DEEP_FETCH_PER_PAGE', '5')))
        except Exception:
            self.deep_fetch_per_page = 5
        try:
            self.deep_fetch_max_chars = max(0, int(os.getenv('GOOGLE_API_DEEP_FETCH_MAX_CHARS', '2000')))
        except Exception:
            self.deep_fetch_max_chars = 2000
    
    def is_configured(self) -> bool:
        """Check if API is properly configured"""
        return bool(self.api_keys and self.search_engine_ids)
    
    def get_next_api_key(self) -> Tuple[Optional[str], Optional[str], int]:
        """Get next API key and search engine ID (rotation)"""
        if not self.api_keys:
            return None, None, -1
        
        # Round-robin rotation
        start_idx = self.current_key_index
        for _ in range(len(self.api_keys)):
            idx = self.current_key_index
            api_key = self.api_keys[idx]
            cx_id = self.search_engine_ids[min(idx, len(self.search_engine_ids) - 1)]
            until = self._key_backoff_until.get(idx, 0)
            now = time.time()
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            if now >= until:
                # Track usage
                self.key_usage[idx] = self.key_usage.get(idx, 0) + 1
                logger.info(f"[dim]Using API key #{idx + 1}/{len(self.api_keys)}[/dim]")
                return api_key, cx_id, idx
        # All keys are backed-off; sleep until earliest
        next_ready = min(self._key_backoff_until.values()) if self._key_backoff_until else time.time() + 1
        sleep_for = max(0.5, next_ready - time.time())
        logger.warning(f"[yellow]All API keys in backoff. Sleeping {sleep_for:.1f}s...[/yellow]")
        time.sleep(sleep_for)
        # After wait, pick again
        idx = self.current_key_index
        api_key = self.api_keys[idx]
        cx_id = self.search_engine_ids[min(idx, len(self.search_engine_ids) - 1)]
        self.key_usage[idx] = self.key_usage.get(idx, 0) + 1
        return api_key, cx_id, idx
        
        # Track usage
        self.key_usage[self.current_key_index] += 1
        
        # Move to next key
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        
        logger.info(f"[dim]Using API key #{self.current_key_index + 1}/{len(self.api_keys)}[/dim]")
        
        return api_key, cx_id
    
    def search(self, query: str, start_index: int = 1, num_results: int = 10) -> Optional[Dict]:
        """
        Search using Google Custom Search API
        
        Args:
            query: Search query
            start_index: Starting index (1-based)
            num_results: Number of results per page (max 10)
        
        Returns:
            API response dict or None
        """
        if not self.is_configured():
            logger.error("[red]Google API not configured. Add GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID to .env[/red]")
            return None
        
        # Get next API key for rotation
        api_key, cx_id, key_idx = self.get_next_api_key()
        
        if not api_key:
            logger.error("[red]No API keys available[/red]")
            return None
        
        params = {
            'key': api_key,
            'cx': cx_id,
            'q': query,
            'start': start_index,
            'num': min(num_results, 10)
        }
        
        try:
            # Global concurrency throttle across threads to avoid burst 429
            if GoogleAPISearcher._GLOBAL_SEM is None:
                max_conc = int(os.getenv('GOOGLE_API_MAX_CONCURRENT', '2'))
                GoogleAPISearcher._GLOBAL_SEM = threading.Semaphore(max(1, max_conc))
            with GoogleAPISearcher._GLOBAL_SEM:
                # Per-call pacing (min interval between any two API calls)
                min_interval = float(os.getenv('GOOGLE_API_MIN_INTERVAL_SEC', '0.25'))
                now = time.time()
                delta = now - GoogleAPISearcher._GLOBAL_LAST_CALL
                if delta < min_interval:
                    time.sleep(min_interval - delta + random.uniform(0, 0.1))
                GoogleAPISearcher._GLOBAL_LAST_CALL = time.time()
                response = requests.get(self.base_url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code in (429, 500, 502, 503):
                # backoff this key progressively
                prev_until = self._key_backoff_until.get(key_idx, 0)
                base = 2 ** (int(prev_until > time.time()) + 1)
                backoff = min(60, base + random.uniform(0, 1.0))
                self._key_backoff_until[key_idx] = time.time() + backoff
                logger.warning(f"[yellow]API HTTP {response.status_code} for key #{key_idx+1}. Backing off {backoff:.1f}s and rotating...[/yellow]")
            else:
                logger.warning(f"[yellow]API returned status {response.status_code}[/yellow]")
            return None
        except Exception as e:
            logger.error(f"[red]API request error: {e}[/red]")
            return None
    
    def extract_profiles_from_results(self, results: Dict) -> List[Dict]:
        """
        Extract profile data from API results
        
        Args:
            results: Google API response
        
        Returns:
            List of profile dictionaries
        """
        profiles = []
        
        items = results.get('items', [])
        
        for idx, item in enumerate(items):
            title = item.get('title', '')
            link = item.get('link', '')
            snippet = item.get('snippet', '')
            
            # Skip unwanted domains
            if any(domain in link.lower() for domain in ['youtube.com', 'facebook.com', 'twitter.com', 'instagram.com']):
                continue
            
            # Optionally fetch page content (limited per page) to help extract experience/location
            page_text = ''
            if self.deep_fetch and idx < self.deep_fetch_per_page:
                try:
                    html = self.fetch_page(link)
                    if html:
                        # Crude text extraction without heavy parsing to keep it light
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        text = soup.get_text(separator=' ', strip=True)
                        if text:
                            page_text = text[: self.deep_fetch_max_chars]
                except Exception:
                    pass

            profile = {
                'name': title,
                'title': title,
                'description': (snippet + ' ' + page_text).strip() if page_text else snippet,
                'profile_link': link,
                'source': f'Google API Search',
                'location': None,
                'experience': None
            }
            
            profiles.append(profile)
        
        return profiles
    
    def scrape(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Scrape using Google Custom Search API
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of processed profile dictionaries
        """
        if not self.is_configured():
            logger.warning("[yellow]Google API not configured. Skipping API search.[/yellow]")
            logger.info("[cyan]Get API key: https://developers.google.com/custom-search/v1/introduction[/cyan]")
            return []
        
        # Optionally inject site restriction to improve precision while staying under limits
        eff_query = query
        if self.default_site:
            eff_query = f"({query}) {self.default_site}"
        logger.info(f"[cyan]🔍 Searching via Google API: '{eff_query}'[/cyan]")
        
        all_profiles = []
        pages_needed = (limit // 10) + 1
        
        for page in range(pages_needed):
            start_index = (page * 10) + 1
            
            if start_index > 100:  # Google API limit
                logger.warning("[yellow]Reached Google API pagination limit (100 results)[/yellow]")
                break
            
            logger.info(f"[blue]Fetching results {start_index}-{start_index + 9}...[/blue]")
            
            results = self.search(eff_query, start_index=start_index, num_results=10)
            
            if not results:
                break
            
            profiles = self.extract_profiles_from_results(results)
            
            for profile in profiles:
                processed = self.parse_profile(profile)
                all_profiles.append(processed)
                
                if len(all_profiles) >= limit:
                    break
            
            if len(all_profiles) >= limit:
                break
            
            # Small delay between API calls
            self.random_delay(0.3, 0.7)
        
        logger.info(f"[green]✓ Found {len(all_profiles)} results via Google API[/green]")
        return all_profiles[:limit]
