"""
Storage utilities for CSV and MongoDB
"""
import os
import csv
from typing import List, Dict
from pathlib import Path
from utils.logger import logger
from utils.database import MongoDBHandler

# Try to import pandas, but make it optional and allow disabling via env
try:
    import os as _os
    _disable_pandas = _os.getenv('DISABLE_PANDAS', '').strip() in ('1', 'true', 'yes')
    if not _disable_pandas:
        import pandas as pd  # type: ignore
        PANDAS_AVAILABLE = True
    else:
        PANDAS_AVAILABLE = False
        logger.info("[dim]DISABLE_PANDAS set: using CSV module for file writing[/dim]")
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("Pandas not available, using CSV module for file writing")


def _dedup_records(data: List[Dict]) -> List[Dict]:
    """
    Deduplicate list of dicts based on stable key: profile_link else name|source.
    Keeps first occurrence.
    """
    seen = set()
    unique: List[Dict] = []

    def key_fn(x: Dict) -> str:
        link = (x.get('profile_link') or '').strip().lower()
        if link:
            return link
        name = (x.get('name') or '').strip().lower()
        source = (x.get('source') or '').strip().lower()
        return f"{name}|{source}"

    for item in data:
        k = key_fn(item)
        if not k:
            # If we cannot form a key, include once using object id guard
            k = f"__idx__:{id(item)}"
        if k in seen:
            continue
        seen.add(k)
        unique.append(item)
    return unique


def save_to_csv(data: List[Dict], output_path: str = "data/tutors.csv") -> bool:
    """
    Save data to CSV file
    
    Args:
        data: List of dictionaries containing profile data
        output_path: Path to save the CSV file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create data directory if it doesn't exist
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Dedup incoming data first
        data = _dedup_records(data)

        if PANDAS_AVAILABLE:
            # Use pandas if available
            try:
                df = pd.DataFrame(data)
                # Drop duplicate rows by identity key if present
                key_cols = [c for c in ['profile_link', 'name', 'source'] if c in df.columns]
                if key_cols:
                    # Prefer profile_link; if absent, use name+source
                    subset = ['profile_link'] if 'profile_link' in key_cols else key_cols
                    df = df.drop_duplicates(subset=subset, keep='first')
                df.to_csv(output_path, index=False, encoding='utf-8')
            except Exception as e:
                logger.warning(f"[yellow]Pandas write failed, falling back to CSV module: {e}[/yellow]")
                # Fallback to CSV module
                if not data:
                    return False
                fieldnames = set()
                for item in data:
                    fieldnames.update(item.keys())
                fieldnames = sorted(list(fieldnames))
                with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
        else:
            # Fallback to CSV module
            if not data:
                return False
            
            # Get all unique keys from all dictionaries
            fieldnames = set()
            for item in data:
                fieldnames.update(item.keys())
            fieldnames = sorted(list(fieldnames))
            
            # Write CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
        
        logger.info(f"[green]✓ Saved {len(data)} records to {output_path}[/green]")
        return True
    
    except Exception as e:
        logger.error(f"[red]✗ Error saving to CSV: {e}[/red]")
        return False


def save_to_mongodb(data: List[Dict]) -> bool:
    """
    Save data to MongoDB
    
    Args:
        data: List of dictionaries containing profile data
    
    Returns:
        True if successful, False otherwise
    """
    try:
        db_handler = MongoDBHandler()
        
        if db_handler.connect():
            result = db_handler.insert_many(data)
            db_handler.close()
            return result
        else:
            logger.warning("[yellow]Skipping MongoDB storage[/yellow]")
            return False
    
    except Exception as e:
        logger.error(f"[red]✗ Error saving to MongoDB: {e}[/red]")
        return False


def save_data(data: List[Dict], output_format: str = "csv", output_path: str = None, separate_by_role: bool = True, append_mode: bool = True) -> bool:
    """
    Save data to specified format(s)
    
    Args:
        data: List of dictionaries containing profile data
        output_format: Format to save ('csv', 'mongo', or 'both')
        output_path: Custom path for CSV file
        separate_by_role: If True, create separate files for tutors and students
    
    Returns:
        True if at least one save operation successful
    """
    if not data:
        logger.warning("[yellow]No data to save[/yellow]")
        return False
    
    success = False
    
    if output_format in ['csv', 'both']:
        if separate_by_role:
            # Separate tutors and students
            tutors = [item for item in data if item.get('role', '').lower() == 'tutor']
            students = [item for item in data if item.get('role', '').lower() == 'student']
            
            # Load existing data if append mode
            existing_tutors = []
            existing_students = []
            if append_mode:
                tutor_path = output_path or "data/tutors.csv"
                student_path = output_path.replace('tutors', 'students') if output_path else "data/students.csv"
                
                # Load existing tutors
                if Path(tutor_path).exists():
                    try:
                        with open(tutor_path, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            existing_tutors = list(reader)
                    except Exception as _e:
                        logger.debug(f"Failed reading existing tutors CSV, continuing without merge: {_e}")
                
                # Load existing students
                if Path(student_path).exists():
                    try:
                        with open(student_path, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            existing_students = list(reader)
                    except Exception as _e:
                        logger.debug(f"Failed reading existing students CSV, continuing without merge: {_e}")
            
            # Merge new and existing data
            all_tutors = _dedup_records(existing_tutors + tutors)
            all_students = _dedup_records(existing_students + students)
            
            # Save tutors
            if all_tutors:
                tutor_path = output_path or "data/tutors.csv"
                if save_to_csv(all_tutors, tutor_path):
                    logger.info(f"[green]✓ Saved {len(all_tutors)} tutors to {tutor_path}[/green]")
                    success = True
            
            # Save students
            if all_students:
                student_path = output_path.replace('tutors', 'students') if output_path else "data/students.csv"
                if save_to_csv(all_students, student_path):
                    logger.info(f"[green]✓ Saved {len(all_students)} students to {student_path}[/green]")
                    success = True
            
            # If no classification, save all
            if not tutors and not students:
                csv_path = output_path or "data/all_profiles.csv"
                if save_to_csv(_dedup_records(data), csv_path):
                    success = True
        else:
            # Save all together
            csv_path = output_path or "data/tutors.csv"
            if save_to_csv(_dedup_records(data), csv_path):
                success = True
    
    if output_format in ['mongo', 'both']:
        if save_to_mongodb(data):
            success = True
    
    return success
