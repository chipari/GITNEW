import os
import glob
import pandas as pd
import shutil
import subprocess

# === CONFIGURAZIONE ===
CARTELLA_CSV = "./dati_csv"
CARTELLA_CLASSIFICHE_OUTPUT = "./classifiche_csv"
CAMPIONATI = {
    "serie_a": "I1", "serie_b": "I2", "premier": "E0", "championship": "E1",
    "bundesliga": "D1", "2bundesliga": "D2", "ligue1": "F1", "ligue2": "F2",
    "la_liga": "SP1", "laliga2": "SP2", "jupiler_league": "B1",
    "eredivisie": "N1", "liga_1": "P1"
}

# === FUNZIONI DI UTILITÀ (le stesse degli altri script) ===

def svuota_cartella(path):
    """Svuota una cartella eliminando file e sottodirectory."""
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    print(f"🧹 Cartella '{path}' svuotata e ricreata.")

def git_push(commit_msg="Aggiornamento classifiche campionati"):
    """Aggiunge la cartella delle classifiche, committa e pusha su Git."""
    try:
        subprocess.run(["git", "add", CARTELLA_CLASSIFICHE_OUTPUT], check=True)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ Commit e push per le classifiche completato.")
        else:
            print("✅ Nessuna modifica nelle classifiche da committare.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore durante il processo Git: {e}")

# === LOGICA PRINCIPALE PER LA CLASSIFICA ===

def genera_classifica_campionato(nome_campionato):
    """
    Genera la classifica per la stagione corrente di un dato campionato.
    """
    # Carica solo il file della stagione più recente
    files = sorted(glob.glob(os.path.join(CARTELLA_CSV, f"{nome_campionato}_*.csv")), reverse=True)
    if not files:
        print(f"⚠️ Nessun file CSV trovato per {nome_campionato}")
        return pd.DataFrame()

    df_stagione_corrente = pd.read_csv(files[0])
    
    # Prendi la lista di tutte le squadre
    squadre = pd.unique(df_stagione_corrente[['squadra_casa', 'squadra_trasferta']].values.ravel('K'))
    
    # Inizializza la struttura dati per la classifica
    classifica = {squadra: {
        'Punti': 0, 'Giocate': 0, 'Vinte': 0, 'Nulle': 0, 'Perse': 0,
        'GF': 0, 'GS': 0, 'DR': 0
    } for squadra in squadre}

    # Itera su ogni partita per calcolare i punti e le statistiche
    for _, partita in df_stagione_corrente.iterrows():
        casa = partita['squadra_casa']
        trasferta = partita['squadra_trasferta']
        gol_casa = partita['gol_casa']
        gol_trasferta = partita['gol_trasferta']

        # Aggiorna partite giocate, GF e GS per entrambe
        classifica[casa]['Giocate'] += 1
        classifica[trasferta]['Giocate'] += 1
        classifica[casa]['GF'] += gol_casa
        classifica[trasferta]['GF'] += gol_trasferta
        classifica[casa]['GS'] += gol_trasferta
        classifica[trasferta]['GS'] += gol_casa

        # Assegna punti e risultato
        if gol_casa > gol_trasferta: # Vittoria casa
            classifica[casa]['Punti'] += 3
            classifica[casa]['Vinte'] += 1
            classifica[trasferta]['Perse'] += 1
        elif gol_trasferta > gol_casa: # Vittoria trasferta
            classifica[trasferta]['Punti'] += 3
            classifica[trasferta]['Vinte'] += 1
            classifica[casa]['Perse'] += 1
        else: # Pareggio
            classifica[casa]['Punti'] += 1
            classifica[trasferta]['Punti'] += 1
            classifica[casa]['Nulle'] += 1
            classifica[trasferta]['Nulle'] += 1
            
    # Converti il dizionario in un DataFrame di Pandas
    df_classifica = pd.DataFrame.from_dict(classifica, orient='index')
    df_classifica['Squadra'] = df_classifica.index
    
    # Calcola la differenza reti
    df_classifica['DR'] = df_classifica['GF'] - df_classifica['GS']
    
    # Ordina la classifica secondo le regole standard (Punti > DR > GF)
    df_classifica.sort_values(by=['Punti', 'DR', 'GF'], ascending=[False, False, False], inplace=True)
    
    # Aggiungi la colonna della posizione e riordina le colonne per leggibilità
    df_classifica.insert(0, 'Pos', range(1, len(df_classifica) + 1))
    df_classifica = df_classifica[['Pos', 'Squadra', 'Punti', 'Giocate', 'Vinte', 'Nulle', 'Perse', 'GF', 'GS', 'DR']]
    
    return df_classifica

if __name__ == "__main__":
    svuota_cartella(CARTELLA_CLASSIFICHE_OUTPUT)

    for nome_campionato in CAMPIONATI:
        print(f"🏆 Genero classifica per: {nome_campionato}")
        df_classifica = genera_classifica_campionato(nome_campionato)
        
        if not df_classifica.empty:
            nome_file = f"classifica_{nome_campionato}.csv"
            file_path = os.path.join(CARTELLA_CLASSIFICHE_OUTPUT, nome_file)
            df_classifica.to_csv(file_path, index=False)
            print(f"✅ Classifica salvata: {nome_file}")

    git_push()