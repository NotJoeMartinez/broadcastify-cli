import os
import re
import json
import random
import requests
import click
import datetime


from rich.console import Console
from rich.progress import track

from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from pprint import pprint

load_dotenv(".env")

BRODCASTIFY_CLI_VERSION = "0.1.0"

console = Console()

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(BRODCASTIFY_CLI_VERSION, message='brodcastify-cli version: %(version)s')
def cli():
    pass


@cli.command("download", help="Download archives by date and feed id")
@click.option("--feed-id", "-id", required=True, help="Broadcastify feed id")
@click.option("--date", "-d", required=False, help="Date in format MM/DD/YYYY") 
@click.option("--range", "-r", required=False, help="Date range in format MM/DD/YYYY-MM/DD/YYYY")
@click.option("--jobs", "-j", type=int, default=1, help="Number of concurrent download jobs")
def download(feed_id, date, range, jobs):

    user_agent = get_urser_agent()
    login_cookie = get_login_cookie(user_agent)

    if login_cookie is None:
        print("Failed to get login cookie")
        return

    if date:
        console.print(f"Downloading archives for feed id: {feed_id} on {date}")
        download_archive_by_date(feed_id, date, "archives", user_agent, login_cookie, jobs)
        console.print(f"Download complete: archives/{feed_id}/{date.replace('/', '')}")
        return
    
    if range:
        start_date, end_date = range.split("-")
        console.print(f"Downloading archives for feed id: {feed_id} from {start_date} to {end_date}")
        download_archives_by_range(feed_id, start_date, end_date, "archives", user_agent, login_cookie, jobs)
        console.print(f"Download complete: archives/{feed_id}/{date.replace('/', '')}")
        return

    console.print(f"Downloading all archives for feed id: {feed_id}")    
    download_all_archives(feed_id, "archives", user_agent, login_cookie, jobs)
    console.print(f"Download complete: archives/{feed_id}/{date.replace('/', '')}")


def download_archives_by_range(feed_id, start_date, end_date, output_dir, user_agent, login_cookie, jobs):

    today = datetime.datetime.now().strftime("%m/%d/%Y")

    if start_date > today or end_date > today:
        console.print("[red]Error:[/red] Invalid date range, start date and end date must be before today")
        exit(1)

    if start_date > end_date:
        console.print("[red]Error:[/red] Invalid date range, start date must be before end date")
        exit(1)


    start_date = datetime.datetime.strptime(start_date, "%m/%d/%Y")
    end_date = datetime.datetime.strptime(end_date, "%m/%d/%Y")

    dates = []

    while start_date <= end_date:
        dates.append(start_date.strftime("%m/%d/%Y"))
        start_date += datetime.timedelta(days=1)

    for date in dates:
        download_archive_by_date(feed_id, date, output_dir, user_agent, login_cookie, jobs)


def download_all_archives(feed_id, output_dir, user_agent, login_cookie, jobs):

    # get all dates between today and exactly one year ago
    dates = []
    current_date = datetime.datetime.now()
    one_year_ago = current_date - datetime.timedelta(days=365)

    while current_date >= one_year_ago:
        dates.append(current_date.strftime("%m/%d/%Y"))
        current_date -= datetime.timedelta(days=1)


    for date in dates:
        download_archive_by_date(feed_id, date, output_dir, user_agent, login_cookie, jobs) 
    console.print(f"Download complete: {output_dir}/{feed_id}")


def download_archive_by_date(feed_id, date, output_dir, user_agent, login_cookie, jobs):

    base_download_url = "https://www.broadcastify.com/archives/downloadv2"
    archive_ids = get_archive_ids(feed_id, date)

    date_dir_name = date.replace("/", "")

    os.makedirs(f"{output_dir}/{feed_id}", exist_ok=True)
    os.makedirs(f"{output_dir}/{feed_id}/{date_dir_name}", exist_ok=True)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = []
        for id in archive_ids:
            split_date = date.split("/")
            url_date = f"{split_date[2]}{split_date[0]}{split_date[1]}"
            url = f"{base_download_url}/{feed_id}/{url_date}/{id}"
            current_output_dir = f"{output_dir}/{feed_id}/{date_dir_name}"
            futures.append(executor.submit(download_mp3, url, current_output_dir, user_agent, login_cookie))

        for future in track(as_completed(futures), total=len(futures), description=f"{date}:"):
            pass


def download_mp3(url, output_dir, user_agent, login_cookie):

    user_agent = str(user_agent)

    headers = {
        "user-agent": user_agent,
        "cookie": login_cookie
    }

    response = requests.get(url, headers=headers, stream=True)

    file_name = response.url.split("/")[-1]
    output_path = os.path.join(output_dir, file_name)


    if response.status_code == 200:

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)


    else:
        print("Failed to download mp3")
        print(response.text)


def get_archive_ids(feedId, date):
    base_url = 'https://www.broadcastify.com/archives/ajax.php'

    query_params = f"feedId={feedId}&date={date}"
    full_url = f"{base_url}?{query_params}" 


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


def get_login_cookie(user_agent):

    # load loagin cookie from cookies.json if it exists
    # otherwise get the login cookie and save it to cookies.json 
    if os.path.exists("cookies.json"):
        with open("cookies.json", encoding='utf-8', errors='ignore') as f:
            cookies = json.load(f)
        return f"bcfyuser1={cookies['bcfyuser1']}" 

    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    user_agent = str(user_agent)

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
            exit(1)

    return None

