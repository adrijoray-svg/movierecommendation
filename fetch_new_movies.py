## Purpose is to fetch the movies from TMDB database reshape it and make the new movies and new credits table

import argparse
import json
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from config import BASE_URL, TMDB_API_KEY

REQUEST_TIMEOUT = 10  # seconds — treat a hung connection as a failure, not a hang

def build_session() -> requests.Session:
    # Session with automatic retries for dropped connections, timeouts,
    # and transient server errors (including TMDB rate-limiting on 429).

    session = requests.Session()
    retry_strategy = Retry(
        total=5,                       # up to 5 retries per request
        backoff_factor=1,              # 1s, 2s, 4s, 8s, 16s between attempts
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = build_session()


def safe_get(url: str, params: dict, max_attempts: int = 3):
    # Extra outer-layer safety net on top of the session's built-in retries —
    # catches connection drops / timeouts that happen *before* a response
    # even comes back, which the urllib3 Retry above won't always cover.
    for attempt in range(1, max_attempts + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            wait = 2 ** attempt
            print(f"  [warn] connection issue ({e.__class__.__name__}), retrying in {wait}s... "
                  f"(attempt {attempt}/{max_attempts})")
            time.sleep(wait)
    print(f"  [error] giving up on {url} after {max_attempts} attempts")
    return None


def discover_movie_ids(start_year: int, end_year: int, pages_per_year: int, min_votes: int) -> list[int]:
    """Get a list of movie IDs released between start_year and end_year."""
    ids = []
    for year in range(start_year, end_year + 1):
        for page in range(1, pages_per_year + 1):
            resp = safe_get(
                f"{BASE_URL}/discover/movie",
                params={
                    "api_key": TMDB_API_KEY,
                    "primary_release_year": year,
                    "sort_by": "popularity.desc",
                    "vote_count.gte": min_votes,
                    "page": page,
                },
            )
            if resp is None or resp.status_code != 200:
                status = resp.status_code if resp is not None else "no response"
                print(f"  [warn] year={year} page={page} failed: {status} — skipping this page")
                continue

            data = resp.json()
            results = data.get("results", [])
            if not results:
                break  # no more pages for this year

            ids.extend(m["id"] for m in results)

            if page >= data.get("total_pages", 1):
                break

            time.sleep(0.03)  # be polite to the API

        print(f"Year {year}: collected {len(ids)} total IDs so far")

    return sorted(set(ids))


def fetch_movie_details(movie_id: int) -> dict | None:
    """Fetch full details + credits + keywords for one movie, in a single call."""
    resp = safe_get(
        f"{BASE_URL}/movie/{movie_id}",
        params={
            "api_key": TMDB_API_KEY,
            "append_to_response": "credits,keywords",
        },
    )
    if resp is None or resp.status_code != 200:
        return None
    return resp.json()


def to_tmdb5000_movie_row(d: dict) -> dict:
    """Reshape a /movie/{id} response into the tmdb_5000_movies.csv schema."""
    return {
        "budget": d.get("budget", 0),
        "genres": json.dumps(
            [{"id": g["id"], "name": g["name"]} for g in d.get("genres", [])]
        ),
        "homepage": d.get("homepage", ""),
        "id": d.get("id"),
        "keywords": json.dumps(
            [{"id": k["id"], "name": k["name"]} for k in d.get("keywords", {}).get("keywords", [])]
        ),
        "original_language": d.get("original_language", ""),
        "original_title": d.get("original_title", ""),
        "overview": d.get("overview", ""),
        "popularity": d.get("popularity", 0.0),
        "production_companies": json.dumps(
            [{"name": c["name"], "id": c["id"]} for c in d.get("production_companies", [])]
        ),
        "production_countries": json.dumps(
            [{"iso_3166_1": c["iso_3166_1"], "name": c["name"]} for c in d.get("production_countries", [])]
        ),
        "release_date": d.get("release_date", ""),
        "revenue": d.get("revenue", 0),
        "runtime": d.get("runtime"),
        "spoken_languages": json.dumps(
            [{"iso_639_1": l["iso_639_1"], "name": l["name"]} for l in d.get("spoken_languages", [])]
        ),
        "status": d.get("status", ""),
        "tagline": d.get("tagline", ""),
        "title": d.get("title", ""),
        "vote_average": d.get("vote_average", 0.0),
        "vote_count": d.get("vote_count", 0),
    }


def to_tmdb5000_credits_row(d: dict) -> dict:
    """Reshape credits into the tmdb_5000_credits.csv schema."""
    credits = d.get("credits", {})

    cast = [
        {
            "cast_id": c.get("cast_id"),
            "character": c.get("character"),
            "credit_id": c.get("credit_id"),
            "gender": c.get("gender"),
            "id": c.get("id"),
            "name": c.get("name"),
            "order": c.get("order"),
        }
        for c in credits.get("cast", [])
    ]

    crew = [
        {
            "credit_id": c.get("credit_id"),
            "department": c.get("department"),
            "gender": c.get("gender"),
            "id": c.get("id"),
            "job": c.get("job"),
            "name": c.get("name"),
        }
        for c in credits.get("crew", [])
    ]

    return {
        "movie_id": d.get("id"),
        "title": d.get("title", ""),
        "cast": json.dumps(cast),
        "crew": json.dumps(crew),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_year", type=int, default=2018)
    parser.add_argument("--end_year", type=int, default=2026)
    parser.add_argument("--pages_per_year", type=int, default=10, help="~20 movies per page")
    parser.add_argument("--min_votes", type=int, default=20, help="skip movies with too few votes/too obscure")
    args = parser.parse_args()

    print("Discovering movie IDs...")
    movie_ids = discover_movie_ids(args.start_year, args.end_year, args.pages_per_year, args.min_votes)
    print(f"Found {len(movie_ids)} unique movies to fetch.")

    movie_rows, credit_rows = [], []
    failed_ids = []
    CHECKPOINT_EVERY = 200  # save partial progress periodically, in case of a crash

    for i, movie_id in enumerate(tqdm(movie_ids, desc="Fetching movie details"), start=1):
        details = fetch_movie_details(movie_id)
        if details is None:
            failed_ids.append(movie_id)
            continue
        movie_rows.append(to_tmdb5000_movie_row(details))
        credit_rows.append(to_tmdb5000_credits_row(details))
        time.sleep(0.03)

        if i % CHECKPOINT_EVERY == 0:
            pd.DataFrame(movie_rows).to_csv("Datasets/extracted/new_movies.csv", index=False)
            pd.DataFrame(credit_rows).to_csv("Datasets/extracted/new_credits.csv", index=False)

    movies_df = pd.DataFrame(movie_rows)
    credits_df = pd.DataFrame(credit_rows)

    movies_df.to_csv("Datasets/extracted/new_movies.csv", index=False)
    credits_df.to_csv("Datasets/extracted/new_credits.csv", index=False)

    print(f"\nSaved {len(movies_df)} movies")
    print(f"Saved {len(credits_df)} credit records ")

    if failed_ids:
        print(f"\n{len(failed_ids)} movies failed after all retries and were skipped.")
        print(f"IDs: {failed_ids[:20]}{' ...' if len(failed_ids) > 20 else ''}")
