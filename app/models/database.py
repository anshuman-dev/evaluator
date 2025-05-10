from app import db
from datetime import datetime

class Hackathon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    devfolio_link = db.Column(db.String(200), nullable=False)
    github_link = db.Column(db.String(200), nullable=False)
    video_link = db.Column(db.String(200), nullable=False)
    tracks = db.Column(db.String(200))
    deployed_link = db.Column(db.String(200))
    score = db.Column(db.Float, default=0.0)
    evaluation_status = db.Column(db.String(20), default='pending')
    evaluation_details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
