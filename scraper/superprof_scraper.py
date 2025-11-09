"""
Superprof scraper for tutor profiles
"""
import re
from typing import List, Dict
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from scraper.base import BaseScraper
from utils.logger import logger


class SuperprofScraper(BaseScraper):
    """Scraper for Superprof tutor profiles"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.superprof.co.in"
    
    def build_search_url(self, subject: str, location: str = "delhi") -> str:
        """
        Build Superprof search URL
        
        Args:
            subject: Subject to search for
            location: Location (default: delhi)
        
        Returns:
            Complete search URL
        """
        # Clean and format
        subject_clean = subject.lower().replace(' ', '-')
        location_clean = location.lower().replace(' ', '-')
        
        return f"{self.base_url}/lessons/{subject_clean}/{location_clean}.html"
    
    def extract_profiles(self, html: str) -> List[Dict]:
        """
        Extract tutor profiles from Superprof page
        
        Args:
            html: HTML content
        
        Returns:
            List of profile dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        profiles = []
        
        # Find tutor cards
        tutor_cards = soup.find_all(['div', 'article'], class_=re.compile('teacher|tutor|card|profile'))
        
        if not tutor_cards:
            # Try alternative selectors
            tutor_cards = soup.find_all('div', {'data-testid': re.compile('teacher|tutor')})
        
        for card in tutor_cards[:20]:  # Limit to first 20
            try:
                # Extract name
                name_elem = card.find(['h2', 'h3'], class_=re.compile('name|title'))
                if not name_elem:
                    name_elem = card.find('a', class_=re.compile('name|title'))
                
                if not name_elem:
                    continue
                
                name = name_elem.get_text(strip=True)
                
                # Extract profile link
                link_elem = card.find('a', href=re.compile('/tutors/'))
                if not link_elem:
                    link_elem = card.find('a')
                
                profile_link = None
                if link_elem and link_elem.get('href'):
                    href = link_elem.get('href')
                    profile_link = href if href.startswith('http') else self.base_url + href
                
                # Extract description/tagline
                desc_elem = card.find(['p', 'div'], class_=re.compile('desc|tagline|bio|about'))
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                
                # Extract experience
                exp_elem = card.find(string=re.compile(r'\d+\s*(?:years?|yrs?)', re.IGNORECASE))
                experience = exp_elem.strip() if exp_elem else None
                
                # Extract location
                location_elem = card.find(['span', 'div'], class_=re.compile('location|city|area'))
                location = location_elem.get_text(strip=True) if location_elem else None
                
                # Extract rating/price if available
                price_elem = card.find(string=re.compile(r'₹|Rs\.?\s*\d+'))
                price = price_elem.strip() if price_elem else None
                
                profile = {
                    'name': name,
                    'title': f"{name} - Tutor",
                    'description': description + (f" | Price: {price}" if price else ""),
                    'profile_link': profile_link,
                    'source': 'Superprof',
                    'location': location,
                    'experience': experience
                }
                
                profiles.append(profile)
            
            except Exception as e:
                logger.debug(f"Error parsing Superprof profile: {e}")
                continue
        
        return profiles
    
    def scrape(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Scrape Superprof for tutor profiles
        
        Args:
            query: Search query (e.g., "math tutor Delhi")
            limit: Maximum number of results
        
        Returns:
            List of processed profile dictionaries
        """
        logger.info(f"[cyan]🔍 Searching Superprof for: '{query}'[/cyan]")
        
        # Parse query to extract subject and location
        query_lower = query.lower()
        
        # Extract subject
        subject = "mathematics"
        subjects = {
            'math': 'mathematics',
            'physics': 'physics',
            'chemistry': 'chemistry',
            'biology': 'biology',
            'english': 'english',
            'computer': 'computer-science',
            'programming': 'programming'
        }
        
        for key, value in subjects.items():
            if key in query_lower:
                subject = value
                break
        
        # Extract location
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
            logger.warning("[yellow]Failed to fetch Superprof page[/yellow]")
            return []
        
        profiles = self.extract_profiles(html)
        
        # Process profiles
        processed_profiles = []
        for profile in profiles[:limit]:
            processed = self.parse_profile(profile)
            processed_profiles.append(processed)
        
        logger.info(f"[green]✓ Found {len(processed_profiles)} profiles from Superprof[/green]")
        return processed_profiles
