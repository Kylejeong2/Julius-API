from flask import Flask, request, jsonify, session
from flask_cors import CORS
from browserbase import Browserbase, Session
from scrapegraphai.graphs import OmniScraperGraph
import os
from dotenv import load_dotenv
import time
from playwright.sync_api import sync_playwright
from loguru import logger

load_dotenv()

# Configure loguru
logger.remove()  # Remove default handler
logger.add("app.log", rotation="10 MB", retention="1 week", level="INFO")
logger.add(lambda msg: print(msg, flush=True), level="INFO")  # Also log to console

app = Flask(__name__)
CORS(app)

browserbase = Browserbase(os.getenv('BROWSERBASE_API_KEY'), os.getenv('BROWSERBASE_PROJECT_ID'))

# Add this new function to get the live URL
# def get_session_live_url(session_id):
#     session = Session(browserbase, session_id)
#     live_urls = session.get_live_urls()
#     return live_urls.get('debuggerFullscreenUrl')

def login_to_julius(page, email, password):
    logger.info(f"Attempting to log in to Julius.ai with email: {email}")

    page.goto('https://julius.ai/chat?iss=https%3A%2F%2Fauth.julius.ai%2F')

    page.wait_for_selector('button:has-text("Continue with email")')
    page.click('button:has-text("Continue with email")')

    logger.info(f"Clicked 'Continue with email' button. Current URL: {page.url}")

    page.fill('input[class="input c4053936d caff7ffcc"][inputmode="email"][name="username"][id="username"][type="text"][required][autocomplete="email"][autocapitalize="none"][spellcheck="false"][autofocus]', email)
    page.fill('input[class="input c4053936d cf01611a1"][name="password"][id="password"][type="password"][required][autocomplete="current-password"][autocapitalize="none"][spellcheck="false"]', password)
    page.click('button:has-text("Continue")')

    if 'https://julius.ai/chat' in page.url:
        logger.success("Successfully logged in to Julius.ai with email")
    else:
        logger.error(f"Failed to log in to Julius.ai. Current URL: {page.url}")
    
def wait_for_response(page):
    logger.info("Waiting for response from Julius.ai")
    # Wait for 45 seconds
    time.sleep(45)
    logger.info("Wait time for response completed")
    return True

@app.route('/api/prompt', methods=['POST'])
def prompt_julius():
    logger.info("Received POST request to /api/prompt")
    data = request.json
    prompt = data.get('prompt')
    email = data.get('email')
    password = data.get('password')
    
    if not all([prompt, email, password]):
        logger.error("Missing required fields in request")
        return jsonify({'error': 'Prompt, email, and password are required'}), 400

    try:
        logger.info("Initializing Playwright")
        with sync_playwright() as playwright:
            chromium = playwright.chromium
            logger.info("Connecting to Browserbase")
            browser = chromium.connect_over_cdp(browserbase.get_connect_url())
            page = browser.new_page()

            # session_id = browser.context.browser.browser_id
            # live_url = get_session_live_url(session_id)
            # logger.info(f"Live session URL: {live_url}")

            # Store the session ID
            # session['current_session_id'] = session_id

            logger.info("Logging in to Julius.ai")
            page.goto('https://julius.ai/chat?iss=https%3A%2F%2Fauth.julius.ai%2F')
            try:
                page.wait_for_selector('button:has-text("Continue with email")', timeout=5000)
                needToLogin = True
                logger.info("Need to login to Julius.ai")
            except:
                needToLogin = False
            
            if needToLogin:
                login_to_julius(page, email, password)
            else:
                logger.info("Already logged in to Julius.ai")
            
            logger.info(f"Submitting prompt: {prompt[:50]}...")  # Log first 50 chars of prompt
            page.fill('textarea[data-cy="chat-input-box"]', prompt)
            page.click('button[type="submit"]')
            
            if not wait_for_response(page):
                logger.error("Timeout waiting for response from Julius.ai")
                raise Exception("Timeout waiting for response")

            logger.info("Configuring OmniScraperGraph")
            graph_config = {
                "llm": {
                    "model": "gpt-4o-mini",
                    "api_key": os.getenv('OPENAI_API_KEY'),
                },
                "headless": True,
            }

            logger.info("Running OmniScraperGraph")
            omni_scraper_graph = OmniScraperGraph(
                prompt="Extract the text response and any code blocks from the Julius chat interface.",
                source=page.content(),
                config=graph_config
            )

            result = omni_scraper_graph.run()

            response_text = result.get('text', '')
            response_code = result.get('code', '')

            logger.success("Successfully processed Julius.ai response")
            return jsonify({
                'text': response_text,
                'code': response_code,
                # 'live_url': live_url
            })
    except Exception as e:
        logger.exception(f"An error occurred: {str(e)}")
        return jsonify({'error': str(e)}), 500

# # Add a new endpoint to get the live URL
# @app.route('/api/live-url', methods=['GET'])
# def get_live_url():
#     session_id = session.get('current_session_id')
#     if not session_id:
#         return jsonify({'error': 'No active session found'}), 404
    
#     live_url = get_session_live_url(session_id)
#     return jsonify({'live_url': live_url})

if __name__ == '__main__':
    logger.info("Starting Flask server")
    app.run(host='0.0.0.0', port=5000, debug=True)