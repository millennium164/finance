import csv
import datetime
import pytz
import requests
import urllib
import uuid

from flask import redirect, render_template, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    symbol = symbol.upper()
    end = datetime.datetime.now(pytz.timezone("US/Eastern"))
    start = end - datetime.timedelta(days=7)

    # Alpha Vantage API
    API_KEY = "KGC9RPMVYX2GZDAF"
    url = (
        f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
        f"&symbol={symbol}&apikey={API_KEY}"
    )

    # Query API
    try:
        response = requests.get(url)
        response.raise_for_status()

        # Parse JSON response
        data = response.json()

        # Obter o preço de fechamento mais recente
        if "Time Series (Daily)" in data:
            # Pega a data mais recente no formato yyyy-mm-dd
            latest_date = max(data["Time Series (Daily)"].keys())
            latest_close = data["Time Series (Daily)"][latest_date]["4. close"]

            price = round(float(latest_close), 2)
            return {"price": price, "symbol": symbol}
        else:
            return None
    except (KeyError, IndexError, requests.RequestException, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"