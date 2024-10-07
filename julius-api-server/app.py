from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from browserbase import Browserbase
from scrapegraphai.graphs import OmniScraperGraph
import os
from dotenv import load_dotenv
import asyncio
from playwright.async_api import async_playwright, Page
from loguru import logger
import httpx
import json

load_dotenv()

# Configure loguru
logger.remove()  # Remove default handler
logger.add("app.log", rotation="10 MB", retention="1 week", level="INFO")
logger.add(lambda msg: print(msg, flush=True), level="INFO")  # Also log to console

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

browserbase = Browserbase(os.getenv('BROWSERBASE_API_KEY'), os.getenv('BROWSERBASE_PROJECT_ID'))

COOKIE_FILE = "cookies.json"
SITE_URL = "https://julius.ai"
SITE_LOGIN_URL = "https://auth.julius.ai/"
SITE_PROTECTED_URL = "https://julius.ai/chat"

class PromptRequest(BaseModel):
    prompt: str
    email: str
    password: str

async def create_browserbase_session():
    url = "https://www.browserbase.com/v1/sessions"
    headers = {
        "X-BB-API-Key": os.getenv('BROWSERBASE_API_KEY'),
        "Content-Type": "application/json"
    }
    payload = {
        "projectId": os.getenv('BROWSERBASE_PROJECT_ID'),
        "browserSettings": {
            "blockAds": True,
            "solveCaptchas": True,
            "recordSession": True,
            "logSession": True
        },
        "proxies": True,
        "timeout": 600  # 10 minutes, adjust as needed
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return response.json()['id']
    else:
        raise HTTPException(status_code=500, detail=f"Failed to create Browserbase session: {response.text}")

def store_cookies(browser_tab: Page):
    # Retrieve all the cookies for this URL
    all_cookies = browser_tab.context.cookies(SITE_URL)

    # You might want to put these in some durable storage, but for now
    # just keep them in a simple file as JSON.
    with open(COOKIE_FILE, "w") as cookie_file:
        json.dump(all_cookies, cookie_file, indent=4)

    print(f"Saved {len(all_cookies)} cookie(s) from the browser context")


async def restore_cookies(browser_tab: Page):
    # Return all cookies to the browser context
    try:
        with open(COOKIE_FILE) as cookie_file:
            cookies = json.load(cookie_file)
    except FileNotFoundError:
        # No cookies to restore
        return

    await browser_tab.context.add_cookies(cookies)
    logger.info(f"Restored {len(cookies)} cookie(s) to the browser context")

async def get_session_live_url(session_id: str):
    url = f"https://www.browserbase.com/v1/sessions/{session_id}/debug"
    headers = {
        "X-BB-API-Key": os.getenv('BROWSERBASE_API_KEY')
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
    if response.status_code == 200:
        live_urls = response.json()
        return live_urls.get('debuggerFullscreenUrl')
    else:
        logger.error(f"Failed to get session live URL: {response.text}")
        return None

async def login_to_julius(page, email: str, password: str):
    logger.info(f"Attempting to log in to Julius.ai with email: {email}")

    await restore_cookies(page)

    await page.goto('https://julius.ai/chat?iss=https%3A%2F%2Fauth.julius.ai%2F')

    await page.wait_for_selector('button:has-text("Continue with email")')
    await page.click('button:has-text("Continue with email")')
    await page.wait_for_load_state('networkidle')  # Wait until the page is fully loaded

    logger.info(f"Clicked 'Continue with email' button. Current URL: {page.url}")
    
    await page.wait_for_selector('input[name="username"][id="username"][type="text"][autocomplete="email"]')
    await page.fill('input[name="username"][id="username"][type="text"][autocomplete="email"]', email)
    logger.info(f"Filled email field with: {email}")
    await page.wait_for_selector('input[name="password"][id="password"][type="password"][autocomplete="current-password"]')
    await page.fill('input[name="password"][id="password"][type="password"][autocomplete="current-password"]', password)
    logger.info(f"Filled password field with: {password}")
    await page.screenshot(path="beforewait.png", full_page=True)

    await page.wait_for_timeout(5000)

    await page.screenshot(path="screenshotbefore.png", full_page=True)

    await page.click('button[type="submit"][name="action"][value="default"][data-action-button-primary="true"]')

    await page.screenshot(path="screenshot.png", full_page=True)

    logger.info("Clicked 'Continue' button. Waiting for Julius.ai to load...")
    await page.wait_for_load_state('networkidle')  # Wait until the page is fully loaded

    if 'https://julius.ai/chat' in page.url:
        logger.success("Successfully logged in to Julius.ai with email")
    else:
        raise HTTPException(status_code=500, detail=f"Failed to log in to Julius.ai. Current URL: {page.url}")

async def wait_for_response(page):
    logger.info("Waiting for response from Julius.ai")
    await asyncio.sleep(45)
    logger.info("Wait time for response completed")
    return True

@app.post('/api/prompt')
async def prompt_julius(request: PromptRequest):
    logger.info("Received POST request to /api/prompt")
    
    try:
        logger.info("Initializing Playwright")
        async with async_playwright() as playwright:
            chromium = playwright.chromium
            logger.info("Creating Browserbase session")
            session_id = await create_browserbase_session()
            logger.info(f"Created Browserbase session with ID: {session_id}")
            
            logger.info("Connecting to Browserbase")
            browser = await chromium.connect_over_cdp(browserbase.get_connect_url())
            page = await browser.new_page()

            live_url = await get_session_live_url(session_id)
            logger.info(f"@Browserbase Live session URL: {live_url}")

            logger.info("Restoring cookies")
            await restore_cookies(page)

            if 'https://julius.ai/chat' in page.url:
                logger.info("Already logged in to Julius.ai")
            else:
                logger.info("Need to login to Julius.ai")
                await page.goto('https://julius.ai/chat?iss=https%3A%2F%2Fauth.julius.ai%2F')
                await login_to_julius(page, request.email, request.password)
            
            logger.info("Logged in to Julius.ai Sucessfully")

            logger.info(f"Submitting prompt: {request.prompt[:50]}...")  # Log first 50 chars of prompt
            await page.fill('textarea[data-cy="chat-input-box"]', request.prompt)
            await page.click('button[type="submit"]')
            
            if not await wait_for_response(page):
                logger.error("Timeout waiting for response from Julius.ai")
                raise HTTPException(status_code=500, detail="Timeout waiting for response")

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
                source=await page.content(),
                config=graph_config
            )

            result = omni_scraper_graph.run()

            response_text = result.get('text', '')
            response_code = result.get('code', '')

            logger.success("Successfully processed Julius.ai response")
            return {
                'text': response_text,
                'code': response_code,
                'live_url': live_url
            }
    except Exception as e:
        logger.exception(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    logger.info("Starting FastAPI server")
    uvicorn.run(app, host='127.0.0.1', port=5000)