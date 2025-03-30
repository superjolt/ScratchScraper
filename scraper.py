import requests
import os
import re
import concurrent.futures
from bs4 import BeautifulSoup

# API Endpoints
SCRATCH_API_USERS = "https://api.scratch.mit.edu/users/{}"
SCRATCH_API_PROJECTS = "https://api.scratch.mit.edu/users/{}/projects/?limit=1&offset=0"
SCRATCH_USER_PROFILE = "https://scratch.mit.edu/users/{}/"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_usernames():
    """Fetch usernames from Scratch's explore projects API."""
    usernames = set()
    for offset in range(0, 200, 40):  # Adjust range to get more usernames
        url = f"https://api.scratch.mit.edu/explore/projects/?limit=40&offset={offset}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print("Failed to fetch usernames at offset", offset)
            continue
        projects = response.json()
        for project in projects:
            author = project.get("author", {})
            username = author.get("username")
            if username:
                usernames.add(username)
    return list(usernames)

def get_follower_count(username):
    """Scrape the follower count from Scratch profile page (HTML parsing)."""
    url = SCRATCH_USER_PROFILE.format(username)
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to scrape profile for {username}")
        return "N/A"

    soup = BeautifulSoup(response.text, "html.parser")
    script_tags = soup.find_all("script")
    
    for script in script_tags:
        pattern = r'{"count":(\d+),"user":"' + re.escape(username) + r'"}'
        match = re.search(pattern, script.text)
        if match:
            return match.group(1)

    return "N/A"

def get_user_details(username):
    """Fetch detailed user profile info from Scratch's API and scrape followers."""
    url = SCRATCH_API_USERS.format(username)
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to fetch data for {username}")
        return None
    
    data = response.json()
    profile = data.get("profile", {})
    history = data.get("history", {})

    # Extract relevant details
    user_info = {
        "Username": data.get("username"),
        "User ID": data.get("id"),
        "Joined": history.get("joined"),
        "About Me": profile.get("bio"),
        "What I'm Working On": profile.get("status"),
        "Country": profile.get("country"),
        "Profile Image": profile.get("images", {}).get("90x90"),
        "Followers": get_follower_count(username)  # Scrape followers
    }

    # Fetch project count
    project_url = SCRATCH_API_PROJECTS.format(username)
    project_response = requests.get(project_url, headers=HEADERS)
    if project_response.status_code == 200:
        projects = project_response.json()
        user_info["Projects Created"] = len(projects)
    else:
        user_info["Projects Created"] = "N/A"

    return user_info

def save_to_file(data, filename="scratch_users.txt"):
    """Save data to a .txt file, overwriting if it already exists."""
    with open(filename, "w", encoding="utf-8") as file:
        for user in data:
            file.write(f"Username: {user['Username']}\n")
            file.write(f"User ID: {user['User ID']}\n")
            file.write(f"Joined: {user['Joined']}\n")
            file.write(f"About Me: {user['About Me']}\n")
            file.write(f"What I'm Working On: {user['What I'm Working On']}\n")
            file.write(f"Country: {user['Country']}\n")
            file.write(f"Profile Image: {user['Profile Image']}\n")
            file.write(f"Followers: {user['Followers']}\n")
            file.write(f"Projects Created: {user['Projects Created']}\n")
            file.write("=" * 40 + "\n")

    print(f"Data saved to {filename}")

def main():
    usernames = get_usernames()
    print(f"Found {len(usernames)} usernames.")
    data = []

    # Multi-threaded fetching
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_user_details, user): user for user in usernames}
        for future in concurrent.futures.as_completed(futures):
            user_info = future.result()
            if user_info:
                data.append(user_info)
                print(f"Scraped: {user_info['Username']} ({user_info['Followers']} followers)")

    save_to_file(data)

if __name__ == "__main__":
    main()
