import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Your OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def search_recent_news(company_name):
    """Search for recent news about the company"""
    print(f"📰 Searching for recent news about {company_name}...")
    
    try:
        search_query = f"{company_name} funding product launch news"
        search_url = f"https://www.google.com/search?q={search_query}&tbm=nws&tbs=qdr:m3"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        news_items = []
        news_divs = soup.find_all('div', class_='g') or soup.find_all('article')
        
        for item in news_divs[:3]:
            title_elem = item.find('h3') or item.find('a')
            snippet_elem = item.find('span', class_='st') or item.find('div', class_='s')
            
            if title_elem:
                title = title_elem.get_text()
                snippet = snippet_elem.get_text() if snippet_elem else ""
                news_items.append(f"• {title}: {snippet[:200]}...")
        
        return "\n".join(news_items) if news_items else "No recent news found"
        
    except Exception as e:
        print(f"❌ News search failed: {e}")
        return "Could not retrieve recent news"

def find_api_docs(base_url, soup):
    """Try to find API documentation links"""
    print("🔍 Searching for API documentation...")
    
    api_patterns = [
        '/api', '/docs', '/developers', '/documentation', '/dev', 
        '/api-docs', '/reference', '/api-reference', '/guides', '/integrate'
    ]
    
    links = soup.find_all('a', href=True)
    api_links = []
    
    for link in links:
        href = link['href']
        text = link.get_text().lower()
        
        if any(pattern in href.lower() for pattern in api_patterns) or \
           any(keyword in text for keyword in ['api', 'docs', 'developer', 'documentation', 'integrate']):
            
            if href.startswith('/'):
                full_url = base_url.rstrip('/') + href
            elif href.startswith('http'):
                full_url = href
            else:
                continue
                
            api_links.append(full_url)
    
    return api_links[:5]

