import pandas as pd
import fasttext
import fasttext.util
import os
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

SEARCH_HISTORY_FILE = "L:\\search_engine\\search_history.csv"
TRAINING_DATA_FILE = "L:\\search_engine\\training_data.txt"
MODEL_PATH = "L:\\search_engine\\fast_model.bin"


def load_search_history():
    try:
        df = pd.read_csv(SEARCH_HISTORY_FILE)
        df.drop_duplicates(subset=["query"], inplace=True)  
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=["query"])

def train_fasttext_model():
    df = load_search_history()
    if not df.empty:
        df["query"].to_csv(TRAINING_DATA_FILE, index=False, header=False)
        model = fasttext.train_unsupervised(TRAINING_DATA_FILE, model="skipgram")
        model.save_model(MODEL_PATH)
        return model
    return None

def load_fasttext_model():
    global fasttext_model  
    if os.path.exists(MODEL_PATH):
        try:
            return fasttext.load_model(MODEL_PATH)
        except ValueError:
            print("Corrupted model detected. Retraining...")
            os.remove(MODEL_PATH)
            return train_fasttext_model()
    return train_fasttext_model()

fasttext_model = load_fasttext_model()


def get_related_searches(query, history_df, model, threshold=0.7):
    if history_df.empty:
        return []
    input_vector = model.get_sentence_vector(query)
    history_vectors = np.array([model.get_sentence_vector(q) for q in history_df["query"]])
    similarities = cosine_similarity([input_vector], history_vectors).flatten()
    related_searches = history_df.loc[similarities >= threshold, "query"].tolist()
    return related_searches


def process_search(query):
    global fasttext_model
    history_df = load_search_history()
    related_searches = get_related_searches(query, history_df, fasttext_model)
    
    if related_searches:
        print("🔍 Related searches found:")
        for search in related_searches:
            print(f" :--{search}")
    else:
        print("No related searches found. Adding to training data...")
        new_entry = pd.DataFrame({"query": [query]})
        history_df = pd.concat([history_df, new_entry], ignore_index=True)
        history_df.to_csv(SEARCH_HISTORY_FILE, index=False)
        fasttext_model = train_fasttext_model()

# Example usage
if __name__ == "__main__":
    user_query = input("Enter search query: ")
    process_search(user_query)
