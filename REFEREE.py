import os
import json
import time
import random
import glob
import subprocess
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc



# === Config ===
CARTELLA_JSON = r"C:\Users\Raffaele\Desktop\GIT\dati_flashscore"
CARTELLA_SALVATAGGIO = r"C:\Users\Raffaele\Desktop\GIT\dati_arbitri"
LOG_ERRORI = os.path.join(CARTELLA_SALVATAGGIO, "arbitri_non_trovati.log")

# Crea la cartella di salvataggio se non esiste
os.makedirs(CARTELLA_SALVATAGGIO, exist_ok=True)

# Lista di user-agent comuni (puoi aggiungerne altri)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:58.0) Gecko/20100101 Firefox/58.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.97 Safari/537.36",
    # Aggiungi altri user-agent qui
]
# LOG ERRORI
def scrivi_log_errore(arbitro, motivo="Errore generico"):
    with open(LOG_ERRORI, "a", encoding="utf-8") as log:
        log.write(f"{arbitro} - {motivo}\n")

# === CONFIGURAZIONE DRIVER ===
def get_driver():
    options = uc.ChromeOptions()
   # options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--window-position=-10000,-10000")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    return uc.Chrome(options=options)  

def wait_random(min_wait=2, max_wait=5):
    time.sleep(random.uniform(min_wait, max_wait))

# === Funzione per leggere gli arbitri dai JSON ===
def estrai_arbitri(cartella):
    arbitri = set()
    for file in glob.glob(os.path.join(cartella, "*.json")):
        with open(file, "r", encoding="utf-8") as f:
            dati = json.load(f)
            nome_arbitro = dati.get("arbitro", "").strip()
            if nome_arbitro:
                arbitri.add(nome_arbitro)
    return sorted(arbitri)
# === Funzione per chiudere eventuali pop-up ===

def chiudi_popup(driver):
    try:
        # 1. Primo popup
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.close-popup"))
            )
            close_button.click()
            print("❌ Primo popup chiuso.")
        except:
            print("✅ Nessun primo popup.")

        # 2. Banner cookie — usando testo visibile "ACCETTO"
        try:
            accetto_button = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='ACCETTO']]"))
            )
            driver.execute_script("arguments[0].click();", accetto_button)  # se normale .click() fallisce
            print("🍪 Cookie accettati.")
        except Exception as e:
            print(f"⚠️ Cookie non accettati o già accettati. Dettagli: {e}")

        # 3. Secondo popup
        try:
            close_x_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.close-popup-x"))
            )
            close_x_button.click()
            print("❌ Secondo popup chiuso.")
        except:
            print("✅ Nessun secondo popup.")

    except Exception as e:
        print(f"[❌] Errore generale nella gestione dei pop-up: {e}")


# === Estrai tutte le statistiche dell'arbitro in Serie A ===
def estrai_statistiche_arbitro(driver):
    try:
        righe = driver.find_elements(By.CSS_SELECTOR, "#referee-tournaments-table-body tr")
        for riga in righe:
            # Controllo per il campionato specifico
            if "Serie A" in riga.text:
                competizione = "Serie A"
            elif "LaLiga" in riga.text:
                competizione = "La Liga"
            elif "Bundesliga" in riga.text:
                competizione = "Bundesliga"
            elif "Eredivisie" in riga.text:
                competizione = "Eredivisie"
            elif "Ligue 1" in riga.text:
                competizione = "Ligue 1"
            elif "Liga Portugal" in riga.text:
                competizione = "Liga Portugal"
            elif "Championship" in riga.text:
                competizione = "Championship"
            elif "Premier League" in riga.text:
                competizione = "Premier League"
            elif "Jupiler Pro League" in riga.text:
                competizione = "Jupiler Pro League"
            elif "2. Bundesliga" in riga.text:
                competizione = "2.Bundesliga"  # Aggiunto il controllo per la 2. Bundesliga
            else:
                continue  # Skip this row if no competition matches

            # Estrazione delle celle per il campionato trovato
            celle = riga.find_elements(By.TAG_NAME, "td")
            if len(celle) >= 9:
                return {
                    "competizione": competizione,
                    "presenze": celle[1].text.strip(),
                    "falli_pg": celle[2].text.strip(),
                    "falli_per_contrasto": celle[3].text.strip(),
                    "rigori_pg": celle[4].text.strip(),
                    "gialli_pg": celle[5].text.strip(),
                    "gialli_tot": celle[6].text.strip(),
                    "rossi_pg": celle[7].text.strip(),
                    "rossi_tot": celle[8].text.strip()
                }
    except Exception as e:
        print(f"[❌] Errore durante l'estrazione delle statistiche: {e}")
    return None


