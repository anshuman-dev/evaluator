import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
print(f"Testing API key: {api_key[:10]}...")

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

data = {
    'model': 'gpt-3.5-turbo',
    'messages': [
        {'role': 'user', 'content': 'Say "The API is working!" in a creative way.'}
    ],
    'max_tokens': 50
}

try:
    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers=headers,
        json=data,
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("Success! API Response:")
        print(response.json()['choices'][0]['message']['content'])
    else:
        print("Error:")
        print(response.text)
        
except Exception as e:
    print(f"Exception: {e}")
