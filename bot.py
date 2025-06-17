import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
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
    def extract_company_name_smart(title):
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
    
    return extract_company_name_smart(title)

def analyze_competitor_url(url):
    """Analyze a competitor URL and generate intelligence"""
    print(f"🔍 Analyzing: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.find('title').text if soup.find('title') else "No title"
        text_content = soup.get_text()[:3000]
        
        print(f"📄 Page title: {title}")
        print("✅ Successfully grabbed page content")
        
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
            print("❌ No substantial API documentation found")
        
        print("🤖 Sending to AI for analysis...")
        
        # Complete Monite context
        monite_context = """
        MONITE'S COMPLETE CAPABILITIES FOR COMPARISON:
        
        Core API Endpoints:
        - Accounts Receivable: Create quotes/invoices, auto-recurring invoices, payment links, reconciliation
        - Accounts Payable: Submit bills, OCR invoice capture, approval workflows
        - Payments: Payment intents, automated bill payment, payment links, multiple payment methods
        - E-Invoicing: Legally compliant e-invoices across 30+ jurisdictions
        - Accounting Integration: 40+ accounting systems sync (QuickBooks, Xero, NetSuite, etc.)
        - Utilities: File management, OCR, PDF generation, entity onboarding
        
        Integration Options:
        - Full REST API for backend control
        - React UI SDK with reusable components
        - Drop-in components (framework-agnostic)
        
        Key Differentiators:
        - Microservice-based scalable architecture with redundancy/failover
        - AI-enhanced workflows (OCR & reconciliation)
        - Full lifecycle management (onboarding to deactivation)
        - Developer-first platform with interactive API explorer, sandbox, SDKs
        - Embedded finance designed for marketplaces, neobanks, B2B SaaS
        - 2-week implementation timeline
        - Global compliance ready (30+ countries, multi-currency)
        - Best-in-class Developer Experience (DevPortal Awards 2023 nominations)
        - Revenue sharing model (0.1-2% on transactions)
        """
        
        prompt = f"""
        You are Steve Jobs analyzing a competitor to Monite. Monite is WINNING deals - be confident but strategic about threats.

        COMPETITOR: {company_name}
        Data: {text_content}
        News: {recent_news}
        API Analysis: {api_analysis if api_analysis else "No API docs found"}

        {monite_context}

        CONTEXT: Monite regularly competes against and BEATS major competitors like Codat in deals. Analyze from a position of strength.

        STEVE JOBS ANALYSIS - BE DIRECT BUT CONFIDENT:

        **THREAT LEVEL: [HIGH if direct feature overlap + same market / MEDIUM if adjacent / LOW if different focus]**

        **WHY THIS THREAT LEVEL:** [Specific overlapping capabilities, but note where Monite has advantages]

        **RECENT INTEL:** {recent_news}

        **COMPETITIVE REALITY CHECK:**
        - Their approach vs Monite's winning strategy: [How do they compete and why do we usually win?]
        - Their strengths we need to watch: [Real threats to address]
        - Our advantages they can't match: [Why prospects choose Monite]
        - Market positioning battle: [Who owns what narrative]

        **WHAT THEY DO WELL:** [Honest assessment of their strengths]

        **WHERE MONITE WINS:** [Specific advantages that win deals - be confident about these]

        **IMMEDIATE ACTIONS:**
        - Product team: [Investigate specific capabilities, but from position of strength]
        - Sales team: [Emphasize winning differentiators]
        - Technical team: [Enhance advantages, monitor their developments]

        **BATTLE STRATEGY:**
        - Lead conversations with: [Monite's proven winning points]
        - Neutralize their strength by: [How to counter their best features]
        - Close deals by asking: [Questions that highlight Monite's advantages]

        **SUMMARY:**
        [Direct advice that reflects Monite's competitive success - confident but not complacent. 2-3 sentences max.]

        FORMAT FOR SLACK:
- Use *bold text* for headers (not **bold**)
- Add blank lines between sections for spacing
- Use emoji for threat level: 🔴 HIGH, 🟡 MEDIUM, 💚 LOW
- Keep it clean and readable in Slack

Remember: Monite wins deals for good reasons. Analyze threats but maintain confidence in our proven advantages.

        """
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900
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
                        text=f"🚨 **RivalRadar Analysis**\n\n{analysis}",
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
        respond(f"🚨 **RivalRadar Analysis**\n\n{analysis}")
    else:
        respond("Please provide a URL to analyze: `/analyze https://competitor.com`")

if __name__ == "__main__":
    # Add your tokens and uncomment to run

    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))


    handler.start()
    print("🚨 RivalRadar ready! React with 📡 or 🔍 to any URL to trigger analysis!")
    print("Emoji trigger system loaded - no more automatic URL analysis!")