import os
import shutil
import random
import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass
from enum import Enum
from typing import List


class MenuCategory(Enum):
    KOTIRUOKA = "Kotiruoka"
    KEITTORUOKA = "Keittoruoka"
    KASVISRUOKA = "Kasvisruoka"
    ERIKOISRUOKA = "Erikoisruoka"
    JALKIRUOKA = "Jälkiruoka"
    MUU_RUOKA = "Muu ruoka"

    def __str__(self):
        return self.value


@dataclass(frozen=True)
class MealItem:
    name: str
    diet: str


@dataclass(frozen=True)
class MenuItem:
    category: MenuCategory
    meals: List[MealItem]


URL = "https://fi.jamix.cloud/apps/menu/?anro=91938&k=3&mt=56"
PUBLIC_DIR = "public"
TEMPLATE_DIR = "templates"
STATIC_DIR = "assets"

_CATEGORY_MAPPING = {
    "koti": MenuCategory.KOTIRUOKA,
    "keitto": MenuCategory.KEITTORUOKA,
    "kasvis": MenuCategory.KASVISRUOKA,
    "erikois": MenuCategory.ERIKOISRUOKA,
    "jälki": MenuCategory.JALKIRUOKA,
}

_CATEGORY_PRIORITY = {
    MenuCategory.KOTIRUOKA: 0,
    MenuCategory.KEITTORUOKA: 1,
    MenuCategory.KASVISRUOKA: 2,
    MenuCategory.ERIKOISRUOKA: 3,
    MenuCategory.MUU_RUOKA: 4,
    MenuCategory.JALKIRUOKA: 5,
}


def clean_text(text: str) -> str:
    return text.replace("*", "").strip().strip(",").strip(".").strip()


def is_ignored_meal(name: str) -> bool:
    name_lower = name.lower()
    return "salaatit" in name_lower or "leivät" in name_lower or "juomat" in name_lower


def get_category_name(category_name_raw: str) -> MenuCategory:
    category_name_lower = category_name_raw.lower()
    for keyword, category in _CATEGORY_MAPPING.items():
        if keyword in category_name_lower:
            return category
    return MenuCategory.MUU_RUOKA


def sort_by_menu_category_name(menus: List[MenuItem]) -> List[MenuItem]:
    return sorted(menus, key=lambda m: _CATEGORY_PRIORITY.get(m.category, 99))


def scrape_menu() -> List[MenuItem]:
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
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".multiline-button-caption-text")
            )
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")

        menus = []

        # The structure groups meals inside "multiline" buttons
        buttons = soup.find_all("div", class_="multiline")
        for btn in buttons:
            title_el = btn.find("span", class_="multiline-button-caption-text")
            if not title_el:
                continue

            category_name_raw = title_el.get_text(separator=" ", strip=True)
            meals = []

            item_wrappers = btn.find_all("span", class_="menu-item")
            for wrap in item_wrappers:
                name_el = wrap.find("span", class_="item-name")
                diet_el = wrap.find("span", class_="menuitem-diets")

                if name_el:
                    name = clean_text(name_el.get_text(strip=True)).capitalize()
                    if is_ignored_meal(name):
                        continue
                    diet = (
                        clean_text(diet_el.get_text(strip=True)).upper()
                        if diet_el
                        else ""
                    )
                    meals.append(MealItem(name=name, diet=diet))

            if meals:
                menus.append(
                    MenuItem(category=get_category_name(category_name_raw), meals=meals)
                )

    except Exception as e:
        print(f"Error scraping menu: {e}")
        menus = []
    finally:
        driver.quit()

    return sort_by_menu_category_name(menus)


def generate_html(menus: List[MenuItem]) -> None:
    if not os.path.exists(PUBLIC_DIR):
        os.makedirs(PUBLIC_DIR)

    if os.path.exists(STATIC_DIR):
        for item in os.listdir(STATIC_DIR):
            s = os.path.join(STATIC_DIR, item)
            d = os.path.join(PUBLIC_DIR, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("index.html.j2")
    
    meta_description_lines = []
    for menu in menus:
        # Simplify category text for the embed
        meta_description_lines.append(menu.category.value)
        for meal in menu.meals:
            meta_description_lines.append(f"• {meal.name}")
        meta_description_lines.append("")

    meta_desc = "\n".join(meta_description_lines).strip()
    
    if not menus:
        meta_desc = "Ei ruokalistaa tälle päivälle."
        page_title = "Voi harmi. Ei ruokalistaa tälle päivälle."
        og_title = "Voi harmi."
        card_image = ""
    else:
        page_title = "Syömään? Lounasmenu"
        og_title = "Syömään?"
        cards_dir = os.path.join(STATIC_DIR, "cards")
        card_image = "maha.gif"
        if os.path.exists(cards_dir):
            cards = [
                f
                for f in os.listdir(cards_dir)
                if os.path.isfile(os.path.join(cards_dir, f))
            ]
            if cards:
                card_image = random.choice(cards)

    tz = ZoneInfo("Europe/Helsinki")
    updated_time_str = datetime.datetime.now(tz).strftime("%d.%m.%Y klo %H:%M (%Z)")

    html_content = template.render(
        menus=menus,
        meta_description=meta_desc,
        updated_at=updated_time_str,
        card_image=card_image,
        page_title=page_title,
        og_title=og_title,
    )

    with open(os.path.join(PUBLIC_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[{datetime.datetime.now()}] HTML generated successfully.")


if __name__ == "__main__":
    menus = scrape_menu()
    generate_html(menus)
