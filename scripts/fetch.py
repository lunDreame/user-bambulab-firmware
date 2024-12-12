"""Fetch the HTML content of a URL using aiohttp."""
import re
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def fetch_url(session, url):
    """Fetch the HTML content of a URL using aiohttp."""
    try:
        async with session.get(url) as response:
            text = await response.text()
            soup = BeautifulSoup(text, 'html.parser')
            selector = soup.select_one("#__next > div > div > div > div.portal-css-npiem8 > div.pageContent.MuiBox-root.portal-css-0 > div > div > div.portal-css-1v0qi56 > div.flex > div.detailContent > div > div > div.portal-css-kyyjle > div.top > div.versionContent > div > div.linkContent.pc > a:nth-child(2)")
            if selector:
                return selector.get("href")
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

async def fetch_multiple_urls(urls):
    """Fetch the HTML content of multiple URLs using aiohttp."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        return await asyncio.gather(*tasks)

def create_firmware_json(offline_firmware_url):
    """Create a JSON object for firmware."""
    pattern = r"offline\/([\w-]+)\/([\d\.]+)\/([\w]+)\/offline-([\w\-\.]+)\.zip"
    info = re.search(pattern, offline_firmware_url).groups()
    if not info:
        print("Failed to parse the URL.")
        return None
    
    a1_series_ams_json = {}             # A1, A1 Mini
    other_series_ams_json = {           # X1, P1, X1E
        "dev_model_name": "BL-A001",
        "address": 0,
        "device_id": "",
        "firmware": [
            {
                "version": "00.00.06.40",
                "force_update": False,
                "url": "https://public-cdn.bambulab.com/upgrade/device/BL-A001/00.00.06.40/product/ams-ota_v00.00.06.40-20230906131441.json.sig",
                "description": "",
                "status": "testing"
            }
        ],
        "firmware_current": None
    }

    firmware_json = {
        "user_id": "0",
        "upgrade": {
            "sequence_id": "0",
            "command": "upgrade_history",
            "src_id": 2,
            "firmware_optional": {
                "firmware": {
                    "version": info[1],
                    "url": f"https://public-cdn.bblmw.com/upgrade/device/{info[0]}/{info[1]}/product/{info[2]}/{info[3]}.json.sig",
                    "force_update": False,
                    "description": "",
                    "status": "release"
                },
                "ams": []
            }
        }
    }
    if info[0] not in {"N2S", "N1"}:
        firmware_json["upgrade"]["firmware_optional"]["ams"].append(other_series_ams_json)
        
    print(f"Firmware JSON: {firmware_json}")

    # Save the JSON to a file
    try:
        save_firmware_json(info, firmware_json)
        print("JSON file saved successfully!")
    except ValueError as e:
        print(e)

def save_firmware_json(info, firmware_json):
    """Saves the firmware JSON to a file based on the info key."""
    file_name_mapping = {
        "N2S": "./assets/a1_ams.json",
        "N1": "./assets/a1_mini_ams.json",
        "BL-P001": "./assets/x1_series_ams.json",
        "C11": "./assets/p1_series_ams.json",
        "C13": "./assets/x1e_ams.json"
    }

    file_name = file_name_mapping.get(info[0])
    if file_name is None:
        raise ValueError(f"No matching file name found for key: {info[0]}")
        
    with open(file_name, "w", encoding="utf-8") as file:
        json.dump(firmware_json, file, ensure_ascii=False, indent=4)
        
if __name__ == "__main__":
    urls = [
        "https://bambulab.com/en/support/firmware-download/x1",
        "https://bambulab.com/en/support/firmware-download/p1",
        "https://bambulab.com/en/support/firmware-download/a1",
        "https://bambulab.com/en/support/firmware-download/a1-mini",
        "https://bambulab.com/en/support/firmware-download/x1e"
    ]
    
    results = asyncio.run(fetch_multiple_urls(urls))
    for i, result in enumerate(results):
        #print(f"Result from {urls[i]}:  {result}")
        if result:
            create_firmware_json(result)