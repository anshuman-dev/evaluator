from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
import json

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-for-testing')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Custom Jinja2 filter
@app.template_filter('json_extract')
def json_extract_filter(json_str, key):
    """Extract a value from a JSON string"""
    try:
        if not json_str:
            return None
        data = json.loads(json_str)
        return data.get(key)
    except:
        return None

# Import routes after db is initialized
with app.app_context():
    from app import main
