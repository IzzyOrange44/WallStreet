from flask import Flask, jsonify, request, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String
import requests
import logging
import pandas as pd
from display_bollinger import create_graph

app = Flask(__name__)

class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

class User(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

class HistoricalData(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(500), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # Store date as string
    open_price: Mapped[float] = mapped_column(nullable=False)
    high: Mapped[float] = mapped_column(nullable=False)
    low: Mapped[float] = mapped_column(nullable=False)
    close: Mapped[float] = mapped_column(nullable=False)
    volume: Mapped[int] = mapped_column(nullable=False)


ALPHA_VANTAGE_API_KEY = "7S1WKHB241M3HNC1"

@app.route("/clear", methods=["POST"])
def clear():
    with app.app_context():
        db.drop_all()
    return redirect('/')

def fetch_historical_data(ticker):
    with app.app_context():
        db.create_all()

    url = f"https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    response = requests.get(url, params=params)
    logging.debug("API Response: %s", response.json())
    if response.status_code == 200:
        data = response.json()
        if "Time Series (Daily)" in data:
            return data["Time Series (Daily)"]
        else:
            raise ValueError(f"No historical data found for ticker: {ticker}")
    else:
        raise ValueError(f"Error fetching data from Alpha Vantage: {response.status_code}")

def store_historical_data(ticker, historical_data):
    for date, stats in historical_data.items():
        new_record = HistoricalData(
            ticker=ticker,
            date=date,
            open_price=float(stats["1. open"]),
            high=float(stats["2. high"]),
            low=float(stats["3. low"]),
            close=float(stats["4. close"]),
            volume=int(stats["5. volume"]),
        )
        db.session.add(new_record)
    db.session.commit()

def return_historical_data():
    db.session.execute(db.select)

@app.route('/')
def home():
    with app.app_context():
        db.create_all()
    return render_template('test.html')

@app.route('/submit', methods=['POST'])
def get_user_input():
    ticker = request.form.get("ticker")
    if ticker:
        new_request = User(name=ticker)
        db.session.add(new_request)
        db.session.commit()

        try:
            historical_data = fetch_historical_data(ticker)
            store_historical_data(ticker, historical_data)
            return render_template("test.html", message="Ticker and historical data stored successfully!")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    return jsonify("Error: Invalid input"), 400


@app.route('/display-data', methods=['POST'])
def display_data():
    # Fetch all records from HistoricalData
    results = HistoricalData.query.all()

    # Convert the results to a list of dictionaries for DataFrame
    data = [{
        'id': record.id,
        'ticker': record.ticker,
        'date': record.date,
        'open_price': record.open_price,
        'high': record.high,
        'low': record.low,
        'close': record.close,
        'volume': record.volume
    } for record in results]

    # Create the DataFrame
    df = pd.DataFrame(data)


    df_html, chart_path = create_graph(df)

    # Render data on an HTML template
    return render_template('historical_data.html', tables=df_html, chart_url=chart_path)

if __name__ == '__main__':
    app.run(debug=True)
