import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


async def fetch(session, url):
   if not url.startswith(('http://', 'https://')):
       url = f'https://{url}'
       
   headers = {
       "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
   }

   try:
       async with session.get(url, headers=headers, timeout=10) as response:
           if response.status != 200:
               return None, response.status
           return await response.text(), None
   except Exception as e:
       return None, str(e)

async def site_audit(base_url):
    """
    Asynchronously audits the website for:
    - Broken internal/external links (ignoring "javascript:void(0);" & "mailto:")
    - Missing H1, meta descriptions, and title tags
    - Duplicate meta descriptions & titles
    - Keyword scan (including ALT text in images)
    - Checking if pages are uncompressed

    Args:
        base_url (str): The target website URL.

    Returns:
        dict: Results containing various SEO findings.
    """

    visited = set()
    queue = [base_url]  # Start with homepage
    results = {
        "missing_meta_descriptions": [],
        "missing_titles": [],
        "missing_h1_tags": [],
        "duplicate_meta_descriptions": {},
        "duplicate_titles": {},
        "broken_links": [],
        "keyword_scan": {},
        "uncompressed_pages": []
    }
    metadata_hash = {"meta_descriptions": {}, "titles": {}}

    async with aiohttp.ClientSession() as session:
        while queue:
            url = queue.pop(0)

            # Limit crawl depth to homepage + first-level subpages only
            parsed_url = urlparse(url)
            if parsed_url.path.count("/") > 1:
                continue

            if url in visited:
                continue

            # Fetch page content
            html, error = await fetch(session, url)
            if error:
                results["broken_links"].append((url, error))
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Extract Title & Meta Description
            title = soup.title.string.strip() if soup.title else None
            meta_desc_tag = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and "content" in meta_desc_tag.attrs else None

            # Extract H1 Tags
            h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]

            # Check for missing metadata
            if not title:
                results["missing_titles"].append(url)
            if not meta_desc:
                results["missing_meta_descriptions"].append(url)
            if not h1_tags:
                results["missing_h1_tags"].append(url)

            # Check for duplicate metadata
            if title:
                results["duplicate_titles"].setdefault(title, []).append(url)
            if meta_desc:
                results["duplicate_meta_descriptions"].setdefault(meta_desc, []).append(url)

            # Keyword Scan (Including ALT Text in Images)
            keywords = []
            for img in soup.find_all("img"):
                alt_text = img.get("alt", "").strip()
                if alt_text:
                    keywords.append(alt_text)

            if keywords:
                results["keyword_scan"][url] = keywords

            # Check for Uncompressed Pages (Improved Detection)
            if "gzip" not in str(soup).lower() and "br" not in str(soup).lower():
                results["uncompressed_pages"].append(url)

            visited.add(url)

            # Extract only direct subpages (ignore deep links)
            for link in soup.find_all("a", href=True):
                absolute_link = urljoin(base_url, link["href"])
                parsed_link = urlparse(absolute_link)

                # Ignore non-navigational JavaScript & mailto links
                if absolute_link.startswith("javascript:void(0)") or absolute_link.startswith("mailto:"):
                    continue

                # Ensure it's an internal link & not too deep
                if parsed_link.netloc == parsed_url.netloc and parsed_link.path.count("/") <= 1:
                    if absolute_link not in visited and absolute_link not in queue:
                        queue.append(absolute_link)

                # Check if external link is broken
                elif parsed_link.netloc != parsed_url.netloc:
                    _, external_error = await fetch(session, absolute_link)
                    if external_error:
                        results["broken_links"].append((absolute_link, external_error))

    return results



