import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # get current cash
    cash = (db.execute("SELECT cash FROM users WHERE id = :id_cur", id_cur=session["user_id"]))[0]['cash']

    # get history
    rows = db.execute("SELECT symbol,SUM(shares),user_id FROM history WHERE user_id = :id_cur GROUP BY symbol", id_cur=session["user_id"])

    table = []
    stockval = 0

    for row in rows:
        share=lookup(row['symbol'])
        table.append({
        'symbol' : row['symbol'],
        'stock_name' : share['name'],
        'shares' : row['SUM(shares)'],
        'price' : share['price'],
        'total' : float(row['SUM(shares)']) * float(share['price'])
        })
        stockval += float(row['SUM(shares)']) * float(share['price'])

    return render_template("index.html", total=(cash + stockval), table=table, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # intialize var
    stock_data = 0

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol & shares was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        elif not request.form.get("shares"):
            return apology("must buy at lease one shares", 403)
        elif int(request.form.get("shares")) < 0:
            return apology("must buy at lease one shares", 403)

        # get stock data & remain cash
        stock_data = lookup(request.form.get("symbol"))
        if stock_data == None:
            return apology("please provide a valid stock symbol", 403)

        cash = (db.execute("SELECT cash FROM users WHERE id = :id_cur",
                          id_cur=session["user_id"]))[0]['cash']

        # start trading
        cash = cash - float(stock_data['price']) * float(request.form.get("shares"))

        # make sure have enough money
        if cash > 0:

            db.execute("INSERT INTO history (symbol, shares, user_id) VALUES (:symbol, :shares, :id_cur)", id_cur=session["user_id"], symbol=request.form.get("symbol"), shares=request.form.get("shares"))

            # update remain cash
            db.execute("UPDATE users SET cash=:cash WHERE id=:id_cur",id_cur=session["user_id"], cash=cash)

            # redirect to home
            return redirect("/")

        # if cash run out
        else:
            return apology("you are running your money off", 403)

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # get history
    rows = db.execute("SELECT symbol,shares,time FROM history WHERE user_id = :id_cur ", id_cur=session["user_id"])

    table = []

    for row in rows:
        share=lookup(row['symbol'])
        table.append({
        'symbol' : row['symbol'],
        'stock_name' : share['name'],
        'shares' : row['shares'],
        'price' : share['price'],
        'total' : float(row['shares']) * float(share['price']),
        'time' : row['time']
        })

    return render_template("history.html",table=table)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout", methods=['GET','POST'])
def logout():
    """Log user out"""
    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # intialize var
    stock_data = 0

    #User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide a stock symbol", 403)

        # try Get stockdata
        stock_data = lookup(request.form.get("symbol"))

        # Ensure symbol exist
        if lookup(request.form.get("symbol")) == None:
            return apology("invalid symbol", 403)

        # redirct to new page
        return render_template("quoted.html", name=stock_data['name'], symbol=request.form.get("symbol"), price=usd(stock_data['price']))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    #User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password_a was submitted
        elif not request.form.get("password_a"):
            return apology("must provide a password in second query", 403)

        # Ensure 2 password was same
        elif request.form.get("password") != request.form.get("password_a"):
            return apology("must provide same password", 403)

        # Ensure username can not use twice
        rows = db.execute("SELECT username FROM users")
        for row in rows:
            if row == request.form.get("username"):
                return apology("Username has been used", 403)

        # Insert new user info
        db.execute("INSERT INTO users (username, hash)  VALUES (:username, :password)",
                          username=request.form.get("username") ,password=generate_password_hash(request.form.get("password")))

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # intialize var
    stock_data = 0

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol & shares was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        elif not request.form.get("shares"):
            return apology("must sell at lease one shares", 403)
        elif int(request.form.get("shares")) < 0:
            return apology("must sell at lease one shares", 403)

        # get stock data & remain cash
        stock_data = lookup(request.form.get("symbol"))
        if stock_data == None:
            return apology("please provide a valid stock symbol", 403)

        # check if that stock remain
        log = db.execute("SELECT SUM(shares) FROM history WHERE user_id = :id_cur AND symbol = :symbol GROUP BY symbol", id_cur=session["user_id"], symbol=request.form.get("symbol"))

        if not log:
            return apology("you do not have enough stock to sell", 403)

        elif int(log[0]['SUM(shares)']) >= 1:

            # get cur cash
            cash = (db.execute("SELECT cash FROM users WHERE id = :id_cur", id_cur=session["user_id"]))[0]['cash']

            # start trading
            cash = cash + float(stock_data['price']) * float(request.form.get("shares"))

            db.execute("INSERT INTO history (symbol, shares, user_id) VALUES (:symbol, :shares, :id_cur)", id_cur=session["user_id"], symbol=request.form.get("symbol"), shares=-(int(request.form.get("shares"))))

            # update remain cash
            db.execute("UPDATE users SET cash=:cash WHERE id=:id_cur",id_cur=session["user_id"], cash=cash)

            # redirect to home
            return redirect("/")

        else:
            return apology("you do not have enough stock to sell", 403)

    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
