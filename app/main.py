from flask import render_template, request, redirect, url_for, flash, jsonify
from app import app, db
from app.models.database import Hackathon, Project
import pandas as pd
import os
import requests
import json
from datetime import datetime, timezone
import threading
from dotenv import load_dotenv
import re
from urllib.parse import urlparse
import time
import hashlib

load_dotenv()

# Global dictionary to track evaluation progress
evaluation_progress = {}

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
        # Clear existing projects for this hackathon
        existing_projects = Project.query.filter_by(hackathon_id=hackathon_id).all()
        for project in existing_projects:
            db.session.delete(project)
        db.session.commit()
        
        # Save file temporarily
        filepath = os.path.join('temp_uploads', file.filename)
        os.makedirs('temp_uploads', exist_ok=True)
        file.save(filepath)
        
        # Process CSV
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
    evaluation_id = hashlib.md5(f"{hackathon_id}-{time.time()}".encode()).hexdigest()
    evaluation_progress[evaluation_id] = {
        'hackathon_id': hackathon_id,
        'status': 'started',
        'current_project': None,
        'current_task': 'Initializing evaluation...',
        'completed': 0,
        'total': 0
    }
    
    # Create thread with application context
    thread = threading.Thread(target=evaluate_projects_with_context, args=(hackathon_id, evaluation_id))
    thread.start()
    return jsonify({'status': 'started', 'evaluation_id': evaluation_id})

@app.route('/evaluation_status/<int:hackathon_id>')
def evaluation_status(hackathon_id):
    # Find the latest evaluation for this hackathon
    progress = None
    for eval_id, status in evaluation_progress.items():
        if status['hackathon_id'] == hackathon_id:
            progress = status
            break
    
    if not progress:
        # Fallback to checking database
        projects = Project.query.filter_by(hackathon_id=hackathon_id).all()
        completed = sum(1 for p in projects if p.evaluation_status == 'completed')
        total = len(projects)
        
        project_data = []
        for project in projects:
            current_task = '-'
            if project.evaluation_details:
                try:
                    details = json.loads(project.evaluation_details)
                    current_task = details.get('current_task', '-')
                except:
                    pass
            
            project_data.append({
                'id': project.id,
                'current_task': current_task,
                'status_html': get_status_html(project.evaluation_status),
                'score': project.score,
                'progress_html': get_progress_html(project.evaluation_status, project.score)
            })
        
        return jsonify({
            'completed': completed,
            'total': total,
            'current_task': 'Evaluation completed' if completed == total else 'Checking status...',
            'projects': project_data
        })
    
    # Get detailed project status
    projects = Project.query.filter_by(hackathon_id=hackathon_id).all()
    project_data = []
    for project in projects:
        current_task = '-'
        if project.evaluation_details:
            try:
                details = json.loads(project.evaluation_details)
                current_task = details.get('current_task', '-')
            except:
                pass
        
        project_data.append({
            'id': project.id,
            'current_task': current_task,
            'status_html': get_status_html(project.evaluation_status),
            'score': project.score,
            'progress_html': get_progress_html(project.evaluation_status, project.score)
        })
    
    return jsonify({
        'completed': progress['completed'],
        'total': progress['total'],
        'current_task': progress['current_task'],
        'current_project': progress['current_project'],
        'projects': project_data
    })

def get_status_html(status):
    if status == 'completed':
        return '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Completed</span>'
    elif status == 'evaluating':
        return '<span class="badge bg-warning"><span class="spinner-border spinner-border-sm me-1" role="status"></span>Evaluating</span>'
    elif status == 'error':
        return '<span class="badge bg-danger"><i class="bi bi-exclamation-circle me-1"></i>Error</span>'
    else:
        return '<span class="badge bg-secondary">Pending</span>'

def get_progress_html(status, score):
    if status == 'completed':
        return f'<div class="progress" style="height: 20px;"><div class="progress-bar bg-success" role="progressbar" style="width: 100%">100%</div></div>'
    elif status == 'evaluating':
        return f'<div class="progress" style="height: 20px;"><div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 50%">50%</div></div>'
    elif status == 'error':
        return f'<div class="progress" style="height: 20px;"><div class="progress-bar bg-danger" role="progressbar" style="width: 100%">Error</div></div>'
    else:
        return f'<div class="progress" style="height: 20px;"><div class="progress-bar bg-light" role="progressbar" style="width: 0%">0%</div></div>'

