import os
import re
import requests
import zipfile
from collections import defaultdict
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from langdetect import detect
from googletrans import Translator
from thefuzz import process
import pycountry
import pycountry_convert as pc

# Create download folders
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = os.path.join(DOWNLOAD_DIR, "weather_data")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

continent_to_wmo_region = {
    "Africa": "WMO_Region_1_Africa",
    "Asia": "WMO_Region_2_Asia",
    "South America": "WMO_Region_3_South_America",
    "North America": "WMO_Region_4_North_America_Central_America_Caribbean",
    "Central America": "WMO_Region_4_North_America_Central_America_Caribbean",
    "Caribbean": "WMO_Region_4_North_America_Central_America_Caribbean",
    "South-West Pacific": "WMO_Region_5_South_West_Pacific",
    "Europe": "WMO_Region_6_Europe",
    "Antarctica": "WMO_Region_7_Antarctica"
}

wmo_exceptions = {
    "Türkiye": "WMO_Region_6_Europe",
    "Russia": "WMO_Region_6_Europe",
    "Cyprus": "WMO_Region_6_Europe",
    "Greenland": "WMO_Region_4_North_America_Central_America_Caribbean",
    "Armenia": "WMO_Region_6_Europe",
    "Azerbaijan": "WMO_Region_6_Europe",
    "Georgia": "WMO_Region_6_Europe"
}

wmo_region_to_url = {
    "WMO_Region_1_Africa": "https://climate.onebuilding.org/WMO_Region_1_Africa/default.html",
    "WMO_Region_2_Asia": "https://climate.onebuilding.org/WMO_Region_2_Asia/default.html",
    "WMO_Region_3_South_America": "https://climate.onebuilding.org/WMO_Region_3_South_America/default.html",
    "WMO_Region_4_North_America_Central_America_Caribbean": "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/default.html",
    "WMO_Region_5_South_West_Pacific": "https://climate.onebuilding.org/WMO_Region_5_Southwest_Pacific/default.html",
    "WMO_Region_6_Europe": "https://climate.onebuilding.org/WMO_Region_6_Europe/default.html",
    "WMO_Region_7_Antarctica": "https://climate.onebuilding.org/WMO_Region_7_Antarctica/default.html"
}

def get_country_from_city(city_name):
    geolocator = Nominatim(user_agent="geo_locator")
    try:
        location = geolocator.geocode(city_name, exactly_one=True)
        if location:
            if location.raw and "address" in location.raw and "country" in location.raw["address"]:
                country_raw = location.raw["address"]["country"]
            else:
                country_raw = location.address.split(",")[-1].strip()
            return translate_to_english(country_raw)
    except Exception as e:
        print(f"❌ Error: {e}")
    return None

def translate_to_english(text):
    try:
        detected_lang = detect(text)
        if detected_lang != "en":
            translator = Translator()
            translated_text = translator.translate(text, src=detected_lang, dest="en").text
            return translated_text
    except Exception as e:
        print(f"❌ Translation Error: {e}")
    return text

def get_continent(country_name):
    try:
        country = pycountry.countries.lookup(country_name)
        country_code = country.alpha_2
        continent_code = pc.country_alpha2_to_continent_code(country_code)
        return {
            "AF": "Africa", "AS": "Asia", "EU": "Europe",
            "NA": "North America", "SA": "South America",
            "OC": "Oceania", "AN": "Antarctica"
        }.get(continent_code, None)
    except LookupError:
        return None

def get_wmo_region(country, continent):
    if country in wmo_exceptions:
        return wmo_exceptions[country]
    return continent_to_wmo_region.get(continent, None)

def to_variable_name(text):
    return re.sub(r'\W+', '_', text).strip('_')

