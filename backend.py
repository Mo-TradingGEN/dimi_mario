from pymongo import MongoClient
from datetime import datetime, timedelta
import pymongo

# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017/')
db = client['news_ai']
company_collection = db['companyinfo']
news_collection = db['news_data']
daily_sum_collection = db['daily_sum']
weekly_sum_collection = db['weekly_sum']

# Function to search for a company by ticker symbol
def search_company(ticker):
    try:
        # Search for the company in the MongoDB collection using the ticker
        result = company_collection.find_one({"Symbol": ticker.upper()})
        if result:
            # Return the formatted result
            return {
                "company_name": result.get('Company Name (Yahoo)', 'N/A'),
                "symbol": result.get('Symbol', 'N/A'),
                "sector": result.get('GICS Sector', 'N/A'),
                "sub_industry": result.get('GICS Sub-Industry', 'N/A'),
                "headquarters": result.get('Headquarters Location', 'N/A'),
                "founded": result.get('Founded', 'N/A'),
                "employees": result.get('Full-Time Employees', 'N/A'),
                "description": result.get('Description', 'N/A')
            }
        else:
            return None
    except Exception as e:
        print(f"Error occurred while searching for company {ticker}: {e}")
        return None

# Function to fetch the last published date of news articles for a specific ticker
def get_last_published_date(ticker):
    try:
        latest_article = news_collection.find_one(
            {'Ticker': ticker},
            sort=[('PublishedAt', pymongo.DESCENDING)]
        )
        return latest_article['PublishedAt'] if latest_article else None
    except Exception as e:
        print(f"Error occurred while fetching last published date for {ticker}: {e}")
        return None

# Function to fetch and save news for a specific ticker
def fetch_and_save_news_for_ticker(ticker, fetch_news, save_news_to_mongo):
    try:
        company = company_collection.find_one({"Symbol": ticker.upper()})
        if company:
            company_name = company.get('Company Name (Yahoo)', 'Unknown')
            last_published_date = get_last_published_date(ticker) or (datetime.today() - timedelta(days=7)).isoformat()
            query = f"'{company_name}' OR '{ticker}'"
            news_data = fetch_news(query, last_published_date, datetime.today().isoformat())
            if news_data and news_data.get("articles"):
                save_news_to_mongo(news_data["articles"], ticker, company_name)
                return f"News for {ticker} fetched and saved."
            else:
                return f"No news articles found for {ticker} ({company_name})"
        return f"No company found for ticker: {ticker}"
    except Exception as e:
        print(f"Error occurred while fetching news for {ticker}: {e}")
        return f"Error occurred while fetching news for {ticker}."

# Function to get summaries based on a date range
def get_summary(date_range):
    try:
        today = datetime.now().date()
        if date_range == "Today":
            start_date = today
        elif date_range == "Yesterday":
            start_date = today - timedelta(days=1)
        elif date_range == "Week ago":
            start_date = today - timedelta(weeks=1)
        elif date_range == "Month ago":
            start_date = today - timedelta(weeks=4)
        else:
            return "Invalid date range"

        end_date = start_date + timedelta(days=1)
        summary = daily_sum_collection.find_one({
            'date': {'$gte': start_date.isoformat(), '$lt': end_date.isoformat()}
        })
        return summary['daily_summary'] if summary else "No summary found for the selected date range."
    except Exception as e:
        print(f"Error occurred while fetching summary for {date_range}: {e}")
        return f"Error occurred while fetching summary for {date_range}."

# Function to calculate the date range for the previous week (Monday to Sunday)
def calculate_last_week():
    today = datetime.now().date()
    last_sunday = today - timedelta(days=today.weekday() + 1)  # Sunday of last week
    last_monday = last_sunday - timedelta(days=6)  # Monday of last week
    return last_monday, last_sunday

# Function to generate daily summaries for a specific ticker
def generate_summaries_for_ticker(ticker):
    from news_processing import fetch_unique_dates, fetch_articles_by_date_and_ticker, combine_summaries_and_sources, save_daily_summary
    try:
        unique_dates = fetch_unique_dates(ticker)
        for target_date in unique_dates:
            print(f"Generating summary for {ticker} on {target_date}...")
            articles = fetch_articles_by_date_and_ticker(target_date, ticker)
            if articles:
                article_ids = [article['_id'] for article in articles]
                final_summary, sources = combine_summaries_and_sources(articles)
                save_daily_summary(target_date, final_summary, article_ids, ticker, sources)
            else:
                print(f"No articles found for {ticker} on {target_date}")
    except Exception as e:
        print(f"Error occurred while generating summaries for {ticker}: {e}")

# Function to generate weekly summaries
def generate_weekly_summary(ticker="AAPL"):
    from news_processing import fetch_daily_summaries_for_week, combine_summaries_and_sources, save_weekly_summary
    try:
        last_weekly_summary = weekly_sum_collection.find_one(sort=[("week_ending", pymongo.DESCENDING)])
        last_monday, last_sunday = calculate_last_week()

        if last_weekly_summary:
            last_week_ending = datetime.fromisoformat(last_weekly_summary['week_ending']).date()
            next_monday = last_week_ending + timedelta(days=1)
        else:
            next_monday = last_monday

        while next_monday <= datetime.now().date():
            next_sunday = next_monday + timedelta(days=6)
            daily_summaries = fetch_daily_summaries_for_week(next_monday, next_sunday, ticker)
            daily_ids = [summary['_id'] for summary in daily_summaries]
            final_summary, sources = combine_summaries_and_sources(daily_summaries)
            save_weekly_summary(next_sunday, final_summary, daily_ids, sources)
            next_monday += timedelta(days=7)
    except Exception as e:
        print(f"Error occurred while generating weekly summary for {ticker}: {e}")

# Function to trigger summarization
def summarize_articles():
    from news_processing import process_and_summarize_articles
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(process_and_summarize_articles(batch_size=8))
        else:
            asyncio.run(process_and_summarize_articles(batch_size=8))
    except RuntimeError:
        asyncio.run(process_and_summarize_articles(batch_size=8))
