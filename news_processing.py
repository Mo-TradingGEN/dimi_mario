import requests
from goose3 import Goose
from datetime import datetime, timedelta
from joblib import Parallel, delayed
from pymongo import MongoClient  # MongoDB
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
import torch
import pymongo
import gc
import os
import asyncio
import time

# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017/')
db = client['news_ai']  # Database
news_collection = db['news_data']  # News collection
company_info_collection = db['companyinfo']  # Company info collection
daily_sum_collection = db['daily_sum']  # Collection for storing daily summaries
weekly_sum_collection = db['weekly_sum']  # Collection for storing weekly summaries

# Replace this with your own News API key
API_KEY = 'your_api_key_here'

# Initialize Goose (for scraping full article content)
g = Goose()

# Function to fetch news data from News API
def fetch_news(query, from_date, to_date, api_key=API_KEY, language='en', page_size=100):
    url = f"https://newsapi.org/v2/everything?q={query}&from={from_date}&to={to_date}&language={language}&pageSize={page_size}&apiKey={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        news_data = response.json()
        return news_data
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    return None

# Function to clean text
def clean_text(text):
    return '\n\n'.join([para.strip() for para in text.split('\n') if para.strip()])

# Function to scrape full content using Goose3 and apply cleaning
def scrape_full_content(article_url):
    try:
        article = g.extract(url=article_url)
        cleaned_text = clean_text(article.cleaned_text) if article.cleaned_text else "Full content not available"
        return cleaned_text
    except Exception as err:
        print(f"Error scraping content from {article_url}: {err}")
        return "Full content not available"

# Function to process articles and add ticker, company name, and status
def process_article(article, ticker, company_name):
    source = article['source']['name'] if article['source'] and article['source']['name'] else 'N/A'
    author = article['author'] if article['author'] else 'N/A'
    title = article['title'] if article['title'] else 'N/A'
    description = article['description'] if article['description'] else 'N/A'
    url = article['url'] if article['url'] else 'N/A'
    urlToImage = article['urlToImage'] if article['urlToImage'] else 'N/A'
    publishedAt = article['publishedAt'] if article['publishedAt'] else 'N/A'

    # Scrape full content using Goose3
    content = scrape_full_content(url)

    # Return the processed article data including ticker, company name, and status
    return {
        'Source': source,
        'Author': author,
        'Title': title,
        'Description': description,
        'URL': url,
        'URLToImage': urlToImage,
        'PublishedAt': publishedAt,
        'Content': content,
        'Ticker': ticker,  # Add ticker to the document
        'CompanyName': company_name,  # Add company name
        'status': 0  # Status: 0 = "unprocessed"
    }

# Function to save news data to MongoDB
def save_news_to_mongo(news_data, ticker, company_name):
    if news_data:
        # Use parallel processing to process the articles
        processed_articles = Parallel(n_jobs=-1)(delayed(process_article)(article, ticker, company_name) for article in news_data)

        # Filter out unwanted articles (those with "Full content not available" and unwanted URLs)
        filtered_articles = [article for article in processed_articles if article['Content'] != "Full content not available"]
        
        if filtered_articles:  # Only save if there is any data left after filtering
            news_collection.insert_many(filtered_articles)  # Save to MongoDB
            print(f"News data for {ticker} ({company_name}) saved to MongoDB in 'news_ai.news_data'")
        else:
            print("No articles to save after filtering.")
    else:
        print("No articles found.")

# Check if CUDA (GPU) is available
device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
print(f"Using device: {'GPU' if torch.cuda.is_available() else 'CPU'}")

# Set CUDA memory config to avoid fragmentation
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"

# Load the model and tokenizer for summarization
model = AutoModelForSeq2SeqLM.from_pretrained("t5-base").to(device)
tokenizer = AutoTokenizer.from_pretrained("t5-base")

# Load articles from MongoDB for summarization
def load_articles_from_mongo(batch_size=8):
    cursor = news_collection.find(
        {'status': 0},  # Only fetch articles that haven't been summarized
        {'_id': 1, 'Content': 1, 'Ticker': 1}
    ).batch_size(batch_size)

    for article in cursor:
        yield article

def summarize_batch(batch):
    texts = [article['Content'] for article in batch]
    inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)

    with torch.cuda.amp.autocast():
        summaries = model.generate(input_ids=inputs['input_ids'], attention_mask=inputs['attention_mask'], max_length=150, min_length=50)

    return [tokenizer.decode(summary, skip_special_tokens=True) for summary in summaries]

# Async function to summarize and update MongoDB
async def process_and_summarize_articles(batch_size=8):
    batch = []
    for article in load_articles_from_mongo(batch_size):
        batch.append(article)
        
        if len(batch) == batch_size:
            summaries = summarize_batch(batch)
            bulk_updates = [{'filter': {'_id': article['_id']}, 'update': {'$set': {'Summary': summaries[idx], 'status': 1}}} for idx, article in enumerate(batch)]
            await update_mongo_async(bulk_updates)
            torch.cuda.empty_cache()
            gc.collect()
            batch = []

    if batch:
        summaries = summarize_batch(batch)
        bulk_updates = [{'filter': {'_id': article['_id']}, 'update': {'$set': {'Summary': summaries[idx], 'status': 1}}} for idx, article in enumerate(batch)]
        await update_mongo_async(bulk_updates)

# Async function to update MongoDB after summarization
async def update_mongo_async(bulk_updates):
    bulk_ops = [pymongo.UpdateOne(op['filter'], op['update']) for op in bulk_updates]
    result = news_collection.bulk_write(bulk_ops)
    print(f"Bulk update completed: {result.bulk_api_result}")

# Function to fetch unique dates for a specific ticker
def fetch_unique_dates(ticker):
    unique_dates = news_collection.distinct("PublishedAt", {"Ticker": ticker})
    return sorted(set([datetime.fromisoformat(date).date() for date in unique_dates]))

# Function to fetch articles by date and ticker
def fetch_articles_by_date_and_ticker(target_date, ticker):
    start_date = datetime.combine(target_date, datetime.min.time())
    end_date = start_date + timedelta(days=1)
    return list(news_collection.find({'PublishedAt': {'$gte': start_date.isoformat(), '$lt': end_date.isoformat()}, 'Ticker': ticker}))

# Function to combine summaries and sources
def combine_summaries_and_sources(articles):
    combined_summary_text = " ".join([article['Summary'] for article in articles])
    sources = list(set([article['Source'] for article in articles]))
    return combined_summary_text, sources

# Function to save daily summaries to MongoDB
def save_daily_summary(target_date, final_summary, article_ids, ticker, sources):
    summary_data = {
        "date": target_date.isoformat(),
        "ticker": ticker,
        "daily_summary": final_summary,
        "article_ids": article_ids,
        "sources": sources,
        "created_at": datetime.now().isoformat()
    }
    daily_sum_collection.insert_one(summary_data)

# Function to generate weekly summaries
def fetch_daily_summaries_for_week(monday, sunday, ticker="AAPL"):
    return list(daily_sum_collection.find({'date': {'$gte': monday.isoformat(), '$lt': (sunday + timedelta(days=1)).isoformat()}, 'ticker': ticker}))

def save_weekly_summary(week_ending, final_summary, daily_ids, sources):
    summary_data = {
        "week_ending": week_ending.isoformat(),
        "weekly_summary": final_summary,
        "daily_summary_ids": daily_ids,
        "sources": sources,
        "created_at": datetime.now().isoformat()
    }
    weekly_sum_collection.insert_one(summary_data)
