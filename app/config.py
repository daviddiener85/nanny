

import os
from dotenv import load_dotenv
load_dotenv()
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev-admin-change-this")

class Settings:
    database_url = "sqlite:///./nanny_app.db"

settings = Settings()
