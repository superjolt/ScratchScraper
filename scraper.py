import asyncio
import itertools
import string
import time
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

def create_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def check_user_exists(username):
    driver = create_driver()
    try:
        driver.get(f"https://scratch.mit.edu/users/{username}/")
        time.sleep(1)
        page_source = driver.page_source.lower()
        if "joined" in page_source or "about me" in page_source:
            print(f"✅ Found: {username}")
            return username
        else:
            print(f"❌ Not found: {username}")
            return None
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return None
    finally:
        driver.quit()

def get_following_users(username):
    driver = create_driver()
    try:
        url = f"https://scratch.mit.edu/users/{username}/following/"
        driver.get(url)
        time.sleep(2)
        body = driver.find_element(By.TAG_NAME, "body")
        for _ in range(5):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(1)
        # Use CSS selector for the media-grid usernames
        following_elements = driver.find_elements(By.CSS_SELECTOR, ".media-grid li.user.thumb.item span.title a")
        following_usernames = [element.text for element in following_elements]
        print(f"👥 {username} follows {len(following_usernames)} users")
        return following_usernames
    except Exception as e:
        print(f"Error fetching followers for {username}: {e}")
        return []
    finally:
        driver.quit()

async def generate_usernames_to_queue(queue, length=3):
    # Push a known username first
    await queue.put("superjolt")
    chars = string.ascii_lowercase
    for comb in itertools.product(chars, repeat=length):
        username = ''.join(comb)
        await queue.put(username)
    # Signal completion by putting a None
    await queue.put(None)

async def process_usernames(queue, executor):
    while True:
        username = await queue.get()
        if username is None:
            # Signal the end to other workers
            await queue.put(None)
            break
        loop = asyncio.get_running_loop()
        valid_username = await loop.run_in_executor(executor, check_user_exists, username)
        if valid_username:
            followers = await loop.run_in_executor(executor, get_following_users, valid_username)
            print(f"📌 {valid_username} follows: {followers}")
        queue.task_done()

async def main():
    queue = asyncio.Queue()
    executor = ThreadPoolExecutor(max_workers=5)
    # Start the username generator coroutine
    generator_task = asyncio.create_task(generate_usernames_to_queue(queue, length=3))
    # Start several worker tasks to process usernames
    workers = [asyncio.create_task(process_usernames(queue, executor)) for _ in range(3)]
    await generator_task
    await queue.join()
    for worker in workers:
        worker.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
