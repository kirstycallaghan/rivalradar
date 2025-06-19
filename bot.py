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

def analyze_competitor_url(url):
    """Analyze a competitor URL with improved scraping and threat detection"""
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
        
        # Try multiple scraping approaches
        response = None
        text_content = ""
        title = "No title"
        
        # Attempt 1: Direct scraping
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                title = soup.find('title').text if soup.find('title') else "No title"
                text_content = soup.get_text()[:4000]  # Increased content limit
                print(f"📄 Page title: {title}")
                print("✅ Successfully grabbed page content")
            else:
                print(f"⚠️ HTTP {response.status_code} - trying alternative approach")
                raise requests.RequestException("Non-200 status code")
        except:
            print("❌ Direct scraping failed, trying backup approach...")
            
        # Attempt 2: If direct scraping fails, search for company info
        if len(text_content.strip()) < 100:  # Very little content found
            print("🔍 Content too limited, searching for company information...")
            company_name = extract_company_name_from_url(url)
            
            # Search for company information as backup
            backup_content = search_company_info(company_name)
            if backup_content:
                text_content = backup_content
                title = f"{company_name} - Company Information"
                print("✅ Found backup company information")
            else:
                print("❌ Backup search also failed")
        
        company_name = extract_company_name_smart(title) if title != "No title" else extract_company_name_from_url(url)
        print(f"🏢 Detected company name: {company_name}")
        
        # Search for recent news
        recent_news = search_recent_news(company_name)
        
        # Look for API documentation with multiple attempts
        api_analysis = ""
        if response and response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            api_links = find_api_docs(url, soup)
            
            if api_links:
                print(f"🎯 Found {len(api_links)} potential API doc links")
                for api_url in api_links:
                    api_data = analyze_api_docs(api_url)
                    if api_data and len(api_data['content']) > 500:
                        api_analysis += f"\n\nAPI DOCS ANALYZED: {api_data['title']}\nURL: {api_data['url']}\nContent: {api_data['content'][:1500]}"
                        break
        
        if not api_analysis:
            print("❌ No substantial API documentation found")
        
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
        
        # Enhanced prompt with aggressive threat detection
        prompt = f"""
You are analyzing a competitor to Monite's AP/AR automation platform. Be AGGRESSIVE in threat assessment - better to overestimate than underestimate threats.

COMPETITOR DATA:
URL: {url}
Title: {title}
Content: {text_content}

RECENT NEWS (Last 3 months):
{recent_news}

API DOCUMENTATION:
{api_analysis if api_analysis else "No API docs found - analysis limited to website content"}

{monite_context}

AGGRESSIVE THREAT ASSESSMENT FRAMEWORK:

**AUTOMATIC HIGH THREAT INDICATORS:**
- ANY mention of: "accounts payable", "bill pay", "vendor payments", "AP automation", "invoice processing"
- ANY mention of: "accounts receivable", "invoicing", "payment collection", "AR automation" 
- Target market includes: "small business", "SMB", "B2B payments", "business payments"
- Significant funding: Series A+ or $10M+ raised
- Established player with clear AP/AR focus

**HIGH THREAT = Direct AP or AR functionality + any business traction**
**MEDIUM THREAT = Adjacent financial services + expansion potential**  
**LOW THREAT = Completely different industry**

Analyze in this format:

*THREAT LEVEL:* 🔴 HIGH / 🟡 MEDIUM / 💚 LOW

*THREAT JUSTIFICATION:*
[Be aggressive - if they do ANYTHING related to AP/AR, explain why it's a threat. Look for keywords like bill pay, invoicing, vendor payments, business payments, accounts payable, etc.]

*RECENT DEVELOPMENTS:*
[Key insights from recent news - funding, product launches, partnerships, market expansion]

*AP/AR CAPABILITY ANALYSIS:*
**Accounts Payable:**
- Bill capture & processing: [Their capabilities vs Monite's OCR + workflow engine]
- Approval workflows: [Their workflow features vs Monite's custom approval chains]  
- Payment execution: [Payment methods vs Monite's ACH/wire/international options]
- Vendor management: [Their vendor features vs Monite's vendor portal]

**Accounts Receivable:**
- Invoice creation: [Their invoicing vs Monite's template + recurring billing]
- Payment collection: [Payment methods vs Monite's payment links + multi-method support]
- Customer management: [Their CRM features vs Monite's credit limits + terms management]
- Collections: [Dunning processes vs Monite's automated reminder sequences]

*API & INTEGRATION COMPARISON:*
[If API docs available: endpoint comparison, authentication methods, webhook support, SDK availability vs Monite's 200+ endpoints + React/JS/Python SDKs]

*ACCOUNTING PLATFORM INTEGRATIONS:*
[Their integration count/quality vs Monite's 40+ platforms with bi-directional sync]

*PRODUCT TEAM ANALYSIS:*
- Feature gaps in Monite: [Specific AP/AR features they offer that Monite lacks]
- Technical architecture differences: [API design, integration patterns, scalability approaches]
- Investigation priorities: [Specific areas for Monite product team to research]

*SALES TEAM POSITIONING:*
- Monite's competitive advantages: [Specific AP/AR strengths to emphasize in sales conversations]
- Competitor vulnerabilities: [Gaps in their AP/AR offering to exploit]
- Discovery questions: [Questions to ask prospects that highlight Monite's strengths]

*MARKET POSITIONING:*
[Their go-to-market strategy, target customers, and positioning vs Monite's embedded finance approach]

*OBJECTIVE ASSESSMENT:*
[Balanced view but err on the side of caution - if uncertain, lean toward higher threat level]

FORMAT FOR SLACK:
- Use *bold text* for headers (not **bold**)
- Add blank lines between sections for spacing
- Use emoji for threat level: 🔴 HIGH, 🟡 MEDIUM, 💚 LOW
- Keep it clean and readable in Slack

CRITICAL: If content is limited due to scraping issues, state this clearly but still assess threat based on available information. Don't default to LOW threat just because of technical limitations.
"""
        
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
