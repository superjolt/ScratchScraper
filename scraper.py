from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import itertools
import string

def generate_usernames(length=3):
    """Generates potential usernames, yielding 'superjolt' first, then combinations (e.g., 'a', 'aa', 'aaa', ...)."""
    yield "superjolt"
    chars = string.ascii_lowercase
    for comb in itertools.product(chars, repeat=length):
        yield ''.join(comb)

def check_user_exists(username):
    """Checks if a Scratch profile exists by looking for 'Joined' or 'About me' sections."""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # Run in the background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(f"https://scratch.mit.edu/users/{username}/")
        time.sleep(1)

        page_source = driver.page_source.lower()
        
        # Check if "joined" or "about me" sections exist (indicating a valid profile)
        if "joined" in page_source or "about me" in page_source:
            print(f"✅ Found: {username}")
            return True
        else:
            print(f"❌ Not found: {username}")
            return False
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return False
    finally:
        driver.quit()


def get_following_list(username):
    """Extracts the full list of users that 'username' is following."""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        url = f"https://scratch.mit.edu/users/{username}/following/"
        driver.get(url)
        time.sleep(2)  # Allow page to load
        
        # Scroll down multiple times to load all following
        body = driver.find_element(By.TAG_NAME, "body")
        for _ in range(5):  # Adjust scroll count if needed
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(1)

        # Extract usernames
        following_elements = driver.find_elements(By.CSS_SELECTOR, ".user-following .title")
        following_list = [user.text for user in following_elements]

        return following_list
    except Exception as e:
        print(f"Error fetching {username}: {e}")
        return []
    finally:
        driver.quit()

def recursive_scrape(start_usernames, depth=2):
    """Recursively scrapes following lists up to 'depth' levels."""
    visited = set()
    queue = list(start_usernames)
    data = {}

    for _ in range(depth):
        new_queue = []
        for username in queue:
            if username in visited:
                continue
            visited.add(username)
            print(f"Scraping {username}...")
            following = get_following_list(username)
            data[username] = following
            new_queue.extend(following)  # Add new users to scrape
        queue = new_queue  # Move to the next level

    return data

def save_to_file(data, filename="following_data.txt"):
    """Saves the following data to a text file."""
    with open(filename, "w", encoding="utf-8") as f:
        for user, followings in data.items():
            f.write(f"{user} is following {len(followings)} users:\n")
            f.write(", ".join(followings) + "\n\n")
    print(f"Data saved to {filename}")

if __name__ == "__main__":
    # Step 1: Brute-force username discovery
    found_users = []
    for username in generate_usernames(2):  # Adjust length for more coverage
        if check_user_exists(username):
            found_users.append(username)
        if len(found_users) >= 10:  # Stop after finding 10 valid users
            break

    # Step 2: Start recursive scraping from discovered users
    if found_users:
        following_data = recursive_scrape(found_users, depth=2)
        save_to_file(following_data)
    else:
        print("No valid users found. Try increasing username length.")
