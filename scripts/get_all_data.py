import urllib.request
import urllib.parse
import re
import html

def search_ddg(query):
    print(f'\n--- Searching: {query} ---')
    url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        html_code = urllib.request.urlopen(req).read().decode('utf-8')
        titles = re.findall(r'<h2 class="result__title">.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html_code, flags=re.IGNORECASE | re.DOTALL)
        for i in range(min(4, len(titles))):
            link = titles[i][0]
            clean_t = re.sub(r'<[^>]+>', '', titles[i][1])
            # duckduckgo prepends //duckduckgo.com/l/?uddg= URL encoding
            if "uddg=" in link:
                link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
            print(f"Title: {html.unescape(clean_t).strip()}")
            print(f"URL: {link}\n")
    except Exception as e:
        print('Error:', e)

queries = [
    "hospital medical inventory supply chain",
    "pharmaceutical sales drug demand",
    "IDSP weekly disease outbreak dataset India CSV",
    "integrated disease surveillance dataset",
    "site:kaggle.com disease outbreak india csv"
]

for q in queries:
    search_ddg(q)
