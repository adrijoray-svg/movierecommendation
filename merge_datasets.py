import pandas as pd

RAW = "Datasets/raw"
EXTRACTED = "Datasets/extracted"
OUT = "Datasets/final merged datasets"

def merge_movies():
    original = pd.read_csv(f'{RAW}/tmdb_5000_movies.csv')
    new = pd.read_csv(f'{EXTRACTED}/new_movies.csv')

    combined = pd.concat([original,new],ignore_index=True)
    combined = combined.drop_duplicates(subset="id",keep = "first")

    combined.to_csv(f"{OUT}/tmdb_movies_extended.csv",index=False)
    return combined

def merge_credits(kept_ids: set):
    original = pd.read_csv(f"{RAW}/tmdb_5000_credits.csv")
    new = pd.read_csv(f"{EXTRACTED}/new_credits.csv")
 
    combined = pd.concat([original, new], ignore_index=True)
    combined = combined.drop_duplicates(subset="movie_id", keep="first")
 
    # keep credits only for movies that survived dedup in the movies table
    combined = combined[combined["movie_id"].isin(kept_ids)]
 
    combined.to_csv(f"{OUT}/tmdb_credits_extended.csv", index=False)

if __name__ == "__main__":
    movies_df = merge_movies()
    merge_credits(kept_ids=set(movies_df['id']))
    print('\nDone. Dataset Extended Successfully.')