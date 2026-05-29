from typing import Literal, Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
import json

import os
from run_utils import _load_openswarm_dotenv


class ProductSearch(BaseTool):
    """
    Searches for products on Google Shopping.
    
    Returns product listings with prices, ratings, sellers, and availability.
    Useful for price comparisons, finding deals, and product research.
    
    RATE LIMIT: This tool can only be called ONCE per each user request (message) to save API costs.
    Make sure to request enough results in a single call.
    """

    query: str = Field(
        ...,
        description="Search query for products (e.g., 'iPhone 15 Pro', 'running shoes', 'wireless headphones')"
    )
    
    location: Optional[str] = Field(
        default=None,
        description="Location for the search (e.g., 'United States', 'New York', 'London'). Affects pricing and availability."
    )
    
    country: Optional[str] = Field(
        default="us",
        description="Country code (e.g., 'us', 'gb', 'de', 'fr', 'jp')"
    )
    
    language: Optional[str] = Field(
        default="en",
        description="Interface language (e.g., 'en', 'es', 'fr', 'de')"
    )
    
    sort_by: Optional[Literal["relevance", "review_score", "price_low_to_high", "price_high_to_low"]] = Field(
        default="relevance",
        description="Sort results by: 'relevance', 'review_score', 'price_low_to_high', or 'price_high_to_low'"
    )
    
    price_min: Optional[float] = Field(
        default=None,
        description="Minimum price filter"
    )
    
    price_max: Optional[float] = Field(
        default=None,
        description="Maximum price filter"
    )
    
    condition: Optional[Literal["new", "used"]] = Field(
        default=None,
        description="Filter by product condition: 'new' or 'used'"
    )
    
    num_results: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Number of results to return (1-60)"
    )
    
    page: int = Field(
        default=1,
        ge=1,
        description="Page number for pagination"
    )
    
    def run(self):
        _load_openswarm_dotenv(override=True)
        try:
            import requests
            
            # Rate limiting: Check if already called in this session
            if self.context and self.context.get("product_search_called", False):
                return "Error: ProductSearch can only be called once per user request to save API costs. Use the results from the previous search or web search tool."
            
            api_key = os.getenv("SEARCH_API_KEY")
            if not api_key:
                raise ValueError("SEARCH_API_KEY is not set. Add it to your .env to use ProductSearch.")
            
            # Build request parameters
            params = {
                "engine": "google_shopping",
                "api_key": api_key,
                "q": self.query,
                "num": self.num_results,
                "page": self.page
            }
            
            # Add optional parameters
            if self.location:
                params["location"] = self.location
            
            if self.country:
                params["gl"] = self.country
            
            if self.language:
                params["hl"] = self.language
            
            if self.sort_by and self.sort_by != "relevance":
                params["sort_by"] = self.sort_by
            
            if self.price_min is not None:
                params["price_min"] = str(self.price_min)
            
            if self.price_max is not None:
                params["price_max"] = str(self.price_max)
            
            if self.condition:
                params["condition"] = self.condition
            
            # Make API request
            response = requests.get(
                "https://www.searchapi.io/api/v1/search",
                params=params,
                timeout=30
            )
            
            if response.status_code != 200:
                return f"Error: API returned status {response.status_code}: {response.text}"
            
            data = response.json()
            
            # Check for API errors
            if "error" in data:
                return f"Error from API: {data['error']}"
            
            # Extract and format results
            shopping_results = data.get("shopping_results", [])
            shopping_ads = data.get("shopping_ads", [])
            
            # Combine results (ads first, then organic)
            all_products = []
            
            # Process shopping ads
            for ad in shopping_ads[:5]:  # Limit ads to 5
                all_products.append({
                    "type": "sponsored",
                    "title": ad.get("title"),
                    "price": ad.get("price"),
                    "extracted_price": ad.get("extracted_price"),
                    "original_price": ad.get("original_price"),
                    "seller": ad.get("seller"),
                    "rating": ad.get("rating"),
                    "reviews": ad.get("reviews"),
                    "condition": ad.get("condition"),
                    "delivery": ad.get("delivery"),
                    "link": ad.get("link"),
                    "image": ad.get("image")
                })
            
            # Process organic shopping results
            for result in shopping_results:
                all_products.append({
                    "type": "organic",
                    "title": result.get("title"),
                    "price": result.get("price"),
                    "extracted_price": result.get("extracted_price"),
                    "original_price": result.get("original_price"),
                    "seller": result.get("seller"),
                    "rating": result.get("rating"),
                    "reviews": result.get("reviews"),
                    "condition": result.get("condition"),
                    "delivery": result.get("delivery"),
                    "offers": result.get("offers"),
                    "product_id": result.get("product_id") or result.get("prds"),
                    "product_link": result.get("product_link"),
                    "thumbnail": result.get("thumbnail")
                })
            
            # Mark as called in shared state (rate limiting)
            if self.context:
                self.context.set("product_search_called", True)

            return json.dumps({
                "query": self.query,
                "location": self.location,
                "sort_by": self.sort_by,
                "filters": {
                    "price_min": self.price_min,
                    "price_max": self.price_max,
                    "condition": self.condition
                },
                "total_results": len(all_products),
                "page": self.page,
                "products": all_products
            }, indent=2)
            
        except Exception as e:
            return f"Error searching products: {str(e)}"



if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    
    print("=" * 60)
    print("ProductSearch Test Suite")
    print("=" * 60)
    print()
    
    # Test 1: Basic search
    print("Test 1: Basic product search")
    print("-" * 60)
    tool = ProductSearch(
        query="wireless headphones",
        num_results=5
    )
    result = tool.run()
    
    try:
        data = json.loads(result)
        print(f"Query: {data['query']}")
        print(f"Total results: {data['total_results']}")
        if data['products']:
            print(f"First product: {data['products'][0]['title']}")
            print(f"  Price: {data['products'][0]['price']}")
            print(f"  Seller: {data['products'][0]['seller']}")
    except json.JSONDecodeError:
        print(result)
    print()
    
    # Test 2: Search with price filter
    print("Test 2: Search with price filter")
    print("-" * 60)
    tool = ProductSearch(
        query="running shoes",
        price_min=50,
        price_max=150,
        sort_by="price_low_to_high",
        num_results=3
    )
    result = tool.run()
    
    try:
        data = json.loads(result)
        print(f"Query: {data['query']}")
        print(f"Filters: {data['filters']}")
        print(f"Sort: {data['sort_by']}")
        print(f"Results: {data['total_results']}")
    except json.JSONDecodeError:
        print(result)
    print()
    
    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)
