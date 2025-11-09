"""
Google Custom Search API scraper for real tutor/student data
"""
import os
import requests
from typing import List, Dict, Optional
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
    
    def is_configured(self) -> bool:
        """Check if API is properly configured"""
        return bool(self.api_keys and self.search_engine_ids)
    
    def get_next_api_key(self) -> tuple:
        """Get next API key and search engine ID (rotation)"""
        if not self.api_keys:
            return None, None
        
        # Round-robin rotation
        api_key = self.api_keys[self.current_key_index]
        cx_id = self.search_engine_ids[min(self.current_key_index, len(self.search_engine_ids) - 1)]
        
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
        api_key, cx_id = self.get_next_api_key()
        
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
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning(f"[yellow]API rate limit reached for key #{self.current_key_index}. Rotating to next key...[/yellow]")
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
        
        for item in items:
            title = item.get('title', '')
            link = item.get('link', '')
            snippet = item.get('snippet', '')
            
            # Skip unwanted domains
            if any(domain in link.lower() for domain in ['youtube.com', 'facebook.com', 'twitter.com', 'instagram.com']):
                continue
            
            profile = {
                'name': title,
                'title': title,
                'description': snippet,
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
        
        logger.info(f"[cyan]🔍 Searching via Google API: '{query}'[/cyan]")
        
        all_profiles = []
        pages_needed = (limit // 10) + 1
        
        for page in range(pages_needed):
            start_index = (page * 10) + 1
            
            if start_index > 100:  # Google API limit
                logger.warning("[yellow]Reached Google API pagination limit (100 results)[/yellow]")
                break
            
            logger.info(f"[blue]Fetching results {start_index}-{start_index + 9}...[/blue]")
            
            results = self.search(query, start_index=start_index, num_results=10)
            
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
            self.random_delay(0.5, 1.0)
        
        logger.info(f"[green]✓ Found {len(all_profiles)} results via Google API[/green]")
        return all_profiles[:limit]
