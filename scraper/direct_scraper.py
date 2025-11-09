"""
Direct scraper for multiple tutor platforms with enhanced extraction
"""
import re
from typing import List, Dict
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from scraper.base import BaseScraper
from utils.logger import logger


class UniversalTutorScraper(BaseScraper):
    """Enhanced scraper for multiple tutor platforms"""
    
    def __init__(self):
        super().__init__()
        self.platforms = {
            'vedantu': 'https://www.vedantu.com/tutors',
            'tutor': 'https://www.tutor.com/tutors',
            'wyzant': 'https://www.wyzant.com/tutors/search',
            'preply': 'https://preply.com/en/tutors',
            'skooli': 'https://www.skooli.com/tutors'
        }
    
    def scrape_vedantu(self, subject: str = "math", limit: int = 20) -> List[Dict]:
        """Scrape Vedantu tutor profiles"""
        logger.info(f"[cyan]Scraping Vedantu for {subject} tutors...[/cyan]")
        
        url = f"https://www.vedantu.com/tutors/{subject}"
        html = self.fetch_page(url)
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        profiles = []
        
        # Find tutor cards
        tutor_cards = soup.find_all(['div', 'article'], class_=re.compile('tutor|teacher|profile|card'), limit=limit)
        
        for card in tutor_cards:
            try:
                # Extract name
                name_elem = card.find(['h2', 'h3', 'h4', 'span'], class_=re.compile('name|title'))
                if not name_elem:
                    continue
                
                name = name_elem.get_text(strip=True)
                
                # Extract link
                link_elem = card.find('a', href=True)
                link = link_elem.get('href') if link_elem else None
                if link and not link.startswith('http'):
                    link = 'https://www.vedantu.com' + link
                
                # Extract description
                desc_elem = card.find(['p', 'div'], class_=re.compile('desc|bio|about'))
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                
                profile = {
                    'name': name,
                    'title': name,
                    'description': description,
                    'profile_link': link,
                    'source': 'Vedantu',
                    'location': None,
                    'experience': None
                }
                
                profiles.append(self.parse_profile(profile))
            
            except Exception as e:
                logger.debug(f"Error parsing Vedantu profile: {e}")
                continue
        
        logger.info(f"[green]✓ Found {len(profiles)} profiles from Vedantu[/green]")
        return profiles
    
    def scrape_generic_platform(self, url: str, platform_name: str, limit: int = 20) -> List[Dict]:
        """Generic scraper for tutor platforms"""
        logger.info(f"[cyan]Scraping {platform_name}...[/cyan]")
        
        html = self.fetch_page(url)
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        profiles = []
        
        # Try multiple selectors
        selectors = [
            {'name': 'tutor', 'attrs': {'class': re.compile('tutor|teacher|profile')}},
            {'name': 'div', 'attrs': {'class': re.compile('card|profile|teacher')}},
            {'name': 'article', 'attrs': {'class': re.compile('tutor|profile')}},
        ]
        
        tutor_cards = []
        for selector in selectors:
            cards = soup.find_all(selector['name'], selector['attrs'], limit=limit)
            if cards:
                tutor_cards = cards
                break
        
        for card in tutor_cards[:limit]:
            try:
                # Extract name
                name_elem = card.find(['h1', 'h2', 'h3', 'h4'], class_=re.compile('name|title'))
                if not name_elem:
                    name_elem = card.find('a', class_=re.compile('name|title'))
                
                if not name_elem:
                    continue
                
                name = name_elem.get_text(strip=True)
                
                # Extract link
                link_elem = card.find('a', href=True)
                link = link_elem.get('href') if link_elem else None
                
                # Extract description
                desc_elem = card.find(['p', 'div', 'span'], class_=re.compile('desc|bio|about|summary'))
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                
                profile = {
                    'name': name,
                    'title': name,
                    'description': description,
                    'profile_link': link,
                    'source': platform_name,
                    'location': None,
                    'experience': None
                }
                
                profiles.append(self.parse_profile(profile))
            
            except Exception as e:
                logger.debug(f"Error parsing {platform_name} profile: {e}")
                continue
        
        logger.info(f"[green]✓ Found {len(profiles)} profiles from {platform_name}[/green]")
        return profiles
    
    def scrape(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Scrape from multiple platforms
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of profile dictionaries
        """
        all_profiles = []
        
        # Extract subject from query
        query_lower = query.lower()
        subject = "math"
        subjects = ['math', 'physics', 'chemistry', 'biology', 'english', 'science']
        for subj in subjects:
            if subj in query_lower:
                subject = subj
                break
        
        # Try Vedantu
        try:
            vedantu_profiles = self.scrape_vedantu(subject, limit // 2)
            all_profiles.extend(vedantu_profiles)
        except Exception as e:
            logger.warning(f"[yellow]Vedantu scraping failed: {e}[/yellow]")
        
        # Add delay
        self.random_delay(2, 4)
        
        return all_profiles[:limit]
