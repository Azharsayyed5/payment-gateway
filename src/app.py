from flask import Flask
from flask import Flask,request,redirect,render_template, session, send_file, redirect, url_for, request, flash
from flask.views import MethodView
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_required, current_user, login_user, logout_user, login_required, LoginManager
from sqlalchemy.sql.functions import func
from sqlalchemy.orm import aliased
import datetime
import uuid
import requests
from werkzeug.security import check_password_hash, generate_password_hash
from .paytm_checksum import generate_checksum, verify_checksum
# from paytmchecksum import generateSignature, verifySignature
app = Flask(__name__, template_folder="templates/", static_folder='static/')

# Set up the SQLAlchemy Database to be a local file 'desserts.database'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///payment.db'
app.config['SECRET_KEY'] = '11eb94390242ac130002'


# Set SQLALCHEMY_TRACK_MODIFICATIONS to False
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
database = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

MERCHANT_ID = "<MERCHANT_ID>"
MERCHANT_KEY = "<MERCHANT_KEY>"
WEBSITE_NAME = "WEBSTAGING"
INDUSTRY_TYPE_ID = "Retail"
# BASE_URL = "https://securegw.paytm.in"
BASE_URL = "https://securegw-stage.paytm.in"

class PayView(MethodView):
    
    @login_required
    def get(self):
        transaction_data = {
            "MID": MERCHANT_ID,
            "ORDER_ID": str(uuid.uuid4()),
            "CUST_ID": str(uuid.uuid4()),
            "TXN_AMOUNT": "100",
            "CHANNEL_ID": "WEB",
            "INDUSTRY_TYPE_ID": INDUSTRY_TYPE_ID,
            "WEBSITE": WEBSITE_NAME,
            "MOBILE_NO": "1234567890",
            "CALLBACK_URL": "http://127.0.0.1:5000/callback"
        }

        transaction_data["CHECKSUMHASH"] = generate_checksum(transaction_data, MERCHANT_KEY)
        print("Request params: {transaction_data}".format(transaction_data=transaction_data))
        url = BASE_URL + '/theia/processTransaction'
        return render_template("cart.html", data=transaction_data, url=url)

@app.route('/callback', methods=["GET", "POST"])
def callback():
    callback_response = request.form.to_dict()
    checksum_verification_status= "FAILED"
    print("Transaction response: {callback_response}".format(callback_response=callback_response))
    if callback_response["RESPMSG"] != "Invalid checksum":
        checksum_verification_status = verify_checksum(
            callback_response, MERCHANT_KEY, callback_response.get("CHECKSUMHASH")
            )
        print("checksum_verification_status: {check_status}".format(check_status=checksum_verification_status))

    transaction_verify_payload = {
        "MID": callback_response.get("MID"),
        "ORDERID": callback_response.get("ORDERID"),
        "CHECKSUMHASH": callback_response.get("CHECKSUMHASH")
    }
    url = BASE_URL + '/order/status'
    verification_response = requests.post(url=url, json=transaction_verify_payload)
    print("Verification response: {verification_response}".format(verification_response=verification_response.json()))

    return render_template(
        "response.html", callback_response=callback_response, 
        checksum_verification_status=checksum_verification_status, 
        verification_response=verification_response.json()
        )

class LoginView(MethodView):
    
    def get(self):
        return render_template("login.html")

    def post(self):
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password): 
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))
        login_user(user, remember=remember)
        session['logged_in'] = True
        return redirect(url_for('payment'))

class SignupView(MethodView):
    
    def get(self):
        return render_template("signup.html")

    def post(self):
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user: 
            flash('Email address already exists')
            return redirect(url_for('signup'))
        new_user = User(email=email, name=name, password=generate_password_hash(password, method='sha256'))
        database.session.add(new_user)
        database.session.commit()
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('payment'))
    return redirect(url_for('login'))

def generate_uuid():
    return str(uuid.uuid4())

# START : Database ORM initialization

class User(UserMixin, database.Model):
    id = database.Column(database.String(255), primary_key=True, default=generate_uuid)
    email = database.Column(database.String(100), unique=True)
    password = database.Column(database.String(100))
    name = database.Column(database.String(1000))

    def __repr__(self):
        return '<id %r>' % self.id

# END : Database ORM initialization

database.create_all()
app.add_url_rule('/login',view_func=LoginView.as_view('login'))
app.add_url_rule('/signup',view_func=SignupView.as_view('signup'))
app.add_url_rule('/payment',view_func=PayView.as_view('payment'))