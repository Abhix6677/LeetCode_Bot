import requests, os
from dotenv import load_dotenv
load_dotenv()
headers={'Authorization': 'Bearer ' + os.getenv('AI_API_KEY')}
print(requests.post(os.getenv('AI_BASE_URL')+'/chat/completions', json={'model': os.getenv('AI_MODEL'), 'messages':[{'role':'user','content':'hi'}]}, headers=headers).text)