def analyze_api_docs(api_url):
    """Analyze API documentation if found"""
    try:
        print(f"📚 Analyzing API docs: {api_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(api_url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        content = soup.get_text()[:4000]
        title = soup.find('title').text if soup.find('title') else "API Docs"
        
        return {
            'url': api_url,
            'title': title,
            'content': content
        }
    except Exception as e:
        print(f"❌ Failed to analyze {api_url}: {e}")
        return None

def extract_company_name_smart(title):
    """Extract company name from page title"""
    # Common patterns for company names in titles
    if '|' in title:
        parts = [part.strip() for part in title.split('|')]
        # Look for the part that's likely a company name (first part is usually company)
        company_name = parts[0] if len(parts[0].split()) <= 3 else parts[-1]
    elif '-' in title:
        parts = [part.strip() for part in title.split('-')]
        # Take first part, but if it's too long, take the shortest
        if len(parts[0].split()) <= 3:
            company_name = parts[0]
        else:
            company_name = min(parts, key=len)
    else:
        # Try to extract first meaningful word
        words = title.split()
        company_name = next((word for word in words if word[0].isupper() and len(word) > 2), words[0] if words else title)
    
    # Clean up common words that aren't company names
    common_words = ['the', 'ai', 'api', 'app', 'web', 'new', 'best', 'top', 'powered']
    if company_name.lower() in common_words and '|' in title:
        # If we got a common word, try the last part instead
        parts = [part.strip() for part in title.split('|')]
        company_name = parts[-1] if len(parts) > 1 else company_name
    elif company_name.lower() in common_words and '-' in title:
        # For dash-separated, try the first real word
        words = title.split('-')[0].strip().split()
        company_name = words[0] if words else company_name
        
    return company_name.strip()

def discover_key_pages(base_url, soup):
    """Discover and analyze key feature/product pages beyond the homepage"""
    print("🔍 Discovering key pages beyond homepage...")
    
    # Common page patterns for B2B SaaS companies
    key_page_patterns = [
        '/features', '/feature', '/products', '/product', '/solutions', '/solution',
        '/capabilities', '/services', '/platform', '/how-it-works',
        '/accounts-payable', '/accounts-receivable', '/ap', '/ar', 
        '/bill-pay', '/invoicing', '/payments', '/automation',
        '/approval-workflow', '/workflows', '/integrations'
    ]
    
    # Find navigation links
    discovered_pages = []
    
    # Method 1: Look for navigation menu links
    nav_links = soup.find_all('nav') + soup.find_all('div', class_=['nav', 'menu', 'header', 'navigation'])
    for nav in nav_links:
        links = nav.find_all('a', href=True)
        for link in links:
            href = link['href']
            text = link.get_text().lower().strip()
            
            # Check if link contains key terms
            if any(pattern in href.lower() for pattern in key_page_patterns) or \
               any(keyword in text for keyword in ['features', 'products', 'solutions', 'capabilities', 
                                                 'accounts payable', 'accounts receivable', 'bill pay', 
                                                 'invoicing', 'payments', 'automation', 'workflow']):
                
                # Convert to full URL
                if href.startswith('/'):
                    full_url = base_url.rstrip('/') + href
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                
                if full_url not in discovered_pages and base_url in full_url:
                    discovered_pages.append(full_url)
    
    # Method 2: Try common page patterns directly
    for pattern in key_page_patterns:
        potential_url = base_url.rstrip('/') + pattern
        discovered_pages.append(potential_url)
    
    # Remove duplicates and limit to top 10 most promising pages
    discovered_pages = list(dict.fromkeys(discovered_pages))[:10]
    
    print(f"🎯 Found {len(discovered_pages)} potential key pages to analyze")
    return discovered_pages

def scrape_key_pages(discovered_pages):
    """Scrape content from discovered key pages"""
    print("📚 Analyzing key pages for detailed capabilities...")
    
    aggregated_content = ""
    successful_pages = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for page_url in discovered_pages:
        try:
            print(f"📖 Checking: {page_url}")
            response = requests.get(page_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Get page title and content
                page_title = soup.find('title').text if soup.find('title') else ""
                page_content = soup.get_text()[:1500]  # Limit per page
                
                # Only include if it has substantial content
                if len(page_content.strip()) > 100:
                    aggregated_content += f"\n\nPAGE: {page_title} ({page_url})\nCONTENT: {page_content}\n"
                    successful_pages.append(page_url)
                    print(f"✅ Successfully analyzed: {page_url}")
                else:
                    print(f"⚠️ Minimal content found: {page_url}")
            else:
                print(f"❌ Failed to access: {page_url} (Status: {response.status_code})")
                
        except Exception as e:
            print(f"❌ Error accessing {page_url}: {e}")
            continue
    
    print(f"📊 Successfully analyzed {len(successful_pages)} key pages")
    return aggregated_content, successful_pages

def analyze_competitor_url(url):
    """Enhanced competitor analysis with key page discovery"""
    print(f"🔍 Analyzing: {url}")
    
    try:
        # Enhanced headers to avoid blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Step 1: Scrape homepage
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            raise requests.RequestException(f"HTTP {response.status_code}")
            
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('title').text if soup.find('title') else "No title"
        homepage_content = soup.get_text()[:2000]
        
        print(f"📄 Page title: {title}")
        print("✅ Successfully grabbed homepage content")
        
        # Step 2: Discover and scrape key pages
        discovered_pages = discover_key_pages(url, soup)
        key_pages_content, successful_pages = scrape_key_pages(discovered_pages)
        
        # Combine homepage and key pages content
        full_content = f"HOMEPAGE CONTENT:\n{homepage_content}\n\nKEY PAGES CONTENT:{key_pages_content}"
        
        company_name = extract_company_name_smart(title)
        print(f"🏢 Detected company name: {company_name}")
        
        # Search for recent news
        recent_news = search_recent_news(company_name)
        
        # Look for API documentation
        api_links = find_api_docs(url, soup)
        api_analysis = ""
        
        if api_links:
            print(f"🎯 Found {len(api_links)} potential API doc links")
            for api_url in api_links:
                api_data = analyze_api_docs(api_url)
                if api_data and len(api_data['content']) > 500:
                    api_analysis += f"\n\nAPI DOCS ANALYZED: {api_data['title']}\nURL: {api_data['url']}\nContent: {api_data['content'][:1500]}"
                    break
        
        if not api_analysis:
            print("❌ No API documentation found - this is competitive intelligence too!")
        
        print("🤖 Sending to AI for analysis...")
        
        # Complete Monite context
        monite_context = """
MONITE'S DETAILED AP/AR CAPABILITIES FOR ACCURATE COMPARISON:

ACCOUNTS PAYABLE (AP) FUNCTIONALITY:
- Bill capture: Email forwarding, manual upload, OCR-powered data extraction
- Invoice processing: Automated line-item extraction, coding suggestions, duplicate detection
- Approval workflows: Custom multi-step approval chains, delegation, escalation rules
- Vendor management: Vendor onboarding, payment terms, contact management
- Payment execution: ACH, wire transfers, international payments, check printing
- Payment scheduling: Batch payments, payment date optimization, cash flow management
- Reconciliation: Bank feed integration, automated matching, exception handling
- Reporting: Spend analytics, vendor reports, approval audit trails

ACCOUNTS RECEIVABLE (AR) FUNCTIONALITY:
- Invoice creation: Template-based invoicing, recurring billing, milestone invoicing
- Quote management: Quote-to-invoice conversion, approval workflows, version control
- Payment collection: Payment links, multiple payment methods (card, ACH, bank transfer)
- Payment reminders: Automated dunning sequences, customizable templates
- Customer management: Credit limits, payment terms, contact management
- Reconciliation: Payment matching, allocation, partial payment handling
- Reporting: Aging reports, collection analytics, cash flow forecasting

E-INVOICING & COMPLIANCE:
- Peppol e-invoicing: EU compliance, automated tax calculations
- Multi-country support: 30+ jurisdictions, local tax requirements
- Document formats: PDF generation, XML standards, digital signatures

TECHNICAL ARCHITECTURE:
- REST API: 200+ endpoints, webhook support, rate limiting
- SDK Options: React components, JavaScript SDK, Python SDK
- Integration patterns: Embedded iframes, white-label UI, headless API
- Authentication: OAuth 2.0, API keys, JWT tokens
- Data sync: Real-time webhooks, batch processing, audit logs

ACCOUNTING SYSTEM INTEGRATIONS:
- 40+ platforms: QuickBooks, Xero, NetSuite, Sage, FreshBooks, Wave
- Sync capabilities: Chart of accounts, tax rates, customers, vendors
- Mapping: Flexible field mapping, custom categorization
- Data flow: Bi-directional sync, conflict resolution

EMBEDDED FINANCE POSITIONING:
- Target market: B2B SaaS platforms, marketplaces, neobanks
- Implementation: 2-week average integration time
- Revenue model: Transaction-based pricing, revenue sharing options
- Deployment: Cloud-native, EU and US data centers
"""
        
        # Enhanced prompt with comprehensive analysis
        prompt = f"""
You are analyzing a competitor to Monite's AP/AR automation platform. You now have comprehensive data from their homepage AND key feature pages.

COMPETITOR DATA:
URL: {url}
Title: {title}
Comprehensive Content (Homepage + Key Pages): {full_content}
Pages Successfully Analyzed: {len(successful_pages)} pages including {', '.join(successful_pages[:3])}{'...' if len(successful_pages) > 3 else ''}

RECENT NEWS (Last 3 months):
{recent_news}

API DOCUMENTATION:
{api_analysis if api_analysis else "No public API documentation found - competitive advantage for their developer experience vs competitors with open APIs"}

{monite_context}

AGGRESSIVE THREAT ASSESSMENT FRAMEWORK:

**AUTOMATIC HIGH THREAT INDICATORS:**
- ANY mention of: "accounts payable", "bill pay", "vendor payments", "AP automation", "invoice processing", "approval workflow"
- ANY mention of: "accounts receivable", "invoicing", "payment collection", "AR automation", "dunning"
- Target market includes: "small business", "SMB", "B2B payments", "business payments"
- Clear business traction or established presence

Analyze in this format:

*THREAT LEVEL:* 🔴 HIGH / 🟡 MEDIUM / 💚 LOW

*THREAT JUSTIFICATION:*
[Based on comprehensive analysis of their homepage AND feature pages - be aggressive in assessment]

*RECENT DEVELOPMENTS:*
[Key insights from recent news - funding, product launches, partnerships, market expansion]

*COMPREHENSIVE AP/AR CAPABILITY ANALYSIS:*
**Accounts Payable:**
- Bill capture & processing: [Their specific capabilities found on their pages vs Monite's OCR + workflow engine]
- Approval workflows: [Detailed comparison based on their workflow pages vs Monite's custom approval chains]
- Payment execution: [Their payment methods vs Monite's ACH/wire/international options]
- Vendor management: [Their vendor features vs Monite's vendor portal]

**Accounts Receivable:**
- Invoice creation: [Their invoicing capabilities vs Monite's template + recurring billing]
- Payment collection: [Their collection methods vs Monite's payment links + multi-method support]
- Customer management: [Their CRM features vs Monite's credit limits + terms management]
- Collections: [Their dunning processes vs Monite's automated reminder sequences]

*API & INTEGRATION COMPARISON:*
[Compare their API offering (or lack thereof) vs Monite's 200+ endpoints + React/JS/Python SDKs. Note: Lack of public APIs can be competitive intelligence]

*ACCOUNTING PLATFORM INTEGRATIONS:*
[Their integration capabilities vs Monite's 40+ platforms with bi-directional sync]

*PRODUCT TEAM ANALYSIS:*
- Feature gaps in Monite: [Specific AP/AR features they have that Monite might lack]
- Technical architecture differences: [Based on their technical approach vs Monite's architecture]
- Investigation priorities: [Specific areas for Monite team to research further]

*SALES TEAM POSITIONING:*
- Monite's competitive advantages: [Clear advantages over this competitor]
- Competitor vulnerabilities: [Gaps in their offering to exploit]
- Discovery questions: [Questions to ask prospects that highlight Monite's strengths]

*MARKET POSITIONING:*
[Their positioning and target market vs Monite's embedded finance approach]

*OBJECTIVE ASSESSMENT:*
[Balanced assessment based on comprehensive page analysis]

FORMAT FOR SLACK:
- Use *bold text* for headers (not **bold**)
- Add blank lines between sections for spacing
- Use emoji for threat level: 🔴 HIGH, 🟡 MEDIUM, 💚 LOW
- Keep it clean and readable in Slack

IMPORTANT: You now have comprehensive data from multiple pages - use this to provide detailed, accurate competitive analysis.
"""
        
        # Call OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200
        )
        
        analysis = response.choices[0].message.content
        print("🎯 AI Analysis complete!")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"❌ Analysis failed: {str(e)}"
        
        # Call OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        analysis = response.choices[0].message.content
        print("🎯 AI Analysis complete!")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"❌ Analysis failed: {str(e)}"

def extract_company_name_from_url(url):
    """Extract company name from URL when title extraction fails"""
    try:
        # Remove protocol and www
        domain = url.replace('https://', '').replace('http://', '').replace('www.', '')
        # Get domain name without extension
        company_name = domain.split('.')[0]
        return company_name.capitalize()
    except:
        return "Unknown Company"

def search_company_info(company_name):
    """Search for company information when direct scraping fails"""
    try:
        print(f"🔍 Searching for {company_name} company information...")
        
        # Search for company description/about information
        search_query = f"{company_name} company what does accounts payable invoicing"
        search_url = f"https://www.google.com/search?q={search_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract search result snippets
        snippets = []
        for result in soup.find_all('div', class_='g')[:5]:  # Top 5 results
            snippet = result.find('span', class_='st') or result.find('div', class_='s')
            if snippet:
                snippets.append(snippet.get_text()[:300])
        
        if snippets:
            return f"Company information from search results: " + " ".join(snippets)
        
        return None
        
    except Exception as e:
        print(f"❌ Backup search failed: {e}")
        return None
        
        # Call OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        analysis = response.choices[0].message.content
        print("🎯 AI Analysis complete!")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"❌ Analysis failed: {str(e)}"

def extract_urls_from_text(text):
    """Extract URLs from message text"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)

@app.event("reaction_added")
def handle_reaction_added(event, say):
    """Handle when someone adds a reaction to trigger analysis"""
    
    # DEBUG: Print all reaction events
    print(f"🔍 Reaction detected: {event['reaction']} by user {event['user']}")
    
    # Check if reaction is our trigger emoji
    if event["reaction"] in ["satellite_antenna"]:
        print("✅ Satellite antenna reaction detected!")
        
        try:
            # Get the message that was reacted to
            result = app.client.conversations_history(
                channel=event["item"]["channel"],
                latest=event["item"]["ts"],
                limit=1,
                inclusive=True
            )
            
            if result["messages"]:
                message = result["messages"][0]
                message_text = message.get("text", "")
                
                # Look for URLs in the message
                urls = extract_urls_from_text(message_text)
                
                if urls:
                    # Add eyes reaction to show we're processing
                    app.client.reactions_add(
                        channel=event["item"]["channel"],
                        timestamp=event["item"]["ts"],
                        name="eyes"
                    )
                    
                    # Analyze the first URL
                    url = urls[0]
                    analysis = analyze_competitor_url(url)
                    
                    # Post analysis in thread
                    say(
                        text=f"🚨 *RivalRadar Analysis*\n\n{analysis}",
                        thread_ts=event["item"]["ts"],
                        channel=event["item"]["channel"]
                    )
                    
                    # Remove eyes reaction and add checkmark
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
                    # No URLs found in the message
                    say(
                        text="📡 RivalRadar triggered but no URLs found in this message!",
                        thread_ts=event["item"]["ts"],
                        channel=event["item"]["channel"]
                    )
                    
        except Exception as e:
            print(f"❌ Error handling reaction: {e}")
            say(
                text=f"❌ RivalRadar error: {str(e)}",
                thread_ts=event["item"]["ts"],
                channel=event["item"]["channel"]
            )

# Test command for debugging
@app.command("/analyze")
def analyze_command(ack, respond, command):
    ack()
    url = command['text'].strip()
    if url:
        analysis = analyze_competitor_url(url)
        respond(f"🚨 *RivalRadar Analysis*\n\n{analysis}")
    else:
        respond("Please provide a URL to analyze: `/analyze https://competitor.com`")

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
    print("🚨 RivalRadar ready! React with 📡 to any URL to trigger analysis!")
    print("Emoji trigger system loaded - no more automatic URL analysis!")
