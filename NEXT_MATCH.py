import os
import re
import json
import time
import random
import subprocess
from datetime import datetime
from unidecode import unidecode
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# === COSTANTI ===
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

URLS = [
    "https://www.flashscore.it/calcio/italia/serie-a/calendario/",
    "https://www.flashscore.it/calcio/italia/serie-b/calendario/",
    "https://www.flashscore.it/calcio/francia/ligue-1/calendario/",
    "https://www.flashscore.it/calcio/francia/ligue-2/calendario/",
    "https://www.flashscore.it/calcio/germania/bundesliga/calendario/",
    "https://www.flashscore.it/calcio/germania/2-bundesliga/calendario/",
    "https://www.flashscore.it/calcio/inghilterra/premier-league/calendario/",
    "https://www.flashscore.it/calcio/inghilterra/championship/calendario/",
    "https://www.flashscore.it/calcio/olanda/eredivisie/calendario/",
    "https://www.flashscore.it/calcio/spagna/laliga/calendario/",
    "https://www.flashscore.it/calcio/spagna/laliga2/calendario/",
    "https://www.flashscore.it/calcio/portogallo/liga-portugal/calendario/",
    "https://www.flashscore.it/calcio/belgio/jupiler-league/calendario/"
]

# === DRIVER SETUP ===
def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    return uc.Chrome(options=options)

# === UTILS ===
def scroll_page(driver, step=1200, pause=1.2, max_attempts=6):
    height = 0
    for _ in range(max_attempts):
        driver.execute_script(f"window.scrollBy(0, {step});")
        time.sleep(pause + random.uniform(0, 0.8))
        new_height = driver.execute_script("return window.pageYOffset;")
        if new_height == height:
            break
        height = new_height

def normalizza_nome(nome):
    nome = unidecode(nome.lower().replace('.', '').strip())
    nome = re.sub(r'\(.*?\)', '', nome)
    nome = re.sub(r'\b\w$', '', nome)
    nome = re.sub(r'[^a-z\s]', '', nome)
    return nome.strip()

def filtra_indisponibili(raw_list, titolari):
    titolari_normalizzati = {normalizza_nome(n) for n in titolari}
    return [
        g for g in raw_list
        if (n := normalizza_nome(g)) not in titolari_normalizzati
        and n not in {'p', 'gk', 'por', 'portiere'}
        and n != ''
    ]

def svuota_cartella(cartella):
    for f in os.listdir(cartella):
        path = os.path.join(cartella, f)
        if os.path.isfile(path):
            os.remove(path)
            try:
                subprocess.run(["git", "rm", "--cached", path], check=True)
            except subprocess.CalledProcessError:
                pass
    print(f"🧹 Cartella '{cartella}' svuotata (anche su Git).")

def git_push():
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Aggiornati file scraping Flashscore"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Push su GitHub completato.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore push: {e}")

# === LOGICA PRINCIPALE ===
def get_match_links(driver, wait, url):
    try:
        driver.get(url)
        wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "event__match--scheduled")))
        return [
            el.find_element(By.CLASS_NAME, "eventRowLink").get_attribute("href")
            for el in driver.find_elements(By.CLASS_NAME, "event__match--scheduled")
        ]
    except Exception as e:
        print(f"⚠️ Errore raccolta link da {url}: {e}")
        return []

# def estrai_informazioni_partita(driver, wait, url, competizione):
#     try:
#         driver.get(url)
#         try:
#             wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
#         except:
#             pass

#         squadre = wait.until(EC.presence_of_all_elements_located(
#             (By.XPATH, "//strong[contains(@class,'detailTeamForm__teamName--ellipsis')]")))
#         home, away = squadre[0].text, squadre[1].text

#         arbitro = "Non trovato"
#         try:
#             blocco_info = driver.find_element(By.CSS_SELECTOR, "div[data-testid='wcl-summaryMatchInformation']")
#             for el in blocco_info.find_elements(By.CSS_SELECTOR, "strong[data-testid='wcl-scores-simpleText-01']"):
#                 if el.text.strip():
#                     arbitro = el.text.strip().capitalize()
#                     break
#         except:
#             pass

#         return {
#             'home_team': home,
#             'away_team': away,
#             'arbitro': arbitro,
#             'competizione': competizione,
#         }
#     except Exception as e:
#         print(f"❌ Errore in {url}: {e}")
#         return None

def estrai_informazioni_partita(driver, wait, url, competizione):
    try:
        driver.get(url)
        try:
            wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        except:
            pass

        squadre = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//strong[contains(@class,'detailTeamForm__teamName--ellipsis')]")))
        home, away = squadre[0].text, squadre[1].text

        arbitro = ""
        try:
            blocco_info = driver.find_element(By.CSS_SELECTOR, "div[data-testid='wcl-summaryMatchInformation']")
            spans = blocco_info.find_elements(By.TAG_NAME, "span")
            strongs = blocco_info.find_elements(By.TAG_NAME, "strong")

            for i, span in enumerate(spans):
                if span.text.strip().upper() == "ARBITRO:":
                    if i < len(strongs):
                        arbitro = strongs[0].text.strip()
                    break
        except Exception as e:
            print(f"[❌] Errore estraendo arbitro: {e}")

        return {
            'home_team': home,
            'away_team': away,
            'arbitro': arbitro,
            'competizione': competizione,
        }

    except Exception as e:
        print(f"[❌] Errore generale nel parsing: {e}")
        return None

# === MAIN ===
def main():
    os.makedirs("dati_flashscore", exist_ok=True)
    svuota_cartella("dati_flashscore")

    driver = get_driver()
    wait = WebDriverWait(driver, 12)

    try:
        for url in URLS:
            print(f"\n📅 Analisi campionato: {url}")
            competizione = url.split("/")[4].replace("-", " ").title()

            match_links = get_match_links(driver, wait, url)
            for link in match_links[:10]:  # Limita a 10 match per test
                print(f"\n🔍 Estrazione: {link}")
                dati = estrai_informazioni_partita(driver, wait, link, competizione)
                if not dati:
                    continue

                file_name = f"{dati['home_team']} - {dati['away_team']}.json".replace("/", "-").replace("\\", "-")
                path = os.path.join("dati_flashscore", file_name)

                with open(path, "w", encoding="utf-8") as f:
                    json.dump(dati, f, ensure_ascii=False, indent=2)

                print(f"📂 Salvato: {path}")
                print(f"🏠 {dati['home_team']} | 🚗 {dati['away_team']} | 👨‍⚖️ {dati['arbitro']}")

                delay = random.uniform(4, 7)
                print(f"⏳ Attesa {delay:.1f}s...\n")
                time.sleep(delay)

        git_push()

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
