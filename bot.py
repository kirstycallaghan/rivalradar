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
SERP_API_KEY = os.environ.get("SERP_API_KEY")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY")

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
            
            time.sleep(1)
        
        if all_results:
            return "\n".join(all_results[:10])
            
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
                    all_results.append(f"• {title}: {description}")
            
            time.sleep(1)
        
        if all_results:
            return "\n".join(all_results[:8])
            
    except Exception as e:
        print(f"❌ Brave API search failed: {e}")
        return None

def find_and_analyze_api_docs(url, company_name):
    """Find and analyze competitor API documentation"""
    print(f"🔍 Searching for API documentation for {company_name}...")
    
    api_patterns = [
        f"{url.rstrip('/')}/api",
        f"{url.rstrip('/')}/docs",
        f"{url.rstrip('/')}/developers",
        f"{url.rstrip('/')}/api-docs",
        f"{url.rstrip('/')}/documentation",
        f"{url.rstrip('/')}/reference",
        f"{url.rstrip('/')}/dev",
        f"https://docs.{company_name.lower()}.com",
        f"https://api.{company_name.lower()}.com",
        f"https://developers.{company_name.lower()}.com"
    ]
    
    api_analysis = ""
    
    for api_url in api_patterns:
        try:
            response = simple_request(api_url)
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                content = soup.get_text()
                
                if any(keyword in content.lower() for keyword in ['api', 'endpoint', 'webhook', 'authentication', 'sdk', 'integration']):
                    api_content = ' '.join(content.split())[:2000]
                    api_analysis += f"API DOCUMENTATION FOUND ({api_url}):\n{api_content}\n\n"
                    print(f"✅ Found API docs at {api_url}")
                    break
        except:
            continue
    
    if not api_analysis:
        try:
            response = simple_request(url)
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                api_mentions = []
                for element in soup.find_all(['div', 'section', 'p'], string=lambda text: text and 'api' in text.lower()):
                    text = element.get_text().strip()
                    if len(text) > 50 and any(keyword in text.lower() for keyword in ['api', 'integration', 'webhook', 'sdk']):
                        api_mentions.append(text[:300])
                
                if api_mentions:
                    api_analysis = f"API REFERENCES FOUND ON MAIN SITE:\n" + "\n".join(api_mentions[:3])
        except:
            pass
    
    return api_analysis if api_analysis else "No public API documentation found"

def gather_competitor_intelligence(company_name, failed_url):
    """Gather competitive intelligence when direct scraping fails"""
    print(f"🕵️ Gathering intelligence on {company_name} using alternative methods...")
    
    intelligence = []
    
    serp_results = search_with_serp_api(company_name)
    if serp_results:
        intelligence.append(f"SEARCH INTELLIGENCE:\n{serp_results}")
    
    brave_results = search_with_brave_api(company_name)
    if brave_results:
        intelligence.append(f"BRAVE SEARCH RESULTS:\n{brave_results}")
    
    alternative_pages = [
        f"https://{company_name.lower()}.com/about",
        f"https://{company_name.lower()}.com/features", 
        f"https://{company_name.lower()}.com/pricing",
        f"https://www.{company_name.lower()}.com",
        f"https://{company_name.lower()}.io"
    ]
    
    for alt_url in alternative_pages:
        if alt_url != failed_url:
            response = simple_request(alt_url)
            if response and response.status_code == 200:
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    content = soup.get_text()[:1500]
                    if len(content.strip()) > 200:
                        intelligence.append(f"FROM {alt_url}:\n{content}")
                        break
                except:
                    continue
    
    if failed_url:
        api_analysis = find_and_analyze_api_docs(failed_url, company_name)
        if "No public API documentation found" not in api_analysis:
            intelligence.append(api_analysis)
    
    linkedin_search_url = f"https://www.linkedin.com/company/{company_name.lower()}"
    response = simple_request(linkedin_search_url)
    if response and response.status_code == 200:
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
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
    
    response = simple_request(url)
    
    if response and response.status_code == 200:
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find('title').text if soup.find('title') else "No title"
            content = soup.get_text()
            content = ' '.join(content.split())[:3000]
            
            if len(content.strip()) > 100:
                company_name = extract_company_name_smart(title)
                
                api_analysis = find_and_analyze_api_docs(url, company_name)
                
                full_content = f"WEBSITE CONTENT:\n{content}\n\n{api_analysis}"
                
                return {
                    'success': True,
                    'title': title,
                    'content': full_content,
                    'company_name': company_name,
                    'status': f"Successfully analyzed {url}",
                    'method': 'direct_scraping'
                }
        except Exception as e:
            print(f"❌ Error parsing content: {e}")
    
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
        return {
            'success': False,
            'title': f"{company_name} - Limited Access",
            'content': f"Could not analyze {url} directly and intelligence gathering was limited. {company_name} may be blocking automated access. Manual research recommended: check LinkedIn company page, Crunchbase profile, or Google '{company_name} AP automation features' for competitive intelligence.",
            'company_name': company_name,
            'status': f"Analysis blocked - manual research needed",
            'method': 'failed'
        }

