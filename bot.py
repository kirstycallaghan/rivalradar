import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import time

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Your OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

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
        
    # Handle common title patterns
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

def analyze_competitor_simple(url):
    """Simple competitor analysis without overthinking"""
    print(f"🔍 Analyzing: {url}")
    
    company_name = extract_company_name_from_url(url)
    
    # Try basic request first
    response = simple_request(url)
    
    if response and response.status_code == 200:
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find('title').text if soup.find('title') else "No title"
            
            # Get main content
            content = soup.get_text()
            
            # Clean up content
            content = ' '.join(content.split())[:3000]
            
            if len(content.strip()) > 100:
                company_name = extract_company_name_smart(title)
                
                return {
                    'success': True,
                    'title': title,
                    'content': content,
                    'company_name': company_name,
                    'status': f"Successfully analyzed {url}"
                }
        except Exception as e:
            print(f"❌ Error parsing content: {e}")
    
    # If we get here, something failed
    if response:
        status_msg = f"Got HTTP {response.status_code} from {url}"
        if response.status_code == 403:
            status_msg += " (Forbidden - try manual research)"
        elif response.status_code == 404:
            status_msg += " (Not Found - check URL)"
        elif response.status_code == 500:
            status_msg += " (Server Error - site may be down)"
    else:
        status_msg = f"Could not connect to {url}"
    
    return {
        'success': False,
        'title': f"{company_name} - Limited Access",
        'content': f"Could not fully analyze {url}. {status_msg}. Based on the domain, this appears to be {company_name}. Manual research recommended: check their LinkedIn, about page, or Google '{company_name} features' for competitive intelligence.",
        'company_name': company_name,
        'status': status_msg
    }

def search_company_news_simple(company_name):
    """Simple news search without Google scraping"""
    print(f"📰 Looking for news about {company_name}...")
    
    # Try to find company blog/news
    possible_domains = [f"{company_name.lower()}.com", f"{company_name.lower()}.io"]
    news_paths = ["/blog", "/news", "/press"]
    
    for domain in possible_domains:
        for path in news_paths:
            try:
                news_url = f"https://{domain}{path}"
                response = simple_request(news_url)
                if response and response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    # Look for recent posts
                    articles = soup.find_all(['article', 'h2', 'h3'])[:3]
                    if articles:
                        news_items = []
                        for article in articles:
                            text = article.get_text().strip()[:100]
                            if text and len(text) > 20:
                                news_items.append(f"• {text}")
                        if news_items:
                            return "\n".join(news_items)
            except:
                continue
    
    return "No recent news found"

def generate_analysis(url, analysis_result, news):
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
    
    prompt = f"""
Analyze this potential competitor to Monite's AP/AR automation platform.

COMPETITOR: {company_name}
URL: {url}
ANALYSIS STATUS: {status}
PAGE TITLE: {title}

WEBSITE CONTENT:
{content}

RECENT NEWS:
{news}

{monite_context}

Please provide analysis in this format:

*THREAT LEVEL:* 🔴 HIGH / 🟡 MEDIUM / 💚 LOW

*QUICK ASSESSMENT:*
[2-3 sentences on threat level and why]

*KEY FINDINGS:*
[What we learned about their capabilities]

*COMPETITIVE COMPARISON:*
**Their Strengths:** [vs Monite]
**Their Weaknesses:** [vs Monite]  
**Monite Advantages:** [Clear differentiators]

*RECOMMENDED ACTIONS:*
- [For Product Team]
- [For Sales Team]
- [For further research]

GUIDELINES:
- HIGH threat: Direct AP/AR competitor with strong capabilities
- MEDIUM threat: Related business software with some overlap
- LOW threat: Different market or limited capabilities
- Be concise and actionable
- If analysis was limited, focus on what we can reasonably infer and next steps
"""
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"❌ AI analysis failed: {str(e)}\n\nManual analysis needed for {company_name} at {url}"

def analyze_competitor_url(url):
    """Main function to analyze competitor URL"""
    print(f"🚨 Starting RivalRadar analysis: {url}")
    
    try:
        # Analyze the website
        analysis_result = analyze_competitor_simple(url)
        
        # Search for news
        news = search_company_news_simple(analysis_result['company_name'])
        
        # Generate AI analysis
        analysis = generate_analysis(url, analysis_result, news)
        
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
    
    print(f"🔍 Reaction detected: {event['reaction']}")
    
    if event["reaction"] == "satellite_antenna":
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

@app.command("/analyze")
def analyze_command(ack, respond, command):
    """Direct analysis command for testing"""
    ack()
    url = command['text'].strip()
    if url:
        try:
            analysis = analyze_competitor_url(url)
            respond(f"🚨 *RivalRadar Analysis*\n\n{analysis}")
        except Exception as e:
            respond(f"❌ Analysis failed: {str(e)}")
    else:
        respond("Please provide a URL: `/analyze https://competitor.com`")

@app.command("/rivalradar")
def health_check(ack, respond):
    """Health check command"""
    ack()
    respond("🚨 RivalRadar is online! React with 📡 to any URL or use `/analyze <url>`")

if __name__ == "__main__":
    print("🚨 Starting RivalRadar...")
    
    # Check environment variables
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "OPENAI_API_KEY"]
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        exit(1)
    
    try:
        handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        handler.start()
        print("✅ RivalRadar ready! React with 📡 to any URL to trigger analysis!")
    except Exception as e:
        print(f"❌ Failed to start: {e}")
