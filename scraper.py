import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

def create_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

def check_user_exists(username):
    driver = create_driver()
    try:
        driver.get(f"https://scratch.mit.edu/users/{username}/")
        time.sleep(1)
        page = driver.page_source.lower()
        return ("joined" in page or "about me" in page)
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return False
    finally:
        driver.quit()

def get_following_users(username):
    driver = create_driver()
    try:
        driver.get(f"https://scratch.mit.edu/users/{username}/following/")
        time.sleep(2)
        body = driver.find_element(By.TAG_NAME, "body")
        for _ in range(5):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(1)
        elements = driver.find_elements(By.CSS_SELECTOR, ".media-grid li.user.thumb.item span.title a")
        return [el.text for el in elements]
    except Exception as e:
        print(f"Error fetching followers for {username}: {e}")
        return []
    finally:
        driver.quit()

async def process_user(queue, visited, executor, file_lock):
    loop = asyncio.get_running_loop()
    while True:
        username = await queue.get()
        if username is None:
            await queue.put(None)
            break
        try:
            exists = await loop.run_in_executor(executor, check_user_exists, username)
            if exists:
                followers = await loop.run_in_executor(executor, get_following_users, username)
                print(f"📌 {username} follows {len(followers)}: {followers}")
                async with file_lock:
                    with open("following_data.txt", "a", encoding="utf-8") as f:
                        f.write(f"{username} follows {len(followers)}: {', '.join(followers)}\n")
                for user in followers:
                    if user not in visited:
                        visited.add(user)
                        await queue.put(user)
        except Exception as ex:
            print(f"Error processing {username}: {ex}")
        finally:
            queue.task_done()

async def main():
    initial = ["superjolt", "griffpatch", "johnm", "mres", "natalie", "ScratchCat", "HollowGoblin", "chipm0nk", "GonSanVi", "ProdigyZeta7"]
    queue = asyncio.Queue()
    visited = set(initial)
    for user in initial:
        await queue.put(user)
    file_lock = asyncio.Lock()
    max_workers = os.cpu_count() * 4
    executor = ThreadPoolExecutor(max_workers=max_workers)
    workers = [asyncio.create_task(process_user(queue, visited, executor, file_lock)) for _ in range(max_workers // 2)]
    await queue.join()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
