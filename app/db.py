import os
from google.cloud import firestore
from google.oauth2 import service_account

def get_db():
    """
    Initialize and return a Firestore client.
    Uses service-account.json if present, otherwise relies on ADC (Application Default Credentials).
    """
    key_path = "service-account.json"
    
    if os.path.exists(key_path):
        # Authenticate using the service account file
        credentials = service_account.Credentials.from_service_account_file(key_path)
        return firestore.Client(credentials=credentials, database="fairsightdb")
    else:
        # Fallback to default credentials
        return firestore.Client(database="fairsightdb")

# Global database instance
db = get_db()
