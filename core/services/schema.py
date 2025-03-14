import json
from playwright.async_api import async_playwright
import asyncio

async def check_schema(url):
    """Check a website for schema markup, validate JSON-LD schemas, and return a readable summary."""
    async with async_playwright() as p:
        def validate_json_ld_schema(schema):
            """Validate JSON-LD schema structure based on its @type."""
            errors = []
            schema_type = schema.get("@type", "Unknown")

            if schema_type == "Organization":
                # Check for required fields
                if "name" not in schema:
                    errors.append("Missing required field: 'name'")
                if "url" in schema and not isinstance(schema["url"], str):
                    errors.append("'url' should be a string")

            elif schema_type == "WebSite":
                # Check for required fields
                if "name" not in schema:
                    errors.append("Missing required field: 'name'")
                if "potentialAction" not in schema:
                    errors.append("Missing required field: 'potentialAction'")

            elif schema_type == "WebPage":
                # Check for required fields
                if "name" not in schema:
                    errors.append("Missing required field: 'name'")

            # Add more schema types as needed
            return errors

        # Launch the browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to the URL
            await page.goto(url, timeout=60000)
        except Exception as e:
            await browser.close()
            return {
                "url": url,
                "status": "Failed",
                "message": f"Could not load the page: {str(e)}"
            }

        # Extract JSON-LD schemas
        json_ld_schemas = await page.evaluate("""
            () => Array.from(
                document.querySelectorAll('script[type="application/ld+json"]'),
                el => el.innerText
            )
        """)

        # Extract Microdata or RDFa schemas
        microdata_schemas = await page.evaluate("""
            () => Array.from(
                document.querySelectorAll('[itemscope][itemtype]'),
                el => el.outerHTML
            )
        """)

        # Prepare the results
        schema_count = len(json_ld_schemas) + len(microdata_schemas)
        summary = {
            "url": url,
            "status": "Success",
            "total_schemas_found": schema_count,
            "json_ld_schemas_count": len(json_ld_schemas),
            "microdata_schemas_count": len(microdata_schemas),
            "json_ld_schemas": [],
            "microdata_schemas": [],
            "errors": []
        }

        # Process JSON-LD schemas
        for schema in json_ld_schemas:
            try:
                parsed_schema = json.loads(schema)

                # Ensure parsed_schema is always a dictionary or handle a list
                if isinstance(parsed_schema, list):
                    for schema_item in parsed_schema:
                        schema_type = schema_item.get("@type", "Unknown")
                        validation_errors = validate_json_ld_schema(schema_item)
                        if validation_errors:
                            summary["errors"].append({schema_type: validation_errors})
                        summary["json_ld_schemas"].append({"type": schema_type, "details": schema_item})
                else:
                    schema_type = parsed_schema.get("@type", "Unknown")
                    validation_errors = validate_json_ld_schema(parsed_schema)
                    if validation_errors:
                        summary["errors"].append({schema_type: validation_errors})
                    summary["json_ld_schemas"].append({"type": schema_type, "details": parsed_schema})

            except json.JSONDecodeError as e:
                summary["errors"].append(f"Invalid JSON-LD schema: {str(e)}")

        # Add Microdata or RDFa schemas
        for schema in microdata_schemas:
            summary["microdata_schemas"].append(schema)

        # Close the browser
        await browser.close()

        # Generate a readable report
        readable_report = {
            "Website URL": summary["url"],
            "Status": summary["status"],
            "Total Schemas Found": summary["total_schemas_found"],
            "JSON-LD Schemas Found": summary["json_ld_schemas_count"],
            "Microdata/RDFa Schemas Found": summary["microdata_schemas_count"],
            "Errors": summary["errors"]
        }

        readable_report["JSON-LD Schema Details"] = [
            {
                "Type": schema["type"],
                "Details": schema["details"]
            } for schema in summary["json_ld_schemas"]
        ]

        readable_report["Microdata/RDFa Schema Details"] = summary["microdata_schemas"]

        return readable_report
