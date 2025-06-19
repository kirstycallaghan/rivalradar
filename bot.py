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

import time
import random

def get_stealth_headers():
    """Generate realistic browser headers that rotate to avoid detection"""
    
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    # Rotate user agent randomly
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
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }
    
    return headers

def stealth_request(url, session=None):
    """Make a stealthy request that looks like a real browser visit"""
    if session is None:
        session = requests.Session()
    
    try:
        # Step 1: Get fresh headers
        headers = get_stealth_headers()
        
        # Step 2: Add realistic delay (humans don't browse instantly)
        time.sleep(random.uniform(1, 3))
        
        # Step 3: Make the request with realistic timeout
        response = session.get(
            url, 
            headers=headers, 
            timeout=15,
            allow_redirects=True
        )
        
        print(f"📡 Request to {url}: Status {response.status_code}")
        return response
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Stealth request failed: {e}")
        return None

def analyze_with_fallback_strategies(url):
    """Try multiple strategies to get competitor data"""
    print(f"🕵️ Deploying stealth analysis for: {url}")
    
    session = requests.Session()
    content_found = False
    title = "No title"
    full_content = ""
    company_name = ""
    
    # Strategy 1: Direct stealth scraping
    print("🎭 Strategy 1: Direct stealth scraping...")
    response = stealth_request(url, session)
    
    if response and response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('title').text if soup.find('title') else "No title"
        homepage_content = soup.get_text()[:2000]
        
        if len(homepage_content.strip()) > 100:
            print("✅ Direct scraping successful!")
            content_found = True
            full_content = f"HOMEPAGE CONTENT:\n{homepage_content}\n"
            
            # Try to get key pages too
            print("🔍 Looking for additional pages...")
            discovered_pages = discover_key_pages_stealth(url, soup, session)
            key_content = scrape_key_pages_stealth(discovered_pages, session)
            full_content += key_content
            
        else:
            print("⚠️ Direct scraping got minimal content")
    else:
        print("❌ Direct scraping blocked")
    
    # Strategy 2: Search-based intelligence gathering
    if not content_found:
        print("🕵️ Strategy 2: Search-based intelligence gathering...")
        company_name = extract_company_name_from_url(url)
        search_content = gather_company_intelligence(company_name)
        
        if search_content:
            print("✅ Found company intelligence via search!")
            full_content = f"COMPANY INTELLIGENCE FROM SEARCH:\n{search_content}\n"
            content_found = True
        else:
            print("❌ Search-based gathering also failed")
    
    # Strategy 3: Competitor database lookup (last resort)
    if not content_found:
        print("🔍 Strategy 3: Known competitor database...")
        known_info = check_known_competitor(url)
        if known_info:
            print("✅ Found in known competitor database!")
            full_content = f"KNOWN COMPETITOR INFO:\n{known_info}\n"
            content_found = True
    
    # Extract company name if not already done
    if not company_name:
        company_name = extract_company_name_smart(title) if title != "No title" else extract_company_name_from_url(url)
    
    return {
        'title': title,
        'content': full_content,
        'company_name': company_name,
        'content_found': content_found,
        'access_status': 'success' if content_found else 'blocked'
    }

def discover_key_pages_stealth(base_url, soup, session):
    """Discover key pages using stealth mode"""
    print("🕵️ Stealth page discovery...")
    
    key_page_patterns = [
        '/features', '/products', '/solutions', '/platform',
        '/accounts-payable', '/ap', '/bill-pay', '/invoicing',
        '/approval-workflow', '/workflows', '/automation'
    ]
    
    discovered_pages = []
    
    # Look for navigation links
    nav_links = soup.find_all(['nav', 'header']) + soup.find_all('div', class_=['nav', 'menu', 'header'])
    for nav in nav_links:
        links = nav.find_all('a', href=True)
        for link in links:
            href = link['href']
            text = link.get_text().lower().strip()
            
            if any(pattern in href.lower() for pattern in key_page_patterns) or \
               any(keyword in text for keyword in ['features', 'products', 'bill pay', 'workflow']):
                
                if href.startswith('/'):
                    full_url = base_url.rstrip('/') + href
                elif href.startswith('http') and base_url in href:
                    full_url = href
                else:
                    continue
                
                if full_url not in discovered_pages:
                    discovered_pages.append(full_url)
    
    # Try common patterns directly
    for pattern in key_page_patterns:
        potential_url = base_url.rstrip('/') + pattern
        discovered_pages.append(potential_url)
    
    return discovered_pages[:8]  # Limit to avoid too many requests

