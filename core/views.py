from django.shortcuts import render
from django.core.cache import cache
from .services.traffic import get_semrush_traffic_metrics
from .services.peformance1 import analyze_website_performance
from .services.ssl import analyze_ssl_security
from .services.indexing_and_crawlability import indexing_and_crawlability
from .services.schema import check_schema
from .services.audit import site_audit
from.services.domain_and_whois_data import fetch_domain_info
from openai import OpenAI

import asyncio
import json
from collections import OrderedDict


# def home(request):
#     if request.GET.get('refresh') == 'true':
#         # Clear session data
#         request.session.flush()

#         # Clear Django cache
#         cache.clear()

#         print("Cache and session data cleared. Performing a fresh scan.")

#     return render(request, "index.html")

def home(request):
    # Always clear session and cache when the page loads
    request.session.flush()
    cache.clear()

    print("Cache and session data cleared. Performing a fresh scan.")

    return render(request, "index.html")


import json
from openai import OpenAI

def get_ai_analysis(analysis_data):
    """
    Conducts a complete, long-form analysis using GPT-4o with expanded explanations.
    Returns structured, detailed insights suitable for non-technical users.
    
    Args:
        analysis_data (dict): The compiled results of all website analyses
        
    Returns:
        dict: The AI analysis with Overview, Complete Analysis, Weaknesses, Strengths, and Advice
    """
    try:
        # Initialize OpenAI client with your API key
        client = OpenAI(api_key="")
        
        # Convert analysis data to JSON
        json_data = json.dumps(analysis_data, default=str)
        
        # Define the system and user messages with detailed instructions
        messages = [
            {"role": "system", "content": (
                "You are an advanced AI specialized in website performance and SEO analysis. "
                "Generate long, detailed, and comprehensive reports suitable for a NON-TECHNICAL audience. "
                "Write in simple language, avoiding jargon, and use practical analogies. For each section—"
                "Overview, Complete Analysis, Weaknesses, Strengths, and Advice—provide in-depth explanations.\n\n"
                "**Important Instructions:**\n"
                "- For every metric, explain WHY it matters and HOW it affects user experience and search rankings.\n"
                "- Provide multi-step breakdowns and thorough reasoning for each insight.\n"
                "- Use relatable analogies (e.g., 'Think of page speed like the waiting time at a restaurant...').\n"
                "- In the Advice section, provide actionable recommendations explained in detail.\n"
                "- Ensure the response is LONG, DETAILED, and NEVER BRIEF.\n"
                "- Strictly return a VALID JSON response with the keys: Overview, Complete Analysis, Weaknesses, Strengths, and Advice.\n"
                "- Check JSON validity (no unquoted strings, proper formatting, etc.)."
            )},
            {"role": "user", "content": (
                "Analyze the following JSON data and provide a STRICTLY VALID JSON response with these exact keys: "
                "\"Overview\", \"Complete Analysis\", \"Weaknesses\", \"Strengths\", and \"Advice\".\n\n"
                "The analysis should:\n"
                "- Be comprehensive and LONG, providing multi-paragraph explanations.\n"
                "- Break down each performance metric step-by-step.\n"
                "- Provide practical analogies and relatable explanations for non-technical readers.\n"
                "- Each section must be fully detailed, focusing on the impact of each metric on SEO and user engagement.\n\n"
                f"{json_data}"
            )}
        ]

        # Send request to GPT-4o
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        # Extract response content and clean code block markers
        result = response.choices[0].message.content.strip()
        if result.startswith("```json"):
            result = result[len("```json"):].strip()
        if result.endswith("```"):
            result = result[:-len("```")].strip()

        # Parse JSON response
        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            print(f"Error parsing AI response as JSON: {e}")
            return {
                "Overview": "Error processing AI analysis.",
                "Complete Analysis": "An error occurred while analyzing the data.",
                "Weaknesses": "Could not determine weaknesses due to processing error.",
                "Strengths": "Could not determine strengths due to processing error.",
                "Advice": "Please try running the analysis again."
            }

    except Exception as e:
        print(f"Error in AI analysis: {e}")
        return {
            "Overview": "Error processing AI analysis.",
            "Complete Analysis": "An error occurred while analyzing the data.",
            "Weaknesses": "Could not determine weaknesses due to processing error.",
            "Strengths": "Could not determine strengths due to processing error.",
            "Advice": "Please try running the analysis again."
        }


