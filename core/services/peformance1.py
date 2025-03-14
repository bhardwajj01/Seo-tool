from playwright.async_api import async_playwright
import requests
import json

async def analyze_website_performance(url):
    async def calculate_scores(metrics, correction_factors, origin_country):
        universal_values = {
            "TTFB": {"worst": 300, "best": 100},
            "Redirect Time": {"worst": 100, "best": 0},
            "Connect Time": {"worst": 200, "best": 100},
            "Backend Time": {"worst": 400, "best": 200},
            "First Contentful Paint": {"worst": 2500, "best": 1000},
            "Largest Contentful Paint": {"worst": 3000, "best": 1200},
            "Cumulative Layout Shift": {"worst": 0.25, "best": 0},
            "Onload Time": {"worst": 2500, "best": 1000},
            "Fully Loaded Time": {"worst": 2500, "best": 1000},
            "TBT (Total Blocking Time)": {"worst": 600, "best": 100},
            "TTI (Time to Interactive)": {"worst": 5000, "best": 2000},
            "SI (Speed Index)": {"worst": 6000, "best": 2000}
        }

        weights = {
            "TTFB": 0.05,  # Reduced; TTFB is important but already excellent.
            "Redirect Time": 0.02,  # Minimal impact; reduced.
            "Connect Time": 0.03,  # Slight reduction; usually fast in most cases.
            "Backend Time": 0.05,  # Backend optimization matters, but not as much as LCP or TBT.
            "First Contentful Paint": 0.10,  # Important, but not as critical as LCP/TBT.
            "Largest Contentful Paint": 0.25,  # Significantly impactful on UX, so increased.
            "Cumulative Layout Shift": 0.05,  # Reduced since it already scores well.
            "Onload Time": 0.02,  # Minimal impact on real user experience.
            "Fully Loaded Time": 0.02,  # Same as Onload Time; reduced.
            "TBT (Total Blocking Time)": 0.30,  # Major contributor to user experience; increased.
            "TTI (Time to Interactive)": 0.10,  # Important but less critical than TBT.
            "SI (Speed Index)": 0.06  # Lowered slightly; complementary to LCP and FCP.
        }

        origin_factor = correction_factors[origin_country]

        # Calculate raw score
        raw_scores = {}
        for param, value in metrics.items():
            if param in universal_values:  # Only calculate scores for metrics with defined values
                worst = universal_values[param]["worst"]
                best = universal_values[param]["best"]

                # Handle missing or None values
                if value is None:
                    value = worst  # Assume the worst-case scenario for missing values

                normalized_score = max(0, min(1, (worst - value) / (worst - best)))
                raw_scores[param] = normalized_score * weights[param]

        raw_score = sum(raw_scores.values()) * 100

        # Adjust for target countries
        adjusted_scores = {
            country: min(raw_score * (origin_factor / factor), 100)  # Ensure score doesn't exceed 100
            for country, factor in correction_factors.items()
        }

        return raw_score, adjusted_scores

    def grade_performance(score):
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        elif score >= 50:
            return "E"
        else:
            return "F"

    def get_page_speed_metrics(api_key, url):
        api_url = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"

        params = {
            'url': url,
            'key': api_key,
            'strategy': 'desktop'
        }

        try:
            response = requests.get(api_url, params=params)
            response.raise_for_status()

            data = response.json()
            lighthouse_metrics = data.get('lighthouseResult', {}).get('audits', {})

            metrics = {
                'TBT (Total Blocking Time)': lighthouse_metrics.get('total-blocking-time', {}).get('numericValue', None),
                'TTI (Time to Interactive)': round(lighthouse_metrics.get('interactive', {}).get('numericValue', 0) / 1000, 2),
                'SI (Speed Index)': round(lighthouse_metrics.get('speed-index', {}).get('numericValue', 0) / 1000, 2),
                'First Contentful Paint': round(lighthouse_metrics.get('first-contentful-paint', {}).get('numericValue', 0) / 1000, 2)
            }

            return metrics

        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {e}"}

    correction_factors = {
        "USA": 0.9,
        "Canada": 0.95,
        "France": 0.92,
        "Turkey": 1.1,
        "Brazil": 1.15,
        "Japan": 0.93
    }
    origin_country = "Turkey"

    api_key = ""  # Replace with your actual API key

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to the URL
        # Navigate to the URL with increased timeout
        await page.goto(url, timeout=60000)  # 60 seconds instead of default 30

        # Inject JavaScript to capture advanced metrics
        metrics_script = """
        (function () {
            const metrics = {};

            // Capture basic performance timing
            metrics.timing = performance.timing.toJSON();

            // Capture paint events
            metrics.paint = performance.getEntriesByType('paint').reduce((acc, entry) => {
                acc[entry.name] = entry.startTime;
                return acc;
            }, {});

            // Use PerformanceObserver to capture LCP and CLS
            metrics.webVitals = { lcp: 0, cls: 0 };
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach((entry) => {
                    if (entry.entryType === 'largest-contentful-paint') {
                        metrics.webVitals.lcp = entry.startTime;
                    }
                    if (entry.entryType === 'layout-shift' && !entry.hadRecentInput) {
                        metrics.webVitals.cls += entry.value;
                    }
                });
            });
            observer.observe({ type: 'largest-contentful-paint', buffered: true });
            observer.observe({ type: 'layout-shift', buffered: true });

            // Wait for everything to settle
            return new Promise((resolve) => {
                setTimeout(() => {
                    resolve(metrics);
                }, 3000); // Wait for 3 seconds to ensure metrics are captured
            });
        })();
        """

        metrics = await page.evaluate(metrics_script)

        # Calculate derived metrics
        timing = metrics['timing']
        ttfb = timing['responseStart'] - timing['requestStart']
        redirect_time = timing['redirectEnd'] - timing['redirectStart']
        connect_time = timing['connectEnd'] - timing['connectStart']
        backend_time = timing['responseStart'] - timing['connectEnd']

        # Extract paint metrics
        first_contentful_paint = metrics['paint'].get('first-contentful-paint', None)
        largest_contentful_paint = metrics['webVitals']['lcp']
        cumulative_layout_shift = metrics['webVitals']['cls']

        # Calculate additional metrics
        onload_time = timing['loadEventEnd'] - timing['navigationStart']
        fully_loaded_time = timing['domComplete'] - timing['navigationStart']

        playwright_metrics = {
            # Core performance metrics
            'TTFB': ttfb,
            'Redirect Time': redirect_time,
            'Connect Time': connect_time,
            'Backend Time': backend_time,
            'First Contentful Paint': first_contentful_paint,
            'Largest Contentful Paint': largest_contentful_paint,
            'Cumulative Layout Shift': cumulative_layout_shift,
            'Onload Time': onload_time,
            'Fully Loaded Time': fully_loaded_time,
            
            # Detailed timing metrics
            'Request Start Time': timing['requestStart'],
            'Response Start Time': timing['responseStart'],
            'Response End Time': timing['responseEnd'],
            'DOM Loading Time': timing['domLoading'],
            'DOM Interactive Time': timing['domInteractive'],
            'Navigation Start Time': timing['navigationStart'],
            'DOM Complete Time': timing['domComplete'],
            'Load Event End Time': timing['loadEventEnd'],
            
            # Raw paint events and Web Vitals data
            'Paint Events Data': metrics['paint'],
            'Web Vitals Data': metrics['webVitals'],
            
            # Additional timing information
            'Complete Timing Data': timing
        }

        await browser.close()

    # Fetch PageSpeed Insights metrics
    psi_metrics = get_page_speed_metrics(api_key, url)

    # Merge the metrics
    metrics_combined = {**playwright_metrics, **psi_metrics}

    # Calculate scores
    raw_score, adjusted_scores = await calculate_scores(metrics_combined, correction_factors, origin_country)

    # Format output
    output = {
        "Performance Metrics": metrics_combined,
        "Raw Performance Score": raw_score,
        "Adjusted Scores": {
            country: {
                "Score": score,
                "Grade": grade_performance(score)
            } for country, score in adjusted_scores.items()
        }
    }

    return output


import asyncio

async def main():
    url = "https://seoone.com"  # Replace with the actual URL to test
    result = await analyze_website_performance(url)
    
    # Print formatted result
    print(json.dumps(result, indent=4))

# Run the test
if __name__ == "__main__":
    asyncio.run(main())
