import os
import re
import json
import random
import datetime
import glob
import warnings

import requests
import click

from faster_whisper import WhisperModel
from rich.console import Console
from rich.progress import track
from pathlib import Path
from pydub import AudioSegment
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from pprint import pprint

load_dotenv(".env")
warnings.filterwarnings("ignore", module="whisper")

BRODCASTIFY_CLI_VERSION = "0.1.2"

console = Console()

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(BRODCASTIFY_CLI_VERSION, message='brodcastify-cli version: %(version)s')
def cli():
    pass


@cli.command("download", help="Download archives by date and feed id")
@click.option("--feed-id", "-id", required=True, help="Broadcastify feed id")
@click.option("--date", "-d", required=False, help="Date in format MM/DD/YYYY") 
@click.option("--range", "-r", required=False, help="Date range in format MM/DD/YYYY-MM/DD/YYYY")
@click.option("--combine", is_flag=True, help="Combine downloaded MP3 files into a single file")
@click.option("--transcribe", "-t", is_flag=True, help="Transcribe downloaded MP3 files")
@click.option("--jobs", "-j", type=int, default=1, help="Number of concurrent download jobs")
def download(feed_id, date, range, combine, transcribe, jobs):

    user_agent = get_urser_agent()
    login_cookie = get_login_cookie(user_agent)

    if login_cookie is None:
        print("Failed to get login cookie")
        return

    if date:
        console.print(f"Downloading archives for feed id: {feed_id} on {date}")
        download_archive_by_date(feed_id, date, "archives", user_agent, login_cookie, combine, transcribe, jobs)
        console.print(f"Download complete: archives/{feed_id}/{date.replace('/', '')}")
        return
    
    if range:
        start_date, end_date = range.split("-")
        console.print(f"Downloading archives for feed id: {feed_id} from {start_date} to {end_date}")
        download_archives_by_range(feed_id, start_date, end_date, "archives", user_agent, login_cookie, combine, transcribe, jobs)
        console.print(f"Download complete: archives/{feed_id}")
        return

    console.print(f"Downloading all archives for feed id: {feed_id}")    
    download_all_archives(feed_id, "archives", user_agent, login_cookie, combine, transcribe, jobs)
    console.print(f"Download complete: archives/{feed_id}/{date.replace('/', '')}")


@cli.command("transcribe", help="Transcribe directory of audio files")
@click.option("--directory", "-d", required=True, help="Directory containing audio files")
def transcribe(directory):
    transcribe_audio(directory)


def download_archives_by_range(feed_id, start_date, end_date, output_dir, user_agent, login_cookie, combine, transcribe, jobs):

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
        download_archive_by_date(feed_id, date, output_dir, user_agent, login_cookie, combine, transcribe, jobs)


def download_all_archives(feed_id, output_dir, user_agent, login_cookie, combine, transcribe, jobs):

    # get all dates between today and exactly one year ago
    dates = []
    current_date = datetime.datetime.now()
    one_year_ago = current_date - datetime.timedelta(days=365)

    while current_date >= one_year_ago:
        dates.append(current_date.strftime("%m/%d/%Y"))
        current_date -= datetime.timedelta(days=1)


    for date in dates:
        download_archive_by_date(feed_id, date, output_dir, user_agent, login_cookie, combine, transcribe, jobs) 
    console.print(f"Download complete: {output_dir}/{feed_id}")


def download_archive_by_date(feed_id, date, output_dir, user_agent, login_cookie, combine, transcribe, jobs):

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

    if combine:
        combine_mp3_files(f"{output_dir}/{feed_id}/{date_dir_name}", feed_id, date)
    
    if transcribe:
        transcribe_audio(f"{output_dir}/{feed_id}/{date_dir_name}")


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
    num_var = random.randint(100, 1000)
    num_var3 = random.randint(10, 100)
    num_var2 = num_var3 % 10
    num_var4 = random.randint(100, 1000)

    user_agent = {
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{num_var4}.36 (KHTML, like Gecko) "
                        f"Chrome/58.0.{num_var2}.3029.{num_var} Safari/537.{num_var3}"
    }

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


def combine_mp3_files(directory, feed_id, date):

    date = date.replace("/", "")

    mp3_files = sorted(glob.glob(f"{directory}/*.mp3"))
    
    combined_audio = None
    for mp3_file in track(mp3_files, description=f"combining audio"):
        audio = AudioSegment.from_mp3(mp3_file)
        if combined_audio is None:
            combined_audio = audio
        else:
            combined_audio += audio

    with console.status("Exporting combined MP3 file...") as status:
        if combined_audio is not None:
            output_file = f"{directory}/combined_{feed_id}_{date}.mp3"
            combined_audio.export(output_file, format="mp3")
            print(f"Combined MP3 saved to: {output_file}")
        else:
            console.print("No MP3 files found to combine.")


def transcribe_audio(directory):
    transcript_dir = f"{directory}/transcripts"
    os.makedirs(transcript_dir, exist_ok=True)

    mp3_files = sorted(glob.glob(f"{directory}/*.mp3"))
    model_size = "large-v3"
    model = WhisperModel(model_size, device="cpu", compute_type="int8")


    for audio_file in track(mp3_files, description="transcribing audio"):
        segments, info = model.transcribe(audio_file, beam_size=5, condition_on_previous_text=False, language="en", no_speech_threshold=2, initial_prompt="you are listening to police scanner radio traffic")

        transcript_fname = Path(audio_file).stem + ".json"
        transcript_path = f"{transcript_dir}/{transcript_fname}"


        output  = {
                    "text": "",
                    "segments": []
                }

        for segment in segments:
            print(segment.text)

            output["text"] += segment.text + " "

            output["segments"].append({
                "text": segment.text,
                "start": segment.start,
                "end": segment.end,
                "seek": segment.seek
            })

        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4)



    # model = whisper.load_model("base") 
    # for mp3_file in track(mp3_files, description="transcribing audio"):
    #     audio = whisper.load_audio(mp3_file)


    #     prompt = "you are listening to police scanner radio traffic"
    #     result = model.transcribe(audio, no_speech_threshold=2, initial_prompt=prompt,  condition_on_previous_text=False, language="en")
        
    #     transcript_fname = Path(mp3_file).stem + ".json"
    #     transcript_path = f"{transcript_dir}/{transcript_fname}"

    #     write_json = WriteJSON(transcript_dir)

    #     with open(transcript_path, "w", encoding="utf-8") as f:
    #         write_json.write_result(result, f)