def get_monite_context():
    """Get detailed Monite context for comparison"""
    return """MONITE COMPREHENSIVE AP/AR CAPABILITIES - DETAILED TECHNICAL SPECS:

ACCOUNTS PAYABLE (AP) AUTOMATION:
Core Processing:
- OCR bill capture: Email forwarding (@bills.monite.com), drag-drop upload, mobile scanning
- Data extraction: Line items, tax amounts, vendor details, invoice numbers, due dates
- Duplicate detection: Automated matching against existing bills and payments
- Coding & categorization: Chart of accounts mapping, tax code assignment, cost center allocation
- Multi-currency support: 50+ currencies with real-time exchange rates

Approval Workflows:
- Custom multi-step approval chains: Sequential, parallel, conditional routing
- Approval rules: Amount thresholds, vendor-specific, category-based, GL account triggers
- Delegation & escalation: Temporary delegates, auto-escalation on timeout
- Mobile approval: Native mobile apps with push notifications
- Audit trails: Complete approval history with timestamps and comments

Vendor Management:
- Vendor onboarding: Self-service portal, W-9/tax form collection, bank details verification
- Vendor database: Contact management, payment terms, preferred payment methods
- Vendor communications: Automated notifications, payment confirmations
- Duplicate vendor detection: Fuzzy matching on name, TIN, address

Payment Execution:
- Payment methods: ACH (same-day, next-day), wire transfers, international wires, check printing
- Payment scheduling: Future-dated payments, recurring payments, batch processing
- Payment optimization: Cash flow calendars, early payment discounts
- Bank integrations: Direct bank feeds, reconciliation automation
- Payment status tracking: Real-time payment status, failed payment handling

ACCOUNTS RECEIVABLE (AR) AUTOMATION:
Invoice Management:
- Invoice creation: Template-based, recurring billing, milestone invoicing, project-based
- Line item management: Product catalogs, tax calculations, discounts, custom fields
- Invoice customization: Branded templates, custom fields, terms and conditions
- Multi-currency invoicing: Currency conversion, international tax handling

Quote & Estimate Management:
- Quote creation: Template-based quotes, line item management, approval workflows
- Quote-to-invoice conversion: One-click conversion with change tracking
- Quote versioning: Multiple versions, comparison views, approval history
- Expiration management: Auto-expiration, renewal reminders

Payment Collection:
- Payment links: Embedded in invoices, standalone payment pages, mobile-optimized
- Payment methods: Credit cards, ACH, bank transfers, digital wallets
- Partial payments: Automatic allocation, payment plans, installment tracking
- Payment portals: Customer self-service, payment history, auto-pay setup

Customer Management:
- Customer database: Contact management, billing addresses, payment preferences
- Credit management: Credit limits, payment terms, risk scoring
- Customer communications: Automated notifications, payment confirmations, statements

Collections & Dunning:
- Automated dunning: Customizable sequences, escalation rules, multiple channels
- Collection workflows: Task management, collector assignment, priority scoring
- Payment reminders: Email, SMS, phone integration, multi-language support
- Collections reporting: Aging reports, collection effectiveness, DSO tracking

E-INVOICING & COMPLIANCE:
- Peppol e-invoicing: EU compliance, automated routing, digital signatures
- Tax compliance: VAT, GST, sales tax calculation across 30+ countries
- Document standards: UBL, XML, PDF/A-3, CII formats
- Audit requirements: Immutable records, compliance reporting, archival

TECHNICAL ARCHITECTURE:
REST API:
- 200+ endpoints covering all AP/AR functionality
- Webhook system: Real-time notifications for 50+ events
- Rate limiting: 1000 requests/minute per API key
- Authentication: OAuth 2.0, API keys with scoping, JWT tokens
- API versioning: Semantic versioning with backward compatibility

SDKs & Integration:
- React SDK: Pre-built components, hooks, TypeScript support
- JavaScript SDK: Vanilla JS, Node.js support, Promise-based
- Python SDK: Full API coverage, async support, type hints
- Webhook handling: Signature verification, retry logic, dead letter queues

UI Components:
- Embedded iframes: White-label UI, responsive design, mobile-optimized
- React components: Customizable, theme support, accessibility compliant
- Hosted pages: Payment pages, invoice portals, vendor onboarding

Data Architecture:
- Real-time sync: Bi-directional with accounting platforms
- Data mapping: Flexible field mapping, custom categorization
- Conflict resolution: Automated and manual conflict handling
- Data retention: Configurable retention policies, GDPR compliance

ACCOUNTING INTEGRATIONS:
Supported Platforms (40+):
- Enterprise: NetSuite, SAP, Oracle, Microsoft Dynamics
- SMB: QuickBooks Online/Desktop, Xero, Sage, FreshBooks, Wave
- Specialized: Zoho Books, Kashoo, Manager, GnuCash

Sync Capabilities:
- Chart of accounts: Real-time sync, custom mapping, hierarchy support
- Tax rates: Automated tax code mapping, multi-jurisdiction support
- Customers/Vendors: Contact sync, payment terms, custom fields
- Transactions: Invoice sync, payment matching, reconciliation

COMPLIANCE & SECURITY:
- SOC 2 Type II certified
- PCI DSS Level 1 compliant
- GDPR compliant with data residency options
- Bank-level encryption (AES-256)
- Multi-factor authentication
- Role-based access control

DEPLOYMENT & IMPLEMENTATION:
- Cloud-native: AWS/Azure deployment, 99.9% uptime SLA
- Data centers: EU (Frankfurt), US (Virginia), with data residency options
- Implementation: 2-week average, dedicated implementation team
- Support: 24/7 technical support, dedicated customer success manager
- Monitoring: Real-time system monitoring, automated alerting

PRICING MODEL:
- Transaction-based pricing: Percentage of payment volume
- Revenue sharing: Optional for platform partners
- Usage-based API pricing: Per API call beyond included limits
- No setup fees, no monthly minimums for basic tier"""

