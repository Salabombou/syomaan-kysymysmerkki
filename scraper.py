import os
import time
import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from jinja2 import Environment, FileSystemLoader

URL = "https://fi.jamix.cloud/apps/menu/?anro=91938&k=3&mt=56"
PUBLIC_DIR = "public"
TEMPLATE_DIR = "templates"

def clean_text(text: str):
    return text.replace("*", "").strip().strip(",").strip(".").strip()

def scrape_menu():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Needs chromium/chrome installed in the container
    driver = webdriver.Chrome(options=chrome_options)
    
    print(f"[{datetime.datetime.now()}] Fetching menu from {URL}...")
    try:
        driver.get(URL)
        # Jamix takes a moment to render content dynamically.
        # Wait for the menu options to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".multiline-button-caption-text"))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        menus = []
        
        # The structure groups meals inside "multiline" buttons
        buttons = soup.find_all("div", class_="multiline")
        for btn in buttons:
            title_el = btn.find("span", class_="multiline-button-caption-text")
            if not title_el:
                continue
            
            category_name = title_el.get_text(separator=" ", strip=True)
            menu_dict = {"category": category_name, "meals": []}
            
            item_wrappers = btn.find_all("span", class_="menu-item")
            for wrap in item_wrappers:
                name_el = wrap.find("span", class_="item-name")
                diet_el = wrap.find("span", class_="menuitem-diets")
                
                if name_el:
                    name = clean_text(name_el.get_text(strip=True))
                    diet = clean_text(diet_el.get_text(strip=True)) if diet_el else ""
                    menu_dict["meals"].append({"name": name, "diet": diet})
                    
            if menu_dict["meals"]:
                menus.append(menu_dict)
                
    except Exception as e:
        print(f"Error scraping menu: {e}")
        menus = []
    finally:
        driver.quit()
        
    return menus

def generate_html(menus):
    if not os.path.exists(PUBLIC_DIR):
        os.makedirs(PUBLIC_DIR)
        
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
        
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("index.html.j2")
    
    meta_description_lines = []
    for menu in menus:
        # Simplify category text for the embed
        cat_name = menu["category"].split(" ")[0:2] # e.g. "Xamk Kasvislounas"
        meta_description_lines.append(" ".join(cat_name))
        for meal in menu["meals"]:
            meta_description_lines.append(f"- {meal['name']}")
        meta_description_lines.append("")
    
    meta_desc = "\n".join(meta_description_lines).strip()
    if not meta_desc:
        meta_desc = "Ei ruokalistaa tälle päivälle."

    tz = ZoneInfo("Europe/Helsinki")
    updated_time_str = datetime.datetime.now(tz).strftime("%d.%m.%Y klo %H:%M:%S (%Z)")

    html_content = template.render(
        menus=menus,
        meta_description=meta_desc,
        updated_at=updated_time_str
    )
    
    with open(os.path.join(PUBLIC_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[{datetime.datetime.now()}] HTML generated successfully.")

if __name__ == "__main__":
    menus = scrape_menu()
    if not menus:
        # Fallback text if menu is unavailable, empty, or parsing failed
        menus = [{"category": "Huom", "meals": [{"name": "Ei ruokalistaa tälle päivälle.", "diet": ""}]}]
    generate_html(menus)
