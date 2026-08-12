import asyncio
import re
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

async def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Asynchronously performs web search using ddgs.
    Returns list of dicts with 'title', 'href', 'body'.
    """
    def _sync_search():
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return results
        except Exception as e:
            print(f"[WebSearch] Search error: {e}")
            return []

    return await asyncio.to_thread(_sync_search)

async def fetch_web_page(url: str, max_length: int = 3000) -> str:
    """
    Fetches web page content from any URL and returns cleaned text.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code != 200:
                return f"Failed to fetch URL {url}, HTTP status {resp.status_code}"
            
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove scripts & styles
            for elem in soup(["script", "style", "nav", "header", "footer"]):
                elem.extract()

            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            cleaned_text = "\n".join(lines)
            
            if len(cleaned_text) > max_length:
                cleaned_text = cleaned_text[:max_length] + "\n...[truncated]"
                
            return f"### Content from {url}:\n\n{cleaned_text}"
    except Exception as e:
        print(f"[WebSearch] Error fetching web page {url}: {e}")
        return f"Error opening URL {url}: {e}"

async def format_search_results(query: str, max_results: int = 5) -> str:
    results = await search_web(query, max_results=max_results)
    if not results:
        return f"No search results found for query: '{query}'."

    formatted = f"### Web Search Results for '{query}':\n\n"
    for idx, item in enumerate(results, 1):
        formatted += f"[{idx}] {item.get('title', 'No Title')}\n"
        formatted += f"URL: {item.get('href', '')}\n"
        formatted += f"Snippet: {item.get('body', '')}\n\n"
    return formatted
