import requests
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

def extract_github_info(github_url):
    """Extract detailed repository information from GitHub URL using GitHub API"""
    try:
        # Parse GitHub URL to get owner and repo
        parsed_url = urlparse(github_url)
        path_parts = parsed_url.path.strip('/').split('/')
        
        if len(path_parts) < 2:
            return None
            
        owner, repo = path_parts[0], path_parts[1]
        
        # Base API URL
        base_url = f"https://api.github.com/repos/{owner}/{repo}"
        
        # Headers for GitHub API
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Judge-The-Evaluator'
        }
        
        # Add authentication if token available
        github_token = os.getenv('GITHUB_TOKEN')
        if github_token:
            headers['Authorization'] = f'Bearer {github_token}'
        
        # Get repository info
        repo_response = requests.get(base_url, headers=headers, timeout=10)
        if repo_response.status_code != 200:
            return None
            
        repo_data = repo_response.json()
        
        # Get recent commits
        commits_url = f"{base_url}/commits"
        since_date = datetime(2025, 5, 9, 18, 0, 0)  # May 9, 6 PM
        until_date = datetime(2025, 5, 10, 18, 0, 0)  # May 10, 6 PM
        
        params = {
            'since': since_date.isoformat() + 'Z',
            'until': until_date.isoformat() + 'Z',
            'per_page': 100
        }
        
        commits_response = requests.get(commits_url, headers=headers, params=params, timeout=10)
        commits_data = commits_response.json() if commits_response.status_code == 200 else []
        
        # Get file tree
        tree_url = f"{base_url}/git/trees/{repo_data.get('default_branch', 'main')}?recursive=1"
        tree_response = requests.get(tree_url, headers=headers, timeout=10)
        tree_data = tree_response.json() if tree_response.status_code == 200 else {'tree': []}
        
        # Get languages
        languages_url = f"{base_url}/languages"
        languages_response = requests.get(languages_url, headers=headers, timeout=10)
        languages_data = languages_response.json() if languages_response.status_code == 200 else {}
        
        # Get contributors
        contributors_url = f"{base_url}/contributors"
        contributors_response = requests.get(contributors_url, headers=headers, timeout=10)
        contributors_data = contributors_response.json() if contributors_response.status_code == 200 else []
        
        # Get README
        readme_url = f"{base_url}/readme"
        readme_response = requests.get(readme_url, headers=headers, timeout=10)
        has_readme = readme_response.status_code == 200
        
        # Process commit data
        hackathon_commits = []
        for commit in commits_data:
            commit_date = datetime.fromisoformat(commit['commit']['committer']['date'].replace('Z', '+00:00'))
            if since_date <= commit_date.replace(tzinfo=None) <= until_date:
                hackathon_commits.append({
                    'sha': commit['sha'],
                    'message': commit['commit']['message'],
                    'date': commit['commit']['committer']['date'],
                    'author': commit['commit']['author']['name']
                })
        
        # Analyze file types
        file_types = {}
        code_files = []
        for item in tree_data.get('tree', []):
            if item['type'] == 'blob':
                path = item['path']
                ext = path.split('.')[-1].lower() if '.' in path else 'no-ext'
                file_types[ext] = file_types.get(ext, 0) + 1
                
                # Common code file extensions
                if ext in ['py', 'js', 'jsx', 'ts', 'tsx', 'java', 'cpp', 'c', 'go', 'rb', 'php']:
                    code_files.append(path)
        
        # Calculate metrics
        total_files = len([item for item in tree_data.get('tree', []) if item['type'] == 'blob'])
        total_dirs = len([item for item in tree_data.get('tree', []) if item['type'] == 'tree'])
        
        # Determine main language
        if languages_data:
            main_language = max(languages_data.items(), key=lambda x: x[1])[0]
        else:
            main_language = repo_data.get('language', 'Unknown')
        
        # Analyze commit patterns
        commit_authors = {}
        for commit in hackathon_commits:
            author = commit['author']
            commit_authors[author] = commit_authors.get(author, 0) + 1
        
        # Check for deployment configurations
        deployment_files = []
        for item in tree_data.get('tree', []):
            if item['type'] == 'blob':
                filename = item['path'].lower()
                if any(deploy_file in filename for deploy_file in [
                    'dockerfile', 'docker-compose', 'vercel.json', 'netlify.toml',
                    'render.yaml', 'railway.json', 'heroku.yml', 'azure-pipelines'
                ]):
                    deployment_files.append(item['path'])
        
        return {
            'basic_info': {
                'full_name': repo_data.get('full_name'),
                'description': repo_data.get('description'),
                'html_url': repo_data.get('html_url'),
                'private': repo_data.get('private', False),
                'created_at': repo_data.get('created_at'),
                'updated_at': repo_data.get('updated_at'),
                'pushed_at': repo_data.get('pushed_at'),
                'size': repo_data.get('size'),
                'stargazers_count': repo_data.get('stargazers_count', 0),
                'watchers_count': repo_data.get('watchers_count', 0),
                'forks_count': repo_data.get('forks_count', 0),
                'open_issues_count': repo_data.get('open_issues_count', 0),
                'default_branch': repo_data.get('default_branch'),
                'has_issues': repo_data.get('has_issues', False),
                'has_projects': repo_data.get('has_projects', False),
                'has_wiki': repo_data.get('has_wiki', False),
                'has_readme': has_readme
            },
            'hackathon_analysis': {
                'recent_commits': len(hackathon_commits),
                'commit_details': hackathon_commits,
                'commit_authors': commit_authors,
                'commits_during_hackathon': len(hackathon_commits) > 0
            },
            'code_analysis': {
                'main_language': main_language,
                'languages': languages_data,
                'total_files': total_files,
                'total_directories': total_dirs,
                'file_types': file_types,
                'code_files': code_files,
                'lines_of_code': sum(languages_data.values()) if languages_data else 0
            },
            'deployment': {
                'deployment_files': deployment_files,
                'has_deployment_config': len(deployment_files) > 0
            },
            'collaboration': {
                'contributors_count': len(contributors_data),
                'contributors': [
                    {
                        'login': c['login'],
                        'contributions': c['contributions']
                    } for c in contributors_data[:5]  # Top 5 contributors
                ]
            }
        }
        
    except Exception as e:
        print(f"Error extracting GitHub info: {str(e)}")
        return None
