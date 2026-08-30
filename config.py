import os
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")

if not TMDB_API_KEY:
    raise ValueError(
        "TMDB_API_KEY not found. Create a new .env file in the project root"
    )
BASE_URL = "https://api.themoviedb.org/3"