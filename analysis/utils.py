import requests
import os

def download_epw(epw_url, save_path="downloads/temp.epw"):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    response = requests.get(epw_url)
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        return save_path
    else:
        raise Exception(f"Failed to download EPW: {response.status_code} {response.text}")
