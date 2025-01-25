from flask import Flask, Response, jsonify, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, text
import requests
import logging
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from display_bollinger import create_graph
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')


class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI','sqlite:///users.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

class User(UserMixin,db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(500), unique=True)
    name: Mapped[str] = mapped_column(String(500))
    password: Mapped[str] = mapped_column(String(500))

with app.app_context():
    db.create_all()

class HistoricalData(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('user.id'), nullable=False)
    ticker: Mapped[str] = mapped_column(String(500), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # Store date as string
    open_price: Mapped[float] = mapped_column(nullable=False)
    high: Mapped[float] = mapped_column(nullable=False)
    low: Mapped[float] = mapped_column(nullable=False)
    close: Mapped[float] = mapped_column(nullable=False)
    volume: Mapped[int] = mapped_column(nullable=False)


ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_KEY')

# Monkey patch the set_cookie method to ignore 'partitioned'
original_set_cookie = Response.set_cookie

def patched_set_cookie(self, *args, **kwargs):
    kwargs.pop('partitioned', None)  # Remove 'partitioned' if it exists
    return original_set_cookie(self, *args, **kwargs)

Response.set_cookie = patched_set_cookie

# Save the original delete_cookie method
original_delete_cookie = Response.delete_cookie

def patched_delete_cookie(self, *args, **kwargs):
    kwargs.pop('partitioned', None)  # Remove 'partitioned' if it exists
    return original_delete_cookie(self, *args, **kwargs)

# Replace the original method with the patched one
Response.delete_cookie = patched_delete_cookie


def fetch_historical_data(ticker):

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
            user_id=current_user.id,
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

@app.route('/')
def home():
    return render_template('homepage.html', logged_in= current_user.is_authenticated)

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get('email')
        result = db.session.execute(db.select(User).where(User.email == email))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            request.form.get("password"),
            method="pbkdf2:sha256",
            salt_length=8,)

        new_user = User(
            email=request.form.get('email'),
            name=request.form.get('name'),
            password=hash_and_salted_password,
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        return redirect(url_for('test'))

    return render_template("register.html", logged_in= current_user.is_authenticated)

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')

        # Find user by email entered.
        result = db.session.execute(db.select(User).where(User.email == email))
        user = result.scalar()

        # Check stored password hash against entered password hashed.
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('test'))

    return render_template("login.html", logged_in= current_user.is_authenticated)

@app.route('/test')
@login_required
def test():
    with app.app_context():
        db.create_all()
    print(current_user.name)
    return render_template('test.html', name=current_user.name, logged_in=True)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/clear", methods=["POST"])
@login_required
def clear():
    try:
        # Delete rows instead of dropping the table
        HistoricalData.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        flash("All historical data has been deleted successfully.")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {str(e)}")
    return redirect(url_for('test'))


@app.route('/submit', methods=['POST'])
@login_required
def get_user_input():
    ticker = request.form.get("ticker")
    if ticker:
        try:
            historical_data = fetch_historical_data(ticker)
            store_historical_data(ticker, historical_data)
            return redirect(url_for('test'))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    return jsonify("Error: Invalid input"), 400


@app.route('/display-data', methods=['POST'])
@login_required
def display_data():
    # Fetch all records from HistoricalData
    results = HistoricalData.query.filter_by(user_id=current_user.id).all()

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
    app.run(debug=False)