def analyze(request):
    if request.method == "POST":
        url = request.POST.get("url")
        
        # Try to get cached results
        cache_key = f'website_analysis_{url}'
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return render(request, "results.html", cached_result)
        
        # If no cache, perform analysis
        async def run_analysis():
            # Run all analyses concurrently
            performance_task = analyze_website_performance(url)
            ssl_task = analyze_ssl_security(url)
            indexing_task = indexing_and_crawlability(url)
            audit_task = site_audit(url) 
            schema_task = check_schema(url)
            # domain_info_task= fetch_domain_info(url) 
            # Add traffic metrics task here - but it's synchronous so we need to run it in a separate thread
            traffic_task = asyncio.to_thread(get_semrush_traffic_metrics, url)
            # domain_info_task
            results = await asyncio.gather(performance_task, ssl_task, indexing_task, audit_task, schema_task, traffic_task)
            return results

    #  domain_info_result
        # Run all analyses
        performance_result, security_result, indexing_result, audit_result, schema_result, traffic_result = asyncio.run(run_analysis())
        
        # Get the metrics from the performance result
        metrics = performance_result["Performance Metrics"]
        
        # Organize metrics into categories
        categorized_metrics = {
            'core_metrics': {},
            'pagespeed_metrics': {},
            'timing_metrics': {},
        }
        
        # Core metrics list
        core_metrics_list = [
            'TTFB', 'Redirect Time', 'Connect Time', 'Backend Time',
            'First Contentful Paint', 'Largest Contentful Paint',
            'Cumulative Layout Shift', 'Onload Time', 'Fully Loaded Time'
        ]
        
        # PageSpeed metrics list
        pagespeed_metrics_list = [
            'TBT (Total Blocking Time)',
            'TTI (Time to Interactive)',
            'SI (Speed Index)'
        ]

        # Get navigation start time for relative calculations
        navigation_start = metrics.get('Navigation Start Time', 0)
        
        # Categorize and process each metric
        for key, value in metrics.items():
            if key in core_metrics_list:
                categorized_metrics['core_metrics'][key] = value
            elif key in pagespeed_metrics_list:
                categorized_metrics['pagespeed_metrics'][key] = value
            elif 'Time' in key and key not in core_metrics_list:
                if isinstance(value, (int, float)):
                    relative_time = value - navigation_start
                    categorized_metrics['timing_metrics'][key] = round(relative_time / 1000, 3)
                else:
                    categorized_metrics['timing_metrics'][key] = value

        # Sort timing metrics by sequence
        timing_sequence = [
            'Navigation Start Time',
            'Request Start Time',
            'Response Start Time',
            'Response End Time',
            'DOM Loading Time',
            'DOM Interactive Time',
            'DOM Complete Time',
            'Load Event End Time'
        ]
        
        # Create ordered timing metrics
        timing_metrics_ordered = OrderedDict()
        for metric in timing_sequence:
            if metric in categorized_metrics['timing_metrics']:
                timing_metrics_ordered[metric] = categorized_metrics['timing_metrics'][metric]
        
        for key, value in categorized_metrics['timing_metrics'].items():
            if key not in timing_metrics_ordered:
                timing_metrics_ordered[key] = value

        # Format raw data as JSON strings
        raw_data = {
            'paint_events_data': json.dumps(metrics.get('Paint Events Data', {}), indent=2),
            'web_vitals_data': json.dumps(metrics.get('Web Vitals Data', {}), indent=2),
            'complete_timing_data': json.dumps(metrics.get('Complete Timing Data', {}), indent=2)
        }

        # Get security threat details
        malware_info = security_result.get("malware_info", {})
        threat_details = []
        if malware_info.get("status") == "malicious":
            for match in malware_info.get("details", []):
                threat_details.append({
                    "type": match.get("threatType", "Unknown Threat"),
                    "platform": match.get("platformType", "All Platforms"),
                    "threat_entry": match.get("threat", {}).get("url", "Unknown URL")
                })

        # Process indexing and crawlability results
        serp_analysis = indexing_result.get("serp_analysis", {})
        domain_metrics = indexing_result.get("domain_metrics", {})
        sitemap_analysis = indexing_result.get("sitemap_analysis", {})

        # Prepare context data with all results
        context = {
            # Performance data
            "core_metrics": OrderedDict(sorted(categorized_metrics['core_metrics'].items())),
            "pagespeed_metrics": OrderedDict(sorted(categorized_metrics['pagespeed_metrics'].items())),
            "timing_metrics": timing_metrics_ordered,
            "raw_data": raw_data,
            "raw_score": performance_result["Raw Performance Score"],
            "adjusted_scores": performance_result["Adjusted Scores"],
            "url": url,
            
            # SSL and security data
            "ssl_info": security_result.get("ssl_info", {}),
            "indexing_info": security_result.get("indexing_info", {}),
            "ssl_status": security_result.get("status", "error"),
            
            # Malware information
            "malware_info": {
                "status": malware_info.get("status", "unknown"),
                "check_time": malware_info.get("check_time"),
                "threat_details": threat_details,
                "is_safe": malware_info.get("status") == "safe"
            },
            
            # New indexing and crawlability data
            "serp_analysis": {
                "indexed_pages": serp_analysis.get("indexed_pages", []),
                "rankings": serp_analysis.get("rankings", []),
                "competitors": serp_analysis.get("competitors", [])
            },
            "domain_metrics": domain_metrics,
            "sitemap_analysis": sitemap_analysis,
            
            "audit_results": {
                "missing_meta": audit_result.get("missing_meta_descriptions", []),
                "missing_titles": audit_result.get("missing_titles", []),
                "missing_h1": audit_result.get("missing_h1_tags", []),
                "missing_h2": audit_result.get("missing_h2_tags", []),
                "missing_h3": audit_result.get("missing_h3_tags", []),
                "duplicate_meta": audit_result.get("duplicate_meta_descriptions", {}),
                "duplicate_titles": audit_result.get("duplicate_titles", {}),
                "broken_links": audit_result.get("broken_links", []),
                "keyword_scan": audit_result.get("keyword_scan", {}),
                "uncompressed_pages": audit_result.get("uncompressed_pages", [])
            },
            "schema_analysis": {
                "status": schema_result.get("Status"),
                "total_schemas": schema_result.get("Total Schemas Found", 0),
                "jsonld_count": schema_result.get("JSON-LD Schemas Found", 0),
                "microdata_count": schema_result.get("Microdata/RDFa Schemas Found", 0),
                "errors": schema_result.get("Errors", []),
                "jsonld_details": schema_result.get("JSON-LD Schema Details", []),
                "microdata_details": schema_result.get("Microdata/RDFa Schema Details", [])
            },
            
            # Add this to the context dictionary
            "traffic_metrics": {
                "status": "success" if traffic_result else "error",
                "data": traffic_result.get("metrics", {}) if traffic_result else {},
                "domain": url,
                "timestamp": traffic_result.get("timestamp") if traffic_result else None
            },
            # "domain_info": {
            #     "ip_addresses": domain_info_result.get("ip_addresses", "N/A"),
            #     "whois_info": {
            #         "Domain Name": domain_info_result.get("whois_info", {}).get("Domain Name", "N/A"),
            #         "Registrar": domain_info_result.get("whois_info", {}).get("Registrar", "N/A"),
            #         "Creation Date": domain_info_result.get("whois_info", {}).get("Creation Date", "N/A"),
            #         "Expiration Date": domain_info_result.get("whois_info", {}).get("Expiration Date", "N/A"),
            #         "Status": domain_info_result.get("whois_info", {}).get("Status", "N/A"),
            #     },
            #     "dns_records": domain_info_result.get("dns_records", {}),
            #     "blacklist_status": domain_info_result.get("blacklist_status", "Not Available"),
            # }

            
        }
        # Now run the AI analysis after all other analyses are complete
        ai_analysis_result = get_ai_analysis(context)
        
        # Add the AI analysis results to the context
        context["ai_analysis"] = ai_analysis_result
        print("=============================")
        print("arun codde",context)
        
        # Cache the results for 1 hour (3600 seconds)
        cache.set(cache_key, context, 3600)
        
        return render(request, "results.html", context)

        
    return render(request, "index.html")


