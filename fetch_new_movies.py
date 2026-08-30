##Task is to fetch the new movies from the TMDB API 
##Structure it in the same way as the TMDB 5000 dataset
##So that it is easier to concatenate

import argparse
import os
import json
import time
import requests
from tqdm import tqdm

import pandas as pd
from config import TMDB_API_KEY, BASE_URL

SESSION = requests.Session()

def discover_movie_ids(start_year:int, end_year:int, pages_per_year:int, min_votes:int)->list[int]:
    ## Main goal is to get the list of ids of particular movies in between start year and end year
    ids = []
    for year in range(start_year, end_year+1):
        for pages in range(1,pages_per_year+1):
            resp = SESSION.get(
                f"{BASE_URL}/discover/movie",
                params={
                    "api_key":TMDB_API_KEY,
                    "primary_release_year":year,
                    "sort_by":"popularity.desc",
                    "vote_count_gte": min_votes,
                    "page": pages
                },
            )
            if resp.status_code != 200:
                print(f"[warn] year = {year} page={pages} failed: {resp.status_code}")
                continue

            data = resp.json()
            results = data.get("results",[])
            if not results:
                break
            ids.extend(m["id"] for m in results)

            if pages>=data.get("total_pages",1):
                break

            time.sleep(0.03)

        print(f"Year {year}: collected {len(ids)} total IDs so far")

    return sorted(set(ids))

def fetch_movie_details(movie_id:int)->dict|None :
    resp = SESSION.get(
        f"{BASE_URL}/movie/{movie_id}",
        params = {
            "api_key": TMDB_API_KEY,
            "append_to_response": "credits,keywords",
        },
    )
    if resp.status_code != 200:
        return None
    return resp.json()

def to_og_movie_row(d:dict)->dict:
    return {
        "budget": d.get("budget",0),
        "genres": json.dumps(
            [{"id": g["id"], "name": g["name"]} for g in d.get("genres", [])]
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

def to_og_credit_row(d:dict)->dict:
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_year",type=int,default=2018)
    parser.add_argument("--end_year",type=int,default = 2026)
    parser.add_argument("--pages_per_year",type=int,default=10)
    parser.add_argument("--min_votes",type=int,default = 20)

    args = parser.parse_args()

    print("Discovering Movie IDs...")
    movie_ids = discover_movie_ids(args.start_year,args.end_year,args.pages_per_year,args.min_votes)
    print(f"Found {len(movie_ids)} unique movies to fetch.")

    movie_rows,credits_rows = [],[]

    for movie_id in tqdm(movie_ids, desc="Fetching movie details"):
        details = fetch_movie_details(movie_id)
        if details is None:
            continue
        movie_rows.append(to_og_movie_row(details))
        credits_rows.append(to_og_credit_row(details))
        time.sleep(0.03)
 
    movies_df = pd.DataFrame(movie_rows)
    credits_df = pd.DataFrame(credits_rows)
 
    movies_df.to_csv("Datasets/extracted/new_movies.csv", index=False)
    credits_df.to_csv("Datasets/extracted/new_credits.csv", index=False)
 
    print(f"\nSaved {len(movies_df)} movies to Datasets/extracted/new_movies.csv")
    print(f"Saved {len(credits_df)} credit records to Datasets/extracted/new_credits.csv")
