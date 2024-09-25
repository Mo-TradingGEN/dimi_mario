from flask import Flask, render_template, jsonify, request
from backend import search_company, fetch_and_save_news_for_ticker, generate_summaries_for_ticker, generate_weekly_summary
import pymongo

app = Flask(__name__)


# MongoDB connection setup
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client['news_ai']
company_collection = db['companyinfo']
news_collection = db['news_data']
daily_sum_collection = db['daily_sum']
weekly_sum_collection = db['weekly_sum']

# Homepage route that pre-loads TradingGEN info
# Homepage route that pre-loads TradingGEN info
@app.route('/')
def home():
    companyInfo = {
        "company_name": "Test",
        "symbol": "TG",
        "sector": "Financial Services",
        "sub_industry": "Financial Data Providers",
        "headquarters": "New York, USA",
        "founded": 2005,
        "employees": 1200,
        "description": "A leading financial data provider."
    }
    return render_template('index.html', companyInfo=companyInfo)

@app.route('/search/<ticker>', methods=['GET'])
def search_company_route(ticker):
    try:
        result = company_collection.find_one({"Symbol": ticker.upper()})
        if result:
            return jsonify({
                "company_name": result.get('Company Name (Yahoo)', 'N/A'),
                "symbol": result.get('Symbol', 'N/A'),
                "sector": result.get('GICS Sector', 'N/A'),
                "sub_industry": result.get('GICS Sub-Industry', 'N/A'),
                "headquarters": result.get('Headquarters Location', 'N/A'),
                "founded": result.get('Founded', 'N/A'),
                "employees": result.get('Full-Time Employees', 'N/A'),
                "description": result.get('Description', 'N/A')
            }), 200
        else:
            return jsonify({"error": "Company not found"}), 404
    except Exception as e:
        print(f"Error occurred while searching for company {ticker}: {e}")
        return jsonify({"error": "An error occurred during company search."}), 500
    
# Route for fetching news by ticker symbol
@app.route('/fetch_news/<ticker>', methods=['POST'])
def fetch_news_route(ticker):
    try:
        fetch_and_save_news_for_ticker(ticker)
        return jsonify({"message": f"News for {ticker} fetched successfully."}), 200
    except Exception as e:
        print(f"Error occurred while fetching news for {ticker}: {e}")
        return jsonify({"error": "An error occurred while fetching news."}), 500

# Route for starting the summarization process
@app.route('/summarize', methods=['POST'])
def summarize_route():
    try:
        data = request.get_json()  # Expecting JSON payload with 'ticker'
        ticker = data.get('ticker')
        if not ticker:
            return jsonify({"error": "Ticker is required"}), 400
        generate_summaries_for_ticker(ticker)
        return jsonify({"message": f"Summarization process started for {ticker}."}), 200
    except Exception as e:
        print(f"Error occurred during summarization: {e}")
        return jsonify({"error": "An error occurred during summarization."}), 500

# Route for generating weekly summary for a ticker
@app.route('/weekly_summary/<ticker>', methods=['POST'])
def weekly_summary_route(ticker):
    try:
        generate_weekly_summary(ticker)
        return jsonify({"message": f"Weekly summary for {ticker} generated successfully."}), 200
    except Exception as e:
        print(f"Error occurred while generating weekly summary for {ticker}: {e}")
        return jsonify({"error": "An error occurred while generating the weekly summary."}), 500

if __name__ == '__main__':
    app.run(debug=True)