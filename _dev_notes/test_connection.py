import sys
import os

# Add the app directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_snowflake_session, get_db_names

def test_connection():
    try:
        print("Attempting to connect to Snowflake...")
        session = get_snowflake_session()
        print("✅ Successfully connected to Snowflake!")
        
        dbs = get_db_names()
        print(f"Configured Marketplace Databases:")
        print(f"  - RICHGO: {dbs['richgo']}")
        print(f"  - AJD: {dbs['ajd']}")
        print(f"  - SPH: {dbs['sph']}")
        
        # Test a simple query to verify compute works
        result = session.sql("SELECT CURRENT_VERSION(), CURRENT_ACCOUNT()").collect()
        print(f"Snowflake Version: {result[0][0]}, Account: {result[0][1]}")
        
    except Exception as e:
        print("❌ Failed to connect to Snowflake.")
        print("Error Details:")
        print(e)

if __name__ == "__main__":
    test_connection()
