from flask import render_template, request, redirect, url_for, flash, jsonify
from app import app, db
from app.models.database import Hackathon, Project
import pandas as pd
import os
import requests
import json
from datetime import datetime
import threading
from dotenv import load_dotenv

load_dotenv()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    hackathons = Hackathon.query.all()
    return render_template('dashboard.html', hackathons=hackathons)

@app.route('/upload/<int:hackathon_id>')
def upload_projects(hackathon_id):
    hackathon = Hackathon.query.get_or_404(hackathon_id)
    return render_template('upload.html', hackathon=hackathon)

@app.route('/process_upload/<int:hackathon_id>', methods=['POST'])
def process_upload(hackathon_id):
    if 'file' not in request.files:
        flash('No file uploaded')
        return redirect(url_for('upload_projects', hackathon_id=hackathon_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('upload_projects', hackathon_id=hackathon_id))
    
    if file and file.filename.endswith('.csv'):
        filepath = os.path.join('temp_uploads', file.filename)
        os.makedirs('temp_uploads', exist_ok=True)
        file.save(filepath)
        
        df = pd.read_csv(filepath)
        for _, row in df.iterrows():
            project = Project(
                hackathon_id=hackathon_id,
                name=row['project_name'],
                devfolio_link=row['devfolio_link'],
                github_link=row['github_link'],
                video_link=row['video_link'],
                tracks=row.get('tracks', ''),
                deployed_link=row.get('deployed_link', '')
            )
            db.session.add(project)
        db.session.commit()
        
        os.remove(filepath)
        flash(f'Successfully uploaded {len(df)} projects!')
        return redirect(url_for('evaluation', hackathon_id=hackathon_id))
    
    flash('Invalid file format')
    return redirect(url_for('upload_projects', hackathon_id=hackathon_id))

@app.route('/evaluation/<int:hackathon_id>')
def evaluation(hackathon_id):
    hackathon = Hackathon.query.get_or_404(hackathon_id)
    projects = Project.query.filter_by(hackathon_id=hackathon_id).all()
    return render_template('evaluation.html', hackathon=hackathon, projects=projects)

@app.route('/start_evaluation/<int:hackathon_id>')
def start_evaluation(hackathon_id):
    thread = threading.Thread(target=evaluate_projects, args=(hackathon_id,))
    thread.start()
    return jsonify({'status': 'started'})

def call_openai_api(prompt):
    """Direct API call to OpenAI"""
    api_key = os.getenv('OPENAI_API_KEY')
    print(f"Using API key: {api_key[:10]}..." if api_key else "No API key found!")
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'model': 'gpt-3.5-turbo',
        'messages': [
            {'role': 'system', 'content': 'You are an experienced hackathon judge with expertise in evaluating technical projects.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.5,
        'max_tokens': 1500
    }
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"OpenAI API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            error_msg = f"API Error: {response.status_code}"
            if response.text:
                try:
                    error_json = response.json()
                    error_msg += f" - {error_json.get('error', {}).get('message', response.text)}"
                except:
                    error_msg += f" - {response.text}"
            raise Exception(error_msg)
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        raise

def evaluate_projects(hackathon_id):
    projects = Project.query.filter_by(hackathon_id=hackathon_id).all()
    
    for i, project in enumerate(projects, 1):
        try:
            print(f"Evaluating project {i}/{len(projects)}: {project.name}")
            
            project.evaluation_status = 'evaluating'
            db.session.commit()
            
            evaluation_prompt = f"""
            As an expert hackathon judge, evaluate this hackathon project comprehensively:
            
            Project Details:
            - Name: {project.name}
            - GitHub Repository: {project.github_link}
            - Demo Video: {project.video_link}
            - Deployed Link: {project.deployed_link or 'Not provided'}
            - Track(s): {project.tracks or 'General'}
            
            Please analyze this project based on 5 criteria:
            
            1. Code Quality & Architecture (25%)
               - Clean, well-structured code
               - Best coding practices
               - Documentation quality
            
            2. Hackathon Timeline Compliance (15%)
               - Code appears to be written during May 9-10, 2025
               - Recent commit activity
            
            3. Deployment Status (15%)
               - Working deployment available
               - Accessibility and performance
            
            4. Technical Innovation & Complexity (25%)
               - Novel approaches or technologies
               - Technical difficulty
               - Problem-solving creativity
            
            5. Demo/Presentation Quality (20%)
               - Clear introduction
               - Functionality demonstration
               - Overall presentation
            
            Instructions:
            - Start your response with "Final Score: X/100"
            - Provide detailed feedback for each criterion
            - Be constructive and specific
            - Consider that this is a hackathon project (built in 24 hours)
            """
            
            evaluation_text = call_openai_api(evaluation_prompt)
            print(f"Received evaluation for {project.name}")
            
            # Extract score with multiple regex patterns
            import re
            score_patterns = [
                r'Final Score:\s*(\d+)\/100',
                r'Score:\s*(\d+)\/100',
                r'Overall Score:\s*(\d+)\/100',
                r'Total Score:\s*(\d+)\/100'
            ]
            
            score = None
            for pattern in score_patterns:
                score_match = re.search(pattern, evaluation_text, re.IGNORECASE)
                if score_match:
                    score = float(score_match.group(1))
                    break
            
            if score is None:
                # Try to find any number followed by /100
                score_match = re.search(r'(\d+)/100', evaluation_text)
                if score_match:
                    score = float(score_match.group(1))
                else:
                    # Default score if parsing fails
                    score = 70.0
                    evaluation_text = f"Final Score: {score}/100\n\n{evaluation_text}"
            
            project.score = score
            project.evaluation_details = evaluation_text
            project.evaluation_status = 'completed'
            
            print(f"Completed evaluation for {project.name}: {score}/100")
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error evaluating {project.name}: {error_msg}")
            
            project.evaluation_status = 'error'
            project.evaluation_details = f"Evaluation Error: {error_msg}"
            project.score = 0.0
        
        db.session.commit()
    
    print("Evaluation completed for all projects")

@app.route('/results/<int:hackathon_id>')
def results(hackathon_id):
    hackathon = Hackathon.query.get_or_404(hackathon_id)
    sort_order = request.args.get('sort', 'score_desc')
    
    query = Project.query.filter_by(hackathon_id=hackathon_id)
    
    if sort_order == 'score_desc':
        projects = query.order_by(Project.score.desc()).all()
    elif sort_order == 'score_asc':
        projects = query.order_by(Project.score.asc()).all()
    else:
        projects = query.all()
    
    return render_template('results.html', hackathon=hackathon, projects=projects, sort_order=sort_order)
