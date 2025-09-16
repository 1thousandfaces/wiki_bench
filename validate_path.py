#!/usr/bin/env python3
"""
Standalone script to validate a WikiBench path manually
"""

from wikibench import WikipediaNavigator
import sys


def validate_wikibench_path(start_page: str, path: list) -> dict:
    """Validate a WikiBench path and return detailed results"""
    navigator = WikipediaNavigator()
    
    # Construct full path including start page
    full_path = [start_page] + path
    
    print(f"Validating path: {' → '.join(full_path)}")
    print("=" * 60)
    
    validation_results = {
        "valid": True,
        "errors": [],
        "step_details": []
    }
    
    for i in range(len(full_path) - 1):
        current_page = full_path[i]
        next_page = full_path[i + 1]
        
        print(f"\nStep {i + 1}: {current_page} → {next_page}")
        
        try:
            # Get current page URL
            current_url = f"https://en.wikipedia.org/wiki/{current_page.replace(' ', '_')}"
            print(f"  Checking links on: {current_url}")
            
            # Get all links from current page
            links = navigator.get_page_links(current_url)
            link_titles = [title for title, _ in links]
            
            # Check if next page is in the links
            found = False
            for title in link_titles:
                if title.lower() == next_page.lower():
                    found = True
                    break
            
            if found:
                print(f"  ✓ Found '{next_page}' in links")
                validation_results["step_details"].append({
                    "from": current_page,
                    "to": next_page,
                    "valid": True
                })
            else:
                print(f"  ✗ '{next_page}' NOT found in links")
                print(f"    Available links (first 10): {link_titles[:10]}")
                validation_results["valid"] = False
                validation_results["errors"].append(f"Step {i + 1}: Cannot navigate from '{current_page}' to '{next_page}'")
                validation_results["step_details"].append({
                    "from": current_page,
                    "to": next_page,
                    "valid": False,
                    "available_links": link_titles[:20]  # Store some available links
                })
                
        except Exception as e:
            print(f"  ✗ Error checking page: {e}")
            validation_results["valid"] = False
            validation_results["errors"].append(f"Step {i + 1}: Error accessing page '{current_page}': {e}")
            validation_results["step_details"].append({
                "from": current_page,
                "to": next_page,
                "valid": False,
                "error": str(e)
            })
    
    return validation_results


def main():
    if len(sys.argv) < 3:
        print("Usage: python validate_path.py <start_page> <page1> <page2> ... <pageN>")
        print("Example: python validate_path.py 'bradawl' 'Woodworking' 'United States' 'Hollywood' 'Kevin Bacon'")
        sys.exit(1)
    
    start_page = sys.argv[1]
    path = sys.argv[2:]
    
    # Validate the path
    results = validate_wikibench_path(start_page, path)
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    if results["valid"]:
        print("✅ Path is VALID!")
        print(f"Successfully validated all {len(path)} steps")
        
        # Calculate WikiBench score
        score = len(path)  # Base score is path length
        print(f"WikiBench score: {score} (lower is better)")
        
    else:
        print("❌ Path is INVALID!")
        print(f"Found {len(results['errors'])} error(s):")
        for error in results["errors"]:
            print(f"  - {error}")
        
        # Suggest fixes for failed steps
        print("\nSuggestions for fixing invalid steps:")
        for i, step in enumerate(results["step_details"]):
            if not step["valid"] and "available_links" in step:
                print(f"\nStep {i + 1} ({step['from']} → {step['to']}):")
                print("  Consider these available alternatives:")
                for link in step["available_links"][:5]:
                    print(f"    - {link}")


if __name__ == "__main__":
    main()