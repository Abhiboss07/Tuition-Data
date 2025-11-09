"""
UrbanPro scraper for tutor profiles
"""
import re
from typing import List, Dict
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from scraper.base import BaseScraper
from utils.logger import logger


class UrbanProScraper(BaseScraper):
    """Scraper for UrbanPro tutor profiles"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.urbanpro.com"
    
    def build_search_url(self, subject: str, location: str = "delhi") -> str:
        """
        Build UrbanPro search URL
        
        Args:
            subject: Subject to search for
            location: Location (default: delhi)
        
        Returns:
            Complete search URL
        """
        # Clean and format subject
        subject_clean = subject.lower().replace(' tutor', '').replace(' ', '-')
        location_clean = location.lower().replace(' ', '-')
        
        return f"{self.base_url}/{subject_clean}/in-{location_clean}"
    
    def extract_profiles(self, html: str) -> List[Dict]:
        """
        Extract tutor profiles from UrbanPro page
        
        Args:
            html: HTML content
        
        Returns:
            List of profile dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        profiles = []
        
        # Find tutor cards (UrbanPro structure may vary)
        tutor_divs = soup.find_all('div', class_=re.compile('tutor|profile|card'))
        
        if not tutor_divs:
            # Try alternative structure
            tutor_divs = soup.find_all('div', {'itemtype': re.compile('Person')})
        
        for div in tutor_divs[:20]:  # Limit to first 20
            try:
                # Extract name
                name_elem = div.find(['h2', 'h3', 'h4', 'a'], class_=re.compile('name|title'))
                if not name_elem:
                    name_elem = div.find('a', href=re.compile('/tutor/'))
                
                if not name_elem:
                    continue
                
                name = name_elem.get_text(strip=True)
                
                # Extract profile link
                link_elem = div.find('a', href=re.compile('/tutor/|/profile/'))
                profile_link = self.base_url + link_elem.get('href') if link_elem and link_elem.get('href') else None
                
                # Extract description
                desc_elem = div.find(['p', 'div'], class_=re.compile('desc|about|bio'))
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                
                # Extract experience
                exp_elem = div.find(string=re.compile(r'\d+\s*(?:years?|yrs?)', re.IGNORECASE))
                experience = exp_elem.strip() if exp_elem else None
                
                # Extract location
                location_elem = div.find(['span', 'div'], class_=re.compile('location|area|city'))
                location = location_elem.get_text(strip=True) if location_elem else None
                
                profile = {
                    'name': name,
                    'title': f"{name} - Tutor",
                    'description': description,
                    'profile_link': profile_link,
                    'source': 'UrbanPro',
                    'location': location,
                    'experience': experience
                }
                
                profiles.append(profile)
            
            except Exception as e:
                logger.debug(f"Error parsing UrbanPro profile: {e}")
                continue
        
        return profiles
    
    def scrape(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Scrape UrbanPro for tutor profiles
        
        Args:
            query: Search query (e.g., "math tutor Delhi")
            limit: Maximum number of results
        
        Returns:
            List of processed profile dictionaries
        """
        logger.info(f"[cyan]🔍 Searching UrbanPro for: '{query}'[/cyan]")
        
        # Parse query to extract subject and location
        query_lower = query.lower()
        
        # Extract subject (default to "math" if not found)
        subject = "math"
        subjects = ['math', 'physics', 'chemistry', 'biology', 'english', 'computer', 'science']
        for subj in subjects:
            if subj in query_lower:
                subject = subj
                break
        
        # Extract location (default to "delhi" if not found)
        location = "delhi"
        cities = ['delhi', 'mumbai', 'bangalore', 'chennai', 'kolkata', 'pune', 'hyderabad']
        for city in cities:
            if city in query_lower:
                location = city
                break
        
        url = self.build_search_url(subject, location)
        logger.info(f"[blue]Fetching from: {url}[/blue]")
        
        html = self.fetch_page(url)
        if not html:
            logger.warning("[yellow]Failed to fetch UrbanPro page[/yellow]")
            return []
        
        profiles = self.extract_profiles(html)
        
        # Process profiles
        processed_profiles = []
        for profile in profiles[:limit]:
            processed = self.parse_profile(profile)
            processed_profiles.append(processed)
        
        logger.info(f"[green]✓ Found {len(processed_profiles)} profiles from UrbanPro[/green]")
        return processed_profiles
