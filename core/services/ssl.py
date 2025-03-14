import ssl
import socket
import asyncio
from datetime import datetime
import json
import aiohttp
from bs4 import BeautifulSoup

# Your Google Safe Browsing API key
API_KEY = ""

async def check_malware(url: str) -> dict:
    """
    Asynchronous function to check if a URL is malicious using Google Safe Browsing API.
    """
    api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={API_KEY}"

    payload = {
        "client": {
            "clientId": "malware-checker",
            "clientVersion": "1.0"
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }

    headers = {"Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, data=json.dumps(payload), headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    malware_info = {
                        "status": "malicious" if "matches" in result else "safe",
                        "details": result.get("matches", []) if "matches" in result else [],
                        "check_time": datetime.utcnow()  # Changed: removed isoformat()
                    }
                    return malware_info
                else:
                    return {
                        "status": "error",
                        "message": f"API request failed with status code {response.status}",
                        "check_time": datetime.utcnow()  # Changed: removed isoformat()
                    }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "check_time": datetime.utcnow()  # Changed: removed isoformat()
        }

async def analyze_ssl_security(url: str) -> dict:
    # Extract hostname from URL
    hostname = url.replace("https://", "").replace("http://", "").split("/")[0]
    
    try:
        # Run SSL check and malware check concurrently
        ssl_task = analyze_ssl_certificate(hostname)
        malware_task = check_malware(url)
        
        # Wait for both tasks to complete
        ssl_result, malware_result = await asyncio.gather(ssl_task, malware_task)
        
        # Combine results
        result = {
            **ssl_result,
            "malware_info": malware_result,
            "status": "success" if ssl_result["status"] == "success" and malware_result["status"] != "error" else "error"
        }
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "ssl_info": None,
            "indexing_info": None,
            "malware_info": None
        }

async def analyze_ssl_certificate(hostname: str) -> dict:
    try:
        # SSL certificate check
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        expiration_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
        days_left = (expiration_date - datetime.utcnow()).days
        ssl_info = {
            "expiration_date": expiration_date,  # Changed: removed isoformat()
            "days_left": days_left,
            "is_valid": days_left > 0,
            "issuer": dict(x[0] for x in cert['issuer']),
            "subject": dict(x[0] for x in cert['subject']),
            "version": cert.get('version', None),
            "serialNumber": cert.get('serialNumber', None),
            "status": "Valid" if days_left > 0 else "Expired"
        }

        # Robots.txt and indexing check
        async with aiohttp.ClientSession() as session:
            robots_txt_url = f"https://{hostname}/robots.txt"
            try:
                async with session.get(robots_txt_url) as response:
                    robots_status = response.status
                    robots_txt = await response.text() if robots_status == 200 else None
            except:
                robots_status = None
                robots_txt = None

            indexing_info = {
                "robots_txt_status": robots_status == 200,
                "robots_txt_content": robots_txt if robots_status == 200 else None,
                "noindex_meta": None
            }

            # Check homepage for meta robots
            try:
                async with session.get(f"https://{hostname}") as response:
                    if response.status == 200:
                        content = await response.text()
                        soup = BeautifulSoup(content, "html.parser")
                        meta_robots = soup.find("meta", {"name": "robots"})
                        indexing_info["noindex_meta"] = (
                            "noindex" in meta_robots.get("content", "").lower()
                            if meta_robots else False
                        )
            except:
                indexing_info["noindex_meta"] = None

        return {
            "ssl_info": ssl_info,
            "indexing_info": indexing_info,
            "status": "success"
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "ssl_info": None,
            "indexing_info": None
        }
