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
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def simple_request(url):
    """Simple request function"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        return response
    except:
        return None

def extract_company_name_from_url(url):
    """Extract company name from URL"""
    try:
        domain = url.replace('https://', '').replace('http://', '').replace('www.', '')
        return domain.split('.')[0].capitalize()
    except:
        return "Unknown Company"

def get_monite_context():
    """Get Monite context - keeping it simple to avoid syntax issues"""
    return """Monite is an embedded AP/AR automation platform targeting:
- Vertical SaaS platforms (healthcare, construction, staffing, professional services)
- Horizontal SaaS platforms (marketplaces, neobanks, business tools)

Key AP capabilities: OCR bill capture, approval workflows, vendor management, ACH/wire payments
Key AR capabilities: Invoice creation, payment collection, dunning, customer management
Technical: 200+ API endpoints, React/JS/Python SDKs, 40+ accounting integrations
Implementation: 2-week average, transaction-based revenue sharing model

Direct competitors include: Bill.com, Melio, Mercoa, and other embedded AP/AR platforms"""

def analyze_competitor_simple(url):
    """Simple competitor analysis"""
    company_name = extract_company_name_from_url(url)
    
    response = simple_request(url)
    
    if response and response.status_code == 200:
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find('title').text if soup.find('title') else "No title"
            content = soup.get_text()
            content = ' '.join(content.split())[:2000]
            
            if len(content.strip()) > 100:
                return {
                    'success': True,
                    'title': title,
                    'content': content,
                    'company_name': company_name
                }
        except:
            pass
    
    return {
        'success': False,
        'title': f"{company_name} - Limited Access",
        'content': f"Could not fully analyze {url}. Manual research recommended.",
        'company_name': company_name
    }

def generate_analysis(url, result):
    """Generate AI analysis"""
    monite_context = get_monite_context()
    
    prompt = f"""Analyze this competitor to Monite's embedded AP/AR automation platform.

COMPETITOR: {result['company_name']}
URL: {url}
SUCCESS: {result['success']}

WEBSITE CONTENT:
{result['content']}

MONITE CONTEXT:
{monite_context}

Provide analysis with:

THREAT LEVEL: HIGH/MEDIUM/LOW
- HIGH: Direct AP/AR competitor targeting SaaS platforms with automation features
- MEDIUM: Some AP/AR overlap but different focus
- LOW: Minimal overlap or different market

EVIDENCE-BASED ASSESSMENT:
[What the evidence shows about their capabilities]

FUNCTIONAL COMPARISON:
AP Capabilities: [Their bill processing, workflows, payments vs Monite]
AR Capabilities: [Their invoicing, collections, customer management vs Monite]

COMPETITIVE POSITIONING:
Where competitor appears stronger: [Based on evidence]
Where Monite appears stronger: [Based on evidence]

ACTIONABLE RECOMMENDATIONS:
For Product Team: [Specific features to investigate or enhance]
For Sales Team: [Key advantages to emphasize, competitor gaps to highlight]
For Research: [Manual research priorities]

Be objective, focus on AP/AR functionality, and make recommendations actionable."""

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Analysis failed: {str(e)}"

def analyze_competitor_url(url):
    """Main analysis function"""
    print(f"🚨 Analyzing: {url}")
    
    try:
        result = analyze_competitor_simple(url)
        analysis = generate_analysis(url, result)
        return analysis
    except Exception as e:
        return f"RivalRadar analysis failed: {str(e)}"

def extract_urls_from_text(text):
    """Extract URLs from text"""
    return re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)

@app.event("reaction_added")
def handle_reaction_added(event, say):
    """Handle reaction trigger"""
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
                urls = extract_urls_from_text(message.get("text", ""))
                
                if urls:
                    app.client.reactions_add(
                        channel=event["item"]["channel"],
                        timestamp=event["item"]["ts"],
                        name="eyes"
                    )
                    
                    analysis = analyze_competitor_url(urls[0])
                    
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
                        text="📡 No URLs found in message!",
                        thread_ts=event["item"]["ts"],
                        channel=event["item"]["channel"]
                    )
        except Exception as e:
            say(
                text=f"❌ Error: {str(e)}",
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
    respond("🚨 RivalRadar is online! React with 📡 to any URL or use `/analyze <url>`")

if __name__ == "__main__":
    print("🚨 Starting RivalRadar...")
    
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "OPENAI_API_KEY"]
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        exit(1)
    
    try:
        handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        handler.start()
        print("✅ RivalRadar ready!")
    except Exception as e:
        print(f"❌ Failed to start: {e}")
