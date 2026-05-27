import urllib.request
import json
url = 'https://api.github.com/users/abhi-dev99/repos?sort=updated&per_page=100'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        repos = json.loads(response.read().decode())
        for r in repos:
            print(f"{r['name']}: {r.get('description', 'No desc')} - {r.get('language')}")
except Exception as e:
    print('Failed:', e)