# === Funzione per cercare su Swisscows e ottenere i dati da WhoScored ===
def cerca_su_swisscows(arbitro):
    print(f"[✔️] Cercando {arbitro} su Swisscows...")

    driver = get_driver()

    try:
        driver.get(f"https://swisscows.com/it/web?query={arbitro}+referee whoscored")
        wait_random(4, 6)

        # Cerca tutti i link e seleziona quello di WhoScored (anche sottodomini come es.whoscored.com)
        tutti_link = driver.find_elements(By.CSS_SELECTOR, "a.mainlink")
        href = None
        for link in tutti_link:
            url = link.get_attribute("href")
            if "whoscored.com" in url:
                href = url
                break

        if not href:
            print(f"[❌] Nessun link WhoScored trovato per {arbitro}")
            scrivi_log_errore(arbitro, "Nessun link WhoScored trovato")
            driver.quit()
            return
        
        


        driver.get(href)
        wait_random(4, 6)

        stats = estrai_statistiche_arbitro(driver)
        if stats:
            print(f"[📊] Statistiche per {arbitro} in Serie A:")
            for k, v in stats.items():
                print(f"   - {k}: {v}")

            stats["nome_arbitro"] = arbitro
            stats["url_whoscored"] = href  # Salva il link di WhoScored
            nome_file = f"arbitro_{arbitro.replace(' ', '').replace('.', '')}.json"
            percorso = os.path.join(CARTELLA_SALVATAGGIO, nome_file)
            with open(percorso, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            print(f"[💾] Statistiche salvate in: {percorso}")

        else:
            print(f"[❌] Statistiche Serie A non trovate per {arbitro}")
            scrivi_log_errore(arbitro, "Statistiche Serie A non trovate")
    
    except Exception as e:
        print(f"[❌] Errore durante la procedura per {arbitro}: {e}")
        scrivi_log_errore(arbitro, f"Eccezione: {str(e)}")
    
    finally:
        driver.quit()  # Chiude sempre il driver

def pulisci_file_vecchi(cartella, giorni=7):
    now = time.time()
    for f in os.listdir(cartella):
        p = os.path.join(cartella, f)
        if os.path.isfile(p) and now - os.path.getmtime(p) > giorni * 86400:
            os.remove(p)
            print(f"🗑️  Rimosso: {f}")

# Pulizia dei file vecchi
pulisci_file_vecchi(CARTELLA_SALVATAGGIO)

# === GIT PUSH ===
def git_push():
    try:
        subprocess.run(["git", "add", "."], check=True)  # Aggiunge tutti i file modificati e nuovi
        subprocess.run(["git", "commit", "-m", "Aggiornati file scraping arbitri"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Push su GitHub completato.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore push: {e}")

# === Main ===
if __name__ == "__main__":
    arbitri = estrai_arbitri(CARTELLA_JSON)
    print(f"Trovati {len(arbitri)} arbitri: {arbitri}")

    for arbitro in arbitri:
        try:
            cerca_su_swisscows(arbitro)
        except Exception as e:
            print(f"[❌] Errore con l'arbitro {arbitro}: {e}")

    # Esegui il push su GitHub solo alla fine
    git_push()
