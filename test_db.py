from app.db import db

def test_connection():
    try:
        print("Attempting to connect to Firestore...")
        # Try to list collections as a simple connection test
        collections = list(db.collections())
        print(f"Connection successful! Found {len(collections)} collections.")
        for coll in collections:
            print(f" - {coll.id}")
            
        # Try to check for 'audit_history' specifically
        print("\nChecking for 'audit_history' collection...")
        docs = list(db.collection("audit_history").limit(1).stream())
        if docs:
            print("Found existing records in 'audit_history'.")
        else:
            print("'audit_history' collection exists but is empty, or hasn't been created yet.")
            
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
