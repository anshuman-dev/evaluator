import os
from app import app, db
from app.models.database import Hackathon

with app.app_context():
    # Create tables
    db.create_all()
    
    # Add a dummy hackathon if none exists
    if not Hackathon.query.first():
        hackathon = Hackathon(name="Demo Hackathon 2025", url="https://demo-hackathon.com")
        db.session.add(hackathon)
        db.session.commit()
        print("Database initialized with demo hackathon!")
    else:
        print("Database already initialized!")