# Add these imports to your views.py file
from django.http import HttpResponse
from django.core.cache import cache
from django.template.loader import get_template
import csv
from io import BytesIO
import json
from xhtml2pdf import pisa
from datetime import datetime

def export_csv(request):
    """Export comprehensive analysis results to CSV format matching all tabs"""
    # Get cached results using the same URL parameter
    url = request.GET.get("url")
    cache_key = f'website_analysis_{url}'
    cached_result = cache.get(cache_key)
    
    # Debug information
    print(f"DEBUG - CSV Export - URL: {url}")
    print(f"DEBUG - CSV Export - Cache key: {cache_key}")
    print(f"DEBUG - CSV Export - Cache hit: {cached_result is not None}")
    
    # Try alternate cache keys if the primary one fails
    if not cached_result and url:
        # Try with trailing slash
        alt_url = url if url.endswith('/') else f"{url}/"
        alt_cache_key = f'website_analysis_{alt_url}'
        cached_result = cache.get(alt_cache_key)
        print(f"DEBUG - CSV Export - Trying alternate key: {alt_cache_key}")
        print(f"DEBUG - CSV Export - Alternate cache hit: {cached_result is not None}")
        
        # Try without protocol
        if not cached_result:
            clean_url = url.replace("https://", "").replace("http://", "")
            clean_cache_key = f'website_analysis_{clean_url}'
            cached_result = cache.get(clean_cache_key)
            print(f"DEBUG - CSV Export - Trying clean key: {clean_cache_key}")
            print(f"DEBUG - CSV Export - Clean cache hit: {cached_result is not None}")
    
    if not cached_result:
        return HttpResponse("No analysis data found. Please run the analysis first.", status=404)
    
    # Create a response object with CSV content type
    response = HttpResponse(content_type='text/csv')
    domain = url.replace("https://", "").replace("http://", "").split("/")[0]
    response['Content-Disposition'] = f'attachment; filename="{domain}_analysis_report.csv"'
    
    # Create CSV writer with proper quoting
    writer = csv.writer(response, quoting=csv.QUOTE_MINIMAL)
    
    # Write report header
    writer.writerow(['WEBSITE ANALYSIS REPORT', url])
    writer.writerow(['Generated on', datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])
    
    # ===== PERFORMANCE METRICS SECTION =====
    writer.writerow(['====== PERFORMANCE METRICS ======'])
    writer.writerow([])
    
    # Performance Score and Grade
    writer.writerow(['--- Performance Score ---'])
    for country, data in cached_result.get('adjusted_scores', {}).items():
        if country == "USA":
            writer.writerow(['Performance Score', f"{data.get('Score', 0):.2f}"])
            writer.writerow(['Performance Grade', data.get('Grade', 'N/A')])
    writer.writerow([])
    
    # Core Web Vitals
    writer.writerow(['--- Core Web Vitals ---'])
    writer.writerow(['Metric', 'Value', 'Status'])
    for key, value in cached_result.get('core_metrics', {}).items():
        status = "Good"
        if key in ['First Contentful Paint', 'Largest Contentful Paint']:
            if value > 2500:
                status = "Poor"
            elif value > 1000:
                status = "Needs Improvement"
        elif key == 'Cumulative Layout Shift':
            if value > 0.25:
                status = "Poor"
            elif value > 0.1:
                status = "Needs Improvement"
                
        writer.writerow([key, value, status])
    writer.writerow([])
    
    # PageSpeed Metrics
    writer.writerow(['--- PageSpeed Metrics ---'])
    writer.writerow(['Metric', 'Value'])
    for key, value in cached_result.get('pagespeed_metrics', {}).items():
        writer.writerow([key, value])
    writer.writerow([])
    
    # Timing Metrics
    writer.writerow(['--- Timing Metrics ---'])
    writer.writerow(['Metric', 'Value (seconds)'])
    for key, value in cached_result.get('timing_metrics', {}).items():
        writer.writerow([key, value])
    writer.writerow([])
    
    # ===== SECURITY & SSL SECTION =====
    writer.writerow(['====== SECURITY & SSL ======'])
    writer.writerow([])
    
    # SSL Certificate
    writer.writerow(['--- SSL Certificate ---'])
    ssl_info = cached_result.get('ssl_info', {})
    writer.writerow(['SSL Status', cached_result.get('ssl_status', 'Unknown')])
    
    # SSL Issuer Info
    if ssl_info.get('issuer'):
        writer.writerow(['Issuer Information'])
        for key, value in ssl_info.get('issuer', {}).items():
            writer.writerow([key, value])
            
    # SSL Subject Info
    if ssl_info.get('subject'):
        writer.writerow(['Certificate Subject'])
        for key, value in ssl_info.get('subject', {}).items():
            writer.writerow([key, value])
    
    # SSL Expiration
    if ssl_info:
        writer.writerow(['Expiration Date', ssl_info.get('expiration_date', 'Unknown')])
        writer.writerow(['Days Remaining', ssl_info.get('days_left', 'Unknown')])
        writer.writerow(['Version', ssl_info.get('version', 'Unknown')])
        writer.writerow(['Serial Number', ssl_info.get('serialNumber', 'Unknown')])
    writer.writerow([])
    
    # Malware Detection
    writer.writerow(['--- Security Status ---'])
    malware_info = cached_result.get('malware_info', {})
    writer.writerow(['Security Status', 'Safe' if malware_info.get('is_safe') else 'At Risk'])
    writer.writerow(['Last Check', malware_info.get('check_time', 'Unknown')])
    
    # Threat Details
    if malware_info.get('threat_details'):
        writer.writerow([])
        writer.writerow(['--- Threat Details ---'])
        writer.writerow(['Type', 'Platform', 'Threat Entry'])
        for threat in malware_info.get('threat_details', []):
            writer.writerow([
                threat.get('type', 'Unknown'),
                threat.get('platform', 'Unknown'),
                threat.get('threat_entry', 'Unknown')
            ])
    writer.writerow([])
    
    # Robots.txt Information
    writer.writerow(['--- Indexing Information ---'])
    indexing_info = cached_result.get('indexing_info', {})
    writer.writerow(['Robots.txt Present', 'Yes' if indexing_info.get('robots_txt_status') else 'No'])
    writer.writerow(['No-Index Meta Tag', 'Yes' if indexing_info.get('noindex_meta') else 'No'])
    
    if indexing_info.get('robots_txt_content'):
        writer.writerow([])
        writer.writerow(['Robots.txt Content'])
        writer.writerow([indexing_info.get('robots_txt_content')])
    writer.writerow([])
    
    # ===== INDEXING & CRAWLABILITY SECTION =====
    writer.writerow(['====== INDEXING & CRAWLABILITY ======'])
    writer.writerow([])
    
    # Indexed Pages and Crawled Pages
    serp_analysis = cached_result.get('serp_analysis', {})
    domain_metrics = cached_result.get('domain_metrics', {})
    
    writer.writerow(['--- Indexing Overview ---'])
    writer.writerow(['Indexed Pages', len(serp_analysis.get('indexed_pages', []))])
    writer.writerow(['Pages Crawled', domain_metrics.get('pages_crawled', 'N/A')])
    writer.writerow([])
    
    # Search Rankings
    writer.writerow(['--- Search Rankings ---'])
    if serp_analysis.get('rankings'):
        writer.writerow(['Title', 'Position', 'Displayed Link', 'Link'])
        for ranking in serp_analysis.get('rankings', []):
            writer.writerow([
                ranking.get('title', 'N/A'),
                ranking.get('position', 'N/A'),
                ranking.get('displayed_link', 'N/A'),
                ranking.get('link', 'N/A')
            ])
    else:
        writer.writerow(['No ranking data available'])
    writer.writerow([])
    
    # Competitors
    writer.writerow(['--- Competitors ---'])
    if serp_analysis.get('competitors'):
        for competitor in serp_analysis.get('competitors', []):
            writer.writerow([competitor])
    else:
        writer.writerow(['No competitor data available'])
    writer.writerow([])
    
    # Sitemap Analysis
    sitemap_analysis = cached_result.get('sitemap_analysis', {})
    writer.writerow(['--- Sitemap Analysis ---'])
    if sitemap_analysis.get('status') == 'error':
        writer.writerow(['Error', sitemap_analysis.get('error_message', 'Unknown error')])
    else:
        writer.writerow(['Total URLs', sitemap_analysis.get('total', 0)])
        writer.writerow(['Working URLs', sitemap_analysis.get('working', 0)])
        writer.writerow(['Broken URLs', sitemap_analysis.get('broken', 0)])
        writer.writerow(['Server Errors', sitemap_analysis.get('errors', 0)])
    writer.writerow([])
    
    # ===== META DATA & STRUCTURE SECTION =====
    writer.writerow(['====== META DATA & STRUCTURE ======'])
    writer.writerow([])
    
    # Status Overview
    audit_results = cached_result.get('audit_results', {})
    writer.writerow(['--- Overview ---'])
    writer.writerow(['Missing Meta Descriptions', len(audit_results.get('missing_meta', []))])
    writer.writerow(['Missing Titles', len(audit_results.get('missing_titles', []))])
    writer.writerow(['Missing H1 Tags', len(audit_results.get('missing_h1', []))])
    writer.writerow(['Broken Links', len(audit_results.get('broken_links', []))])
    writer.writerow(['Uncompressed Pages', len(audit_results.get('uncompressed_pages', []))])
    writer.writerow([])
    
    # Missing Elements
    if audit_results.get('missing_h1'):
        writer.writerow(['--- Missing H1 Tags ---'])
        for url in audit_results.get('missing_h1', []):
            writer.writerow([url])
        writer.writerow([])
    
    if audit_results.get('missing_meta'):
        writer.writerow(['--- Missing Meta Descriptions ---'])
        for url in audit_results.get('missing_meta', []):
            writer.writerow([url])
        writer.writerow([])
    
    # Duplicate Content
    has_duplicates = False
    for title, urls in audit_results.get('duplicate_titles', {}).items():
        if len(urls) > 1:
            has_duplicates = True
            break
    
    if has_duplicates:
        writer.writerow(['--- Duplicate Content ---'])
        for title, urls in audit_results.get('duplicate_titles', {}).items():
            if len(urls) > 1:
                writer.writerow(['Duplicate Title:', title])
                for url in urls:
                    writer.writerow(['', url])
        writer.writerow([])
    
    # Broken Links
    if audit_results.get('broken_links'):
        writer.writerow(['--- Broken Links ---'])
        writer.writerow(['Link', 'Error'])
        for link, error in audit_results.get('broken_links', []):
            writer.writerow([link, error])
        writer.writerow([])
    
    # Keyword Analysis
    if audit_results.get('keyword_scan'):
        writer.writerow(['--- Keyword Analysis ---'])
        for url, keywords in audit_results.get('keyword_scan', {}).items():
            writer.writerow([url])
            writer.writerow(['Keywords:', ', '.join(keywords)])
        writer.writerow([])
    
    # ===== SCHEMA SECTION =====
    writer.writerow(['====== SCHEMA MARKUP ======'])
    writer.writerow([])
    
    # Schema Overview
    schema_analysis = cached_result.get('schema_analysis', {})
    writer.writerow(['--- Schema Overview ---'])
    writer.writerow(['Total Schemas', schema_analysis.get('total_schemas', 0)])
    writer.writerow(['JSON-LD Schemas', schema_analysis.get('jsonld_count', 0)])
    writer.writerow(['Microdata/RDFa Schemas', schema_analysis.get('microdata_count', 0)])
    writer.writerow(['Schema Errors', len(schema_analysis.get('errors', []))])
    writer.writerow([])
    
    # Schema Errors
    if schema_analysis.get('errors'):
        writer.writerow(['--- Schema Validation Errors ---'])
        for error in schema_analysis.get('errors', []):
            writer.writerow([error])
        writer.writerow([])
    
    # ===== BACKLINK PROFILE SECTION =====
    writer.writerow(['====== BACKLINK PROFILE ======'])
    writer.writerow([])
    
    # Domain Metrics
    writer.writerow(['--- Domain Metrics ---'])
    writer.writerow(['Domain Authority', domain_metrics.get('domain_authority', 'N/A')])
    writer.writerow(['Page Authority', domain_metrics.get('page_authority', 'N/A')])
    writer.writerow(['Total Backlinks', domain_metrics.get('total_backlinks', 'N/A')])
    writer.writerow(['Spam Score', domain_metrics.get('spam_score', 'N/A')])
    writer.writerow([])
    
    # Backlink Profile
    writer.writerow(['--- Backlink Profile ---'])
    writer.writerow(['External Backlinks', domain_metrics.get('external_backlinks', 'N/A')])
    writer.writerow(['Root Domains Linking', domain_metrics.get('root_domains_linking', 'N/A')])
    writer.writerow(['Deleted Backlinks', domain_metrics.get('deleted_backlinks', 'N/A')])
    writer.writerow(['Nofollow Backlinks', domain_metrics.get('nofollow_backlinks', 'N/A')])
    writer.writerow([])
    
    # ===== TRAFFIC PROFILE SECTION =====
    writer.writerow(['====== TRAFFIC PROFILE ======'])
    writer.writerow([])
    
    # Traffic Overview
    traffic_metrics = cached_result.get('traffic_metrics', {})
    if traffic_metrics.get('status') == 'success':
        writer.writerow(['--- Traffic Overview ---'])
        writer.writerow(['Total Visits', traffic_metrics.get('data', {}).get('visits', 'N/A')])
        writer.writerow(['Visits Change', traffic_metrics.get('data', {}).get('visits_change', 'N/A')])
        writer.writerow(['Unique Visitors', traffic_metrics.get('data', {}).get('unique_visitors', 'N/A')])
        writer.writerow(['Unique Visitors Change', traffic_metrics.get('data', {}).get('unique_visitors_change', 'N/A')])
        writer.writerow(['Bounce Rate', traffic_metrics.get('data', {}).get('bounce_rate', 'N/A')])
        writer.writerow(['Bounce Rate Change', traffic_metrics.get('data', {}).get('bounce_rate_change', 'N/A')])
        writer.writerow(['Avg. Visit Duration', traffic_metrics.get('data', {}).get('avg_visit_duration', 'N/A')])
        writer.writerow(['Avg. Visit Duration Change', traffic_metrics.get('data', {}).get('avg_visit_duration_change', 'N/A')])
        writer.writerow([])
        
        # Engagement Metrics
        writer.writerow(['--- Engagement Metrics ---'])
        writer.writerow(['Pages Per Visit', traffic_metrics.get('data', {}).get('pages_per_visit', 'N/A')])
        writer.writerow(['Pages Per Visit Change', traffic_metrics.get('data', {}).get('pages_per_visit_change', 'N/A')])
        writer.writerow([])
        
        # Device Breakdown
        writer.writerow(['--- Device Breakdown ---'])
        writer.writerow(['Mobile Share', traffic_metrics.get('data', {}).get('mobile_share', 'N/A')])
        writer.writerow(['Desktop Share', traffic_metrics.get('data', {}).get('desktop_share', 'N/A')])
        writer.writerow([])
        
        # Market Analysis
        writer.writerow(['--- Market Analysis ---'])
        writer.writerow(['Market Share', traffic_metrics.get('data', {}).get('market_share', 'N/A')])
        writer.writerow(['Market Traffic', traffic_metrics.get('data', {}).get('market_traffic', 'N/A')])
    else:
        writer.writerow(['Traffic data not available'])
    writer.writerow([])
    
    # ===== AI ANALYSIS SECTION =====
    writer.writerow(['====== AI ANALYSIS ======'])
    writer.writerow([])
    
    # AI Analysis
    ai_analysis = cached_result.get('ai_analysis', {})
    
    # Overview
    if ai_analysis.get('Overview'):
        writer.writerow(['--- Overview ---'])
        writer.writerow([ai_analysis.get('Overview')])
        writer.writerow([])
    
    # Strengths
    if ai_analysis.get('Strengths'):
        writer.writerow(['--- Strengths ---'])
        writer.writerow([ai_analysis.get('Strengths')])
        writer.writerow([])
    
    # Weaknesses
    if ai_analysis.get('Weaknesses'):
        writer.writerow(['--- Weaknesses ---'])
        writer.writerow([ai_analysis.get('Weaknesses')])
        writer.writerow([])
    
    # Advice
    if ai_analysis.get('Advice'):
        writer.writerow(['--- Advice ---'])
        writer.writerow([ai_analysis.get('Advice')])
    
    return response

