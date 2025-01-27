from flask import Flask, request, jsonify, session
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import time
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "http://127.0.0.1:5500"}})

mongo_uri = "mongodb://localhost:27017"
client = MongoClient(mongo_uri)
db = client["library_db"]
users_collection = db["users"]
books_collection = db["books"]

# Helper functions
def create_user(username, password):
    password_hash = generate_password_hash(password)
    users_collection.insert_one({"username": username, "password": password_hash, "is_admin": False})

def authenticate_user(username, password):
    user = users_collection.find_one({"username": username})
    if user and check_password_hash(user["password"], password):
        return user
    return None

# Middleware to check session expiration
def check_session():
    if "session_start" in session and time.time() - session["session_start"] > 3600:  # 1 hour session expiry
        session.pop("username", None)
        session.pop("session_start", None)
        return False
    return True

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username, password = data.get("username"), data.get("password")
    if users_collection.find_one({"username": username}):
        return jsonify({"message": "User  already exists"}), 400
    create_user(username, password)
    return jsonify({"message": "User  registered successfully"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username, password = data.get("username"), data.get("password")
    user = authenticate_user(username, password)
    if user:
        session["username"] = username
        session["session_start"] = time.time()  # Record session start time
        return jsonify({"message": "Login successful"})
    return jsonify({"message": "Invalid credentials"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    session.pop("session_start", None)
    return jsonify({"message": "Logged out successfully"})

@app.route("/add_book", methods=["POST"])
def add_book():
    if not check_session():
        return jsonify({"message": "Session expired. Please log in again."}), 401
    if "username" not in session:
        return jsonify({"message": "Unauthorized"}), 401
    
    data = request.json
    title, author, isbn = data.get("title"), data.get("author"), data.get("isbn")
    books_collection.insert_one({"title": title, "author": author, "isbn": isbn, "is_borrowed": False})
    return jsonify({"message": "Book added successfully"})

@app.route("/list_books", methods=["GET"])
def list_books():
    if not check_session():
        return jsonify({"message": "Session expired. Please log in again."}), 401
    if "username" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    books = list(books_collection.find({}, {"_id": 0}))
    return jsonify(books)

@app.route("/search_books", methods=["GET"])
def search_books():
    if not check_session():
        return jsonify({"message": "Session expired. Please log in again."}), 401
    if "username" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    query = request.args.get("query", "")
    books = list(books_collection.find({
        "$or": [
            {"title": {"$regex": query, "$options": "i"}},
            {"author": {"$regex": query, "$options": "i"}},
            {"isbn": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}))
    
    return jsonify(books)

@app.route("/borrow_book", methods=["POST"])
def borrow_book():
    if not check_session():
        return jsonify({"message": "Session expired. Please log in again."}), 401
    if "username" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json
    isbn = data.get("isbn")
    book = books_collection.find_one({"isbn": isbn})

    if book:
        if book["is_borrowed"]:
            return jsonify({"message": "Book already borrowed."}), 400
        # Update the book to set it as borrowed and add the borrow date
        books_collection.update_one({"isbn": isbn}, {"$set": {"is_borrowed": True, "borrow_date": datetime.now()}})
        return jsonify({"message": "Book borrowed successfully."})
    return jsonify({"message": "Book not found."}), 404

@app.route("/return_book", methods=["POST"])
def return_book():
    if not check_session():
        return jsonify({"message": "Session expired. Please log in again."}), 401
    if "username" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json
    isbn = data.get("isbn")
    book = books_collection.find_one({"isbn": isbn})

    if book:
        if not book["is_borrowed"]:
            return jsonify({"message": "This book was not borrowed."}), 400
        books_collection.update_one({"isbn": isbn}, {"$set": {"is_borrowed": False}})
        return jsonify({"message": "Book returned successfully."})
    return jsonify({"message": "Book not found."}), 404

@app.route("/borrowed_books", methods=["GET"])
def borrowed_books():
    if not check_session():
        return jsonify({"message": "Session expired. Please log in again."}), 401
    if "username" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    borrowed_books = list(books_collection.find({"is_borrowed": True}, {"_id": 0}))
    return jsonify(borrowed_books)

if __name__ == "__main__":
    app.run(debug=True)