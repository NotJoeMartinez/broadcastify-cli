import os
import re
import json
import random
import requests
import sys

from dotenv import load_dotenv
from pprint import pprint


load_dotenv(".env")

def main():

    feed_id = sys.argv[1]
    date = sys.argv[2]

    user_agent = get_urser_agent()

    # load loagin cookie from cookies.json if it exists
    # otherwise get the login cookie and save it to cookies.json 
    if os.path.exists("cookies.json"):
        # cookies = json.load(open("cookies.json"))
        with open("cookies.json", encoding='utf-8', errors='ignore') as f:
            cookies = json.load(f)
        login_cookie = f"bcfyuser1={cookies['bcfyuser1']}" 
    else:
        username = os.getenv("USERNAME")
        passowrd = os.getenv("PASSWORD")
        login_cookie = get_login_cookie(username, passowrd, user_agent)

    
    download_archive_by_date(feed_id, date, "archives", user_agent, login_cookie)


def download_archive_by_date(feed_id, date, output_dir, user_agent, login_cookie):

    base_download_url = "https://www.broadcastify.com/archives/downloadv2"
    archive_ids = get_archive_ids(feed_id, date)

    date_dir_name = date.replace("/", "")

    os.makedirs(f"{output_dir}/{feed_id}", exist_ok=True)
    os.makedirs(f"{output_dir}/{feed_id}/{date_dir_name}", exist_ok=True)


    for id in archive_ids:
        # 04/17/2024 -> 20240417
        split_date = date.split("/")
        url_date = f"{split_date[2]}{split_date[0]}{split_date[1]}"
        url = f"{base_download_url}/{feed_id}/{url_date}/{id}" 

        current_output_dir = f"{output_dir}/{feed_id}/{date_dir_name}"
        download_mp3(url, current_output_dir, user_agent, login_cookie)


def download_mp3(url, output_dir, user_agent, login_cookie):

    user_agent = str(user_agent)

    headers = {
        "user-agent": user_agent,
        "cookie": login_cookie
    }

    response = requests.get(url, headers=headers, stream=True)

    file_name = response.url.split("/")[-1]
    output_path = os.path.join(output_dir, file_name)


    print(f"url: {url}")
    print(f"file_name: {file_name}")
    print(f"output_path: {output_path}")


    if response.status_code == 200:

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        print("Downloaded mp3 to: ", output_path)

    else:
        print("Failed to download mp3")
        print(response.text)


def get_archive_ids(feedId, date):
    base_url = 'https://www.broadcastify.com/archives/ajax.php'

    query_params = f"feedId={feedId}&date={date}"
    full_url = f"{base_url}?{query_params}" 

    print(full_url)

    headers = get_urser_agent()
    res = requests.get(full_url, headers=headers)
    dict_res = json.loads(res.text)
    file_names = [f"{i[0]}" for i in dict_res['data']]

    return file_names


def get_urser_agent():
    num_var = random.randint(100,1000)
    num_var3 = random.randint(10,100)
    num_var2 = num_var3 % 10
    num_var4 = random.randint(1000,10000)
    num_var5 = random.randint(100,1000)

    user_agent={"User-Agent": f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/{num_var5}.36 (KHTML, like Gecko) "+
        f"Chrome/51.{num_var2}.2704.{num_var} Safari/537.{num_var3} OPR/38.0.{num_var4}.41"}
    
    return user_agent


def get_login_cookie(username, password, user_agent):
    user_agent = str(user_agent)
    user_agent.replace("'", "")

    url = "https://www.broadcastify.com/login/"
    headers = {
        "user-agent": user_agent, 
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.5",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.broadcastify.com",
        "dnt": "1",
        "referer": "https://www.broadcastify.com/login/",
        "upgrade-insecure-requests": "1",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "te": "trailers"
    }
    data = {
        "username": username,
        "password": password,
        "action": "auth",
        "redirect": "https://www.broadcastify.com"
    }

    response = requests.post(url, headers=headers, data=data, allow_redirects=False)

    if response.status_code == 302:
        cookies = response.headers.get("set-cookie")
        if cookies:
            match = re.search(r"bcfyuser1=([^;]+)", cookies)
            if match:
                bcfyuser1 = match.group(1)

                with open("cookies.json", "w") as f:
                    json.dump({"bcfyuser1": bcfyuser1}, f)
                return bcfyuser1
        else:
            print("No cookies found")
            print(response.headers)
    return None

if __name__ == '__main__':
    main()