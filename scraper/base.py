"""
Base scraper class with common functionality
"""
import time
import random
from typing import Optional, Dict, List
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from utils.logger import logger
from utils.classifier import classify_role, extract_subjects, extract_location, extract_experience


class BaseScraper:
    """Base class for all scrapers with common functionality"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.ua = UserAgent()
        self.session = requests.Session()
    
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
            response = self.session.get(
                url,
                headers=self.get_headers(),
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                return response.text
            elif response.status_code == 429:  # Rate limited
                wait_time = (retry_count + 1) * 5
                logger.warning(f"[yellow]Rate limited. Waiting {wait_time}s...[/yellow]")
                time.sleep(wait_time)
                
                if retry_count < self.max_retries:
                    return self.fetch_page(url, retry_count + 1)
            else:
                logger.warning(f"[yellow]Status {response.status_code} for {url}[/yellow]")
                return None
        
        except requests.exceptions.Timeout:
            logger.warning(f"[yellow]Timeout for {url}[/yellow]")
            if retry_count < self.max_retries:
                time.sleep(2)
                return self.fetch_page(url, retry_count + 1)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[red]Request error for {url}: {e}[/red]")
            if retry_count < self.max_retries:
                time.sleep(2)
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
