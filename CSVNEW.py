import os
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import subprocess
import shutil # Aggiunto per svuota_cartella_git più robusta

# === CONFIGURAZIONE (invariata) ===
CAMPIONATI = {
    "serie_a": "I1", "serie_b": "I2", "premier": "E0", "championship": "E1",
    "bundesliga": "D1", "2bundesliga": "D2", "ligue1": "F1", "ligue2": "F2",
    "la_liga": "SP1", "laliga2": "SP2", "jupiler_league": "B1",
    "eredivisie": "N1", "liga_1": "P1"
}
URL_BASE = "https://www.football-data.co.uk/mmz4281"
CARTELLA_CSV = "./dati_csv" # I file CSV grezzi verranno salvati qui

MAPPA_COLONNE = { # Come l'avevamo definita per la pulizia dei nomi
    'Date': 'data', 'HomeTeam': 'squadra_casa', 'AwayTeam': 'squadra_trasferta',
    'FTHG': 'gol_casa', 'FTAG': 'gol_trasferta', 'HTHG': 'gol_casa_1T',
    'HTAG': 'gol_trasferta_1T', 'HS': 'tiri_casa', 'AS': 'tiri_trasferta',
    'HST': 'tiri_porta_casa', 'AST': 'tiri_porta_trasferta', 'HC': 'corner_casa',
    'AC': 'corner_trasferta', 'HF': 'falli_casa', 'AF': 'falli_trasferta',
    'HY': 'gialli_casa', 'AY': 'gialli_trasferta', 'HR': 'rossi_casa', 'AR': 'rossi_trasferta'
}
COLONNE_DA_TENERE_ORIGINALI = list(MAPPA_COLONNE.keys()) # Nomi originali da football-data.co.uk

# === FUNZIONI DI UTILITÀ GIT E PULIZIA CARTELLA ===
def svuota_cartella_git(cartella):
    """
    Svuota la cartella specificata, rimuovendo i file anche dal tracciamento Git se presenti.
    Se la cartella non esiste, la crea.
    """
    if os.path.exists(cartella):
        print(f"🧹 Inizio svuotamento e pulizia Git per la cartella: {cartella}")
        # Prima rimuovi i file da Git, poi dal filesystem
        # Questo evita errori se un file è tracciato ma già cancellato localmente
        file_da_rimuovere_git = []
        for root, _, files in os.walk(cartella):
            for name in files:
                file_da_rimuovere_git.append(os.path.join(root, name).replace("\\", "/")) # Git usa slash /
        
        if file_da_rimuovere_git:
            try:
                # Tentativo di rimuovere i file dall'indice di Git
                # L'opzione --ignore-unmatch è utile per non generare errori se i file non sono tracciati
                comando_git_rm = ["git", "rm", "-f", "--cached"] + file_da_rimuovere_git
                subprocess.run(comando_git_rm, check=True, capture_output=True, text=True)
                print(f"🗑️ File rimossi dall'indice di Git nella cartella '{cartella}'.")
            except subprocess.CalledProcessError as e:
                # Non è un errore bloccante se `git rm` fallisce (es. file non tracciati)
                print(f"⚠️ Avviso durante git rm: {e.stderr}")
        
        # Ora svuota fisicamente la cartella
        shutil.rmtree(cartella)
        os.makedirs(cartella, exist_ok=True)
        print(f"✅ Cartella '{cartella}' svuotata e ricreata.")
    else:
        os.makedirs(cartella, exist_ok=True)
        print(f"✅ Cartella '{cartella}' creata perché non esisteva.")


