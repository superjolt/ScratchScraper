from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import concurrent.futures
import time

time.sleep(3)  # make sure the goofy page loads

def get_following_users(username):
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        url = f"https://scratch.mit.edu/users/{username}/following/"
        driver.get(url)

        time.sleep(2)
        
        scroll_count = 5 # increase this lol if it dosent load properly
        body = driver.find_element(By.TAG_NAME, "body")
        for _ in range(scroll_count):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(1)

        following_elements = driver.find_elements(By.XPATH, '//div[@class="media-grid"]//li[@class="user thumb item"]/span[@class="title"]/a')
        following_usernames = [element.text for element in following_elements]

        return following_usernames
    except Exception as e:
        print(f"Error: {e}")
        return []
    finally:
        driver.quit()


def main():
    usernames = ["griffpatch", "johnm", "mres", "natalie"]

    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(get_following_users, usernames))

    for username, following_list in zip(usernames, results):
        print(f"{username} is following {len(following_list)} users:")
        print(", ".join(following_list) if following_list else "No users found.")


if __name__ == "__main__":
    main()