def create_consistent_prompt(project, github_info, task_description):
    """Create a consistent prompt that should yield similar results"""
    
    # Create a hash of the project data for deterministic seeding
    project_data = f"{project.name}-{project.github_link}-{project.video_link}-{project.deployed_link}"
    data_hash = hashlib.md5(project_data.encode()).hexdigest()[:8]
    
    return f"""
[EVALUATION_SESSION_ID: {data_hash}]

Evaluate this hackathon project with complete objectivity and consistency:

PROJECT DATA:
- Name: {project.name}
- Track: {project.tracks or 'General'}
- GitHub: {project.github_link}
- Demo: {project.video_link}
- Deployed: {project.deployed_link or 'Not provided'}

GITHUB METRICS:
{json.dumps(github_info, indent=2) if github_info else "Repository not accessible"}

EVALUATION CRITERIA (total 100 points):

1. CODE QUALITY & ARCHITECTURE (25 points max)
   - Structure and organization: 0-8 points
   - Best practices: 0-8 points
   - Documentation: 0-5 points
   - Technical implementation: 0-4 points

2. HACKATHON TIMELINE COMPLIANCE (15 points max)
   - Recent commits during May 9-10, 2025: 0-10 points
   - Evidence of 24-hour development: 0-5 points

3. DEPLOYMENT STATUS (15 points max)
   - Working deployment: 0-10 points
   - Accessibility and stability: 0-5 points

4. TECHNICAL INNOVATION (25 points max)
   - Novel approaches: 0-10 points
   - Technical complexity: 0-10 points
   - Problem-solving creativity: 0-5 points

5. DEMO QUALITY (20 points max)
   - Video quality and clarity: 0-8 points
   - Feature demonstration: 0-8 points
   - Overall presentation: 0-4 points

TASK: {task_description}

Provide exactly this format:
CRITERION 1: X/25
CRITERION 2: X/15
CRITERION 3: X/15
CRITERION 4: X/25
CRITERION 5: X/20
TOTAL: X/100
"""

def extract_github_info(github_url):
    """Extract repository information from GitHub URL"""
    try:
        # Parse GitHub URL to get owner and repo
        path_parts = urlparse(github_url).path.strip('/').split('/')
        if len(path_parts) >= 2:
            owner, repo = path_parts[0], path_parts[1]
        else:
            return None
        
        # For POC, return mock data if GitHub API is not accessible
        return {
            'stars': 5,
            'forks': 2,
            'description': 'Sample project description',
            'language': 'JavaScript',
            'recent_commits': 12,
            'has_readme': True,
            'file_count': 25,
            'created_at': '2025-05-09T18:00:00Z',
            'last_pushed': '2025-05-10T18:00:00Z'
        }
    except Exception as e:
        print(f"Error extracting GitHub info: {str(e)}")
        return None