def scrape_key_pages_stealth(discovered_pages, session):
    """Scrape key pages using stealth mode with delays"""
    print("🕵️ Stealth key page analysis...")
    
    aggregated_content = ""
    successful_pages = 0
    
    for page_url in discovered_pages:
        if successful_pages >= 5:  # Limit to avoid suspicion
            break
            
        print(f"🔍 Stealthily checking: {page_url}")
        
        # Random delay between requests (humans don't browse instantly)
        time.sleep(random.uniform(2, 5))
        
        response = stealth_request(page_url, session)
        
        if response and response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            page_content = soup.get_text()[:1000]  # Limit per page
            
            if len(page_content.strip()) > 100:
                aggregated_content += f"\n\nKEY PAGE: {page_url}\nCONTENT: {page_content[:800]}\n"
                successful_pages += 1
                print(f"✅ Successfully analyzed: {page_url}")
        else:
            print(f"❌ Blocked: {page_url}")
    
    print(f"🎯 Successfully analyzed {successful_pages} key pages")
    return aggregated_content

def gather_company_intelligence(company_name):
    """Gather company intelligence from search when direct scraping fails"""
    try:
        print(f"🔍 Gathering intelligence on {company_name}...")
        
        # Search for company + key terms
        search_terms = [
            f"{company_name} accounts payable bill pay features",
            f"{company_name} AP automation capabilities",
            f"{company_name} business payments platform"
        ]
        
        intelligence = ""
        
        for search_term in search_terms:
            time.sleep(random.uniform(1, 3))  # Avoid rapid requests
            
            search_url = f"https://www.google.com/search?q={search_term.replace(' ', '+')}"
            headers = get_stealth_headers()
            
            try:
                response = requests.get(search_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Extract search snippets
                    snippets = []
                    for result in soup.find_all('div', class_='g')[:3]:
                        snippet = result.find('span', class_='st') or result.find('div', class_='s')
                        if snippet:
                            snippets.append(snippet.get_text()[:200])
                    
                    if snippets:
                        intelligence += f"Search for '{search_term}': " + " | ".join(snippets) + "\n\n"
                        
            except Exception as e:
                print(f"Search failed for {search_term}: {e}")
                continue
        
        return intelligence if intelligence else None
        
    except Exception as e:
        print(f"❌ Intelligence gathering failed: {e}")
        return None

def check_known_competitor(url):
    """Check if this is a known major competitor (fallback only)"""
    domain = url.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
    
    # Only include the most obvious major competitors as last resort
    known_competitors = {
        'meliopayments.com': 'Major AP bill pay platform for small businesses. Key features: vendor payments, approval workflows, ACH/check payments, QuickBooks integration. High threat in AP automation space.',
        'melio.com': 'Major AP bill pay platform for small businesses. Key features: vendor payments, approval workflows, ACH/check payments, QuickBooks integration. High threat in AP automation space.',
        'codat.io': 'Data connectivity platform for accounting integrations. Enables fintech access to business financial data. High threat for accounting integration space.',
        'bill.com': 'Established AP/AR automation platform. Full-featured bill pay, invoicing, approval workflows. Public company, major competitor.',
    }
    
    return known_competitors.get(domain)

# Updated main analysis function
def analyze_competitor_url(url):
    """Enhanced competitor analysis with stealth capabilities and fallback strategies"""
    print(f"🕵️ Starting stealth competitive analysis: {url}")
    
    try:
        # Use advanced stealth analysis
        analysis_result = analyze_with_fallback_strategies(url)
        
        title = analysis_result['title']
        full_content = analysis_result['content']
        company_name = analysis_result['company_name']
        access_status = analysis_result['access_status']
        
        print(f"🏢 Detected company name: {company_name}")
        print(f"📊 Access status: {access_status}")
        
        # Search for recent news (existing function)
        recent_news = search_recent_news(company_name)
        
        # Note: API docs search would use existing function
        api_analysis = "API documentation analysis skipped in stealth mode to avoid detection"
        
        print("🤖 Sending comprehensive intelligence to AI...")
        
        # [Include the same monite_context and enhanced prompt from previous version]
        # [Rest of the analysis logic remains the same]
        
        # Enhanced prompt that handles different content sources
        prompt = f"""
You are analyzing a competitor to Monite using intelligence gathered through multiple methods.

COMPETITOR DATA:
URL: {url}
Title: {title}
Company: {company_name}
Access Status: {access_status}
Content Source: {'Direct website analysis' if access_status == 'success' else 'Alternative intelligence gathering'}

COMPREHENSIVE INTELLIGENCE:
{full_content}

RECENT NEWS: {recent_news}

[Include full monite_context here]

ANALYSIS INSTRUCTIONS:
- If content source is "Direct website analysis" - analyze their actual capabilities thoroughly
- If content source is "Alternative intelligence" - note limitations but still provide threat assessment
- Be transparent about data limitations while still providing useful competitive analysis
- Focus on confirmed capabilities vs assumptions

[Include same analysis format as enhanced version]

IMPORTANT: Note any limitations in data access and distinguish between confirmed features and assumptions.
"""
        
        # Call OpenAI with enhanced analysis
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200
        )
        
        analysis = response.choices[0].message.content
        print("🎯 Stealth analysis complete!")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Stealth analysis failed: {e}")
        return f"❌ Analysis failed: {str(e)}"
        
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
