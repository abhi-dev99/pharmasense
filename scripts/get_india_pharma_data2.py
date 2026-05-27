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
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html_code, flags=re.IGNORECASE | re.DOTALL)
        for i in range(min(5, len(titles))):
            link = titles[i][0]
            clean_t = re.sub(r'<[^>]+>', '', titles[i][1])
            clean_s = re.sub(r'<[^>]+>', '', snippets[i]) if i < len(snippets) else ""
            if "uddg=" in link:
                link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
            print(f"Title: {html.unescape(clean_t).strip()}")
            print(f"URL: {link}")
            print(f"Snippet: {html.unescape(clean_s).strip()}\n")
    except Exception as e:
        print('Error:', e)

search_ddg("india-medicines-and-drug-info-dataset kaggle apkaayush")
search_ddg("site:github.com pharmacy transaction dataset csv india")
