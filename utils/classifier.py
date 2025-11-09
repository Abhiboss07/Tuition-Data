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
