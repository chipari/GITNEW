import os
import re # Il tuo script originale lo importava
import json
import time
import random
import subprocess
# from datetime import datetime # Non era usato nel tuo script caricato
from unidecode import unidecode # Presente nel tuo script caricato
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

# --- MODIFICA CHIAVE: URL_MAP ---
# Questa mappa associa l'URL specifico al nome corretto e completo della competizione
# I nomi competizione qui devono essere quelli che vuoi vedere nel JSON finale
# e che poi PRONOSTICO_V2.py userà per trovare i file di statistiche
# (potrebbe servire una piccola mappa di conversione in PRONOSTICO_V2.py se questi nomi
# non corrispondono 1:1 ai prefissi dei file, es. "Premier League" -> "premier")
URL_MAP = {
    "https://www.flashscore.it/calcio/italia/serie-a/calendario/": "Serie A",
    "https://www.flashscore.it/calcio/italia/serie-b/calendario/": "Serie B",
    "https://www.flashscore.it/calcio/francia/ligue-1/calendario/": "Ligue 1",
    "https://www.flashscore.it/calcio/francia/ligue-2/calendario/": "Ligue 2",
    "https://www.flashscore.it/calcio/germania/bundesliga/calendario/": "Bundesliga",
    "https://www.flashscore.it/calcio/germania/2-bundesliga/calendario/": "2. Bundesliga",
    "https://www.flashscore.it/calcio/inghilterra/premier-league/calendario/": "Premier League",
    "https://www.flashscore.it/calcio/inghilterra/championship/calendario/": "Championship",
    "https://www.flashscore.it/calcio/olanda/eredivisie/calendario/": "Eredivisie",
    "https://www.flashscore.it/calcio/spagna/laliga/calendario/": "LaLiga",
    "https://www.flashscore.it/calcio/spagna/laliga2/calendario/": "LaLiga2",
    "https://www.flashscore.it/calcio/portogallo/liga-portugal/calendario/": "Liga Portugal",
    "https://www.flashscore.it/calcio/belgio/jupiler-league/calendario/": "Jupiler Pro League"
}
# --- FINE MODIFICA CHIAVE ---


# === DRIVER SETUP (Come da tuo script) ===
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

# === UTILS (Esattamente come da tuo script) ===
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
    nome = re.sub(r'[^a-z\s]', '', nome) # Tolto 0-9, se non serve per nomi squadra/lega
    return nome.strip()

def filtra_indisponibili(raw_list, titolari):
    titolari_normalizzati = {normalizza_nome(n) for n in titolari}
    return [
        g for g in raw_list
        if (n := normalizza_nome(g)) not in titolari_normalizzati
        and n not in {'p', 'gk', 'por', 'portiere'}
        and n != ''
    ]

def svuota_cartella(cartella): # La tua funzione originale
    # Assicura che la cartella esista
    if not os.path.exists(cartella):
        os.makedirs(cartella)
        print(f"Cartella '{cartella}' creata.")
    # Svuota la cartella
    for f in os.listdir(cartella):
        path = os.path.join(cartella, f)
        if os.path.isfile(path):
            os.remove(path)
            # La tua logica originale per git rm --cached
            try:
                subprocess.run(["git", "rm", "--cached", path], check=False) # check=False per non bloccare se file non tracciato
            except subprocess.CalledProcessError:
                pass # Ignora errore se git rm fallisce
    print(f"🧹 Cartella '{cartella}' svuotata.")


def git_push(): # La tua funzione originale
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Aggiornati file scraping Flashscore"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Push su GitHub completato.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore push: {e}")

# === LOGICA PRINCIPALE (Come da tuo script, con 'competizione' dalla mappa) ===
def get_match_links(driver, wait, url): # La tua funzione originale
    try:
        driver.get(url)
        wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "event__match--scheduled")))
        # La tua logica per estrarre i link potrebbe essere diversa, la ripristino alla tua versione caricata
        # se hai una logica specifica per eventRowLink. Qui uso un approccio comune.
        links = []
        elements = driver.find_elements(By.CLASS_NAME, "event__match--scheduled")
        for el in elements:
            try:
                # Tentativo di trovare un link diretto più robusto
                link_tag = el.find_element(By.CSS_SELECTOR, "a[href*='/partita/']")
                href = link_tag.get_attribute("href")
                if href and href.startswith("https://www.flashscore.it/partita/"):
                    links.append(href)
                else: # Fallback se l'href non è completo o non è una partita
                    match_id = el.get_attribute("id")
                    if match_id and match_id.startswith("g_1_"):
                        true_id = match_id.split("g_1_")[1]
                        links.append(f"https://www.flashscore.it/partita/{true_id}/#/match-summary")
            except:
                 # Se il primo selettore fallisce, prova quello del tuo script originale per eventRowLink
                try:
                    link_tag_original = el.find_element(By.CLASS_NAME, "eventRowLink")
                    links.append(link_tag_original.get_attribute("href"))
                except Exception as e_inner:
                    # print(f"    Link non trovato per un elemento evento: {e_inner}")
                    continue
        return links
    except Exception as e:
        print(f"⚠️ Errore raccolta link da {url}: {e}")
        return []

