import os
import glob
import pandas as pd
import numpy as np
import shutil
import subprocess

# === CONFIGURAZIONE ===
CARTELLA_CSV = "./dati_csv"
CARTELLA_MEDIE_OUTPUT = "./medie_csv"
CARTELLA_CLASSIFICHE = "./classifiche_csv" 
CAMPIONATI = {
    "serie_a": "I1", "serie_b": "I2", "premier": "E0", "championship": "E1",
    "bundesliga": "D1", "2bundesliga": "D2", "ligue1": "F1", "ligue2": "F2",
    "la_liga": "SP1", "laliga2": "SP2", "jupiler_league": "B1",
    "eredivisie": "N1", "liga_1": "P1"
}
# CORREZIONE: Nuova struttura per le statistiche per evitare errori nei nomi delle colonne
STATISTICHE_DA_ANALIZZARE = [
    ('gol', 'gol_casa', 'gol_trasferta'),
    ('gol_1T', 'gol_casa_1T', 'gol_trasferta_1T'),
    ('tiri', 'tiri_casa', 'tiri_trasferta'),
    ('tiri_porta', 'tiri_porta_casa', 'tiri_porta_trasferta'),
    ('corner', 'corner_casa', 'corner_trasferta'),
    ('falli', 'falli_casa', 'falli_trasferta'),
    ('gialli', 'gialli_casa', 'gialli_trasferta'),
    ('rossi', 'rossi_casa', 'rossi_trasferta')
]
FINESTRA_MOBILE_PARTITE = 38
SOGLIA_PARTITE_STAGIONE_CORRENTE = 19

# === FUNZIONI DI UTILITÀ E CALCOLO FORMA (invariate) ===
def svuota_cartella(path):
    if os.path.exists(path): shutil.rmtree(path)
    os.makedirs(path)
    print(f"🧹 Cartella '{path}' svuotata e ricreata.")

def git_push(commit_msg="Aggiornamento medie con logica ibrida finale"):
    try:
        subprocess.run(["git", "add", CARTELLA_MEDIE_OUTPUT], check=True)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ Commit e push per le medie completato.")
        else:
            print("✅ Nessuna modifica nelle medie da committare.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore durante il processo Git: {e}")

def calcola_forma_avanzata(partite_squadra, df_classifica, max_partite=7):
    if partite_squadra.empty or df_classifica.empty or len(partite_squadra) < 3: return 0.0
    partite_recenti = partite_squadra.tail(max_partite)
    punti_ottenuti, coefficienti_difficolta = [], []
    num_squadre = len(df_classifica)
    posizioni_classifica = df_classifica.set_index('Squadra')['Pos'].to_dict()
    for _, row in partite_recenti.iterrows():
        squadra_in_analisi = row['squadra_in_analisi']
        squadra_in_casa = row['squadra_casa'] == squadra_in_analisi
        avversario = row['squadra_trasferta'] if squadra_in_casa else row['squadra_casa']
        punti = 0
        if squadra_in_casa:
            if row['gol_casa'] > row['gol_trasferta']: punti = 3
            elif row['gol_casa'] == row['gol_trasferta']: punti = 1
        else:
            if row['gol_trasferta'] > row['gol_casa']: punti = 3
            elif row['gol_trasferta'] == row['gol_casa']: punti = 1
        punti_ottenuti.append(punti)
        pos_avversario = posizioni_classifica.get(avversario, num_squadre / 2)
        difficolta = (num_squadre - pos_avversario + 1) / num_squadre
        coefficienti_difficolta.append(difficolta)
    pesi_recenza = np.arange(1, len(punti_ottenuti) + 1)
    punteggio_ponderato = np.sum(np.array(punti_ottenuti) * pesi_recenza * np.array(coefficienti_difficolta))
    massimo_punteggio_possibile = np.sum(3 * pesi_recenza)
    forma = punteggio_ponderato / massimo_punteggio_possibile if massimo_punteggio_possibile > 0 else 0
    return round(forma, 3)

# CORREZIONE: La funzione ora itera sulla nuova struttura STATISTICHE_DA_ANALIZZARE
def calcola_statistiche_medie_campionato(df_campionato):
    stat_campionato = {}
    for nome_base, col_casa, col_trasferta in STATISTICHE_DA_ANALIZZARE:
        stat_campionato[f'media_{nome_base}_casa_campionato'] = df_campionato[col_casa].mean()
        stat_campionato[f'media_{nome_base}_trasferta_campionato'] = df_campionato[col_trasferta].mean()
    return stat_campionato

