"""
Google Search scraper for tutor/student profiles
"""
import re
from typing import List, Dict
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup
from scraper.base import BaseScraper
from utils.logger import logger


class GoogleScraper(BaseScraper):
    """Scraper for Google Search results"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.google.com/search"
    
    def build_search_url(self, query: str, start: int = 0) -> str:
        """
        Build Google search URL
        
        Args:
            query: Search query
            start: Result offset
        
        Returns:
            Complete search URL
        """
        encoded_query = quote_plus(query)
        return f"{self.base_url}?q={encoded_query}&start={start}"
    
    def extract_search_results(self, html: str) -> List[Dict]:
        """
        Extract search results from Google page
        
        Args:
            html: HTML content
        
        Returns:
            List of search result dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        results = []
        
        # Find all search result divs
        search_divs = soup.find_all('div', class_='g')
        
        for div in search_divs:
            try:
                # Extract title
                title_elem = div.find('h3')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                
                # Extract link
                link_elem = div.find('a')
                if not link_elem or not link_elem.get('href'):
                    continue
                
                link = link_elem.get('href')
                
                # Skip unwanted domains
                if any(domain in link.lower() for domain in ['youtube.com', 'facebook.com', 'twitter.com', 'instagram.com']):
                    continue
                
                # Extract description/snippet
                desc_elem = div.find('div', class_=['VwiC3b', 'yXK7lf'])
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                
                # Extract domain
                parsed = urlparse(link)
                domain = parsed.netloc.replace('www.', '')
                
                result = {
                    'name': title,
                    'title': title,
                    'description': description,
                    'profile_link': link,
                    'source': f'Google Search ({domain})',
                    'location': None,
                    'experience': None
                }
                
                results.append(result)
            
            except Exception as e:
                logger.debug(f"Error parsing search result: {e}")
                continue
        
        return results
    
    def scrape(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Scrape Google search results
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of processed profile dictionaries
        """
        logger.info(f"[cyan]🔍 Searching Google for: '{query}'[/cyan]")
        
        all_results = []
        pages_to_fetch = (limit // 10) + 1
        
        for page in range(pages_to_fetch):
            start = page * 10
            url = self.build_search_url(query, start)
            
            logger.info(f"[blue]Fetching page {page + 1}...[/blue]")
            
            html = self.fetch_page(url)
            if not html:
                logger.warning(f"[yellow]Failed to fetch page {page + 1}[/yellow]")
                continue
            
            results = self.extract_search_results(html)
            
            if not results:
                logger.info("[yellow]No more results found[/yellow]")
                break
            
            # Process and add results
            for result in results:
                processed = self.parse_profile(result)
                all_results.append(processed)
                
                if len(all_results) >= limit:
                    break
            
            if len(all_results) >= limit:
                break
            
            # Random delay between pages
            self.random_delay(2, 4)
        
        logger.info(f"[green]✓ Found {len(all_results)} results from Google[/green]")
        return all_results[:limit]
