import os
import glob
import pandas as pd
import shutil
import subprocess

# === CONFIGURAZIONE ===
CARTELLA_DATI_CSV = "./dati_csv" # Da dove leggere i file delle partite scaricati
CARTELLA_CLASSIFICHE_CORRENTI = "./classifiche_csv" # Dove salvare le classifiche "attuali" (ultima stagione disponibile)
CARTELLA_CLASSIFICHE_STORICHE = "./classifiche_storiche_csv" # NUOVA: Dove salvare le classifiche finali storiche

# CAMPIONATI è definito in CSV.py, ma qui ci serve per iterare sui nomi dei file.
# Potremmo importarlo o ridefinire i nomi base se necessario.
# Per ora assumiamo che i nomi file in CARTELLA_DATI_CSV seguano il pattern NOMEBASE_CAMPIONATO_STAGIONE.csv
# es. serie_a_2324.csv. Useremo glob per trovare i file.

# === FUNZIONI DI UTILITÀ (le stesse degli altri script) ===

def svuota_e_crea_cartella(path):
    """Svuota una cartella eliminando file e sottodirectory, poi la ricrea."""
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    print(f"🧹 Cartella '{path}' svuotata e ricreata.")

def git_push_classifiche(commit_msg="Aggiornamento classifiche correnti e storiche"):
    """Aggiunge le cartelle delle classifiche, committa e pusha su Git."""
    try:
        subprocess.run(["git", "add", CARTELLA_CLASSIFICHE_CORRENTI, CARTELLA_CLASSIFICHE_STORICHE], check=True)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            print("🚀 Commit per classifiche eseguito.")
            subprocess.run(["git", "push"], check=True)
            print("✅ Push su GitHub per classifiche completato.")
        else:
            print("✅ Nessuna modifica nelle classifiche da committare.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore durante il processo Git per classifiche: {e.output.decode() if e.output else e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        print(f"❌ Errore imprevisto durante il push Git per classifiche: {e}")

# === LOGICA PRINCIPALE PER LA CLASSIFICA (MODIFICATA) ===

def calcola_e_salva_classifica_da_file(percorso_file_csv: str, cartella_output: str, nome_file_output: str):
    """
    Calcola la classifica da un singolo file CSV di una stagione e la salva.
    """
    try:
        df_stagione = pd.read_csv(percorso_file_csv)
        if df_stagione.empty:
            print(f"⚠️ File CSV vuoto: {percorso_file_csv}. Salto.")
            return
            
        # Assicurati che le colonne necessarie esistano e siano del tipo corretto
        colonne_richieste = ['squadra_casa', 'squadra_trasferta', 'gol_casa', 'gol_trasferta']
        for col in colonne_richieste:
            if col not in df_stagione.columns:
                print(f"ERRORE: Colonna '{col}' mancante in {percorso_file_csv}. Salto.")
                return
        
        # Conversione sicura a numerico, gestendo eventuali stringhe vuote o non numeriche
        for col in ['gol_casa', 'gol_trasferta']:
             df_stagione[col] = pd.to_numeric(df_stagione[col], errors='coerce').fillna(0).astype(int)

    except Exception as e:
        print(f"ERRORE: Impossibile leggere o processare il file {percorso_file_csv}: {e}. Salto.")
        return

    squadre = pd.unique(df_stagione[['squadra_casa', 'squadra_trasferta']].values.ravel('K'))
    squadre = [s for s in squadre if pd.notna(s)] # Rimuovi eventuali NaN se presenti nei nomi squadra

    classifica = {squadra: {
        'Punti': 0, 'Giocate': 0, 'Vinte': 0, 'Nulle': 0, 'Perse': 0,
        'GF': 0, 'GS': 0, 'DR': 0
    } for squadra in squadre}

    for _, partita in df_stagione.iterrows():
        casa = partita['squadra_casa']
        trasferta = partita['squadra_trasferta']
        gol_casa = partita['gol_casa']
        gol_trasferta = partita['gol_trasferta']

        if pd.isna(casa) or pd.isna(trasferta): # Salta righe con squadre mancanti
            continue

        classifica[casa]['Giocate'] += 1
        classifica[trasferta]['Giocate'] += 1
        classifica[casa]['GF'] += gol_casa
        classifica[trasferta]['GF'] += gol_trasferta
        classifica[casa]['GS'] += gol_trasferta
        classifica[trasferta]['GS'] += gol_casa

        if gol_casa > gol_trasferta:
            classifica[casa]['Punti'] += 3
            classifica[casa]['Vinte'] += 1
            classifica[trasferta]['Perse'] += 1
        elif gol_trasferta > gol_casa:
            classifica[trasferta]['Punti'] += 3
            classifica[trasferta]['Vinte'] += 1
            classifica[casa]['Perse'] += 1
        else: # Pareggio (anche 0-0)
            classifica[casa]['Punti'] += 1
            classifica[trasferta]['Punti'] += 1
            classifica[casa]['Nulle'] += 1
            classifica[trasferta]['Nulle'] += 1
            
    df_classifica = pd.DataFrame.from_dict(classifica, orient='index')
    if df_classifica.empty:
        print(f"⚠️  Classifica vuota generata per {percorso_file_csv}. Salto salvataggio.")
        return
        
    df_classifica['Squadra'] = df_classifica.index
    df_classifica['DR'] = df_classifica['GF'] - df_classifica['GS']
    df_classifica.sort_values(by=['Punti', 'DR', 'GF'], ascending=[False, False, False], inplace=True)
    df_classifica.insert(0, 'Pos', range(1, len(df_classifica) + 1))
    df_classifica = df_classifica[['Pos', 'Squadra', 'Punti', 'Giocate', 'Vinte', 'Nulle', 'Perse', 'GF', 'GS', 'DR']]
    
    os.makedirs(cartella_output, exist_ok=True) # Assicura che la cartella esista
    percorso_salvataggio = os.path.join(cartella_output, nome_file_output)
    df_classifica.to_csv(percorso_salvataggio, index=False)
    print(f"✅ Classifica salvata: {percorso_salvataggio}")


if __name__ == "__main__":
    svuota_e_crea_cartella(CARTELLA_CLASSIFICHE_CORRENTI)
    svuota_e_crea_cartella(CARTELLA_CLASSIFICHE_STORICHE)

    # Trova tutti i file CSV nella cartella dei dati grezzi
    tutti_i_file_csv_stagionali = glob.glob(os.path.join(CARTELLA_DATI_CSV, "*.csv"))

    campionati_elaborati = {} # Per tenere traccia dell'ultima stagione per la classifica "corrente"

    for percorso_file_csv in tutti_i_file_csv_stagionali:
        nome_file_con_estensione = os.path.basename(percorso_file_csv)
        nome_file_senza_estensione = os.path.splitext(nome_file_con_estensione)[0]
        
        # Estrai nome base campionato e stagione dal nome file
        # Es. "serie_a_2324" -> nome_base = "serie_a", stagione_str = "2324"
        parti_nome_file = nome_file_senza_estensione.split('_')
        if len(parti_nome_file) < 2:
            print(f"⚠️ Nome file non standard, impossibile estrarre stagione: {nome_file_con_estensione}. Salto.")
            continue
        
        stagione_str = parti_nome_file[-1] # Ultima parte è la stagione
        nome_base_campionato = "_".join(parti_nome_file[:-1]) # Tutto il resto è il nome base

        # Controlla se la stagione_str è numerica e di lunghezza 4 (es. 2324)
        if not (stagione_str.isdigit() and len(stagione_str) == 4):
            print(f"⚠️ Formato stagione non riconosciuto in {nome_file_con_estensione}. Salto.")
            continue

        # 1. Salva la classifica storica
        nome_file_classifica_storica = f"classifica_{nome_base_campionato}_{stagione_str}_finale.csv"
        calcola_e_salva_classifica_da_file(percorso_file_csv, CARTELLA_CLASSIFICHE_STORICHE, nome_file_classifica_storica)

        # 2. Determina se è il file più recente per questo campionato per la classifica "corrente"
        if nome_base_campionato not in campionati_elaborati or stagione_str > campionati_elaborati[nome_base_campionato]['stagione']:
            campionati_elaborati[nome_base_campionato] = {
                'stagione': stagione_str,
                'percorso_file': percorso_file_csv
            }

    # 3. Genera le classifiche "correnti" usando i file più recenti identificati
    print("\n--- Genero Classifiche Correnti (basate sulla stagione più recente disponibile) ---")
    for nome_base_campionato, info in campionati_elaborati.items():
        nome_file_classifica_corrente = f"classifica_{nome_base_campionato}_corrente.csv"
        calcola_e_salva_classifica_da_file(info['percorso_file'], CARTELLA_CLASSIFICHE_CORRENTI, nome_file_classifica_corrente)
        
    git_push_classifiche()