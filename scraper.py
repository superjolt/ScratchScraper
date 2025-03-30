from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import concurrent.futures
import requests

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

SCRATCH_USER_PROFILE = "https://scratch.mit.edu/users/{}/"

def get_following_count(username):
    """Use Selenium to scrape the number of people a user is following."""
    url = SCRATCH_USER_PROFILE.format(username)

    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        driver.get(url)
        driver.implicitly_wait(5)  # Wait for elements to load

        # Get the number of users in the following list
        following_elements = driver.find_elements(By.CSS_SELECTOR, ".scroll-content .user.thumb.item")
        
        return len(following_elements)

    except Exception as e:
        print(f"Error scraping following count for {username}: {e}")
        return "N/A"

    finally:
        driver.quit()


def main():
    usernames = ["griffpatch", "johnm", "mres", "natalie"]  # Replace with your list

    # Use ProcessPoolExecutor instead of ThreadPoolExecutor
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(get_following_count, usernames))

    for username, count in zip(usernames, results):
        print(f"{username} is following {count} users.")


# Ensure this runs only when script is executed directly
if __name__ == "__main__":
    main()
