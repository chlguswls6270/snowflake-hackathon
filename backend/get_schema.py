import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_snowflake_session, get_db_names

def research_demographics():
    session = get_snowflake_session()
    sph_db = get_db_names()['sph']
        
    query_age = f"SELECT DISTINCT AGE_GROUP FROM {sph_db}.GRANDATA.CARD_SALES_INFO LIMIT 20;"
    query_time = f"SELECT DISTINCT TIME_SLOT FROM {sph_db}.GRANDATA.CARD_SALES_INFO LIMIT 20;"
    query_wknd = f"SELECT DISTINCT WEEKDAY_WEEKEND FROM {sph_db}.GRANDATA.CARD_SALES_INFO LIMIT 20;"
    
    print("--- AGE_GROUP ---")
    for r in session.sql(query_age).collect(): print(r)
        
    print("--- TIME_SLOT ---")
    for r in session.sql(query_time).collect(): print(r)
        
    print("--- WEEKDAY_WEEKEND ---")
    for r in session.sql(query_wknd).collect(): print(r)

if __name__ == "__main__":
    research_demographics()
