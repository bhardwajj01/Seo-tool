import requests
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiohttp
import json
# from serpapi import GoogleSearch
from serpapi.google_search import GoogleSearch
import serpapi

# API Keys
SERPAPI_KEY = "94d8e48b7083bd2afba329179b7aac932bf9fd23f0dd735b7d1fd4b1151ab2c4"
MOZ_API_TOKEN = ""
MOZ_API_URL = "https://lsapi.seomoz.com/v2/url_metrics"

async def indexing_and_crawlability(website_url: str) -> dict:
    """
    Comprehensive SEO analysis function that combines sitemap analysis, 
    SerpAPI insights, and Moz metrics.
    
    Args:
        website_url (str): The website URL to analyze
        
    Returns:
        dict: Combined analysis results including sitemap analysis, SERP data, and domain metrics
    """
    """
    Comprehensive SEO analysis function that combines sitemap analysis, 
    SerpAPI insights, and Moz metrics.
    
    Args:
        website_url (str): The website URL to analyze
        
    Returns:
        dict: Combined analysis results
    """
    
    # Helper functions for sitemap analysis
    def find_xml_files(domain):
        robots_url = urljoin(domain, "/robots.txt")
        common_paths = [
            "/sitemap.xml",
            "/wp-sitemap.xml",
            "/sitemap_index.xml", 
            "/sitemap/sitemap.xml",
            "/post-sitemap.xml",
            "/page-sitemap.xml",
            "/product-sitemap.xml",
            "/category-sitemap.xml",
            "/author-sitemap.xml"
        ]
        
        try:
            response = requests.get(robots_url, timeout=10)
            if response.status_code == 200:
                found = re.findall(r"(?i)(https?://\S+?\.xml)", response.text)
                if found:
                    return found
        except requests.exceptions.RequestException as e:
            print(f"Error accessing robots.txt: {e}")
            
        return [urljoin(domain, path) for path in common_paths]

    def get_sitemap(xml_urls):
        for url in xml_urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200 and any(x in response.text.lower() for x in ['sitemap', 'urlset', '.xml']):
                    return response.text, url
            except requests.exceptions.RequestException:
                continue
        return None, None

    def parse_sitemap(xml_data):
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            return []
            
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = []
        
        # Handle both sitemap index and regular sitemaps
        if root.tag.endswith(("sitemapindex", "urlset")):
            for loc in root.findall(".//ns:loc", namespace):
                urls.append({"url": loc.text})
                
        return urls

    def check_single_url(url_dict):
        try:
            response = requests.get(url_dict["url"], timeout=5)
            url_dict["status"] = response.status_code
        except requests.exceptions.RequestException:
            url_dict["status"] = "Failed"
        return url_dict

    def check_urls_parallel(urls, batch_size=5):
        if not urls:
            return []
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            results = list(executor.map(check_single_url, urls))
        return results

    # Helper functions for SerpAPI analysis
    async def fetch_serpapi(params):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://serpapi.com/search", params=params) as response:
                return await response.json()

    # Helper function for Moz metrics
    async def fetch_domain_metrics(domain):
        headers = {"Authorization": f"Bearer {MOZ_API_TOKEN}"}
        payload = {"targets": [domain]}
        async with aiohttp.ClientSession() as session:
            async with session.post(MOZ_API_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and "results" in data:
                        result = data["results"][0]
                        return {
                            "domain_authority": result.get("domain_authority", "N/A"),
                            "page_authority": result.get("page_authority", "N/A"),
                            "spam_score": result.get("spam_score", "N/A"),
                            "total_backlinks": result.get("pages_to_root_domain", "N/A"),
                            "external_backlinks": result.get("external_pages_to_root_domain", "N/A"),
                            "root_domains_linking": result.get("root_domains_to_root_domain", "N/A"),
                            "deleted_backlinks": result.get("deleted_pages_to_root_domain", "N/A"),
                            "nofollow_backlinks": result.get("nofollow_pages_to_root_domain", "N/A"),
                            "pages_crawled": result.get("pages_crawled_from_root_domain", "N/A"),
                        }
                else:
                    return {"error": f"Failed to fetch metrics: {response.status} - {await response.text()}"}

    # Main analysis results dictionary
    results = {
        "sitemap_analysis": {},
        "serp_analysis": {
            "indexed_pages": [],
            "rankings": [],
            "competitors": []
        },
        "domain_metrics": {},
        "status": "success",
        "error_message": None
    }

    try:
        # 1. Sitemap Analysis
        xml_files = find_xml_files(website_url)
        if not xml_files:
            results["sitemap_analysis"]["status"] = "error"
            results["sitemap_analysis"]["error_message"] = "No sitemap files found"
        else:
            sitemap_data, sitemap_url = get_sitemap(xml_files)
            if not sitemap_data:
                results["sitemap_analysis"]["status"] = "error"
                results["sitemap_analysis"]["error_message"] = "Could not retrieve sitemap content"
            else:
                results["sitemap_analysis"]["main_sitemap"] = sitemap_url
                sitemaps = parse_sitemap(sitemap_data)
                
                if not sitemaps:
                    results["sitemap_analysis"]["status"] = "error"
                    results["sitemap_analysis"]["error_message"] = "No URLs found in sitemap"
                else:
                    checked_sitemaps = check_urls_parallel(sitemaps)
                    results["sitemap_analysis"]["sitemaps"] = checked_sitemaps
                    results["sitemap_analysis"]["total"] = len(checked_sitemaps)
                    results["sitemap_analysis"]["working"] = sum(1 for url in checked_sitemaps if str(url['status']).startswith('2'))
                    results["sitemap_analysis"]["broken"] = sum(1 for url in checked_sitemaps if str(url['status']).startswith('4'))
                    results["sitemap_analysis"]["errors"] = sum(1 for url in checked_sitemaps if str(url['status']).startswith('5'))

        # 2. SERP Analysis
        print(f"\n🔹 Analyzing Website: {website_url}\n")
        
        # Indexed Pages
        print("\n🔎 Indexed Pages in Google:")
        params_indexed = {"q": f"site:{website_url}", "api_key": SERPAPI_KEY}
        indexed_results = await fetch_serpapi(params_indexed)
        results["serp_analysis"]["indexed_pages"] = [r["link"] for r in indexed_results.get("organic_results", []) if "link" in r]
        
        if results["serp_analysis"]["indexed_pages"]:
            for i, page in enumerate(results["serp_analysis"]["indexed_pages"][:10], 1):
                print(f"  {i}. {page}")
        else:
            print("  ❌ No indexed pages found!")

        keyword = "SEO strategies"
        print(f"\n🔎 Top 5 Organic Search Rankings for '{keyword}':")
        params_rankings = {"q": f"site:{website_url} {keyword}", "api_key": SERPAPI_KEY}
        ranking_results = await fetch_serpapi(params_rankings)
        results["serp_analysis"]["rankings"] = [r for r in ranking_results.get("organic_results", []) if "link" in r and website_url in r["link"]]
        
        if results["serp_analysis"]["rankings"]:
            for i, r in enumerate(results["serp_analysis"]["rankings"][:5], 1):
                print(f"  {i}. {r['title']} → {r['link']}")
        else:
            print("  ❌ No rankings found!")

        print("\n🔍 Potential Competitor Websites:")
        params_competitors = {"q": f"related:{website_url}", "api_key": SERPAPI_KEY}
        competitor_results = await fetch_serpapi(params_competitors)
        results["serp_analysis"]["competitors"] = [r["link"] for r in competitor_results.get("organic_results", []) if "link" in r and website_url not in r["link"]]
        
        if results["serp_analysis"]["competitors"]:
            for i, comp in enumerate(results["serp_analysis"]["competitors"][:5], 1):
                print(f"  {i}. {comp}")
        else:
            print("  ❌ No competitor websites found!")

        # 3. Domain Metrics
        results["domain_metrics"] = await fetch_domain_metrics(website_url)

        return results

    except Exception as e:
        results["status"] = "error"
        results["error_message"] = str(e)
        return results
    