def elabora_statistiche_campionato(nome_campionato):
    files = sorted(glob.glob(os.path.join(CARTELLA_CSV, f"{nome_campionato}_*.csv")), reverse=True)
    if not files: return pd.DataFrame()
    df_corrente = pd.read_csv(files[0])
    df_corrente['data'] = pd.to_datetime(df_corrente['data'], errors='coerce')
    df_precedente = pd.read_csv(files[1]) if len(files) > 1 else pd.DataFrame()
    if not df_precedente.empty:
        df_precedente['data'] = pd.to_datetime(df_precedente['data'], errors='coerce')
    squadre_correnti = set(pd.unique(df_corrente[['squadra_casa', 'squadra_trasferta']].values.ravel('K')))
    squadre_precedenti = set(pd.unique(df_precedente[['squadra_casa', 'squadra_trasferta']].values.ravel('K'))) if not df_precedente.empty else set()
    squadre_neopromosse = squadre_correnti - squadre_precedenti
    print(f"Squadre neopromosse in {nome_campionato}: {squadre_neopromosse if squadre_neopromosse else 'Nessuna'}")
    df_campionato_completo = pd.concat([df_corrente, df_precedente])
    stat_campionato = calcola_statistiche_medie_campionato(df_campionato_completo)
    path_classifica = os.path.join(CARTELLA_CLASSIFICHE, f"classifica_{nome_campionato}.csv")
    df_classifica = pd.read_csv(path_classifica) if os.path.exists(path_classifica) else pd.DataFrame()
    risultati_finali = []
    for squadra in squadre_correnti:
        is_neopromossa = squadra in squadre_neopromosse
        partite_correnti_squadra = df_corrente[(df_corrente['squadra_casa'] == squadra) | (df_corrente['squadra_trasferta'] == squadra)].sort_values(by='data')
        if is_neopromossa:
            df_analisi_squadra = partite_correnti_squadra
        elif len(partite_correnti_squadra) >= SOGLIA_PARTITE_STAGIONE_CORRENTE:
            df_analisi_squadra = partite_correnti_squadra
        else:
            partite_da_prendere_da_prec = FINESTRA_MOBILE_PARTITE - len(partite_correnti_squadra)
            if partite_da_prendere_da_prec > 0 and not df_precedente.empty:
                partite_precedenti_squadra = df_precedente[(df_precedente['squadra_casa'] == squadra) | (df_precedente['squadra_trasferta'] == squadra)].sort_values(by='data')
                df_analisi_squadra = pd.concat([partite_precedenti_squadra.tail(partite_da_prendere_da_prec), partite_correnti_squadra])
            else:
                df_analisi_squadra = partite_correnti_squadra
        if len(df_analisi_squadra) < 8:
            continue
        df_analisi_squadra['squadra_in_analisi'] = squadra
        df_casa = df_analisi_squadra[df_analisi_squadra['squadra_casa'] == squadra]
        df_trasferta = df_analisi_squadra[df_analisi_squadra['squadra_trasferta'] == squadra]
        record_squadra = {'squadra': squadra}
        partite_correnti_squadra['squadra_in_analisi'] = squadra
        record_squadra['forma_avanzata_totale'] = calcola_forma_avanzata(partite_correnti_squadra, df_classifica)
        
        # CORREZIONE: Il ciclo ora usa la nuova struttura ed è privo di errori
        for nome_base, col_casa, col_trasferta in STATISTICHE_DA_ANALIZZARE:
            media_fatti_casa = df_casa[col_casa].mean() if not df_casa.empty else 0
            media_subiti_casa = df_casa[col_trasferta].mean() if not df_casa.empty else 0
            media_fatti_trasferta = df_trasferta[col_trasferta].mean() if not df_trasferta.empty else 0
            media_subiti_trasferta = df_trasferta[col_casa].mean() if not df_trasferta.empty else 0
            
            record_squadra[f'media_{nome_base}_fatti_casa'] = round(media_fatti_casa, 2)
            record_squadra[f'media_{nome_base}_subiti_casa'] = round(media_subiti_casa, 2)
            record_squadra[f'media_{nome_base}_fatti_trasferta'] = round(media_fatti_trasferta, 2)
            record_squadra[f'media_{nome_base}_subiti_trasferta'] = round(media_subiti_trasferta, 2)

            den_casa = stat_campionato.get(f'media_{nome_base}_casa_campionato', 1)
            den_trasf = stat_campionato.get(f'media_{nome_base}_trasferta_campionato', 1)

            record_squadra[f'forza_attacco_{nome_base}_casa'] = round(media_fatti_casa / den_casa, 3) if den_casa > 0 else 1.0
            record_squadra[f'forza_difesa_{nome_base}_casa'] = round(media_subiti_casa / den_trasf, 3) if den_trasf > 0 else 1.0
            record_squadra[f'forza_attacco_{nome_base}_trasferta'] = round(media_fatti_trasferta / den_trasf, 3) if den_trasf > 0 else 1.0
            record_squadra[f'forza_difesa_{nome_base}_trasferta'] = round(media_subiti_trasferta / den_casa, 3) if den_casa > 0 else 1.0
        
        risultati_finali.append(record_squadra)

    return pd.DataFrame(risultati_finali)

if __name__ == "__main__":
    svuota_cartella(CARTELLA_MEDIE_OUTPUT)
    for nome_campionato in CAMPIONATI:
        print(f"📊 Elaboro statistiche avanzate per: {nome_campionato}")
        df_statistiche = elabora_statistiche_campionato(nome_campionato)
        if not df_statistiche.empty:
            colonne_squadra = ['squadra']
            colonne_forma = sorted([col for col in df_statistiche.columns if 'forma' in col])
            colonne_stat = sorted([col for col in df_statistiche.columns if col not in colonne_squadra + colonne_forma])
            df_statistiche = df_statistiche[colonne_squadra + colonne_forma + colonne_stat]
            nome_file = f"{nome_campionato}_statistiche_avanzate.csv"
            file_path = os.path.join(CARTELLA_MEDIE_OUTPUT, nome_file)
            df_statistiche.to_csv(file_path, index=False)
            print(f"✅ Salvato file con indici di forza e forma avanzata: {nome_file}")
    git_push()