def scrape_region(region_url, mapping):
    response = requests.get(region_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/' in href and href.endswith('/index.html'):
            parts = href.split('/')[0].split('_', 1)
            if len(parts) == 2:
                mapping[parts[0]] = parts[1]

def extract_city_name(filename):
    parts = filename.split("_", 3)
    if len(parts) < 4:
        return None
    city_part = parts[3]
    while "_" in city_part:
        city_part = city_part.split("_", 1)[-1]
    match = re.match(r"([^0-9]+)", city_part)
    if match:
        city_name = match.group(1).replace(".", " ")
        return re.sub(r" TMYx$", "", city_name.strip())
    return None

def scrape_datasets(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return [link['href'] for link in soup.find_all('a', href=True) if link['href'].endswith('.zip')]
    except requests.RequestException as e:
        print(f"❌ Error fetching the URL: {e}")
        return []

def download_file_from_webpage(url, file_name):
    if not url or not file_name:
        print("❌ Missing URL or file name")
        return
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        file_links = {link['href']: link['href'].split('/')[-1] for link in soup.find_all('a', href=True) if link['href'].endswith('.zip')}
        best_match, score = process.extractOne(file_name, file_links.values())
        if score < 80:
            print(f"❌ No close match found for '{file_name}'")
            return
        relative_file_path = [key for key, value in file_links.items() if value == best_match][0]
        file_url = f"{url.rsplit('/', 1)[0]}/{relative_file_path}"
        print(f"🔽 Downloading file from: {file_url}")
        local_file_path = os.path.join(DOWNLOAD_DIR, best_match)
        with open(local_file_path, "wb") as file:
            r = requests.get(file_url, stream=True)
            for chunk in r.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"✅ Download complete: {local_file_path}")
    except Exception as e:
        print(f"❌ Error: {e}")

def find_zip_file(target_name):
    zip_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith(".zip")]
    best_match, score = process.extractOne(target_name, zip_files)
    if score > 80:
        return os.path.join(DOWNLOAD_DIR, best_match)
    return None

def main():
    city_name = input("Enter a city name: ").strip()
    country = get_country_from_city(city_name)
    if not country:
        print("❌ Could not determine country.")
        return
    print(f"{city_name} is in {country}")
    continent = get_continent(country)
    if not continent:
        print("❌ Could not determine continent.")
        return
    print(f"{country} is in {continent}")
    wmo_region_var = get_wmo_region(country, continent)
    if not wmo_region_var:
        print("❌ Could not determine WMO region.")
        return
    print(f"The WMO region for {country} is: {wmo_region_var}")

    city_var = to_variable_name(city_name)
    country_var = to_variable_name(country)
    globals()[city_var] = city_name
    globals()[country_var] = country
    globals()["wmo_region_var"] = wmo_region_var

    mapping = {}
    for region in wmo_region_to_url.values():
        scrape_region(region, mapping)

    print(f"\n✅ Total Countries Scraped: {len(mapping)}")
    for i, (code, name) in enumerate(mapping.items()):
        if i < 10:
            print(f"{code}: {name}")

    best_match, score = process.extractOne(country, mapping.values())
    if score < 80:
        print("❌ Country not found.")
        return
    onebuilding_code = next((k for k, v in mapping.items() if v == best_match), None)
    url = wmo_region_to_url.get(wmo_region_var, "").replace("/default.html", f"/{onebuilding_code}_{best_match}/index.html")
    print(f"🔗 Country page: {url}")
    # import webbrowser; webbrowser.open(url)  # optional

    dataset_files = scrape_datasets(url)
    city_datasets = defaultdict(list)
    for f in dataset_files:
        match = re.search(r"(.*?)_TMYx\.(\d{4}-\d{4})?", f)
        if match:
            filename = match.group(1)
            year_range = match.group(2) if match.group(2) else "unknown"
            city = extract_city_name(filename)
            if city:
                city_datasets[city].append((f, year_range))

    latest_datasets = {}
    for city, datasets in city_datasets.items():
        datasets.sort(key=lambda x: x[1] if x[1] != "unknown" else "0000-0000", reverse=True)
        latest_datasets[city] = datasets[0]

    best_city, score = process.extractOne(city_name, latest_datasets.keys())
    if score > 80:
        weather_file, dataset_year = latest_datasets[best_city]
        print(f"✅ Selected Weather File: {weather_file} ({dataset_year})")
        download_file_from_webpage(url, weather_file)
        zip_file_path = find_zip_file(weather_file)
        if zip_file_path:
            print(f"\n📂 Extracting: {zip_file_path}")
            try:
                with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                    zip_ref.extractall(EXTRACT_DIR)
                print("✅ Extraction complete.")
                epw_file = next((f for f in os.listdir(EXTRACT_DIR) if f.endswith(".epw")), None)
                if epw_file:
                    epw_path = os.path.join(EXTRACT_DIR, epw_file)
                    print(f"\n✅ EPW file saved at: {epw_path}")
                else:
                    print("❌ No EPW file found in the archive.")
            except zipfile.BadZipFile:
                print("❌ ZIP file is corrupted.")
    else:
        print("❌ No matching city dataset found.")

