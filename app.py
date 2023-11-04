import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, nowdate

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    
    stcks = db.execute("SELECT * FROM portfolio WHERE user_id = ? ORDER BY invested DESC", session["user_id"])
    user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    try:
        cash = user_info[0]["cash"]
    except IndexError:
        cash = 0

    tot_invested = 0
    tot_inv_ps = []
    tot_stocks = 0


    for s in stcks:
        lookupp = lookup(s["ticker"])["price"]
        tot_stocks += s["quantity"]
        tot_invested += lookupp * s["quantity"]
        tot_inv_ps.append(usd(lookupp * s["quantity"]))

    return render_template("index.html", cash=usd(cash), tot_invested=usd(tot_invested), tot_stocks=tot_stocks, tot_port=usd(cash + tot_invested), stcks=stcks, tot_inv_ps=tot_inv_ps)
    
    

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    
    button = request.form.get('accion')

    # Check the search for stocks button
    if button == "search":
        ticker = request.form.get("ticker")
        amount = request.form.get("amount")

        if not ticker or not amount:
            return render_template("buy.html", nf="You must fill all the forms in order to buy a Stock, try again")
        
        try:
            amount = int(amount)
            session["amount"] = amount
        except ValueError:
            return render_template("buy.html", nf=f"Amount {amount} is not on the vald format, try again")

        info = lookup(ticker)
        if not info:
            return render_template("buy.html", nf=f"{ticker} ticker not found, try again")
        session["info_name"] = info["name"]
        
        total = float(info["price"])*amount
        session["total"] = total
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]['cash']
        future = balance - total
        session["future"] = future

        if future < 0:
            return render_template("sell.html", nf=f"The price of the operation you like to perform, which is {usd(total)} exceeds your balance which is {usd(balance)}")

        return render_template("buy.html", tick=info["name"], amount=session["amount"], price=usd(info["price"]), total=usd(total), balance=usd(balance), future=usd(future))

    # Check for the cancel order button
    elif button == "cancel":
        return render_template("buy.html") # Cambiar este render a que se vaya a la página principal
    
    # In case of the order confirmation
    else:
        date, hour = nowdate()
        db.execute("UPDATE users SET cash = ? WHERE id = ?", session["future"], session["user_id"])
        db.execute("INSERT INTO transactions (user_id, amount, date, hour, type, ticker) VALUES (?, ?, ?, ?, ?, ?)", session["user_id"], session["total"], date, hour, 0, session["info_name"])

        # Check if the user had previously bought that stock
        prevstock = db.execute("SELECT * FROM portfolio WHERE (user_id = ? AND ticker = ?)", session["user_id"], session["info_name"])
        if len(prevstock) == 1:
            money_invested = prevstock[0]["invested"] + session["total"]
            quant = prevstock[0]["quantity"] + session["amount"]
            stock_id = prevstock[0]["stock_id"]

            db.execute("UPDATE portfolio SET invested = ?, quantity = ? WHERE stock_id = ? AND user_id  = ?",money_invested, quant, stock_id, session["user_id"])
            return render_template("buy.html") # Cambiar este render a que se vaya a la página principal


        db.execute("INSERT INTO portfolio (user_id, invested, ticker, quantity) VALUES (?, ?, ?, ?)", session["user_id"], session["total"], session["info_name"], session["amount"])
        return render_template("buy.html") # Cambiar este render a que se vaya a la página principal



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        return render_template("sell.html")
    
    button = request.form.get('accion')

    # Check the search for stocks button
    if button == "search":
        ticker = request.form.get("ticker")
        amount = request.form.get("amount")

        if not ticker or not amount:
            return render_template("sell.html", nf="You must fill all the forms in order to buy a Stock, try again")
        
        try:
            amount = int(amount)
            session["amount"] = amount
        except ValueError:
            return render_template("sell.html", nf=f"Amount {amount} is not on the vald format, try again")
        
        info = lookup(ticker)
        if not info:
            return render_template("sell.html", nf=f"{ticker} ticker not found, try again")
        session["info_name"] = info["name"]
        
        total = float(info["price"])*amount
        session["total"] = total
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]['cash']
        future = balance + total
        session["future"] = future

        prevstock = db.execute("SELECT * FROM portfolio WHERE (user_id = ? AND ticker = ?)", session["user_id"], session["info_name"])

        if len(prevstock) == 0:
            return render_template("sell.html", nf="Stock not found in your portfolio, try again")

        elif prevstock[0]["quantity"] < amount:
            return render_template("sell.html", nf="Not enough stocks in your portfolio, try again with maximum {amount} stocks")

        return render_template("sell.html", tick=info["name"], amount=session["amount"], price=usd(info["price"]), total=usd(total), balance=usd(balance), future=usd(future))
    

    # Check for the cancel order button
    elif button == "cancel":
        return render_template("sell.html") # Cambiar este render a que se vaya a la página principal
    


    # In case of the order confirmation
    else:
        date, hour = nowdate()
        db.execute("UPDATE users SET cash = ? WHERE id = ?", session["future"], session["user_id"])
        db.execute("INSERT INTO transactions (user_id, amount, date, hour, type, ticker) VALUES (?, ?, ?, ?, ?, ?)", session["user_id"], session["total"], date, hour, 1, session["info_name"])

        # Check if the user had previously bought that stock
        prevstock = db.execute("SELECT * FROM portfolio WHERE (user_id = ? AND ticker = ?)", session["user_id"], session["info_name"])

        money_invested = prevstock[0]["invested"] - session["total"]
        quant = prevstock[0]["quantity"] - session["amount"]
        stock_id = prevstock[0]["stock_id"]

        db.execute("UPDATE portfolio SET invested = ?, quantity = ? WHERE stock_id = ? AND user_id  = ?",money_invested, quant, stock_id, session["user_id"])
        return render_template("buy.html") # Cambiar este render a que se vaya a la página principal



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    hist = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC, hour DESC", session["user_id"])

    for h in hist:
        h["amount"] = usd(h["amount"])

    return render_template("history.html", hist=hist)



@app.route("/register", methods=["GET", "POST"])
def register():

     # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "GET":
        return render_template("register.html")
    
    username = request.form.get("username")
    password = request.form.get("password")
    confirm = request.form.get("confirmation")

    # Checking if there is any blank field, if the password is equal to the confirmation, and if it's length its correct
    if not username or not password or not confirm:
        return apology("Must fill all the form in order to create an account", 403)
    elif password != confirm:
        return apology("Password and confirmation don't match", 403)
    elif len(password) < 8:
        return apology("Password is too short", 403)
    

    # CHecking if there is another username on the database equal to the user input
    usrconf = db.execute("SELECT * FROM users WHERE username = ?", username)
    if len(usrconf) > 0:
        return apology("Username already exists, choose another", 403)

    # Hashing the password and inserting the data into the database
    hashed_password = generate_password_hash(password)
    db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed_password)

    
    # Remember which user has logged in
    rows = db.execute("SELECT * FROM users WHERE username = ?", username)
    session["user_id"] = rows[0]["id"]
    session["username"] = rows[0]["username"]

    
    # Redirect user to home page
    return redirect("/")


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

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

    if request.method == "GET":
        return render_template("quote.html")
    
    ticker = request.form.get("ticker")
    if not ticker:
        return render_template("quote.html", nf="You must insert a ticker in order to look for a Stock, try again")
    
    info = lookup(ticker)
    if not info:
        return render_template("quote.html", nf=f"{ticker} ticker not found, try again")

    return render_template("quote.html", tick=info["name"], price=usd(info["price"]))




if __name__ == '__main__':
    port = int(os.getenv("PORT", default=5001))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=True)

