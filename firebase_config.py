"""
Firebase Admin SDK Configuration and Initialization
Core Principle: Singleton pattern ensures single Firebase app instance
Error Handling: Graceful degradation with detailed logging
Security: Environment-based credentials with validation
"""
import os
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from google.cloud import firestore
from google.cloud.firestore_v1.client import Client as FirestoreClient
import firebase_admin
from firebase_admin import credentials, firestore as fb_firestore
from firebase_admin.exceptions import FirebaseError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


@dataclass
class FirebaseConfig:
    """Firebase configuration dataclass for type safety"""
    project_id: str
    credentials_path: Optional[str] = None
    credentials_dict: Optional[Dict[str, Any]] = None
    
    def validate(self) -> bool:
        """Validate Firebase configuration"""
        if not self.project_id:
            logger.error("Firebase project_id is required")
            return False
        
        # Check credentials source
        credentials_count = sum([
            1 if self.credentials_path else 0,
            1 if self.credentials_dict else 0
        ])
        
        if credentials_count == 0:
            logger.error("Either credentials_path or credentials_dict must be provided")
            return False
        
        if credentials_count > 1:
            logger.error("Only one credentials source (path or dict) should be provided")
            return False
            
        if self.credentials_path and not os.path.exists(self.credentials_path):
            logger.error(f"Credentials file not found: {self.credentials_path}")
            return False
            
        return True


class FirebaseManager:
    """Singleton manager for Firebase Admin SDK initialization and Firestore access"""
    _instance: Optional['FirebaseManager'] = None
    _app_initialized: bool = False
    _firestore_client: Optional[FirestoreClient] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
    
    @classmethod
    def initialize(cls, config: FirebaseConfig) -> bool:
        """
        Initialize Firebase Admin SDK with provided configuration
        
        Args:
            config: FirebaseConfig object with project and credentials
            
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            if cls._app_initialized:
                logger.warning("Firebase Admin SDK already initialized")
                return True
            
            if not config.validate():
                logger.error("Firebase configuration validation failed")
                return False
            
            # Initialize credentials
            cred = None
            if config.credentials_path:
                if not os.path.exists(config.credentials_path):
                    logger.error(f"Credentials file not found: {config.credentials_path}")
                    return False
                cred = credentials.Certificate(config.credentials_path)
            elif config.credentials_dict:
                cred = credentials.Certificate(config.credentials_dict)
            
            # Initialize Firebase app
            firebase_admin.initialize_app(
                cred,
                {'projectId': config.project_id}
            )
            
            cls._app_initialized = True
            logger.info(f"Firebase Admin SDK initialized for project: {config.project_id}")
            return True
            
        except FileNotFoundError as e:
            logger.error(f"Credentials file error: {str(e)}")
            return False
        except ValueError as e:
            logger.error(f"Firebase configuration error: {str(e)}")
            return False
        except FirebaseError as e:
            logger.error(f"Firebase initialization error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Firebase initialization: {str(e)}")
            return False
    
    @classmethod
    def get_firestore_client(cls) -> Optional[FirestoreClient]:
        """
        Get Firestore client with lazy initialization
        
        Returns:
            FirestoreClient: Initialized Firestore client or None if failed
        """
        try:
            if cls._firestore_client is None:
                if not cls._app_initialized:
                    logger.error("Firebase not initialized. Call initialize() first")
                    return None
                
                cls._firestore_client = fb_firestore.client()
                logger.info("Firestore client initialized")
            
            return cls._firestore_client
            
        except FirebaseError as e:
            logger.error(f"Firestore client initialization error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting Firestore client: {str(e)}")
            return None
    
    @classmethod
    def is_initialized(cls) -> bool:
        """Check if Firebase is initialized"""
        return cls._app_initialized
    
    @classmethod
    def cleanup(cls) -> None:
        """Cleanup Firebase resources"""
        try:
            if cls._app_initialized:
                firebase_admin.delete_app(firebase_admin.get_app())
                cls._app_initialized = False
                cls._firestore_client = None
                logger.info("Firebase resources cleaned up")
        except Exception as e:
            logger.error(f"Error during Firebase cleanup: {str(e)}")


# Environment-based configuration helper
def get_firebase_config_from_env() -> Optional[FirebaseConfig]:
    """
    Get Firebase configuration from environment variables
    
    Environment Variables:
        FIREBASE_PROJECT_ID: Firebase project ID (required)
        FIREBASE_CREDENTIALS_PATH: Path to service account JSON file
        FIREBASE_CREDENTIALS_JSON: JSON string of service account credentials
        
    Returns:
        FirebaseConfig or None if configuration incomplete
    """
    project_id = os.getenv('FIREBASE_PROJECT_ID')
    credentials_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
    credentials_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
    
    if not project_id:
        logger.error("FIREBASE_PROJECT_ID environment variable not set")
        return None
    
    config_dict = None
    if credentials_json:
        try:
            config_dict = json.loads(credentials_json)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in FIREBASE_CREDENTIALS_JSON: {str(e)}")
            return None
    
    return FirebaseConfig(
        project_id=project_id,
        credentials_path=credentials_path,
        credentials_dict=config_dict
    )