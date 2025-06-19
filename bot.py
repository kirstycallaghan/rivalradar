import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Your OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def get_enhanced_stealth_session():
    """Create a session with retry logic and better stealth"""
    session = requests.Session()
    
    # Add retry strategy
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS"],
        backoff_factor=2
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def get_stealth_headers():
    """Generate realistic browser headers that rotate to avoid detection"""
    
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    user_agent = random.choice(user_agents)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.google.com/',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }
    
    return headers

def enhanced_stealth_request(url, session=None):
    """Enhanced stealth request with better error handling"""
    if session is None:
        session = get_enhanced_stealth_session()
    
    try:
        # Longer delay to avoid rate limiting
        time.sleep(random.uniform(3, 7))
        
        headers = get_stealth_headers()
        
        response = session.get(
            url, 
            headers=headers, 
            timeout=20,
            allow_redirects=True,
            verify=True
        )
        
        print(f"📡 Request to {url}: Status {response.status_code}")
        
        # Handle different status codes
        if response.status_code == 403:
            print(f"🚫 403 Forbidden for {url} - website is blocking automated access")
            return None
        elif response.status_code == 429:
            print(f"⏰ Rate limited for {url} - waiting longer...")
            time.sleep(30)
            return None
        elif response.status_code in [200, 301, 302]:
            return response
        else:
            print(f"⚠️ Unexpected status code {response.status_code} for {url}")
            return None
        
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout accessing {url}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"🔌 Connection error accessing {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed for {url}: {e}")
        return None