def export_pdf(request):
    """Export analysis results to a professional PDF format matching all tabs"""
    # Get cached results using the same URL parameter
    url = request.GET.get("url")
    cache_key = f'website_analysis_{url}'
    cached_result = cache.get(cache_key)
    
    # Debug information
    print(f"DEBUG - PDF Export - URL: {url}")
    print(f"DEBUG - PDF Export - Cache key: {cache_key}")
    print(f"DEBUG - PDF Export - Cache hit: {cached_result is not None}")
    
    # Try alternate cache keys if the primary one fails
    if not cached_result and url:
        # Try with trailing slash
        alt_url = url if url.endswith('/') else f"{url}/"
        alt_cache_key = f'website_analysis_{alt_url}'
        cached_result = cache.get(alt_cache_key)
        print(f"DEBUG - PDF Export - Trying alternate key: {alt_cache_key}")
        print(f"DEBUG - PDF Export - Alternate cache hit: {cached_result is not None}")
        
        # Try without protocol
        if not cached_result:
            clean_url = url.replace("https://", "").replace("http://", "")
            clean_cache_key = f'website_analysis_{clean_url}'
            cached_result = cache.get(clean_cache_key)
            print(f"DEBUG - PDF Export - Trying clean key: {clean_cache_key}")
            print(f"DEBUG - PDF Export - Clean cache hit: {cached_result is not None}")
    
    if not cached_result:
        return HttpResponse("No analysis data found. Please run the analysis first.", status=404)
    
    # Add a timestamp to the context
    cached_result['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Add utility functions for the template
    cached_result['len'] = len
    
    # Process some data for better display in the PDF
    
    # Add performance status helper
    def get_performance_status(metric, value):
        if metric in ['First Contentful Paint', 'Largest Contentful Paint']:
            if float(value) < 1000:
                return "good"
            elif float(value) < 2500:
                return "warning"
            else:
                return "error"
        elif metric == 'Cumulative Layout Shift':
            if float(value) < 0.1:
                return "good"
            elif float(value) < 0.25:
                return "warning"
            else:
                return "error"
        else:
            return "neutral"
    
    cached_result['get_performance_status'] = get_performance_status
    
    # Get the template
    template = get_template('report_pdf.html')
    
    # Render the template
    html = template.render(cached_result)
    
    # Create a PDF file
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    # Return the PDF as response
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        response['Content-Disposition'] = f'attachment; filename="{domain}_analysis_report.pdf"'
        return response
    
    return HttpResponse("Error creating PDF", status=500)