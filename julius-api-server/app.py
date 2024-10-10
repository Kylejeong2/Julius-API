from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from browserbase import Browserbase
from scrapegraphai.graphs import SmartScraperGraph
import os
from dotenv import load_dotenv
import asyncio
from playwright.async_api import async_playwright, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from loguru import logger
import httpx
import json
import uvicorn
from bs4 import BeautifulSoup

load_dotenv()

logger.remove()
logger.add("app.log", rotation="10 MB", retention="1 week", level="INFO")
logger.add(lambda msg: print(msg, flush=True), level="INFO")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

class SolveState:
    started = False
    finished = False
    START_MSG = "browserbase-solving-started"
    END_MSG = "browserbase-solving-finished"

    def handle_console(self, msg):
        if msg.text == self.START_MSG:
            self.started = True
            logger.info("AI has started solving the CAPTCHA...")
        elif msg.text == self.END_MSG:
            self.finished = True
            logger.info("AI solved the CAPTCHA!")

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
            # "recordSession": True,
            # "logSession": True
        },
        "proxies": True,
        "timeout": 600  
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return response.json()['id']
    else:
        raise HTTPException(status_code=500, detail=f"Failed to create Browserbase session: {response.text}")

# async def get_session_live_url(session_id: str):
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

async def login_to_julius(page: Page, email: str, password: str):
    logger.info(f"Attempting to log in to Julius.ai with email: {email}")

    await restore_cookies(page)

    await page.goto('https://julius.ai/chat?iss=https%3A%2F%2Fauth.julius.ai%2F')

    await page.wait_for_selector('button:has-text("Continue with email")')
    await page.click('button:has-text("Continue with email")')
    await page.wait_for_load_state('networkidle')

    logger.info(f"Clicked 'Continue with email' button. Current URL: {page.url}")
    
    await page.wait_for_selector('input[name="username"][id="username"][type="text"][autocomplete="email"]')
    await page.fill('input[name="username"][id="username"][type="text"][autocomplete="email"]', email)
    logger.info(f"Filled email field with: {email}")
    await page.wait_for_selector('input[name="password"][id="password"][type="password"][autocomplete="current-password"]')
    await page.fill('input[name="password"][id="password"][type="password"][autocomplete="current-password"]', password)
    logger.info(f"Filled password field with: {password}")

    state = SolveState()
    page.on("console", state.handle_console)

    logger.info("Clicking 'Continue' button and waiting for potential CAPTCHA...")
    await page.click('button[type="submit"][name="action"][value="default"][data-action-button-primary="true"]')

    try:
        async with page.expect_console_message(
            lambda msg: msg.text == SolveState.END_MSG,
            timeout=30000,
        ):
            pass
    except PlaywrightTimeoutError:
        logger.warning("Timeout: No CAPTCHA solving event detected after 30 seconds")
        logger.info(f"Solve state: started={state.started}, finished={state.finished}")

    if state.started != state.finished:
        logger.warning(f"Solving mismatch! started={state.started}, finished={state.finished}")
    elif state.started == state.finished == False:
        logger.info("No CAPTCHA was presented, or was solved too quickly to detect.")
    else:
        logger.info("CAPTCHA is complete.")

    await page.wait_for_load_state('networkidle')

    if 'https://julius.ai/chat' in page.url:
        logger.success("Successfully logged in to Julius.ai")
        await store_cookies(page)
    else:
        raise HTTPException(status_code=500, detail=f"Failed to log in to Julius.ai. Current URL: {page.url}")

async def store_cookies(page):
    cookies = await page.context.cookies()
    with open("cookies.json", "w") as f:
        json.dump(cookies, f)
    logger.info("Stored cookies after successful login")

async def restore_cookies(page):
    try:
        with open("cookies.json", "r") as f:
            cookies = json.load(f)
        await page.context.add_cookies(cookies)
        await page.goto('https://julius.ai/chat')
        await page.wait_for_load_state('networkidle')

        if 'https://julius.ai/chat' in page.url:
            logger.info("Restored cookies from previous session")
        else:
            logger.info("Failed to restore cookies from previous session")
    except FileNotFoundError:
        logger.info("No stored cookies found")

async def wait_for_response(page):
    logger.info("Waiting for response from Julius.ai")
    await asyncio.sleep(45)
    logger.info("Wait time for response completed")
    return True

async def extract_content(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    target_div = soup.find_all('div', class_="relative flex flex-col w-full gap-2 py-3 sm:p-3 rounded-2xl sm:border sm:bg-gray-50 sm:border-gray-100 sm:dark:bg-neutral-800 sm:dark:border-neutral-800")[1]
    
    if target_div:
        return target_div.get_text(strip=True)
    else:
        logger.warning("Target div not found in the HTML content")
        return ""

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

            # live_url = await get_session_live_url(session_id)
            # logger.info(f"@Browserbase Live session URL: {live_url}")

            logger.info("Restoring cookies")
            await restore_cookies(page)

            if 'https://julius.ai/chat' in page.url:
                logger.info("Already logged in to Julius.ai")
            else:
                logger.info("Need to login to Julius.ai")
                await page.goto('https://julius.ai/chat?iss=https%3A%2F%2Fauth.julius.ai%2F')
                await login_to_julius(page, request.email, request.password)
            
            logger.info("Logged in to Julius.ai Successfully")

            logger.info(f"Submitting prompt: {request.prompt[:50]}...")
            await page.wait_for_selector('textarea[data-cy="chat-input-box"]')
            await page.fill('textarea[data-cy="chat-input-box"]', request.prompt)
            await page.click('button[type="submit"]')

            if not await wait_for_response(page):
                logger.error("Timeout waiting for response from Julius.ai")
                raise HTTPException(status_code=500, detail="Timeout waiting for response")

            logger.info("Getting page URL", page_url=page.url)
            page_url = page.url

            page_content = await page.content()
            logger.info("Extracted page content")

            extracted_text = await extract_content(page_content)
            logger.info("Extracted text from target div")

            graph_config = {
                "llm": {
                    "api_key": os.getenv('OPENAI_API_KEY'),
                    "model": "openai/gpt-4o-mini",
                },
                "verbose": True,
                "headless": True,
            }

            smart_scraper_graph = SmartScraperGraph(
                prompt="Extract the text response and any code blocks from the given content. Also, save the images generated by the ai if possible. Return a JSON with text, code, and images.",
                source=extracted_text,
                config=graph_config
            )

            result = smart_scraper_graph.run()

            logger.success("Successfully processed Julius.ai response")
            return {
                'result': result,
                'page_url': page_url
            }
    except Exception as e:
        logger.exception(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    logger.info("Starting FastAPI server")
    uvicorn.run(app, host='127.0.0.1', port=5000)