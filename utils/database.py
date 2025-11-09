"""
Database connection and operations for MongoDB
"""
import os
from typing import List, Dict, Optional
from pymongo import MongoClient, errors
from dotenv import load_dotenv
from utils.logger import logger

# Load environment variables
load_dotenv()


class MongoDBHandler:
    """Handler for MongoDB operations"""
    
    def __init__(self):
        self.uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        self.database_name = os.getenv('MONGODB_DATABASE', 'tuition_data')
        self.collection_name = os.getenv('MONGODB_COLLECTION', 'tutors_students')
        self.client: Optional[MongoClient] = None
        self.db = None
        self.collection = None
    
    def connect(self) -> bool:
        """
        Establish connection to MongoDB
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            # Test the connection
            self.client.server_info()
            self.db = self.client[self.database_name]
            self.collection = self.db[self.collection_name]
            logger.info(f"[green]✓ Connected to MongoDB: {self.database_name}.{self.collection_name}[/green]")
            return True
        except errors.ServerSelectionTimeoutError:
            logger.warning("[yellow]⚠ MongoDB not available. Will skip MongoDB storage.[/yellow]")
            return False
        except Exception as e:
            logger.error(f"[red]✗ MongoDB connection error: {e}[/red]")
            return False
    
    def insert_many(self, data: List[Dict]) -> bool:
        """
        Insert multiple documents into MongoDB
        
        Args:
            data: List of dictionaries to insert
        
        Returns:
            True if successful, False otherwise
        """
        if not self.collection:
            logger.error("[red]MongoDB not connected[/red]")
            return False
        
        try:
            if data:
                result = self.collection.insert_many(data)
                logger.info(f"[green]✓ Inserted {len(result.inserted_ids)} records to MongoDB[/green]")
                return True
            else:
                logger.warning("[yellow]No data to insert[/yellow]")
                return False
        except Exception as e:
            logger.error(f"[red]✗ Error inserting data to MongoDB: {e}[/red]")
            return False
    
    def find_all(self, limit: int = 100) -> List[Dict]:
        """
        Retrieve all documents from collection
        
        Args:
            limit: Maximum number of documents to retrieve
        
        Returns:
            List of documents
        """
        if not self.collection:
            logger.error("[red]MongoDB not connected[/red]")
            return []
        
        try:
            cursor = self.collection.find().limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"[red]✗ Error retrieving data from MongoDB: {e}[/red]")
            return []
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("[blue]MongoDB connection closed[/blue]")


def get_mongodb_handler() -> MongoDBHandler:
    """
    Factory function to get MongoDB handler
    
    Returns:
        MongoDBHandler instance
    """
    return MongoDBHandler()
