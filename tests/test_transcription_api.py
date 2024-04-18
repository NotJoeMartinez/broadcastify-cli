import json

from pprint import pprint
from openai import OpenAI

client = OpenAI()

audio_file = open("archives/22835/01012024/202401010128-579378-22835.mp3", "rb")
transcript = client.audio.transcriptions.create(
  file=audio_file,
  model="whisper-1",
  response_format="verbose_json",
  timestamp_granularities=["segment"]
)

segments_dict = transcript.to_dict()

print(dir(segments_dict))
pprint(segments_dict)




# Save transcript to a JSON file
with open("transcript.json", "w", encoding="utf-8") as f:
    json.dump(segments_dict, f, ensure_ascii=False, indent=4)