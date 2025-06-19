import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import time
import json

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# API keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERP_API_KEY = os.environ.get("SERP_API_KEY")  # Optional: for Google search API
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY")  # Optional: for Brave search API

def simple_request(url):
    """Simple, reliable request function"""
    print(f"🌐 Fetching: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        print(f"📡 Status: {response.status_code}")
        return response
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def search_with_serp_api(company_name):
    """Use SerpAPI to search for competitor intelligence"""
    if not SERP_API_KEY:
        return None
        
    try:
        search_queries = [
            f"{company_name} accounts payable AP automation features",
            f"{company_name} bill pay vendor payments platform",
            f"{company_name} funding valuation company overview"
        ]
        
        all_results = []
        
        for query in search_queries:
            url = "https://serpapi.com/search"
            params = {
                'api_key': SERP_API_KEY,
                'q': query,
                'engine': 'google',
                'num': 5
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                organic_results = data.get('organic_results', [])
                
                for result in organic_results:
                    title = result.get('title', '')
                    snippet = result.get('snippet', '')
                    link = result.get('link', '')
                    all_results.append(f"• {title}: {snippet} ({link})")
            
            time.sleep(1)  # Rate limiting
        
        if all_results:
            return "\n".join(all_results[:10])  # Top 10 results
            
    except Exception as e:
        print(f"❌ SerpAPI search failed: {e}")
        return None

def search_with_brave_api(company_name):
    """Use Brave Search API for competitor intelligence"""
    if not BRAVE_API_KEY:
        return None
        
    try:
        search_queries = [
            f"{company_name} AP automation bill pay features",
            f"{company_name} company funding business model"
        ]
        
        all_results = []
        
        for query in search_queries:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                'Accept': 'application/json',
                'X-Subscription-Token': BRAVE_API_KEY
            }
            params = {
                'q': query,
                'count': 5
            }
            
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                web_results = data.get('web', {}).get('results', [])
                
                for result in web_results:
                    title = result.get('title', '')
                    description = result.get('description', '')
                    url = result.get('url', '')
                    all_results.append(f"• {title}: {description}")
            
            time.sleep(1)  # Rate limiting
        
        if all_results:
            return "\n".join(all_results[:8])
            
    except Exception as e:
        print(f"❌ Brave API search failed: {e}")
        return None

def gather_competitor_intelligence(company_name, failed_url):
    """Gather competitive intelligence when direct scraping fails"""
    print(f"🕵️ Gathering intelligence on {company_name} using alternative methods...")
    
    intelligence = []
    
    # Method 1: Try search APIs
    serp_results = search_with_serp_api(company_name)
    if serp_results:
        intelligence.append(f"SEARCH INTELLIGENCE:\n{serp_results}")
    
    brave_results = search_with_brave_api(company_name)
    if brave_results:
        intelligence.append(f"BRAVE SEARCH RESULTS:\n{brave_results}")
    
    # Method 2: Try common alternative pages
    alternative_pages = [
        f"https://{company_name.lower()}.com/about",
        f"https://{company_name.lower()}.com/features", 
        f"https://{company_name.lower()}.com/pricing",
        f"https://www.{company_name.lower()}.com",
        f"https://{company_name.lower()}.io"
    ]
    
    for alt_url in alternative_pages:
        if alt_url != failed_url:  # Don't retry the same URL
            response = simple_request(alt_url)
            if response and response.status_code == 200:
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    content = soup.get_text()[:1500]
                    if len(content.strip()) > 200:
                        intelligence.append(f"FROM {alt_url}:\n{content}")
                        break  # Found good content, stop searching
                except:
                    continue
    
    # Method 3: Try to find LinkedIn company page
    linkedin_search_url = f"https://www.linkedin.com/company/{company_name.lower()}"
    response = simple_request(linkedin_search_url)
    if response and response.status_code == 200:
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Look for company description
            desc_elements = soup.find_all(['p', 'div'], class_=['break-words', 'description'])
            for elem in desc_elements:
                text = elem.get_text().strip()
                if len(text) > 100 and company_name.lower() in text.lower():
                    intelligence.append(f"LINKEDIN COMPANY INFO:\n{text[:800]}")
                    break
        except:
            pass
    
    if intelligence:
        return "\n\n".join(intelligence)
    else:
        return f"Could not gather detailed intelligence on {company_name}. Manual research recommended."

def extract_company_name_from_url(url):
    """Extract company name from URL"""
    try:
        domain = url.replace('https://', '').replace('http://', '').replace('www.', '')
        company_name = domain.split('.')[0]
        return company_name.capitalize()
    except:
        return "Unknown Company"

def extract_company_name_smart(title):
    """Extract company name from page title"""
    if not title or title == "No title":
        return "Unknown Company"
        
    if '|' in title:
        parts = [part.strip() for part in title.split('|')]
        company_name = parts[0] if len(parts[0].split()) <= 3 else parts[-1]
    elif '-' in title:
        parts = [part.strip() for part in title.split('-')]
        company_name = parts[0] if len(parts[0].split()) <= 3 else parts[-1]
    else:
        words = title.split()
        company_name = words[0] if words else title
        
    return company_name.strip()

def analyze_competitor_intelligent(url):
    """Intelligent competitor analysis with real-time intelligence gathering"""
    print(f"🔍 Analyzing: {url}")
    
    company_name = extract_company_name_from_url(url)
    
    # Try direct scraping first
    response = simple_request(url)
    
    if response and response.status_code == 200:
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find('title').text if soup.find('title') else "No title"
            content = soup.get_text()
            content = ' '.join(content.split())[:3000]
            
            if len(content.strip()) > 100:
                company_name = extract_company_name_smart(title)
                
                return {
                    'success': True,
                    'title': title,
                    'content': content,
                    'company_name': company_name,
                    'status': f"Successfully analyzed {url}",
                    'method': 'direct_scraping'
                }
        except Exception as e:
            print(f"❌ Error parsing content: {e}")
    
    # Direct scraping failed - use intelligent fallback
    print(f"🚫 Direct scraping failed for {company_name}, switching to intelligence gathering...")
    
    intelligence = gather_competitor_intelligence(company_name, url)
    
    if intelligence and "Could not gather" not in intelligence:
        return {
            'success': True,
            'title': f"{company_name} - Intelligence Gathered",
            'content': intelligence,
            'company_name': company_name,
            'status': f"Gathered intelligence for {company_name} using alternative methods",
            'method': 'intelligence_gathering'
        }
    else:
        # Final fallback
        return {
            'success': False,
            'title': f"{company_name} - Limited Access",
            'content': f"Could not analyze {url} directly and intelligence gathering was limited. {company_name} may be blocking automated access. Manual research recommended: check LinkedIn company page, Crunchbase profile, or Google '{company_name} AP automation features' for competitive intelligence.",
            'company_name': company_name,
            'status': f"Analysis blocked - manual research needed",
            'method': 'failed'
        }

def generate_analysis(url, analysis_result):
    """Generate competitive analysis using OpenAI"""
    
    monite_context = """
MONITE OVERVIEW:
Monite is an embedded AP/AR automation platform for B2B SaaS companies, marketplaces, and neobanks.

KEY CAPABILITIES:
- Accounts Payable: Bill capture, OCR, approval workflows, vendor payments (ACH/wire/international)
- Accounts Receivable: Invoice creation, payment collection, dunning, customer management  
- API-First: 200+ endpoints, React/JS/Python SDKs, webhooks
- Integrations: 40+ accounting platforms (QuickBooks, Xero, NetSuite, etc.)
- Embedded Finance: White-label UI, 2-week implementation
- Compliance: Peppol e-invoicing, multi-country tax support
"""
    
    success = analysis_result['success']
    title = analysis_result['title']
    content = analysis_result['content']
    company_name = analysis_result['company_name']
    status = analysis_result['status']
    method = analysis_result['method']
    
    data_quality_note = {
        'direct_scraping': '✅ FULL DATA: Complete website analysis',
        'intelligence_gathering': '🔍 GATHERED INTELLIGENCE: Using search APIs and alternative sources',
        'failed': '⚠️ LIMITED DATA: Analysis blocked, manual research needed'
    }.get(method, '❓ UNKNOWN DATA SOURCE')
    
    prompt = f"""
Analyze this potential competitor to Monite's AP/AR automation platform.

COMPETITOR: {company_name}
URL: {url}
DATA SOURCE: {data_quality_note}
ANALYSIS METHOD: {method}
STATUS: {status}

INTELLIGENCE GATHERED:
{content}

{monite_context}

ANALYSIS INSTRUCTIONS:
- If method is 'direct_scraping': Provide full analysis based on website content
- If method is 'intelligence_gathering': Analyze based on search results and alternative sources  
- If method is 'failed': Focus on what we can infer from domain/company name and recommend manual research
- Be aggressive in threat assessment when AP/AR keywords are detected in any content

Please provide analysis in this format:

*THREAT LEVEL:* 🔴 HIGH / 🟡 MEDIUM / 💚 LOW

*DATA SOURCE:* {data_quality_note}

*QUICK ASSESSMENT:*
[2-3 sentences on threat level and reasoning based on available intelligence]

*KEY FINDINGS:*
[What we learned about their capabilities from available sources]

*COMPETITIVE COMPARISON:*
**Their Potential Strengths:** [Based on gathered intelligence]
**Gaps/Unknowns:** [What we couldn't determine]  
**Monite Advantages:** [Clear differentiators based on available info]

*RECOMMENDED ACTIONS:*
- **For Product Team:** [Based on competitive intelligence gathered]
- **For Sales Team:** [Positioning based on available info]
- **For Research:** [Specific manual research steps needed]

THREAT ASSESSMENT GUIDELINES:
- HIGH: Clear AP/AR competitor with significant capabilities/funding
- MEDIUM: Business software with some AP/AR overlap or blocked analysis of likely competitor  
- LOW: Different market focus or connection issues suggest minimal threat
- Use intelligence gathered to make informed assessment, not just guess
"""
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"❌ AI analysis failed: {str(e)}\n\nManual analysis needed for {company_name} at {url}"

def analyze_competitor_url(url):
    """Main function to analyze competitor URL with intelligent fallbacks"""
    print(f"🚨 Starting intelligent RivalRadar analysis: {url}")
    
    try:
        # Analyze the website with intelligent fallbacks
        analysis_result = analyze_competitor_intelligent(url)
        
        # Generate AI analysis
        analysis = generate_analysis(url, analysis_result)
        
        print("✅ Analysis complete!")
        return analysis
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return f"❌ RivalRadar analysis failed: {str(e)}\n\nTry manual research for this competitor."

def extract_urls_from_text(text):
    """Extract URLs from message text"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)

@app.event("reaction_added")
def handle_reaction_added(event, say):
    """Handle when someone adds a reaction to trigger analysis"""
    
    if event["reaction"] == "satellite_antenna":
        try:
            result = app.client.conversations_history(
                channel=event["item"]["channel"],
                latest=event["item"]["ts"],
                limit=1,
                inclusive=True
            )
            
            if result["messages"]:
                message = result["messages"][0]
                message_text = message.get("text", "")
                urls = extract_urls_from_text(message_text)
                
                if urls:
                    app.client.reactions_add(
                        channel=event["item"]["channel"],
                        timestamp=event["item"]["ts"],
                        name="eyes"
                    )
                    
                    url = urls[0]
                    analysis = analyze_competitor_url(url)
                    
                    say(
                        text=f"🚨 *RivalRadar Analysis*\n\n{analysis}",
                        thread_ts=event["item"]["ts"],
                        channel=event["item"]["channel"]
                    )
                    
                    app.client.reactions_remove(
                        channel=event["item"]["channel"],
                        timestamp=event["item"]["ts"],
                        name="eyes"
                    )
                    app.client.reactions_add(
                        channel=event["item"]["channel"],
                        timestamp=event["item"]["ts"],
                        name="white_check_mark"
                    )
                else:
                    say(
                        text="📡 RivalRadar triggered but no URLs found!",
                        thread_ts=event["item"]["ts"],
                        channel=event["item"]["channel"]
                    )
                    
        except Exception as e:
            say(
                text=f"❌ RivalRadar error: {str(e)}",
                thread_ts=event["item"]["ts"],
                channel=event["item"]["channel"]
            )

@app.command("/analyze")
def analyze_command(ack, respond, command):
    ack()
    url = command['text'].strip()
    if url:
        analysis = analyze_competitor_url(url)
        respond(f"🚨 *RivalRadar Analysis*\n\n{analysis}")
    else:
        respond("Please provide a URL: `/analyze https://competitor.com`")

@app.command("/rivalradar")
def health_check(ack, respond):
    ack()
    available_apis = []
    if SERP_API_KEY:
        available_apis.append("SerpAPI")
    if BRAVE_API_KEY:
        available_apis.append("Brave Search")
    
    api_status = f"Search APIs: {', '.join(available_apis)}" if available_apis else "No search APIs configured"
    respond(f"🚨 RivalRadar is online!\n{api_status}\nReact with 📡 to any URL or use `/analyze <url>`")

if __name__ == "__main__":
    print("🚨 Starting Intelligent RivalRadar...")
    
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "OPENAI_API_KEY"]
    optional_vars = ["SERP_API_KEY", "BRAVE_API_KEY"]
    
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        exit(1)
    
    # Check optional APIs
    available_search_apis = [var for var in optional_vars if os.environ.get(var)]
    if available_search_apis:
        print(f"✅ Search APIs available: {', '.join(available_search_apis)}")
    else:
        print("⚠️ No search APIs configured - intelligence gathering will be limited")
        print("Consider adding SERP_API_KEY or BRAVE_API_KEY for enhanced analysis")
    
    try:
        handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        handler.start()
        print("✅ Intelligent RivalRadar ready!")
    except Exception as e:
        print(f"❌ Failed to start: {e}")
