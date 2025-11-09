"""
Storage utilities for CSV and MongoDB
"""
import os
import csv
from typing import List, Dict
from pathlib import Path
from utils.logger import logger
from utils.database import MongoDBHandler

# Try to import pandas, but make it optional
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("Pandas not available, using CSV module for file writing")


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
        
        if PANDAS_AVAILABLE:
            # Use pandas if available
            df = pd.DataFrame(data)
            df.to_csv(output_path, index=False, encoding='utf-8')
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
                        import pandas as pd
                        existing_tutors_df = pd.read_csv(tutor_path)
                        existing_tutors = existing_tutors_df.to_dict('records')
                    except:
                        pass
                
                # Load existing students
                if Path(student_path).exists():
                    try:
                        import pandas as pd
                        existing_students_df = pd.read_csv(student_path)
                        existing_students = existing_students_df.to_dict('records')
                    except:
                        pass
            
            # Merge new and existing data
            all_tutors = existing_tutors + tutors
            all_students = existing_students + students
            
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
                if save_to_csv(data, csv_path):
                    success = True
        else:
            # Save all together
            csv_path = output_path or "data/tutors.csv"
            if save_to_csv(data, csv_path):
                success = True
    
    if output_format in ['mongo', 'both']:
        if save_to_mongodb(data):
            success = True
    
    return success
