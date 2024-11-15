## BIBLIOTECAS ##

import os
from dotenv import load_dotenv

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
import psycopg2
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

############################################################################

## CONFIGURAÇÕES ##

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Carrega as variáveis do arquivo .env
load_dotenv()
db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

# Connect to the PostgreSQL database
conn = psycopg2.connect(
    dbname=db_name,
    user=db_user,
    password=db_password,
    host=db_host,
    port='5432'
)

# Create cursor
cursor = conn.cursor()

# Função para ser processada após cada solicitação e antes de enviar resposta
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

############################################################################

## ROUTES ##

## Index/home
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    # Add more money
    if request.method == "POST":
        money = request.form.get("money")
        money = float(money)
        select = '''
        SELECT cash FROM users WHERE id = (%s)
        '''
        cursor.execute(select, (session["user_id"], ))
        cash = cursor.fetchall()
        cash = float(cash[0][0])
        cash = cash + money
        update = '''
        UPDATE users SET cash = (%s) WHERE id = (%s)
        '''
        values = (cash, session["user_id"])
        cursor.execute(update, values)
        conn.commit()
        return redirect("/")
    else:
        # Select stock symbols and n° of shares from user
        select = '''
        SELECT DISTINCT stock, SUM(shares) FROM transactions WHERE user_id = (%s) GROUP BY stock
        '''
        cursor.execute(select, (session["user_id"], ))
        portofolio = cursor.fetchall()

        # Initialize lists for appending every actual unit price and total value
        unit_list = []
        total_list = []
        subtotal = 0

        # Lookup for every stock in portofolio
        for i in portofolio:
            quote = lookup(i[0])
            unit = quote["price"]
            unit_list.append(unit)
            total = round(unit * i[1], 2)
            total_list.append(total)
            subtotal = subtotal + total

        # Passing in arguments to render_template
        table_length = len(unit_list)
        select = '''
        SELECT cash FROM users WHERE id = (%s)
        '''
        cursor.execute(select, (session["user_id"], ))
        cash = cursor.fetchall()
        cash = float(cash[0][0])
        subtotal = subtotal + cash
        return render_template("index.html", portofolio=portofolio, unit=unit_list, total=total_list, length=table_length, cash=cash, subtotal=subtotal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # Cash available
    select = '''
    SELECT cash FROM users WHERE id = (%s)
    '''
    cursor.execute(select, (session["user_id"], ))
    cash = cursor.fetchall()
    cash = float(cash[0][0])

    # Buy form was submitted
    if request.method == "POST":

        # datetime object containing current date and time
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        # Stock symbol and price
        symb = request.form.get("symbol")
        quote = lookup(symb)
        if quote == None:
            return apology("invalid symbol")
        price = quote["price"]
        symbol = quote["symbol"]

        # Number of shares
        shares_i = request.form.get("shares")
        try:
            shares_i = float(shares_i)
        except:
            return apology("not a valid number of shares")
        shares = int(shares_i)
        if shares != shares_i:
            return apology("insert a non-fractional number of shares")
        if shares <= 0:
            return apology("invalid number of shares")

        # Total spent in stock
        spent = price * shares
        if cash < spent:
            return apology("insuficient funds")

        # Update cash
        cash = cash - spent
        update = '''
        UPDATE users SET cash = (%s) WHERE id = (%s)
        '''
        values = (cash, session["user_id"])
        cursor.execute(update, values)
        conn.commit()

        # Uptade portofolio
        insert = '''
        INSERT INTO transactions (user_id, stock, shares, unit, total, datetime) VALUES ((%s), (%s), (%s), (%s), (%s), (%s))
        '''
        values = (session["user_id"], symbol, shares, price, spent, dt_string)
        cursor.execute(insert, values)
        conn.commit()
        return redirect("/")

    # Form for buying stocks
    else:
        return render_template("buy.html", cash=cash)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Select from database stock symbols and n° of shares
    select = '''
    SELECT id, stock, shares, unit, total, datetime FROM transactions WHERE user_id = (%s)
    '''
    cursor.execute(select, (session["user_id"], ))
    history = cursor.fetchall()

    # Passing in arguments to render_template
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        select = '''
        SELECT * FROM users WHERE username = (%s)
        '''
        cursor.execute(select, (request.form.get("username"), ))
        rows = cursor.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0][2], request.form.get("password")
        ):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0][0]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # Stock symbol was submitted
    if request.method == "POST":
        symb = request.form.get("symbol")

        # Stock symbol and price
        quote = lookup(symb)
        if quote == None:
            return apology("invalid symbol")
        return render_template("quoted.html", price=usd(quote["price"]), symbol=quote["symbol"])

    # Form for stock quote
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Register form was submitted
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Apologise if username is blank or already exists
        select = '''
        SELECT * FROM users WHERE username = (%s)
        '''
        cursor.execute(select, (username, ))
        usr = cursor.fetchall()
        if not username:
            return apology("insert a valid username")
        if len(usr) != 0:
            return apology("username already exists")

        # Apologise if passwords are blank or don't match
        if not password or not confirmation:
            return apology("insert a valid password")
        if password != confirmation:
            return apology("passwords don't match")

        # Insert new user in database
        hash = generate_password_hash(password, method='pbkdf2', salt_length=16)
        query = '''
        INSERT INTO users (username, password) VALUES ((%s), (%s))
        '''
        values = (username, hash)
        cursor.execute(query, values)
        conn.commit()
        return redirect("/login")

    # Form for register
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Cash available
    select = '''
    SELECT cash FROM users WHERE id = (%s)
    '''
    cursor.execute(select, (session["user_id"], ))
    cash = cursor.fetchall()
    cash = float(cash[0][0])

    # Select from database stock symbols and n° of shares
    select = '''
    SELECT DISTINCT stock, SUM(shares) FROM transactions WHERE user_id = (%s) GROUP BY stock
    '''
    cursor.execute(select, (session["user_id"], ))
    portofolio = cursor.fetchall()

    # Sell form was submitted
    if request.method == "POST":

        # datetime object containing current date and time
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        # Stock symbol and price
        symb = request.form.get("symbol")
        quote = lookup(symb)
        price = quote["price"]
        symbol = quote["symbol"]

        # Number of shares
        shares = request.form.get("shares")
        shares = float(shares)
        if shares <= 0:
            return apology("invalid number of shares")
        select = '''
        SELECT SUM(shares) FROM transactions WHERE (stock, user_id) = ((%s), (%s))
        '''
        values = (symbol, session["user_id"])
        cursor.execute(select, values)
        owned_shares = cursor.fetchall()
        owned_shares = owned_shares[0][0]
        if shares > owned_shares:
            return apology(f"You don't own that many shares of {symbol}")
        if owned_shares == 0:
            return apology(f"You don't own any of {symbol} shares")

        # Total earned in selling
        sold = price * shares

        # Update cash
        cash = cash + sold
        update = '''
        UPDATE users SET cash = (%s) WHERE id = (%s)
        '''
        values = (cash, (session["user_id"], ))
        cursor.execute(update, values)
        conn.commit()

        # Uptade portofolio
        shares = -shares
        insert = '''
        INSERT INTO transactions (user_id, stock, shares, unit, total, datetime) VALUES ((%s), (%s), (%s), (%s), (%s), (%s))
        '''
        values = (session["user_id"], symbol, shares, price, sold, dt_string)
        cursor.execute(insert, values)
        conn.commit()
        return redirect("/")

    # Form for selling stocks
    else:
        table_length = len(portofolio)
        return render_template("sell.html", portofolio=portofolio, length=table_length, cash=cash)
    
if __name__=='__main__':
    app.run(debug=True)