def search_recent_news(company_name):
    """Search for recent news using alternative methods instead of Google scraping"""
    print(f"📰 Searching for recent news about {company_name}...")
    
    try:
        # Try company's own press/news pages first
        base_domains = [
            f"{company_name.lower()}.com",
            f"{company_name.lower()}.io",
            f"{company_name.lower()}.co"
        ]
        
        press_paths = ["/press", "/news", "/blog", "/newsroom", "/media"]
        
        for domain in base_domains:
            for path in press_paths:
                try:
                    press_url = f"https://{domain}{path}"
                    headers = get_stealth_headers()
                    response = requests.get(press_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        articles = soup.find_all(['article', 'div'], class_=['post', 'article', 'news-item'])[:3]
                        
                        if articles:
                            news_items = []
                            for article in articles:
                                title_elem = article.find(['h1', 'h2', 'h3', 'h4'])
                                if title_elem:
                                    title = title_elem.get_text().strip()[:100]
                                    news_items.append(f"• {title}")
                            
                            if news_items:
                                print(f"✅ Found news from {press_url}")
                                return "\n".join(news_items)
                except:
                    continue
        
        # Fallback: Check if NewsAPI is available
        NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
        if NEWS_API_KEY:
            try:
                url = f"https://newsapi.org/v2/everything?q={company_name}&sortBy=publishedAt&from={time.strftime('%Y-%m-%d', time.gmtime(time.time() - 90*24*3600))}&apiKey={NEWS_API_KEY}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    articles = response.json().get('articles', [])
                    news_items = []
                    for article in articles[:3]:
                        title = article.get('title', '')[:100]
                        description = article.get('description', '')[:100]
                        news_items.append(f"• {title}: {description}")
                    return "\n".join(news_items) if news_items else "No recent news found"
            except Exception as e:
                print(f"NewsAPI failed: {e}")
        
        return "No recent news found - consider checking company's press page manually"
        
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
        headers = get_stealth_headers()
        response = requests.get(api_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
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
    if '|' in title:
        parts = [part.strip() for part in title.split('|')]
        company_name = parts[0] if len(parts[0].split()) <= 3 else parts[-1]
    elif '-' in title:
        parts = [part.strip() for part in title.split('-')]
        if len(parts[0].split()) <= 3:
            company_name = parts[0]
        else:
            company_name = min(parts, key=len)
    else:
        words = title.split()
        company_name = next((word for word in words if word[0].isupper() and len(word) > 2), words[0] if words else title)
    
    common_words = ['the', 'ai', 'api', 'app', 'web', 'new', 'best', 'top', 'powered']
    if company_name.lower() in common_words and '|' in title:
        parts = [part.strip() for part in title.split('|')]
        company_name = parts[-1] if len(parts) > 1 else company_name
    elif company_name.lower() in common_words and '-' in title:
        words = title.split('-')[0].strip().split()
        company_name = words[0] if words else company_name
        
    return company_name.strip()

def extract_company_name_from_url(url):
    """Extract company name from URL when title extraction fails"""
    try:
        domain = url.replace('https://', '').replace('http://', '').replace('www.', '')
        company_name = domain.split('.')[0]
        return company_name.capitalize()
    except:
        return "Unknown Company"

def get_manual_competitor_data(domain):
    """Manual database for frequently analyzed competitors that block scraping"""
    
    manual_data = {
        'bill.com': {
            'title': 'Bill.com - AP/AR Automation',
            'company_name': 'Bill.com',
            'content': 'Established AP/AR automation platform. Features: invoice processing, approval workflows, vendor payments, customer invoicing, integrations with 600+ apps including QuickBooks, NetSuite. Public company (NYSE: BILL). Strong SMB and enterprise presence.'
        },
        'codat.io': {
            'title': 'Codat - Universal API for business data',
            'company_name': 'Codat', 
            'content': 'API platform for accessing business financial data. Enables fintechs to connect to accounting platforms, banking systems, and commerce tools. Strong developer focus with comprehensive APIs and SDKs.'
        },
        'melio.com': {
            'title': 'Melio - B2B Payments',
            'company_name': 'Melio',
            'content': 'B2B payments platform focused on SMBs. Features: vendor payments, approval workflows, QuickBooks integration, ACH and check payments. Strong brand presence in small business market.'
        },
        'meliopayments.com': {
            'title': 'Melio - B2B Payments',
            'company_name': 'Melio',
            'content': 'B2B payments platform focused on SMBs. Features: vendor payments, approval workflows, QuickBooks integration, ACH and check payments. Strong brand presence in small business market.'
        },
        'ramp.com': {
            'title': 'Ramp - Corporate Card & Spend Management',
            'company_name': 'Ramp',
            'content': 'Corporate card and spend management platform. Features: expense management, bill pay, procurement, accounting integrations. High-growth fintech with strong SMB/enterprise presence.'
        },
        'brex.com': {
            'title': 'Brex - Financial Platform for Growing Companies',
            'company_name': 'Brex',
            'content': 'Financial platform offering corporate cards, expense management, and bill pay. Features: automated expense categorization, real-time controls, accounting integrations.'
        }
    }
    
    return manual_data.get(domain)

def discover_key_pages(base_url, soup):
    """Discover and analyze key feature/product pages beyond the homepage"""
    print("🔍 Discovering key pages beyond homepage...")
    
    key_page_patterns = [
        '/features', '/feature', '/products', '/product', '/solutions', '/solution',
        '/capabilities', '/services', '/platform', '/how-it-works',
        '/accounts-payable', '/accounts-receivable', '/ap', '/ar', 
        '/bill-pay', '/invoicing', '/payments', '/automation',
        '/approval-workflow', '/workflows', '/integrations'
    ]
    
    discovered_pages = []
    
    nav_links = soup.find_all('nav') + soup.find_all('div', class_=['nav', 'menu', 'header', 'navigation'])
    for nav in nav_links:
        links = nav.find_all('a', href=True)
        for link in links:
            href = link['href']
            text = link.get_text().lower().strip()
            
            if any(pattern in href.lower() for pattern in key_page_patterns) or \
               any(keyword in text for keyword in ['features', 'products', 'solutions', 'capabilities', 
                                                 'accounts payable', 'accounts receivable', 'bill pay', 
                                                 'invoicing', 'payments', 'automation', 'workflow']):
                
                if href.startswith('/'):
                    full_url = base_url.rstrip('/') + href
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                
                if full_url not in discovered_pages and base_url in full_url:
                    discovered_pages.append(full_url)
    
    for pattern in key_page_patterns:
        potential_url = base_url.rstrip('/') + pattern
        discovered_pages.append(potential_url)
    
    discovered_pages = list(dict.fromkeys(discovered_pages))[:10]
    
    print(f"🎯 Found {len(discovered_pages)} potential key pages to analyze")
    return discovered_pages

def scrape_key_pages_stealth(discovered_pages, session):
    """Scrape key pages using stealth mode with delays"""
    print("🕵️ Stealth key page analysis...")
    
    aggregated_content = ""
    successful_pages = 0
    
    for page_url in discovered_pages:
        if successful_pages >= 5:
            break
            
        print(f"🔍 Stealthily checking: {page_url}")
        
        time.sleep(random.uniform(2, 5))
        
        response = enhanced_stealth_request(page_url, session)
        
        if response and response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            page_content = soup.get_text()[:1000]
            
            if len(page_content.strip()) > 100:
                aggregated_content += f"\n\nKEY PAGE: {page_url}\nCONTENT: {page_content[:800]}\n"
                successful_pages += 1
                print(f"✅ Successfully analyzed: {page_url}")
        else:
            print(f"❌ Blocked: {page_url}")
    
    print(f"🎯 Successfully analyzed {successful_pages} key pages")
    return aggregated_content

def analyze_with_fallback_strategies(url):
    """Enhanced analysis with robust 403 error handling"""
    print(f"🕵️ Deploying analysis for: {url}")
    
    try:
        company_name = extract_company_name_from_url(url)
        print(f"🏢 Detected company: {company_name}")
        
        # Check manual database first for known difficult sites
        domain = url.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
        manual_data = get_manual_competitor_data(domain)
        
        if manual_data:
            print("✅ Using manual competitor database")
            return {
                'title': manual_data['title'],
                'content': manual_data['content'],
                'company_name': manual_data['company_name'],
                'content_found': True,
                'access_status': 'manual_data'
            }
        
        # Try enhanced stealth scraping
        session = get_enhanced_stealth_session()
        response = enhanced_stealth_request(url, session)
        
        if response and response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find('title').text if soup.find('title') else "No title"
            homepage_content = soup.get_text()[:2000]
            
            if len(homepage_content.strip()) > 100:
                print("✅ Direct scraping successful!")
                
                # Try to get key pages too
                discovered_pages = discover_key_pages(url, soup)
                key_content = scrape_key_pages_stealth(discovered_pages, session)
                
                full_content = f"HOMEPAGE CONTENT:\n{homepage_content}\n{key_content}"
                
                return {
                    'title': title,
                    'content': full_content,
                    'company_name': extract_company_name_smart(title),
                    'content_found': True,
                    'access_status': 'success'
                }
        
        # If we get here, direct scraping failed
        print("🚫 Direct scraping blocked or failed")
        
        # Try alternative URL formats
        alt_urls = []
        if url.startswith('https://www.'):
            alt_urls.append(url.replace('https://www.', 'https://'))
        elif url.startswith('https://') and 'www.' not in url:
            alt_urls.append(url.replace('https://', 'https://www.'))
        
        for alt_url in alt_urls:
            print(f"🔄 Trying alternative: {alt_url}")
            response = enhanced_stealth_request(alt_url, session)
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                title = soup.find('title').text if soup.find('title') else "No title"
                content = soup.get_text()[:2000]
                
                if len(content.strip()) > 100:
                    return {
                        'title': title,
                        'content': f"HOMEPAGE CONTENT:\n{content}",
                        'company_name': extract_company_name_smart(title),
                        'content_found': True,
                        'access_status': 'success'
                    }
        
        # All scraping failed - return limited analysis
        print("⚠️ All scraping strategies failed")
        return {
            'title': f"{company_name} - Access Restricted",
            'content': f"Analysis of {url} was blocked (likely HTTP 403). The website {company_name} prevents automated access. Based on the domain, this appears to be a business software company. Manual research recommended for detailed competitive analysis. Consider checking their LinkedIn company page, press releases, or industry reports for more information.",
            'company_name': company_name,
            'content_found': False,
            'access_status': 'blocked_403'
        }
            
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout for {url}")
        return {
            'title': f"{company_name} - Timeout",
            'content': f"Request to {url} timed out. Website may be slow or blocking requests.",
            'company_name': company_name,
            'content_found': False,
            'access_status': 'timeout'
        }
        
    except Exception as e:
        print(f"❌ Error analyzing {url}: {e}")
        return {
            'title': f"{company_name} - Error",
            'content': f"Analysis failed for {url}: {str(e)}. Manual research recommended.",
            'company_name': company_name,
            'content_found': False,
            'access_status': 'error'
        }

def generate_analysis_prompt(url, title, content, company_name, access_status, recent_news):
    """Generate analysis prompt that handles different access scenarios"""
    
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
    
    if access_status == 'success':
        data_quality_note = "Full website analysis available"
    elif access_status == 'blocked_403':
        data_quality_note = "⚠️ LIMITED DATA: Website blocks automated access (403 error). Analysis based on available info only."
    elif access_status == 'manual_data':
        data_quality_note = "✅ RELIABLE DATA: Using curated competitor intelligence database"
    else:
        data_quality_note = f"⚠️ LIMITED DATA: Website access failed ({access_status}). Analysis may be incomplete."
    
    prompt = f"""
You are analyzing a potential competitor to Monite's AP/AR automation platform.

DATA AVAILABILITY: {data_quality_note}

COMPETITOR DATA:
URL: {url}
Title: {title}
Company: {company_name}
Access Status: {access_status}

AVAILABLE CONTENT:
{content}

RECENT NEWS: {recent_news}

{monite_context}

ANALYSIS INSTRUCTIONS:
- If access_status is 'success' or 'manual_data': Provide full competitive analysis
- If access_status is 'blocked_403' or other error: Focus on threat assessment based on available info and recommend manual research
- Be transparent about data limitations
- Still provide useful competitive intelligence where possible

**AUTOMATIC HIGH THREAT INDICATORS:**
- ANY mention of: "accounts payable", "bill pay", "vendor payments", "AP automation", "invoice processing", "approval workflow"
- ANY mention of: "accounts receivable", "invoicing", "payment collection", "AR automation", "dunning"
- Target market includes: "small business", "SMB", "B2B payments", "business payments"
- Clear business traction or established presence

Analyze in this format:

*THREAT LEVEL:* 🔴 HIGH / 🟡 MEDIUM / 💚 LOW

*DATA LIMITATIONS:* {data_quality_note}

*THREAT JUSTIFICATION:*
[Based on available analysis - be aggressive in assessment when AP/AR keywords detected]

*RECENT DEVELOPMENTS:*
[Key insights from recent news - funding, product launches, partnerships, market expansion]

*COMPREHENSIVE AP/AR CAPABILITY ANALYSIS:*
**Accounts Payable:**
- Bill capture & processing: [Their capabilities vs Monite's OCR + workflow engine]
- Approval workflows: [Their workflow features vs Monite's custom approval chains]
- Payment execution: [Their payment methods vs Monite's ACH/wire/international options]
- Vendor management: [Their vendor features vs Monite's vendor portal]

**Accounts Receivable:**
- Invoice creation: [Their invoicing capabilities vs Monite's template + recurring billing]
- Payment collection: [Their collection methods vs Monite's payment links + multi-method support]
- Customer management: [Their CRM features vs Monite's credit limits + terms management]
- Collections: [Their dunning processes vs Monite's automated reminder sequences]

*API & INTEGRATION COMPARISON:*
[Compare their API offering vs Monite's 200+ endpoints + React/JS/Python SDKs]

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

*RECOMMENDED NEXT STEPS:*
[If data is limited, provide specific manual research recommendations]

FORMAT FOR SLACK:
- Use *bold text* for headers (not **bold**)
- Add blank lines between sections for spacing
- Use emoji for threat level: 🔴 HIGH, 🟡 MEDIUM, 💚 LOW
- Keep it clean and readable in Slack

IMPORTANT: Be transparent about data limitations while still providing maximum value analysis.
"""
    
    return prompt

def analyze_competitor_url(url):
    """Enhanced competitor analysis with robust error handling"""
    print(f"🕵️ Starting competitive analysis: {url}")
    
    try:
        # Use enhanced analysis with fallback strategies
        analysis_result = analyze_with_fallback_strategies(url)
        
        title = analysis_result['title']
        full_content = analysis_result['content']
        company_name = analysis_result['company_name']
        access_status = analysis_result['access_status']
        
        print(f"🏢 Detected company name: {company_name}")
        print(f"📊 Access status: {access_status}")
        
        # Search for recent news
        recent_news = search_recent_news(company_name)
        
        print("🤖 Sending comprehensive intelligence to AI...")
        
        # Generate appropriate prompt based on data availability
        prompt = generate_analysis_prompt(url, title, full_content, company_name, access_status, recent_news)
        
        # Call OpenAI with enhanced analysis
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200
        )
        
        analysis = response.choices[0].message.content
        print("🎯 Analysis complete!")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return f"❌ Analysis failed: {str(e)}\n\nThis could be due to:\n- Website blocking automated access (403 error)\n- Network connectivity issues\n- OpenAI API issues\n\nTry again in a few minutes or consider manual research for this competitor."

def extract_urls_from_text(text):
    """Extract URLs from message text"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)

@app.event("reaction_added")
def handle_reaction_added(event, say):
    """Handle when someone adds a reaction to trigger analysis"""
    
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
        try:
            analysis = analyze_competitor_url(url)
            respond(f"🚨 *RivalRadar Analysis*\n\n{analysis}")
        except Exception as e:
            respond(f"❌ Analysis failed: {str(e)}")
    else:
        respond("Please provide a URL to analyze: `/analyze https://competitor.com`")

# Health check command
@app.command("/rivalradar")
def health_check(ack, respond):
    ack()
    respond("🚨 RivalRadar is online! React with 📡 to any URL to trigger analysis, or use `/analyze <url>` for direct analysis.")

if __name__ == "__main__":
    try:
        handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        handler.start()
        print("🚨 RivalRadar ready! React with 📡 to any URL to trigger analysis!")
        print("✅ Enhanced 403 error handling enabled")
        print("🔧 Manual competitor database loaded")
        print("🕵️ Stealth mode activated")
    except Exception as e:
        print(f"❌ Failed to start RivalRadar: {e}")
        print("Check your environment variables:")
        print("- SLACK_BOT_TOKEN")
        print("- SLACK_APP_TOKEN") 
        print("- OPENAI_API_KEY")
        print("- NEWS_API_KEY (optional)")

# Additional utility functions for enhanced error handling

def test_competitor_analysis(test_urls=None):
    """Test function to verify the enhanced error handling works"""
    if test_urls is None:
        test_urls = [
            "https://bill.com",  # Known to block scraping
            "https://codat.io",  # API-focused company
            "https://melio.com", # B2B payments
        ]
    
    print("🧪 Testing enhanced competitor analysis...")
    
    for url in test_urls:
        print(f"\n🔍 Testing: {url}")
        try:
            result = analyze_with_fallback_strategies(url)
            print(f"✅ {result['access_status']}: {result['company_name']}")
        except Exception as e:
            print(f"❌ Test failed for {url}: {e}")
    
    print("\n🎯 Test complete!")

def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = {
        'SLACK_BOT_TOKEN': 'Required for Slack bot functionality',
        'SLACK_APP_TOKEN': 'Required for Socket Mode connection',
        'OPENAI_API_KEY': 'Required for AI analysis'
    }
    
    optional_vars = {
        'NEWS_API_KEY': 'Optional - enables enhanced news search'
    }
    
    print("🔧 Environment validation:")
    
    missing_required = []
    for var, description in required_vars.items():
        if os.environ.get(var):
            print(f"✅ {var}: Set")
        else:
            print(f"❌ {var}: Missing - {description}")
            missing_required.append(var)
    
    for var, description in optional_vars.items():
        if os.environ.get(var):
            print(f"✅ {var}: Set (optional)")
        else:
            print(f"⚠️ {var}: Not set - {description}")
    
    if missing_required:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_required)}")
        return False
    else:
        print("\n✅ All required environment variables are set!")
        return True

# Run environment validation on import
if __name__ == "__main__":
    validate_environment()
