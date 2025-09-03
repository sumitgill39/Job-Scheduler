import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from database.sqlalchemy_models import get_db_session, JobConfiguration

with get_db_session() as session:
    jobs = session.query(JobConfiguration).order_by(JobConfiguration.created_date.desc()).limit(5).all()
    for job in jobs:
        print(f"Job: {job.name} (ID: {job.job_id}) - {job.created_date}")