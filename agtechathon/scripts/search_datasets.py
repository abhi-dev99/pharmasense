import urllib.request
import urllib.parse
import re
import html

def search_ddg(query):
    print(f'\n--- Searching DDG for: {query} ---')
    url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        html_code = urllib.request.urlopen(req).read().decode('utf-8')
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html_code, flags=re.IGNORECASE | re.DOTALL)
        urls = re.findall(r'<a class="result__url" href="([^"]+)">', html_code, flags=re.IGNORECASE)
        titles = re.findall(r'<h2 class="result__title">.*?<a[^>]*>(.*?)</a>', html_code, flags=re.IGNORECASE | re.DOTALL)
        for i in range(min(5, len(snippets))):
            clean_s = re.sub(r'<[^>]+>', '', snippets[i])
            clean_t = re.sub(r'<[^>]+>', '', titles[i]) if i < len(titles) else "No title"
            url_match = urls[i] if i < len(urls) else "No URL"
            print(f"Title: {html.unescape(clean_t).strip()}")
            print(f"Snippet: {html.unescape(clean_s).strip()}\n")
    except Exception as e:
        print('Error:', e)

search_ddg('kaggle dengue dataset india')
search_ddg('National Vector Borne Disease Control Programme dataset csv')
search_ddg('ICMR malaria dengue dataset csv')