def run_epw_pipeline(city_name):
    from collections import defaultdict

    country = get_country_from_city(city_name)
    if not country:
        print("❌ Could not determine country.")
        return None
    print(f"{city_name} is in {country}")
    continent = get_continent(country)
    if not continent:
        print("❌ Could not determine continent.")
        return None
    print(f"{country} is in {continent}")
    wmo_region_var = get_wmo_region(country, continent)
    if not wmo_region_var:
        print("❌ Could not determine WMO region.")
        return None
    print(f"The WMO region for {country} is: {wmo_region_var}")

    city_var = to_variable_name(city_name)
    country_var = to_variable_name(country)
    globals()[city_var] = city_name
    globals()[country_var] = country
    globals()["wmo_region_var"] = wmo_region_var

    mapping = {}
    for region in wmo_region_to_url.values():
        scrape_region(region, mapping)

    best_match, score = process.extractOne(country, mapping.values())
    if score < 80:
        print("❌ Country not found.")
        return None

    onebuilding_code = next((k for k, v in mapping.items() if v == best_match), None)
    url = wmo_region_to_url.get(wmo_region_var, "").replace("/default.html", f"/{onebuilding_code}_{best_match}/index.html")
    print(f"🔗 Country page: {url}")

    dataset_files = scrape_datasets(url)
    city_datasets = defaultdict(list)
    for f in dataset_files:
        match = re.search(r"(.*?)_TMYx\.(\d{4}-\d{4})?", f)
        if match:
            filename = match.group(1)
            year_range = match.group(2) if match.group(2) else "unknown"
            city = extract_city_name(filename)
            if city:
                city_datasets[city].append((f, year_range))

    latest_datasets = {}
    for city, datasets in city_datasets.items():
        datasets.sort(key=lambda x: x[1] if x[1] != "unknown" else "0000-0000", reverse=True)
        latest_datasets[city] = datasets[0]

    result = process.extractOne(city_name, latest_datasets.keys())
    if result:
        best_city, score = result
        if score > 80 and best_city in latest_datasets:
            weather_file, dataset_year = latest_datasets[best_city]
            print(f"✅ Selected Weather File: {weather_file} ({dataset_year})")
            download_file_from_webpage(url, weather_file)
            zip_file_path = find_zip_file(weather_file)
            if zip_file_path:
                print(f"\n📂 Extracting: {zip_file_path}")
                try:
                     # Clear existing EPW files before extracting new ones
                    for f in os.listdir(EXTRACT_DIR):
                        file_path = os.path.join(EXTRACT_DIR, f)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                        zip_ref.extractall(EXTRACT_DIR)
                    print("✅ Extraction complete.")
                    epw_file = next((f for f in os.listdir(EXTRACT_DIR) if f.endswith(".epw")), None)
                    if epw_file:
                        epw_path = os.path.join(EXTRACT_DIR, epw_file)
                        print(f"\n✅ EPW file saved at: {epw_path}")
                        return epw_path
                    else:
                        print("❌ No EPW file found in the archive.")
                        return None
                except zipfile.BadZipFile:
                    print("❌ ZIP file is corrupted.")
                    return None
        else:
            print("❌ No matching city dataset found.")
            return None
    else:
        print("❌ No city match found at all.")
        return None

# Keep this here so you can still run it manually:
if __name__ == "__main__":
    city_name = input("Enter a city name: ").strip()
    run_epw_pipeline(city_name)
