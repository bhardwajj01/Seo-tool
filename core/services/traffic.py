from playwright.sync_api import sync_playwright
import json
import time
import os

def get_semrush_traffic_metrics(domain_to_search):
    """
    Fetches traffic metrics for a specified domain from SEMrush.
    
    Args:
        domain_to_search (str): The domain to analyze (e.g., "wikipedia.org")
        
    Returns:
        dict: JSON object containing all traffic metrics or None if extraction failed
    """
    # Parse Netscape cookie format manually
    def parse_netscape_cookies(file_path):
        cookies = []
        with open(file_path, 'r') as file:
            lines = file.readlines()
            for line in lines:
                if line.strip().startswith('#') or not line.strip():
                    continue
                domain, flag, path, secure, expiration, name, value = line.strip().split('\t')
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': domain,
                    'path': path,
                    'expires': int(expiration),
                    'httpOnly': False,
                    'secure': secure.upper() == 'TRUE',
                    'sameSite': 'Lax'
                })
        return cookies

    def extract_traffic_metrics(page, domain):
        try:
            # Take a screenshot of the page for debugging
            page.screenshot(path="semrush_metrics_page.png")
            
            # Initialize our results object
            results = {
                "domain": domain,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "metrics": {}
            }
            
            # Get all metric cells directly with more precise selectors
            metric_cells = page.locator('div[data-test^="summary-cell"]').all()
            print(f"Found {len(metric_cells)} metric cells")
            
            # Process Visits (1st cell)
            try:
                visits_value = page.locator('div[data-test="summary-cell entrances"] [data-test="value"]').first
                if visits_value and visits_value.is_visible():
                    value = visits_value.text_content().strip()
                    print(f"Found visits value: {value}")
                    results["metrics"]["visits"] = value
                    
                    visits_change = page.locator('div[data-test="summary-cell entrances"] [data-test="diff"]').first
                    if visits_change and visits_change.is_visible():
                        change = visits_change.text_content().strip()
                        results["metrics"]["visits_change"] = change
            except Exception as e:
                print(f"Error extracting visits: {str(e)}")
            
            # Process Unique Visitors (2nd cell)
            try:
                visitors_value = page.locator('div[data-test="summary-cell visitors"] [data-test="value"]').first
                if visitors_value and visitors_value.is_visible():
                    # Handle the link text within this element
                    link = visitors_value.locator('a span').first
                    if link and link.is_visible():
                        value = link.text_content().strip()
                    else:
                        value = visitors_value.text_content().strip()
                        
                    print(f"Found unique visitors value: {value}")
                    results["metrics"]["unique_visitors"] = value
                    
                    visitors_change = page.locator('div[data-test="summary-cell visitors"] [data-test="diff"]').first
                    if visitors_change and visitors_change.is_visible():
                        change = visitors_change.text_content().strip()
                        results["metrics"]["unique_visitors_change"] = change
            except Exception as e:
                print(f"Error extracting unique visitors: {str(e)}")
                
            # Process Purchase Conversion (3rd cell)
            try:
                purchase_value = page.locator('div[data-test="summary-cell purchasePerVisit"] [data-test="value"]').first
                if purchase_value and purchase_value.is_visible():
                    value = purchase_value.text_content().strip()
                    print(f"Found purchase conversion value: {value}")
                    results["metrics"]["purchase_conversion"] = value
                    
                    purchase_change = page.locator('div[data-test="summary-cell purchasePerVisit"] [data-test="diff"]').first
                    if purchase_change and purchase_change.is_visible():
                        change = purchase_change.text_content().strip()
                        results["metrics"]["purchase_conversion_change"] = change
            except Exception as e:
                print(f"Error extracting purchase conversion: {str(e)}")
            
            # Process Pages Per Visit (4th cell)
            try:
                pages_value = page.locator('div[data-test="summary-cell pageViewsPerVisit"] [data-test="value"]').first
                if pages_value and pages_value.is_visible():
                    value = pages_value.text_content().strip()
                    print(f"Found pages per visit value: {value}")
                    results["metrics"]["pages_per_visit"] = value
                    
                    pages_change = page.locator('div[data-test="summary-cell pageViewsPerVisit"] [data-test="diff"]').first
                    if pages_change and pages_change.is_visible():
                        change = pages_change.text_content().strip()
                        results["metrics"]["pages_per_visit_change"] = change
            except Exception as e:
                print(f"Error extracting pages per visit: {str(e)}")
            
            # Process Avg Visit Duration (5th cell)
            try:
                duration_value = page.locator('div[data-test="summary-cell avgVisitDuration"] [data-test="value"]').first
                if duration_value and duration_value.is_visible():
                    value = duration_value.text_content().strip()
                    print(f"Found avg visit duration value: {value}")
                    results["metrics"]["avg_visit_duration"] = value
                    
                    duration_change = page.locator('div[data-test="summary-cell avgVisitDuration"] [data-test="diff"]').first
                    if duration_change and duration_change.is_visible():
                        change = duration_change.text_content().strip()
                        results["metrics"]["avg_visit_duration_change"] = change
            except Exception as e:
                print(f"Error extracting avg visit duration: {str(e)}")
            
            # Process Bounce Rate (6th cell)
            try:
                bounce_value = page.locator('div[data-test="summary-cell bouncesPerVisit"] [data-test="value"]').first
                if bounce_value and bounce_value.is_visible():
                    value = bounce_value.text_content().strip()
                    print(f"Found bounce rate value: {value}")
                    results["metrics"]["bounce_rate"] = value
                    
                    bounce_change = page.locator('div[data-test="summary-cell bouncesPerVisit"] [data-test="diff"]').first
                    if bounce_change and bounce_change.is_visible():
                        change = bounce_change.text_content().strip()
                        results["metrics"]["bounce_rate_change"] = change
            except Exception as e:
                print(f"Error extracting bounce rate: {str(e)}")
                    
            # Get device breakdown
            try:
                desktop_text = page.locator('svg[aria-label="Traffic Share for desktop"] >> xpath=following-sibling::div[1]').first
                mobile_text = page.locator('svg[aria-label="Traffic Share for mobile"] >> xpath=following-sibling::div[1]').first
                
                if desktop_text and desktop_text.is_visible():
                    desktop_share = desktop_text.text_content().strip()
                    print(f"Found desktop share: {desktop_share}")
                    results["metrics"]["desktop_share"] = desktop_share
                    
                if mobile_text and mobile_text.is_visible():
                    mobile_share = mobile_text.text_content().strip()
                    print(f"Found mobile share: {mobile_share}")
                    results["metrics"]["mobile_share"] = mobile_share
            except Exception as e:
                print(f"Error extracting device breakdown: {str(e)}")
                
            # Get market metrics
            try:
                market_share_text = page.locator('text=Market Share >> xpath=following-sibling::a[1]').first
                market_traffic_text = page.locator('text=Market Traffic >> xpath=following-sibling::a[1]').first
                
                if market_share_text and market_share_text.is_visible():
                    market_share = market_share_text.text_content().strip()
                    print(f"Found market share: {market_share}")
                    results["metrics"]["market_share"] = market_share
                    
                if market_traffic_text and market_traffic_text.is_visible():
                    market_traffic = market_traffic_text.text_content().strip()
                    print(f"Found market traffic: {market_traffic}")
                    results["metrics"]["market_traffic"] = market_traffic
            except Exception as e:
                print(f"Error extracting market metrics: {str(e)}")
            
            # Print summary of what we found
            print(f"Found {len(results['metrics'])} metrics in total")
            
            return results
            
        except Exception as e:
            print(f"Error extracting metrics: {str(e)}")
            page.screenshot(path="extraction_error.png")
            print("Error screenshot saved to extraction_error.png")
            return None

    try:
        with sync_playwright() as p:
            # Launch browser with visible UI
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            
            # Load cookies
            print(f"Loading cookies from smrush-cookie.txt...")
            cookies = parse_netscape_cookies(r"X:\Coding Junk\Git Adventure\Website Performance\django\analyzer\core\services\smrush-cookie.txt")
            context.add_cookies(cookies)
            
            # Create a new page and navigate to Semrush
            page = context.new_page()
            print("Navigating to Semrush...")
            page.goto("https://www.semrush.com")
            
            # Verify login
            try:
                page.wait_for_selector("text=Dashboard", timeout=10000)
                print("Login successful.")
            except:
                print("Login failed. Please check your cookies.")
                browser.close()
                return None
                
            # Navigate to Traffic Analytics
            print("Navigating to Traffic Analytics...")
            try:
                # Click on the Traffic Analytics link in the sidebar
                traffic_analytics_link = page.locator("data-test=seo_traffic_analytics").first
                traffic_analytics_link.click()
                page.wait_for_load_state("networkidle")
                
                # Wait for the competitor domain input field to be ready
                print("Preparing to enter domain...")
                page.wait_for_selector("data-testid=input-targets-input", timeout=10000)
                
                # Clear the input field if it has content
                search_input = page.locator("data-testid=input-targets-input").first
                current_value = search_input.input_value()
                if current_value:
                    # Clear using the clear button if visible
                    clear_button = page.locator("data-testid=competitors-clear").first
                    if clear_button.is_visible():
                        clear_button.click()
                        page.wait_for_timeout(1000)  # Wait for clear to complete
                    else:
                        search_input.fill("")
                
                # Enter the domain
                print(f"Entering domain: {domain_to_search}")
                search_input.fill(domain_to_search)
                
                # Click the Analyze button
                print("Clicking Analyze button...")
                analyze_button = page.locator("data-test=submit").first
                analyze_button.click()
                
                # Wait for results to load with significantly more time
                print("Waiting for results...")
                page.wait_for_load_state("networkidle")
                
                # Explicitly wait for the metrics to appear - first wait for the metrics container
                print("Waiting for metrics to load...")
                try:
                    # First wait for the metrics container to appear
                    page.wait_for_selector('div[data-test="Top Metrics Widget"]', timeout=30000)
                    
                    # Then wait for specific metrics to confirm everything is loaded
                    page.wait_for_selector('div[data-test="summary-cell entrances"] [data-test="value"]', timeout=30000)
                    print("Metrics container found, waiting for data to populate...")
                    
                    # Additional timeout to ensure animations complete and all data is populated
                    page.wait_for_timeout(10000)
                except Exception as e:
                    print(f"Warning: Timed out waiting for metrics: {str(e)}")
                    # Take screenshot to see what's on the page
                    page.screenshot(path="semrush_metrics_timeout.png")
                    print("Screenshot saved to semrush_metrics_timeout.png")
                
                # Extract traffic metrics
                print("Extracting traffic metrics...")
                results = extract_traffic_metrics(page, domain_to_search)
                
                if results:
                    # Output the results as JSON to terminal for debugging
                    print("\nTraffic Metrics:")
                    print(json.dumps(results, indent=2))
                    
                    # Close the browser before returning
                    browser.close()
                    return results
                else:
                    print("Failed to extract metrics.")
                    browser.close()
                    return None
                
            except Exception as e:
                print(f"Error during navigation or extraction: {str(e)}")
                # Take a screenshot to help debug
                page.screenshot(path="semrush_error.png")
                print("Error screenshot saved to semrush_error.png")
                browser.close()
                return None
    
    except Exception as e:
        print(f"Script error: {str(e)}")
        return None
    
    
