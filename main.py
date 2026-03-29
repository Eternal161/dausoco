import os
import json
import datetime
from playwright.sync_api import sync_playwright
from github import Github

TARGET_SITE = "https://socolive7.cv/"
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_NAME = os.getenv("GH_REPO") 
FILE_PATH = "bongda.m3u"
WAITING_VIDEO_URL = "https://example.com/video-cho.mp4"

def load_logos(filepath="logos.json"):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def get_match_logo(match_title, logos_db):
    title_lower = match_title.lower()
    for team_name, logo_url in logos_db.items():
        if team_name in title_lower:
            return logo_url
    return "https://example.com/default-logo.png"

def scrape_and_catch_m3u8():
    matches = []
    logos_db = load_logos()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()
        
        print(f"Đang truy cập: {TARGET_SITE}")
        page.goto(TARGET_SITE)
        page.wait_for_load_state("networkidle")

        match_elements = page.locator("a:has-text('Xem ngay'), a:has-text('Trực tiếp')").all()
        
        for el in match_elements:
            try:
                match_url = el.get_attribute("href")
                if match_url and not match_url.startswith("http"):
                    match_url = TARGET_SITE.rstrip('/') + match_url
                    
                parent_block = el.locator("xpath=./ancestor::div[4]")
                raw_text = parent_block.inner_text()
                
                clean_text = " | ".join([line.strip() for line in raw_text.split('\n') if line.strip()])
                parts = clean_text.split(" | ")
                
                if len(parts) >= 4:
                    team_a = parts[0].strip()
                    status_or_time = parts[1].strip()
                    score = parts[2].strip()
                    team_b = parts[-1].strip()
                    
                    title = f"{team_a} vs {team_b}"
                    display_info = f"{status_or_time} ({score})"
                    logo = get_match_logo(title, logos_db)
                    
                    matches.append({
                        "title": title,
                        "display_info": display_info,
                        "logo": logo,
                        "match_url": match_url,
                        "m3u8_link": ""
                    })
            except Exception as e:
                continue
                
        for match in matches:
            m3u8_links = []
            page.on("request", lambda request: m3u8_links.append(request.url) if ".m3u8" in request.url else None)
            
            try:
                page.goto(match["match_url"])
                page.wait_for_timeout(5000) 
            except:
                pass
            
            page.remove_all_listeners("request")
            
            if m3u8_links:
                match["m3u8_link"] = m3u8_links[-1]
            
        browser.close()
    return matches

def generate_m3u(matches):
    m3u = "#EXTM3U\n"
    for match in matches:
        stream = match["m3u8_link"] if match["m3u8_link"] else WAITING_VIDEO_URL
        m3u += f'#EXTINF:-1 tvg-logo="{match["logo"]}" group-title="Socolive", {match["title"]} - {match["display_info"]}\n'
        m3u += f'{stream}\n\n'
    return m3u

def push_to_github(content):
    if not GITHUB_TOKEN or not REPO_NAME:
        print("[!] Thiếu GH_TOKEN hoặc GH_REPO.")
        return

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    vn_time = datetime.datetime.now() + datetime.timedelta(hours=7) 
    commit_msg = f"Cập nhật: {vn_time.strftime('%H:%M %d/%m/%Y')}"
    
    try:
        contents = repo.get_contents(FILE_PATH)
        repo.update_file(contents.path, commit_msg, content, contents.sha)
    except:
        repo.create_file(FILE_PATH, commit_msg, content)

if __name__ == "__main__":
    matches_data = scrape_and_catch_m3u8()
    if matches_data:
        m3u_text = generate_m3u(matches_data)
        push_to_github(m3u_text)