def estrai_informazioni_partita(driver, wait, url, competizione): # La tua funzione originale
    try:
        driver.get(url)
        try:
            wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        except:
            pass

        # Selettore squadre come da tuo script originale
        squadre = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//strong[contains(@class,'detailTeamForm__teamName--ellipsis')]")))
        home, away = squadre[0].text, squadre[1].text

        arbitro = "" # Default a stringa vuota come nel tuo originale
        try:
            # Logica estrazione arbitro come da tuo script originale
            blocco_info = driver.find_element(By.CSS_SELECTOR, "div[data-testid='wcl-summaryMatchInformation']")
            spans = blocco_info.find_elements(By.TAG_NAME, "span")
            # strongs = blocco_info.find_elements(By.TAG_NAME, "strong") # Il tuo script usava gli strongs

            arbitro_trovato = False
            for i, span_element in enumerate(spans): # Rinominato 'span' per evitare conflitto con modulo 'span'
                if span_element.text.strip().upper() == "ARBITRO:":
                    # Cerchiamo l'elemento successivo che contiene il nome, tipicamente un div o strong
                    try:
                        # Tentativo con il div successivo (più comune ora su Flashscore)
                        contenitore_arbitro = span_element.find_element(By.XPATH, "./following-sibling::div[1]")
                        arbitro = contenitore_arbitro.text.strip()
                        if arbitro: arbitro_trovato = True
                        break
                    except:
                        # Fallback: se non è un div, prova a vedere se è in uno strong (come forse era nel tuo)
                        # Questa parte potrebbe necessitare di adattamento al tuo strongs[0] originale se la struttura lo richiede
                        try:
                            # Il tuo codice originale faceva: if i < len(strongs): arbitro = strongs[0].text.strip()
                            # Questo implicava che l'arbitro fosse sempre il primo <strong> nel blocco,
                            # il che potrebbe non essere sempre vero. La logica seguente è un tentativo di
                            # trovare lo strong associato allo span "ARBITRO:", se presente.
                            possible_strongs = blocco_info.find_elements(By.TAG_NAME, "strong")
                            if possible_strongs: # Se ci sono elementi strong nel blocco info
                                # Cerchiamo uno strong che sia vicino allo span "ARBITRO:"
                                # Questa è un'euristica, la tua logica originale con strongs[0] era più diretta se funzionava sempre
                                # Per ora, lascio la logica di prendere il testo dal div successivo, che è più standard
                                # Se la tua logica con strongs[0] è cruciale, ripristinala qui.
                                # Per ora, se il div non funziona, non cerco strongs in modo generico
                                # per evitare di prendere il nome di uno stadio o altro.
                                pass # Lascia che il default sia "" se il div non funziona
                        except:
                            pass # L'arbitro rimane ""
                    break # Esci dal ciclo degli span una volta trovato "ARBITRO:"
            if not arbitro_trovato and arbitro == "": # Se non trovato o rimasto vuoto
                 arbitro = "" # Conferma stringa vuota se non trovato, come da tua preferenza

        except Exception as e:
            # print(f"[❌] Errore estraendo arbitro: {e}") # Silenzio l'errore se preferisci "" come output
            arbitro = ""


        return {
            'home_team': home,
            'away_team': away,
            'arbitro': arbitro, # Rimane stringa vuota se non trovato
            'competizione': competizione, # Questa è ora il nome specifico della lega
        }

    except Exception as e:
        print(f"[❌] Errore generale nel parsing della pagina partita {url}: {e}")
        return None

# === MAIN ===
def main():
    output_folder = "dati_flashscore"
    os.makedirs(output_folder, exist_ok=True)
    svuota_cartella(output_folder) 

    driver = get_driver()
    wait = WebDriverWait(driver, 12) # Il tuo wait originale

    try:
        # --- MODIFICA CHIAVE: Iteriamo sulla mappa URL_MAP ---
        for url, competizione_specifica in URL_MAP.items():
            print(f"\n📅 Analisi campionato: {competizione_specifica} (URL: {url})")
            # La variabile 'competizione' del tuo script originale ora è 'competizione_specifica'
            
            match_links = get_match_links(driver, wait, url)
            if not match_links:
                print(f"    Nessun link di partita trovato per {competizione_specifica}")
                continue

            # Limite di 10 partite come da tua preferenza
            for link_partita in match_links[:10]:  
                print(f"\n🔍 Estrazione: {link_partita}")
                
                # Passiamo la competizione_specifica
                dati_partita = estrai_informazioni_partita(driver, wait, link_partita, competizione_specifica)
                
                if not dati_partita:
                    print(f"    [❌] Dati non estratti per {link_partita}")
                    continue

                # Nome file come nel tuo script originale
                file_name = f"{dati_partita['home_team']} - {dati_partita['away_team']}.json".replace("/", "-").replace("\\", "-")
                path_salvataggio = os.path.join(output_folder, file_name)

                with open(path_salvataggio, "w", encoding="utf-8") as f:
                    json.dump(dati_partita, f, ensure_ascii=False, indent=2)

                print(f"📂 Salvato: {path_salvataggio}")
                # Stampa info come nel tuo script originale
                print(f"🏠 {dati_partita['home_team']} | 🚗 {dati_partita['away_team']} | 👨‍⚖️ {dati_partita['arbitro']}")


                delay = random.uniform(4, 7) # Delay come da tuo script originale
                print(f"⏳ Attesa {delay:.1f}s...\n")
                time.sleep(delay)

        git_push()

    finally:
        driver.quit()
        print("\n🎉 Processo di scraping completato.")

if __name__ == "__main__":
    main()