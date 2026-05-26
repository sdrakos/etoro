import asyncio
import os
import json
import sys
from urllib.parse import urlparse
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from dotenv import load_dotenv

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

load_dotenv()

model_llm = "gpt-4.1-mini"

# We extract "Fragments" from each page and assemble them later
class KnowledgeBaseFragment(BaseModel):
    is_relevant: bool = Field(..., description="True if this page contains business info like About, Services, Contact, FAQ.")
    category: str = Field(..., description="Best fit category: 'Company Overview', 'Products/Services/Amenities', 'Contact', 'Policies/FAQ', 'Other'")
    summary: str = Field(..., description="Comprehensive summary of the relevant information found on this specific page.")

async def consolidate_section(client: AsyncOpenAI, section_name: str, fragments: List[str]) -> str:
    """
    Uses LLM to merge multiple text fragments into a single cohesive section, removing duplicates.
    """
    if not fragments:
        return "N/A"
    
    content_blob = "\n\n".join(fragments)
    
    prompt = f"""
    You are editing a comprehensive Knowledge Base for a business.
    Compile a DETAILED and EXTENSIVE report for the section '{ section_name }' based on the snippets below.
    
    CRITICAL INSTRUCTIONS:
    - Do NOT summarize or condense information. 
    - Retain ALL specific details, descriptions, specifications, amenities, and policies.
    - If there are lists (like room amenities or menu items), keep them complete.
    - Merge duplicate info, but keep the most detailed version.
    - Use bullet points and subheaders to organize the detailed content.
    - The goal is to have a complete reference, not a brief summary.
    
    Input Fragments:
    {content_blob[:25000]}
    """
    
    try:
        response = await client.chat.completions.create(
            model=model_llm,
            messages=[
                {"role": "system", "content": "You are a detailed technical writer."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Warning: Error consolidating section {section_name}: {e}")
        return "\n".join(fragments)

async def create_knowledge_base(urls: List[str], output_dir: str = "."):
    openai_key = os.getenv("OPENAI_API_KEY")
    if not AsyncOpenAI:
        print("Error: 'openai' library not installed. Please install it to use deduplication.")
        return

    client = AsyncOpenAI(api_key=openai_key)

    # Deep Crawl Strategy
    deep_strategy = BFSDeepCrawlStrategy(
        max_depth=1,
        max_pages=25, 
        include_external=False
    )

    # LLM Config
    llm_config = LLMConfig(provider="openai/gpt-4.1-mini", api_token=openai_key)

    # Extraction Strategy applied to EACH page
    llm_strategy = LLMExtractionStrategy(
        llm_config=llm_config,
        schema=KnowledgeBaseFragment.model_json_schema(),
        instruction="""
        Analyze this page content for a Business Knowledge Base.
        Extract FULL COMPREHENSIVE DETAILS. 
        - For Products/Rooms: Copy descriptions, sizes, views, and ALL amenities.
        - For Services: Describe exactly what is offered.
        - For Policies: Keep exact wording if possible.
        - Do NOT simply say "various amenities". List them.
        """
    )

    crawl_config = CrawlerRunConfig(
        deep_crawl_strategy=deep_strategy,
        extraction_strategy=llm_strategy,
        verbose=True
    )

    processed_domains = set()

    async with AsyncWebCrawler() as crawler:
        for url in urls:
            domain = urlparse(url).netloc.replace("www.", "")
            if domain in processed_domains:
                print(f"Skipping {url} (Domain {domain} already processed)")
                continue
            
            processed_domains.add(domain)
            print(f"\n--- Processing Business Root: {url} ---")
            
            kb_sections = {
                "Company Overview": [],
                "Products/Services/Amenities": [],
                "Contact": [],
                "Policies/FAQ": [],
                "Other": []
            }

            try:
                results = await crawler.arun(url=url, config=crawl_config)
                
                print(f"Crawled {len(results)} pages. Aggregating fragments...")

                for res in results:
                    if not res.success:
                        print(f"  [Skipping] Failed crawl: {res.url}")
                        continue
                    
                    if not res.extracted_content:
                        print(f"  [Skipping] No content extracted: {res.url}")
                        continue

                    try:
                        data = json.loads(res.extracted_content)
                        if isinstance(data, list):
                             items = data
                        else:
                             items = [data]
                        
                        count_relevant = 0
                        for item in items:
                            if item.get("is_relevant"):
                                count_relevant += 1
                                cat = item.get("category", "Other")
                                text = item.get("summary", "")
                                if cat in kb_sections:
                                    kb_sections[cat].append(f"Source ({res.url}): {text}")
                                else:
                                    kb_sections["Other"].append(f"Source ({res.url}): {text}")
                        print(f"  -> Found {count_relevant} relevant items.")
                                    
                    except json.JSONDecodeError:
                        print(f"  [Error] JSON Parse Failed for {res.url}")
            
                print("Consolidating sections with LLM (Removing duplicates)...")
                md_output = f"# Knowledge Base: {domain}\n\n"
                
                for section, fragments in kb_sections.items():
                    if fragments:
                        print(f"  - Refining '{section}' ({len(fragments)} fragments)...")
                        consolidated_text = await consolidate_section(client, section, fragments)
                        md_output += f"## {section}\n{consolidated_text}\n\n"
                
                md_output += f"---\n*Generated by Crawl4AI Knowledge Base Extractor from {len(results)} pages.*"

                fname = os.path.join(output_dir, f"{domain}_kb.md")
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(md_output)
                print(f"KB Saved: {fname}")

            except Exception as e:
                print(f"Error processing {url}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_urls = sys.argv[1:]
    else:
        target_urls = [
             "https://www.nisosrestaurant.gr/",
        ]
    
    asyncio.run(create_knowledge_base(target_urls))