def git_push(messaggio="Aggiornati file CSV storici (ultime 5 stagioni)"):
    try:
        # Aggiungo specificamente la cartella dei dati CSV
        subprocess.run(["git", "add", CARTELLA_CSV], check=True)
        
        # Controllo se ci sono modifiche da committare prima di tentare il commit
        # 'git diff --staged --quiet' esce con 1 se ci sono modifiche staged, 0 altrimenti
        result_diff = subprocess.run(["git", "diff", "--staged", "--quiet"])
        
        if result_diff.returncode == 1: # Ci sono modifiche staged
            subprocess.run(["git", "commit", "-m", messaggio], check=True)
            print("🚀 Commit eseguito.")
            subprocess.run(["git", "push"], check=True)
            print("✅ Push su GitHub completato.")
        else:
            print("✅ Nessuna nuova modifica ai file CSV da committare.")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore durante il processo Git: {e.output.decode() if e.output else e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        print(f"❌ Errore imprevisto durante il push Git: {e}")

# === LOGICA PRINCIPALE DI SCARICAMENTO ===
def scarica_csv(numero_stagioni_passate=4): # Scarica attuale + 4 passate = 5 totali
    """
    Scarica i file CSV per i campionati specificati, considerando la stagione attuale
    e un numero definito di stagioni precedenti.
    """
    os.makedirs(CARTELLA_CSV, exist_ok=True)
    
    stagioni_da_processare = []
    anno_corrente_intero = datetime.now().year
    mese_corrente = datetime.now().month

    # Determina l'anno di inizio (breve, es. 23 per 2023) della stagione corrente
    if mese_corrente >= 7: # Da luglio in poi, consideriamo la nuova stagione (es. 24/25 se siamo a luglio 2024)
        anno_inizio_stagione_corrente_short = anno_corrente_intero % 100
    else: # Prima di luglio, siamo ancora nella stagione precedente (es. 23/24 se siamo a maggio 2024)
        anno_inizio_stagione_corrente_short = (anno_corrente_intero - 1) % 100
    
    # Genera le tuple per la stagione corrente e le N stagioni precedenti
    for i in range(numero_stagioni_passate + 1): # +1 per includere la corrente
        start_year_short = anno_inizio_stagione_corrente_short - i
        end_year_short = start_year_short + 1
        stagioni_da_processare.append((start_year_short, end_year_short))

    print(f"🗓️  Stagioni che verranno scaricate (formato YY, YY+1): {stagioni_da_processare}")

    for nome_campionato_file, codice_campionato_data in CAMPIONATI.items():
        print(f"\n--- Elaboro Campionato: {nome_campionato_file.replace('_', ' ').title()} ---")
        for start_yy, end_yy in stagioni_da_processare:
            # Formatta gli anni per l'URL (es. 2324, 0910)
            stagione_url_format = f"{start_yy:02d}{end_yy:02d}"
            url = f"{URL_BASE}/{stagione_url_format}/{codice_campionato_data}.csv"
            
            print(f"➡️  Scarico: {url}")
            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()  # Controlla errori HTTP (4xx, 5xx)
                response.encoding = 'utf-8-sig' # Gestisce il BOM (Byte Order Mark) a volte presente
                
                # Controllo se il contenuto è vuoto o ha solo l'header
                contenuto_csv = response.text.strip()
                if not contenuto_csv or len(contenuto_csv.splitlines()) < 2:
                    print(f"⚠️  File vuoto o solo header per {url}. Salto.")
                    continue

                df = pd.read_csv(StringIO(contenuto_csv))

                # Seleziona solo le colonne che ci interessano (basate sui nomi originali)
                colonne_effettive_da_tenere = [col for col in COLONNE_DA_TENERE_ORIGINALI if col in df.columns]
                if not colonne_effettive_da_tenere:
                    print(f"⚠️  Nessuna colonna rilevante trovata in {url} dopo il filtro. Salto.")
                    continue
                df = df[colonne_effettive_da_tenere]

                # Ridenomina le colonne
                df.rename(columns=MAPPA_COLONNE, inplace=True)
                
                # Conversione tipi di dato e gestione errori
                colonne_numeriche_da_convertire = [
                    'gol_casa', 'gol_trasferta', 'gol_casa_1T', 'gol_trasferta_1T', 'tiri_casa', 
                    'tiri_trasferta', 'tiri_porta_casa', 'tiri_porta_trasferta', 'corner_casa', 
                    'corner_trasferta', 'falli_casa', 'falli_trasferta', 'gialli_casa', 
                    'gialli_trasferta', 'rossi_casa', 'rossi_trasferta'
                ]
                for col in colonne_numeriche_da_convertire:
                    if col in df.columns: # Applica solo se la colonna esiste dopo la ridenominazione
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                
                if 'data' in df.columns:
                    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce') # Modificato format in %y per date tipo 23/08/23
                    df.dropna(subset=['data'], inplace=True) # Rimuove righe con data non valida
                    df.sort_values(by='data', ascending=True, inplace=True) # Ordina per data
                else:
                    print(f"⚠️  Colonna 'data' non trovata in {url}. Impossibile ordinare o validare le date.")


                df["stagione_calc"] = f"{start_yy:02d}{end_yy:02d}" # Per riferimento futuro
                
                nome_file_output = f"{nome_campionato_file}_{start_yy:02d}{end_yy:02d}.csv"
                percorso_file_output = os.path.join(CARTELLA_CSV, nome_file_output)
                df.to_csv(percorso_file_output, index=False)
                print(f"✅ Salvato e pulito: {nome_file_output} ({len(df)} partite)")

            except requests.exceptions.HTTPError as e:
                print(f"❌ Errore HTTP scaricando {url}: {e.response.status_code}. File non trovato o errore server. Salto.")
            except requests.exceptions.RequestException as e:
                print(f"❌ Errore di rete con {url}: {e}. Salto.")
            except pd.errors.EmptyDataError:
                print(f"⚠️  Dati vuoti o illeggibili in {url} dopo il download. Salto.")
            except Exception as e:
                print(f"❌ Errore generico durante l'elaborazione di {url}: {e}")

if __name__ == "__main__":
    # Svuota la cartella CSV e la ricrea, rimuovendo anche i file da Git
    svuota_cartella_git(CARTELLA_CSV)
    
    # Scarica i nuovi CSV (stagione attuale + 4 precedenti)
    # Se vuoi 5 stagioni passate (per un totale di 6 con quella attuale), metti numero_stagioni_passate=5
    scarica_csv(numero_stagioni_passate=4) 
    
    # Esegui commit e push su GitHub
    git_push()