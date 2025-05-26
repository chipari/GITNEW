import os
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import subprocess

# === CONFIGURAZIONE ===
CAMPIONATI = {
    "serie_a": "I1",
    "serie_b": "I2",
    "premier": "E0",
    "championship": "E1",
    "bundesliga": "D1",
    "2bundesliga": "D2",
    "ligue1": "F1",
    "ligue2": "F2",
    "la_liga": "SP1",
    "laliga2": "SP2",
    "jupiler_league": "B1",
    "eredivisie": "N1",
    "liga_1": "P1"
}

URL_BASE = "https://www.football-data.co.uk/mmz4281"
CARTELLA_CSV = "./dati_csv"

# MODIFICA: Mappa per ridenominare le colonne da un formato criptico a uno leggibile.
# Questo semplificherà enormemente tutto il codice di analisi successivo.
MAPPA_COLONNE = {
    'Date': 'data',
    'HomeTeam': 'squadra_casa',
    'AwayTeam': 'squadra_trasferta',
    'FTHG': 'gol_casa',           # Full Time Home Goals
    'FTAG': 'gol_trasferta',      # Full Time Away Goals
    'HTHG': 'gol_casa_1T',        # Half Time Home Goals
    'HTAG': 'gol_trasferta_1T',   # Half Time Away Goals
    'HS': 'tiri_casa',            # Home Shots
    'AS': 'tiri_trasferta',       # Away Shots
    'HST': 'tiri_porta_casa',     # Home Shots on Target
    'AST': 'tiri_porta_trasferta',# Away Shots on Target
    'HC': 'corner_casa',          # Home Corners
    'AC': 'corner_trasferta',     # Away Corners
    'HF': 'falli_casa',           # Home Fouls
    'AF': 'falli_trasferta',     # Away Fouls
    'HY': 'gialli_casa',          # Home Yellow Cards
    'AY': 'gialli_trasferta',     # Away Yellow Cards
    'HR': 'rossi_casa',           # Home Red Cards
    'AR': 'rossi_trasferta'       # Away Red Cards
}

# MODIFICA: Invece di definire cosa RIMUOVERE, definiamo cosa TENERE.
# È più pulito e robusto se il sito aggiunge nuove colonne di scommesse in futuro.
COLONNE_DA_TENERE = list(MAPPA_COLONNE.keys())

def svuota_cartella_git(cartella):
    if not os.path.exists(cartella):
        print(f"ℹ️ La cartella '{cartella}' non esiste, la creo.")
        os.makedirs(cartella)
        return
        
    files = [f for f in os.listdir(cartella) if os.path.isfile(os.path.join(cartella, f))]
    if not files:
        print(f"✅ La cartella '{cartella}' è già vuota.")
        return
        
    print(f"🧹 Svuoto cartella '{cartella}' e la preparo per Git...")
    for f in files:
        path = os.path.join(cartella, f)
        try:
            # Usiamo --ignore-unmatch per non avere errori se il file non è tracciato
            subprocess.run(["git", "rm", "--cached", path], check=True, capture_output=True)
            os.remove(path)
            print(f"🗑️ Rimosso da Git e filesystem: {path}")
        except subprocess.CalledProcessError:
            os.remove(path)
            print(f"🗑️ File rimosso solo dal filesystem (non era tracciato): {path}")

def git_push(messaggio="Aggiornati file CSV da football-data.co.uk"):
    try:
        # Aggiungo specificamente la cartella dei dati per evitare di includere altri file
        subprocess.run(["git", "add", CARTELLA_CSV], check=True)
        # Eseguo il commit solo se ci sono modifiche da committare
        # 'git diff --staged --quiet' esce con 1 se ci sono modifiche, 0 altrimenti
        result = subprocess.run(["git", "diff", "--staged", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", messaggio], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ Push su GitHub completato.")
        else:
            print("✅ Nessuna nuova modifica da committare.")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore durante il processo Git: {e}")

def scarica_csv():
    os.makedirs(CARTELLA_CSV, exist_ok=True)
    mese_attuale = datetime.now().month
    anno = datetime.now().year % 100

    stagione_corrente = (anno, anno + 1) if mese_attuale >= 7 else (anno - 1, anno)
    stagione_precedente = (stagione_corrente[0] - 1, stagione_corrente[0])

    stagioni = [stagione_corrente, stagione_precedente]

    for nome_campionato, codice in CAMPIONATI.items():
        for start, end in stagioni:
            url = f"{URL_BASE}/{start:02d}{end:02d}/{codice}.csv"
            print(f"➡️ Scarico: {url}")
            try:
                response = requests.get(url, timeout=15)
                response.raise_for_status()  # Controlla se ci sono errori HTTP
                response.encoding = 'utf-8-sig' # 'utf-8-sig' gestisce meglio il BOM
                
                # A volte il sito restituisce un file CSV vuoto o con solo l'header
                if len(response.text.strip().splitlines()) < 2:
                    print(f"⚠️ File vuoto o solo header per {nome_campionato} {start}/{end}. Salto.")
                    continue

                df = pd.read_csv(StringIO(response.text))

                # Seleziona solo le colonne che ci interessano
                colonne_effettive_da_tenere = [col for col in COLONNE_DA_TENERE if col in df.columns]
                df = df[colonne_effettive_da_tenere]

                # Ridenomina le colonne in un formato standard e pulito
                df.rename(columns=MAPPA_COLONNE, inplace=True)
                
                # MODIFICA: Converti i tipi di dato per sicurezza
                colonne_numeriche = [
                    'gol_casa', 'gol_trasferta', 'gol_casa_1T', 'gol_trasferta_1T',
                    'tiri_casa', 'tiri_trasferta', 'tiri_porta_casa', 'tiri_porta_trasferta',
                    'corner_casa', 'corner_trasferta', 'falli_casa', 'falli_trasferta',
                    'gialli_casa', 'gialli_trasferta', 'rossi_casa', 'rossi_trasferta'
                ]
                
                for col in colonne_numeriche:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

                df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
                df.dropna(subset=['data'], inplace=True) # Rimuove righe con data non valida

                df["stagione"] = f"{start:02d}{end:02d}"
                
                nome_file = f"{nome_campionato}_{start:02d}{end:02d}.csv"
                file_path = os.path.join(CARTELLA_CSV, nome_file)
                df.to_csv(file_path, index=False)
                print(f"✅ Salvato e pulito: {nome_file} ({len(df)} partite)")

            except requests.exceptions.RequestException as e:
                print(f"❌ Errore di rete con {url}: {e}")
            except Exception as e:
                print(f"❌ Errore generico con {url}: {e}")

if __name__ == "__main__":
    svuota_cartella_git(CARTELLA_CSV)
    scarica_csv()
    git_push()