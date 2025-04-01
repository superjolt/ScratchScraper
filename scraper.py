import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_driver():
    """Creates and configures a new Selenium WebDriver instance."""
    opts = webdriver.ChromeOptions()
    # Run headless (no GUI)
    opts.add_argument("--headless")
    # Necessary arguments for running in restricted environments (like containers)
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # Try to prevent detection
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)

    try:
        # Initialize WebDriver using webdriver-manager to handle driver download/updates
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        # Add stealth measures
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                })
            '''
        })
        return driver
    except Exception as e:
        logging.error(f"Failed to create WebDriver: {e}")
        return None

def check_user_exists(username):
    """Checks if a Scratch user profile page exists."""
    driver = create_driver()
    if not driver:
        return False
    try:
        url = f"https://scratch.mit.edu/users/{username}/"
        logging.info(f"Checking user: {url}")
        driver.get(url)
        # Increased sleep time to allow page loading, especially in headless mode
        time.sleep(2)
        page_content = driver.page_source.lower()
        # Check for common profile elements
        exists = ("joined" in page_content or
                  "about me" in page_content or
                  "what i'm working on" in page_content or
                  "featured project" in page_content)
        logging.info(f"User '{username}' exists: {exists}")
        return exists
    except Exception as e:
        logging.error(f"Error checking user '{username}': {e}")
        return False
    finally:
        if driver:
            driver.quit()

def get_following_users(username):
    """Fetches the list of users a given Scratch user is following."""
    driver = create_driver()
    if not driver:
        return []
    users_followed = []
    try:
        url = f"https://scratch.mit.edu/users/{username}/following/"
        logging.info(f"Fetching following list for: {url}")
        driver.get(url)
        # Wait for initial content load
        time.sleep(3)

        # Scroll down to load more users (adjust range and sleep as needed)
        body = driver.find_element(By.TAG_NAME, "body")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 10 # Limit scrolling to prevent infinite loops

        while scroll_attempts < max_scroll_attempts:
            logging.info(f"Scrolling down page for {username} (Attempt {scroll_attempts + 1})")
            body.send_keys(Keys.PAGE_DOWN)
            # Wait for content to potentially load after scroll
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # If height didn't change, we might be at the bottom or content isn't loading
                logging.info(f"Scroll height didn't change for {username}, attempting one more scroll.")
                body.send_keys(Keys.PAGE_DOWN) # Try one last scroll
                time.sleep(2)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                   logging.info(f"Reached end of scroll for {username}.")
                   break # Exit loop if height still hasn't changed
            last_height = new_height
            scroll_attempts += 1

        # Extract usernames after scrolling
        user_elements = driver.find_elements(By.CSS_SELECTOR, ".media-grid li.user.thumb.item span.title a")
        users_followed = [el.text for el in user_elements if el.text] # Ensure text is not empty
        logging.info(f"Found {len(users_followed)} users followed by '{username}'.")
        return list(set(users_followed)) # Return unique list

    except Exception as e:
        logging.error(f"Error fetching following list for '{username}': {e}")
        return [] # Return empty list on error
    finally:
        if driver:
            driver.quit()

async def process_user(queue, visited_users, users_to_write_queue, executor):
    """Processes a single user: checks existence, gets following list, adds new users to queue."""
    loop = asyncio.get_running_loop()
    while True:
        username = await queue.get()
        if username is None: # Sentinel value to stop the worker
            await queue.put(None) # Put sentinel back for other workers
            break

        try:
            # Check if user exists (run synchronously in thread pool)
            exists = await loop.run_in_executor(executor, check_user_exists, username)

            if exists:
                # Get the list of users they follow (run synchronously in thread pool)
                followed_users = await loop.run_in_executor(executor, get_following_users, username)
                logging.info(f"User '{username}' follows {len(followed_users)} users.")

                newly_found_count = 0
                for user in followed_users:
                    if user and user not in visited_users: # Check if user is valid and not visited
                        visited_users.add(user) # Mark as visited
                        await queue.put(user)   # Add to the processing queue
                        await users_to_write_queue.put(user) # Add to the writing queue
                        newly_found_count += 1
                if newly_found_count > 0:
                     logging.info(f"Added {newly_found_count} new users to the queue from '{username}'s following list.")

            else:
                logging.warning(f"User '{username}' does not seem to exist or profile is inaccessible.")

        except Exception as ex:
            logging.error(f"Error processing user '{username}': {ex}")
        finally:
            queue.task_done() # Signal that this task is complete

async def write_users_to_file(users_to_write_queue, filename="scratch_users_list.txt"):
    """Writes usernames from the queue to the output file, one per line."""
    written_count = 0
    try:
        with open(filename, "w", encoding="utf-8") as f: # Open in 'w' mode to clear previous content
            logging.info(f"Opened '{filename}' for writing.")
            while True:
                username = await users_to_write_queue.get()
                if username is None: # Sentinel value to stop writer
                    users_to_write_queue.task_done()
                    break
                try:
                    f.write(f"{username}\n")
                    written_count += 1
                    if written_count % 100 == 0: # Log progress every 100 users
                        logging.info(f"Written {written_count} usernames to '{filename}'.")
                except Exception as e:
                     logging.error(f"Error writing username '{username}' to file: {e}")
                finally:
                    users_to_write_queue.task_done() # Signal task completion for this user
    except IOError as e:
        logging.error(f"Failed to open or write to file '{filename}': {e}")
    finally:
        logging.info(f"Finished writing. Total usernames written: {written_count}.")


async def main():
    """Main function to set up queues, tasks, and run the crawl."""
    # Initial list of users to start crawling from
    initial_users = ["superjolt", "griffpatch", "johnm", "mres", "natalie", "ScratchCat", "HollowGoblin", "chipm0nk", "GonSanVi", "ProdigyZeta7"]

    # Queue for users to be processed
    processing_queue = asyncio.Queue()
    # Queue for users to be written to the file
    users_to_write_queue = asyncio.Queue()

    # Set to keep track of users already visited or added to the queue
    visited_users = set(initial_users)

    # Add initial users to both queues
    for user in initial_users:
        await processing_queue.put(user)
        await users_to_write_queue.put(user) # Also write initial users

    # Determine the number of worker threads (adjust multiplier as needed)
    # Be mindful of system resources and potential rate limiting
    max_workers = min(os.cpu_count() * 2, 10) # Limit max workers
    logging.info(f"Using {max_workers} worker threads.")
    executor = ThreadPoolExecutor(max_workers=max_workers)

    # Create and start the file writer task
    writer_task = asyncio.create_task(write_users_to_file(users_to_write_queue))

    # Create and start worker tasks for processing users
    worker_tasks = [
        asyncio.create_task(process_user(processing_queue, visited_users, users_to_write_queue, executor))
        for _ in range(max_workers)
    ]

    # Wait for the processing queue to be empty
    await processing_queue.join()
    logging.info("Processing queue is empty. Signaling workers to stop.")

    # Signal worker tasks to stop by putting None (sentinel value)
    await processing_queue.put(None)

    # Wait for all worker tasks to complete
    await asyncio.gather(*worker_tasks, return_exceptions=True)
    logging.info("All worker tasks have finished.")

    # Signal the writer task to stop
    await users_to_write_queue.put(None)
    # Wait for the writer task to complete
    await writer_task
    logging.info("File writer task has finished.")

    # Shutdown the thread pool executor
    executor.shutdown(wait=True)
    logging.info("Thread pool executor shut down.")

if __name__ == "__main__":
    start_time = time.time()
    logging.info("Starting Scratch user crawl...")
    # Run the main asynchronous function
    asyncio.run(main())
    end_time = time.time()
    logging.info(f"Script finished in {end_time - start_time:.2f} seconds.")
