from typing import Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
import json

import os
from run_utils import _load_openswarm_dotenv


class ScholarSearch(BaseTool):
    """
    Searches for scholarly literature on Google Scholar.
    
    Returns academic papers, articles, theses, books, and conference papers.
    Includes links to PDFs and full-text resources when available.
    
    RATE LIMIT: This tool can only be called ONCE per each user request (message) to save API costs.
    Make sure to request enough results in a single call.
    """

    query: str = Field(
        ...,
        description="Search query for scholarly articles (e.g., 'machine learning', 'climate change effects', 'quantum computing')"
    )
    
    year_from: Optional[int] = Field(
        default=None,
        description="Filter results from this year onwards (e.g., 2020)"
    )
    
    year_to: Optional[int] = Field(
        default=None,
        description="Filter results up to this year (e.g., 2024)"
    )
    
    num_results: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Number of results to return (1-20)"
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
            if self.context and self.context.get("scholar_search_called", False):
                return "Error: ScholarSearch can only be called once per user request to save API costs. Use the results from the previous search or web search tool."
            
            api_key = os.getenv("SEARCH_API_KEY")
            if not api_key:
                raise ValueError("SEARCH_API_KEY is not set. Add it to your .env to use ScholarSearch.")
            
            # Build request parameters
            params = {
                "engine": "google_scholar",
                "api_key": api_key,
                "q": self.query,
                "num": self.num_results,
                "page": self.page
            }
            
            # Add year filters
            if self.year_from:
                params["as_ylo"] = self.year_from
            
            if self.year_to:
                params["as_yhi"] = self.year_to
            
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
            
            # Extract results
            organic_results = data.get("organic_results", [])
            profiles = data.get("profiles", [])
            search_info = data.get("search_information", {})
            
            # Format articles
            articles = []
            for result in organic_results:
                # Extract authors
                authors = []
                for author in result.get("authors", []):
                    authors.append(author.get("name", "Unknown"))
                
                # Extract citation info
                inline_links = result.get("inline_links", {})
                cited_by = inline_links.get("cited_by", {})
                versions = inline_links.get("versions", {})
                
                # Extract resource (PDF, etc.)
                resource = result.get("resource", {})
                
                article = {
                    "title": result.get("title"),
                    "link": result.get("link"),
                    "publication": result.get("publication"),
                    "snippet": result.get("snippet"),
                    "authors": authors,
                    "citations": cited_by.get("total"),
                    "cites_id": cited_by.get("cites_id"),
                    "versions_count": versions.get("total"),
                    "cluster_id": versions.get("cluster_id")
                }
                
                # Add resource link (PDF, etc.) - important for reading full papers
                if resource:
                    article["resource"] = {
                        "name": resource.get("name"),
                        "format": resource.get("format"),
                        "link": resource.get("link")
                    }
                
                # Add related links
                if inline_links.get("related_articles_link"):
                    article["related_articles_link"] = inline_links.get("related_articles_link")
                
                articles.append(article)
            
            # Format author profiles if any
            author_profiles = []
            for profile in profiles:
                author_profiles.append({
                    "name": profile.get("name"),
                    "affiliations": profile.get("affiliations"),
                    "email_domain": profile.get("email"),
                    "total_citations": profile.get("cited_by", {}).get("total"),
                    "profile_link": profile.get("link"),
                    "author_id": profile.get("author_id")
                })
            
            # Mark as called in shared state (rate limiting)
            if self.context:
                self.context.set("scholar_search_called", True)

            result = {
                "query": self.query,
                "filters": {
                    "year_from": self.year_from,
                    "year_to": self.year_to
                },
                "total_results": search_info.get("total_results"),
                "page": self.page,
                "articles_count": len(articles),
                "articles": articles
            }
            
            if author_profiles:
                result["author_profiles"] = author_profiles
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error searching scholar: {str(e)}"



if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    
    print("=" * 60)
    print("ScholarSearch Test Suite")
    print("=" * 60)
    print()
    
    # Test 1: Basic search
    print("Test 1: Basic scholarly search")
    print("-" * 60)
    tool = ScholarSearch(
        query="transformer architecture deep learning",
        num_results=5
    )
    result = tool.run()
    
    try:
        data = json.loads(result)
        print(f"Query: {data['query']}")
        print(f"Total results: {data.get('total_results', 'N/A')}")
        print(f"Articles returned: {data['articles_count']}")
        print()
        
        for i, article in enumerate(data['articles'][:3], 1):
            print(f"{i}. {article['title']}")
            print(f"   Authors: {', '.join(article['authors'][:3])}...")
            print(f"   Citations: {article.get('citations', 'N/A')}")
            if article.get('resource'):
                print(f"   PDF: {article['resource'].get('link', 'N/A')}")
            print()
    except json.JSONDecodeError:
        print(result)
    
    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)