def generate_analysis(url, analysis_result):
    """Generate competitive analysis using OpenAI"""
    
    monite_context = get_monite_context()
    
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
    
    threat_guidance = {
        'direct_scraping': 'Provide comprehensive threat analysis based on actual website content',
        'intelligence_gathering': 'Assign MEDIUM threat for any business software/fintech domain. Focus on manual research recommendations',
        'failed': 'Focus on domain analysis and recommend manual research'
    }.get(method, 'Focus on available evidence')
    
    prompt = f"""You are a neutral competitive intelligence analyst evaluating a potential competitor to Monite's AP/AR automation platform. Provide an OBJECTIVE, data-driven analysis based solely on the evidence gathered.

COMPETITOR: {company_name}
URL: {url}
DATA SOURCE: {data_quality_note}
ANALYSIS METHOD: {method}

INTELLIGENCE GATHERED:
{content}

MONITE REFERENCE (for comparison only):
{monite_context}

ANALYSIS FRAMEWORK:
Provide a completely objective analysis with NO bias toward either company. Base ALL conclusions on concrete evidence from the gathered intelligence.

THREAT LEVEL CRITERIA (strictly evidence-based):
🔴 HIGH THREAT: Direct AP/AR automation competitor with similar functionality AND target market
- Must have: Bill processing/capture OR invoice management OR payment automation
- Must have: Clear B2B focus and automation features
- Examples: Bill.com, Melio, comprehensive AP/AR platforms

🟡 MEDIUM THREAT: Overlapping functionality but different primary focus OR partial AP/AR features
- Has some AP/AR features but not comprehensive
- Different target market but some overlap
- Examples: Expense management tools with bill pay, accounting software with basic AP

💚 LOW THREAT: Minimal functional overlap OR clearly different market/use case
- No clear AP/AR automation features
- Different target market (B2C, different vertical)
- Basic invoicing without automation

FORMAT REQUIREMENTS:

*THREAT LEVEL:* [Based ONLY on evidence - explain reasoning]

*EVIDENCE-BASED ASSESSMENT:*
[2-3 sentences based purely on factual findings, no assumptions]

*FUNCTIONAL ANALYSIS:*
**AP (Accounts Payable) Capabilities:**
- Bill capture/processing: [What evidence shows vs Monite's OCR/email forwarding]
- Approval workflows: [Evidence found vs Monite's multi-step chains]
- Payment execution: [Their methods vs Monite's ACH/wire/international]
- Vendor management: [Evidence vs Monite's vendor portal/onboarding]

**AR (Accounts Receivable) Capabilities:**
- Invoice creation: [Evidence vs Monite's templates/recurring billing]
- Payment collection: [Evidence vs Monite's payment links/multi-method]
- Customer management: [Evidence vs Monite's credit limits/terms]
- Collections/dunning: [Evidence vs Monite's automated sequences]

*API & TECHNICAL COMPARISON:*
[Compare based on actual API documentation found vs Monite's 200+ endpoints/SDKs]
- API coverage: [Evidence found]
- Developer tools: [SDKs, documentation quality]
- Integration capabilities: [Evidence vs Monite's 40+ accounting platforms]

*OBJECTIVE COMPETITIVE POSITIONING:*
**Areas where competitor appears stronger:** [Based on evidence only]
**Areas where Monite appears stronger:** [Based on evidence only]  
**Unclear/requires investigation:** [What we couldn't determine]

*RESEARCH RECOMMENDATIONS:*
- **Immediate priorities:** [Specific areas needing verification]
- **Manual research needed:** [Exact steps to gather missing data]
- **Monitoring:** [What to track over time]

CRITICAL INSTRUCTIONS:
- NO promotional language for either company
- NO assumptions beyond available evidence
- When evidence is limited, clearly state limitations
- Focus on specific AP/AR functionality, not generic "financial workflows"
- Compare technical specifications when available
- If API docs were found, provide detailed technical comparison"""
    
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
        analysis_result = analyze_competitor_intelligent(url)
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
