"""
Classification logic for tutors and students
"""
import re
from typing import Optional

# Keywords for classification
TUTOR_KEYWORDS = [
    'tutor', 'teacher', 'instructor', 'educator', 'trainer', 'coach',
    'professor', 'lecturer', 'mentor', 'teaching', 'teaches', 'expert'
]

STUDENT_KEYWORDS = [
    'student', 'learner', 'undergraduate', 'graduate', 'studying',
    'pursuing', 'enrolled', 'pupil', 'scholar', 'learning'
]

SUBJECT_KEYWORDS = [
    'math', 'mathematics', 'physics', 'chemistry', 'biology', 'science',
    'english', 'history', 'geography', 'computer', 'programming', 'coding',
    'language', 'french', 'spanish', 'german', 'economics', 'accounting',
    'statistics', 'calculus', 'algebra', 'geometry', 'music', 'art'
]


def classify_role(text: str) -> str:
    """
    Classify if the profile is a Tutor or Student based on keywords
    
    Args:
        text: Combined text from name, description, and title
    
    Returns:
        'Tutor', 'Student', or 'Unknown'
    """
    if not text:
        return 'Unknown'
    
    text_lower = text.lower()
    
    # Count keyword matches
    tutor_matches = sum(1 for keyword in TUTOR_KEYWORDS if keyword in text_lower)
    student_matches = sum(1 for keyword in STUDENT_KEYWORDS if keyword in text_lower)
    
    if tutor_matches > student_matches:
        return 'Tutor'
    elif student_matches > tutor_matches:
        return 'Student'
    else:
        # Default to Tutor if no clear match (most profiles are tutors)
        return 'Tutor' if tutor_matches > 0 else 'Unknown'


def extract_subjects(text: str) -> list:
    """
    Extract subjects from text based on keyword matching
    
    Args:
        text: Text to extract subjects from
    
    Returns:
        List of detected subjects
    """
    if not text:
        return []
    
    text_lower = text.lower()
    found_subjects = []
    
    for subject in SUBJECT_KEYWORDS:
        if subject in text_lower:
            found_subjects.append(subject.capitalize())
    
    return list(set(found_subjects))  # Remove duplicates


def extract_location(text: str) -> Optional[str]:
    """
    Try to extract location from text (simple pattern matching)
    
    Args:
        text: Text to extract location from
    
    Returns:
        Extracted location or None
    """
    if not text:
        return None
    
    # Common Indian cities and patterns
    indian_cities = [
        'delhi', 'mumbai', 'bangalore', 'chennai', 'kolkata', 'hyderabad',
        'pune', 'ahmedabad', 'jaipur', 'lucknow', 'kanpur', 'nagpur',
        'indore', 'bhopal', 'visakhapatnam', 'surat', 'patna', 'vadodara'
    ]
    
    text_lower = text.lower()
    
    for city in indian_cities:
        if city in text_lower:
            return city.capitalize()
    
    # Try to find pattern like "City, State" or "City"
    location_pattern = r'(?:in|from|at|located in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
    match = re.search(location_pattern, text)
    if match:
        return match.group(1)
    
    return None


def extract_experience(text: str) -> Optional[str]:
    """
    Extract experience information from text
    
    Args:
        text: Text to extract experience from
    
    Returns:
        Extracted experience or None
    """
    if not text:
        return None
    
    # Pattern: "X years" or "X+ years"
    exp_pattern = r'(\d+\+?\s*(?:years?|yrs?)(?:\s+of\s+experience)?)'
    match = re.search(exp_pattern, text.lower())
    
    if match:
        return match.group(1)
    
    return None


def parse_experience_years(experience_str: str) -> Optional[int]:
    """
    Parse experience string to extract numeric years
    
    Args:
        experience_str: Experience string (e.g., "5 years", "10+ years")
    
    Returns:
        Number of years as integer or None if not found
    """
    if not experience_str:
        return None
    
    # Extract number from experience string
    exp_pattern = r'(\d+)\+?\s*(?:years?|yrs?)'
    match = re.search(exp_pattern, experience_str.lower())
    
    if match:
        return int(match.group(1))
    
    return None


def filter_tutors_by_experience(data: list, max_years: int = 5) -> list:
    """
    Filter tutors to only include those with experience less than specified years
    
    Args:
        data: List of profile dictionaries
        max_years: Maximum years of experience to include (default: 5)
    
    Returns:
        Filtered list of tutor profiles
    """
    filtered_tutors = []
    
    for profile in data:
        # Only process tutors
        if profile.get('role') != 'Tutor':
            continue
        
        experience_str = profile.get('experience', '')
        experience_years = parse_experience_years(experience_str)
        
        # Include tutors only if we can determine years and it is strictly less than max_years
        if experience_years is not None and experience_years < max_years:
            filtered_tutors.append(profile)
    
    return filtered_tutors


def is_indian_profile(profile: dict) -> bool:
    """
    Heuristic to determine if a profile belongs to India based on location or text.
    
    Args:
        profile: Profile dict with optional 'location', 'description', 'title', 'name'
    
    Returns:
        True if the profile likely belongs to India, else False
    """
    if not isinstance(profile, dict):
        return False
    
    # If location already extracted and clearly Indian
    loc = (profile.get('location') or '').strip()
    if loc:
        loc_l = loc.lower()
        if 'india' in loc_l:
            return True
        indian_cities = [
            'delhi', 'new delhi', 'mumbai', 'bombay', 'bangalore', 'bengaluru', 'chennai', 'kolkata',
            'hyderabad', 'pune', 'ahmedabad', 'jaipur', 'lucknow', 'kanpur', 'nagpur', 'indore',
            'bhopal', 'visakhapatnam', 'vizag', 'surat', 'patna', 'vadodara', 'gurgaon', 'noida',
            'thane', 'faridabad', 'ghaziabad', 'ludhiana', 'agra', 'nashik', 'pimpri', 'aurangabad',
            'rajkot', 'meerut', 'varanasi', 'madurai', 'coimbatore', 'trichy', 'tiruchirappalli',
            'mangalore', 'kochi', 'trivandrum', 'thiruvananthapuram', 'bhubaneswar', 'ranchi',
            'guwahati', 'amritsar', 'dehradun', 'jalandhar', 'gwalior', 'jodhpur', 'raipur'
        ]
        for city in indian_cities:
            if city in loc_l:
                return True
    
    # Fallback: check combined text for India hints
    text = ' '.join([
        str(profile.get('name') or ''),
        str(profile.get('title') or ''),
        str(profile.get('description') or ''),
    ]).lower()
    if any(word in text for word in ['india', 'indian']):
        return True
    # Common city mentions in text
    for hint in ['delhi', 'mumbai', 'bangalore', 'bengaluru', 'chennai', 'kolkata', 'hyderabad', 'pune', 'ahmedabad', 'jaipur']:
        if hint in text:
            return True
    return False
