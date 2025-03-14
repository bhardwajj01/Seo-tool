import aiohttp
import asyncio
import dns.resolver
import whois
import socket

DOMAIN = "4imi.com"  # Use "yahoo.com", NOT "https://www.yahoo.com/"

def get_dns_records(domain):
    """Retrieve DNS records (A, MX, TXT, NS, CNAME, AAAA, SOA, SRV)"""
    records = {}
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ["8.8.8.8"]  # Use Google's public DNS
    
    record_types = ["A", "MX", "TXT", "NS", "CNAME", "AAAA", "SOA", "SRV"]
    
    for record_type in record_types:
        try:
            if record_type == "MX":
                records[record_type] = [(mx.exchange.to_text(), mx.preference) for mx in resolver.resolve(domain, record_type)]
            else:
                records[record_type] = [r.to_text() for r in resolver.resolve(domain, record_type)]
        except:
            records[record_type] = f"No {record_type} records found"
    
    return records

def get_whois_data(domain):
    """Retrieve WHOIS data"""
    try:
        whois_info = whois.whois(domain)
        return {
            "Domain Name": whois_info.domain_name,
            "Registrar": whois_info.registrar,
            "Creation Date": whois_info.creation_date,
            "Expiration Date": whois_info.expiration_date,
            "Updated Date": whois_info.updated_date,
            "Name Servers": whois_info.name_servers,
            "Status": whois_info.status,
            "Emails": whois_info.emails
        }
    except:
        return "WHOIS lookup failed"

def get_ip_address(domain):
    """Get the IP address of the domain"""
    try:
        ip_addresses = socket.gethostbyname_ex(domain)
        return ip_addresses[2]
    except:
        return "Could not resolve IP"

async def check_blacklist(domain):
    """Check if domain is blacklisted using MXToolbox API (Replace API_KEY)"""
    API_KEY = "YOUR_MXTOOLBOX_API_KEY"  # Use a valid API Key
    url = f"https://mxtoolbox.com/api/v1/lookup/blacklist/{domain}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"status": "error", "message": "Blacklist check failed"}
        except:
            return {"status": "error", "message": "Blacklist check failed"}

async def fetch_domain_info(domain):
    """Fetch all domain information asynchronously"""
    dns_records = get_dns_records(domain)
    whois_data = get_whois_data(domain)
    ip_address = get_ip_address(domain)
    blacklist_status = await check_blacklist(domain)
    
    return {
        "DNS Records": dns_records,
        "WHOIS Data": whois_data,
        "IP Address": ip_address,
        "Blacklist Status": blacklist_status
    }

async def main():
    result = await fetch_domain_info(DOMAIN)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