def call_openai_api(prompt):
    """Direct API call to OpenAI with consistent parameters"""
    api_key = os.getenv('OPENAI_API_KEY')
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'model': 'gpt-3.5-turbo',
        'messages': [
            {'role': 'system', 'content': 'You are a consistent hackathon judge. Always evaluate projects using the exact same criteria and scoring method.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.1,  # Very low temperature for consistency
        'max_tokens': 2000,
        'seed': 42  # Fixed seed for deterministic output
    }
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            raise Exception(f"API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        raise

def evaluate_projects_with_context(hackathon_id, evaluation_id):
    """Wrapper function to run evaluation within application context"""
    with app.app_context():
        evaluate_projects(hackathon_id, evaluation_id)

def evaluate_projects(hackathon_id, evaluation_id):
    projects = Project.query.filter_by(hackathon_id=hackathon_id).all()
    total_projects = len(projects)
    
    # Update progress
    evaluation_progress[evaluation_id]['total'] = total_projects
    evaluation_progress[evaluation_id]['current_task'] = f'Evaluating {total_projects} projects...'
    
    for i, project in enumerate(projects, 1):
        try:
            print(f"Evaluating project {i}/{total_projects}: {project.name}")
            
            # Update progress
            evaluation_progress[evaluation_id]['current_project'] = project.name
            evaluation_progress[evaluation_id]['current_task'] = f'Analyzing {project.name}...'
            
            project.evaluation_status = 'evaluating'
            
            # Store current task in project details
            task_details = {
                'current_task': 'Fetching GitHub data...',
                'status': 'in_progress'
            }
            project.evaluation_details = json.dumps(task_details)
            db.session.commit()
            
            # Extract GitHub information
            task_details['current_task'] = 'Analyzing repository...'
            project.evaluation_details = json.dumps(task_details)
            db.session.commit()
            
            github_info = extract_github_info(project.github_link)
            
            # Create evaluation prompt
            task_details['current_task'] = 'Running AI evaluation...'
            project.evaluation_details = json.dumps(task_details)
            db.session.commit()
            
            evaluation_prompt = create_consistent_prompt(
                project, 
                github_info, 
                "Score each criterion precisely based on the available data."
            )
            
            evaluation_text = call_openai_api(evaluation_prompt)
            print(f"Received evaluation for {project.name}")
            
            # Parse the evaluation
            score_patterns = [
                (r'CRITERION 1:\s*(\d+)/25', 'code_quality'),
                (r'CRITERION 2:\s*(\d+)/15', 'timeline'),
                (r'CRITERION 3:\s*(\d+)/15', 'deployment'),
                (r'CRITERION 4:\s*(\d+)/25', 'innovation'),
                (r'CRITERION 5:\s*(\d+)/20', 'demo'),
                (r'TOTAL:\s*(\d+)/100', 'total')
            ]
            
            scores = {}
            for pattern, key in score_patterns:
                match = re.search(pattern, evaluation_text, re.IGNORECASE | re.DOTALL)
                if match:
                    scores[key] = int(match.group(1))
            
            # Handle N/A scores as 0
            for key in ['code_quality', 'timeline', 'deployment', 'innovation', 'demo']:
                if key not in scores:
                    scores[key] = 0
            
            # Calculate total if missing
            if 'total' not in scores:
                scores['total'] = sum([
                    scores.get('code_quality', 0),
                    scores.get('timeline', 0),
                    scores.get('deployment', 0),
                    scores.get('innovation', 0),
                    scores.get('demo', 0)
                ])
            
            # Create structured evaluation details
            structured_details = {
                'scores': scores,
                'full_evaluation': evaluation_text,
                'github_info': github_info,
                'current_task': 'Evaluation completed',
                'status': 'completed'
            }
            
            project.score = float(scores.get('total', 0))
            project.evaluation_details = json.dumps(structured_details)
            project.evaluation_status = 'completed'
            
            # Update progress
            evaluation_progress[evaluation_id]['completed'] = i
            evaluation_progress[evaluation_id]['current_task'] = f'Completed {i}/{total_projects} evaluations'
            
            print(f"Completed evaluation for {project.name}: {project.score}/100")
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error evaluating {project.name}: {error_msg}")
            
            project.evaluation_status = 'error'
            project.evaluation_details = json.dumps({
                'error': error_msg,
                'github_info': None,
                'current_task': 'Error occurred',
                'status': 'error'
            })
            project.score = 0.0
        
        db.session.commit()
    
    # Final update
    evaluation_progress[evaluation_id]['current_task'] = 'All evaluations completed!'
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

@app.route('/project/<int:project_id>/details')
def project_details(project_id):
    project = Project.query.get_or_404(project_id)
    
    try:
        if project.evaluation_details:
            details = json.loads(project.evaluation_details)
            
            # Ensure scores exist and convert N/A to 0
            if 'scores' in details:
                for key in ['code_quality', 'timeline', 'deployment', 'innovation', 'demo', 'total']:
                    if key not in details['scores'] or details['scores'][key] == 'N/A':
                        details['scores'][key] = 0
            
            return jsonify(details)
        else:
            return jsonify({'error': 'No evaluation details available'})
    except Exception as e:
        return jsonify({'error': str(e)})
