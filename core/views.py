from django.shortcuts import render
from django.core.cache import cache
from .services.traffic import get_semrush_traffic_metrics
from .services.peformance1 import analyze_website_performance
from .services.ssl import analyze_ssl_security
from .services.indexing_and_crawlability import indexing_and_crawlability
from .services.schema import check_schema
from .services.audit import site_audit
from openai import OpenAI

import asyncio
import json
from collections import OrderedDict


def home(request):
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
        # Store URL in session for refresh handling
        request.session['analysis_url'] = url
        return perform_analysis(request, url)
    else:
        # Handle browser refresh - get URL from session
        url = request.session.get('analysis_url')
        if url:
            return perform_analysis(request, url)
        return render(request, "index.html")

def perform_analysis(request, url):
    """Helper function to perform the actual analysis"""
    # Clear existing cache to force fresh analysis
    cache_key = f'website_analysis_{url}'
    cache.delete(cache_key)
    
    try:
        # Run all analyses concurrently
        async def run_analysis():
            performance_task = analyze_website_performance(url)
            ssl_task = analyze_ssl_security(url)
            indexing_task = indexing_and_crawlability(url)
            audit_task = site_audit(url) 
            schema_task = check_schema(url)
            traffic_task = asyncio.to_thread(get_semrush_traffic_metrics, url)
            
            results = await asyncio.gather(
                performance_task, ssl_task, indexing_task, 
                audit_task, schema_task, traffic_task
            )
            
            return results
        
        # Execute analysis
        results = asyncio.run(run_analysis())
        
        # Process results and create context
        context = {
            "url": url,
            "performance_metrics": results[0],
            "ssl_security": results[1],
            "indexing_data": results[2],
            "site_audit": results[3],
            "schema_data": results[4],
            "traffic_metrics": results[5]
        }
        
        # Add AI analysis
        ai_analysis_result = get_ai_analysis(context)
        context["ai_analysis"] = ai_analysis_result
        
        # Cache the new results
        cache.set(cache_key, context, 3600)
        
        return render(request, "results.html", context)
        
    except Exception as e:
        error_context = {
            "error": str(e),
            "url": url
        }
        return render(request, "index.html", error_context)


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