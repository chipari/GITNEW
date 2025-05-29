import os
import glob
import pandas as pd
import numpy as np
import shutil
import subprocess
import json
import math
from datetime import datetime

# === CONFIGURAZIONE ===
CARTELLA_DATI_CSV = "./dati_csv"  # Dove sono i file CSV delle partite scaricati
CARTELLA_CLASSIFICHE_CORRENTI = "./classifiche_csv"
CARTELLA_CLASSIFICHE_STORICHE = "./classifiche_storiche_csv"
CARTELLA_MEDIE_OUTPUT_V2 = "./medie_csv_V2" # NUOVA CARTELLA per output V2

CAMPIONATI_NOMI_FILE = { # Usato per trovare i file e come prefisso output
    "serie_a": "serie_a", "serie_b": "serie_b", "premier": "premier", "championship": "championship",
    "bundesliga": "bundesliga", "2bundesliga": "2bundesliga", "ligue1": "ligue1", "ligue2": "ligue2",
    "la_liga": "la_liga", "laliga2": "laliga2", "jupiler_league": "jupiler_league",
    "eredivisie": "eredivisie", "liga_1": "liga_1"
}

# Nomi delle statistiche e colonne corrispondenti nei file CSV puliti
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

# Parametri per le finestre di analisi
FINESTRA_MOBILE_PARTITE_GENERALE = 38 # Per statistiche generali recenti (Y)
SOGLIA_PARTITE_STAGIONE_CORRENTE_GENERALE = 19 # Per statistiche generali recenti (X)
NUM_STAGIONI_STORICHE_PER_COND = 4 # Quante stagioni passate complete usare per analisi condizionali (oltre a quella corrente)
MIN_PARTITE_PER_STAT_COND = 7 # Minimo partite per calcolare una statistica condizionale valida

# Definizione Tier (percentuali della dimensione del campionato)
PERC_TIER_TOP = 0.35  # Es. 35% -> 7 squadre su 20
PERC_TIER_BOTTOM = 0.25 # Es. 25% -> 5 squadre su 20
# Mid tier sarà il resto
POSIZIONI_RANGO_SIMILE = 2 # +/- 2 posizioni per "Rango Simile"

# === FUNZIONI DI UTILITÀ ===
def svuota_e_crea_cartella(path):
    if os.path.exists(path): shutil.rmtree(path)
    os.makedirs(path)
    print(f"🧹 Cartella '{path}' svuotata e ricreata.")

def git_push_medie_v2(commit_msg="Aggiornamento CALCOLO_MEDIE_V2.py"):
    try:
        subprocess.run(["git", "add", CARTELLA_MEDIE_OUTPUT_V2], check=True)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"])
        if result.returncode == 1:
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ Commit e push per Medie V2 completato.")
        else:
            print("✅ Nessuna modifica nelle Medie V2 da committare.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore durante il processo Git per Medie V2: {e}")

def get_tier_squadra(posizione: int, num_squadre: int) -> str:
    if num_squadre == 0: return "Mid" # Evita divisione per zero
    num_top = math.ceil(PERC_TIER_TOP * num_squadre)
    num_bottom = math.ceil(PERC_TIER_BOTTOM * num_squadre)
    
    if posizione <= num_top:
        return "Top"
    elif posizione > (num_squadre - num_bottom):
        return "Bottom"
    else:
        return "Mid"

def calcola_medie_forza_da_df(df_partite_target: pd.DataFrame, squadra_analisi: str, stat_campionato_generali: dict, nome_stat_base:str, col_casa:str, col_trasferta:str, contesto:str = ""):
    """
    Calcola medie e forza per una squadra da un DataFrame di partite filtrato.
    Contesto può essere es. "_VS_Top", "_VS_Mid", "_VS_Bottom", "_VS_Simile"
    """
    risultati = {}
    df_casa_squadra = df_partite_target[df_partite_target['squadra_casa'] == squadra_analisi]
    df_trasf_squadra = df_partite_target[df_partite_target['squadra_trasferta'] == squadra_analisi]

    # Medie Fatte/Subite dalla squadra nel contesto specifico
    media_fatti_casa = df_casa_squadra[col_casa].mean() if not df_casa_squadra.empty else 0
    media_subiti_casa = df_casa_squadra[col_trasferta].mean() if not df_casa_squadra.empty else 0 # Avversario era in trasferta
    media_fatti_trasferta = df_trasf_squadra[col_trasferta].mean() if not df_trasf_squadra.empty else 0
    media_subiti_trasferta = df_trasf_squadra[col_casa].mean() if not df_trasf_squadra.empty else 0 # Avversario era in casa

    risultati[f'media_{nome_stat_base}_fatti_casa{contesto}'] = round(media_fatti_casa, 2)
    risultati[f'media_{nome_stat_base}_subiti_casa{contesto}'] = round(media_subiti_casa, 2)
    risultati[f'media_{nome_stat_base}_fatti_trasferta{contesto}'] = round(media_fatti_trasferta, 2)
    risultati[f'media_{nome_stat_base}_subiti_trasferta{contesto}'] = round(media_subiti_trasferta, 2)
    
    # Numero di partite usate per queste medie condizionali
    risultati[f'num_partite_casa{contesto}'] = len(df_casa_squadra)
    risultati[f'num_partite_trasferta{contesto}'] = len(df_trasf_squadra)

    # Indici di Forza (relativi alle medie GENERALI del campionato)
    den_casa = stat_campionato_generali.get(f'media_{nome_stat_base}_casa_campionato', 1.0)
    den_trasf = stat_campionato_generali.get(f'media_{nome_stat_base}_trasferta_campionato', 1.0)

    risultati[f'forza_attacco_{nome_stat_base}_casa{contesto}'] = round(media_fatti_casa / den_casa, 3) if den_casa > 0.01 else 1.0
    risultati[f'forza_difesa_{nome_stat_base}_casa{contesto}'] = round(media_subiti_casa / den_trasf, 3) if den_trasf > 0.01 else 1.0
    risultati[f'forza_attacco_{nome_stat_base}_trasferta{contesto}'] = round(media_fatti_trasferta / den_trasf, 3) if den_trasf > 0.01 else 1.0
    risultati[f'forza_difesa_{nome_stat_base}_trasferta{contesto}'] = round(media_subiti_trasferta / den_casa, 3) if den_casa > 0.01 else 1.0
    return risultati

def calcola_forma_avanzata(partite_squadra: pd.DataFrame, df_classifica: pd.DataFrame, max_partite: int = 7) -> float:
    """
    Calcola la forma tenendo conto di:
    1. Punti (3, 1, 0)
    2. Pesi per recenza (la partita più recente pesa di più)
    3. Forza dell'avversario (pesata in base alla sua posizione in classifica)
    """
    if partite_squadra.empty or len(partite_squadra) < 1: # Modificato controllo per permettere calcolo anche con meno di 3 partite
        return 0.0
    
    # Se df_classifica è vuoto o manca 'Squadra'/'Pos', non possiamo pesare per avversario.
    # In tal caso, potremmo procedere senza quel peso o ritornare una forma neutra/default.
    # Per ora, se manca la classifica, il .get(avversario, ...) userà il default.
    classifica_valida = not df_classifica.empty and 'Squadra' in df_classifica.columns and 'Pos' in df_classifica.columns
    
    partite_recenti = partite_squadra.tail(max_partite)
    if partite_recenti.empty: # Ulteriore controllo
        return 0.0

    punti_ottenuti = []
    coefficienti_difficolta = []
    
    num_squadre = len(df_classifica) if classifica_valida else 20 # Default a 20 se classifica non disponibile
    posizioni_classifica = df_classifica.set_index('Squadra')['Pos'].to_dict() if classifica_valida else {}

    for _, row in partite_recenti.iterrows():
        # Assicurati che 'squadra_in_analisi' sia presente nel DataFrame 'row'
        # Questa colonna viene aggiunta prima di chiamare calcola_forma_avanzata nel main
        if 'squadra_in_analisi' not in row:
            # Fallback o errore se 'squadra_in_analisi' non è definita
            # Per ora, assumiamo che sia sempre presente come da logica in elabora_statistiche_campionato_V2
            print(f"ATTENZIONE: 'squadra_in_analisi' non trovata nella riga della partita durante calcolo forma. Salto partita.")
            continue

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

        if classifica_valida:
            pos_avversario = posizioni_classifica.get(avversario, num_squadre // 2) 
            difficolta = (num_squadre - pos_avversario + 1) / float(num_squadre) if num_squadre > 0 else 0.5
        else:
            difficolta = 0.5 # Coefficiente di difficoltà neutro se la classifica non è disponibile
        coefficienti_difficolta.append(difficolta)

    if not punti_ottenuti: # Se non sono state processate partite (es. per 'squadra_in_analisi' mancante)
        return 0.0

    pesi_recenza = np.arange(1, len(punti_ottenuti) + 1)
    
    punteggio_ponderato = np.sum(np.array(punti_ottenuti) * pesi_recenza * np.array(coefficienti_difficolta))
    massimo_punteggio_possibile = np.sum(3 * pesi_recenza) # Massimo teorico se si vincono tutte le partite con difficoltà 1 e peso massimo
                                                        # Non considera il coeff. difficoltà nel massimo per normalizzare la forma tra 0 e ~1
                                                        # dove 1 è vincere tutte le partite recenti. La difficoltà modula questo.
    
    forma = punteggio_ponderato / massimo_punteggio_possibile if massimo_punteggio_possibile > 0 else 0.0
    return round(forma, 3)

def calcola_statistiche_medie_campionato(df_campionato: pd.DataFrame) -> dict:
    """
    Calcola le medie delle statistiche per l'intero campionato aggregato.
    df_campionato è il DataFrame che unisce le ultime N stagioni (es. 2) per questo calcolo.
    """
    stat_campionato = {}
    if df_campionato.empty:
        # Popola con default se il DataFrame è vuoto per evitare errori successivi
        for nome_base, _, _ in STATISTICHE_DA_ANALIZZARE:
            stat_campionato[f'media_{nome_base}_casa_campionato'] = 1.0 # Default generico
            stat_campionato[f'media_{nome_base}_trasferta_campionato'] = 1.0 # Default generico
        return stat_campionato

    for nome_base, col_casa, col_trasferta in STATISTICHE_DA_ANALIZZARE:
        # Assicurati che le colonne esistano e siano numeriche prima di calcolare la media
        if col_casa in df_campionato.columns and pd.api.types.is_numeric_dtype(df_campionato[col_casa]):
            stat_campionato[f'media_{nome_base}_casa_campionato'] = df_campionato[col_casa].mean()
        else:
            print(f"ATTENZIONE: Colonna {col_casa} mancante o non numerica per medie generali. Uso default.")
            stat_campionato[f'media_{nome_base}_casa_campionato'] = 1.0 # Default generico

        if col_trasferta in df_campionato.columns and pd.api.types.is_numeric_dtype(df_campionato[col_trasferta]):
            stat_campionato[f'media_{nome_base}_trasferta_campionato'] = df_campionato[col_trasferta].mean()
        else:
            print(f"ATTENZIONE: Colonna {col_trasferta} mancante o non numerica per medie generali. Uso default.")
            stat_campionato[f'media_{nome_base}_trasferta_campionato'] = 1.0 # Default generico
            
    return stat_campionato
# === FUNZIONE PRINCIPALE DI ELABORAZIONE V2 ===
def elabora_statistiche_campionato_V2(nome_campionato_prefix: str):
    print(f"--- Elaborazione V2 per: {nome_campionato_prefix} ---")
    
    # 1. Carica tutti i dati storici delle partite per questo campionato (ultime N stagioni)
    files_partite_storiche = sorted(glob.glob(os.path.join(CARTELLA_DATI_CSV, f"{nome_campionato_prefix}_*.csv")), reverse=True)
    if not files_partite_storiche:
        print(f"ERRORE: Nessun file CSV di partite trovato per {nome_campionato_prefix}")
        return pd.DataFrame()

    # Carichiamo un massimo di NUM_STAGIONI_PER_COND + 1 (quella attuale) stagioni storiche
    df_storico_completo_list = []
    for f_path in files_partite_storiche[:NUM_STAGIONI_STORICHE_PER_COND + 1]:
        try:
            df_s = pd.read_csv(f_path)
            df_s['data'] = pd.to_datetime(df_s['data'], errors='coerce')
            # Estrai stagione dal nome file per filtraggio corretto neopromosse
            nomefile = os.path.basename(f_path)
            stagione_file = nomefile.replace(f"{nome_campionato_prefix}_", "").replace(".csv","") #es 2324
            df_s['stagione_file'] = stagione_file 
            df_storico_completo_list.append(df_s)
        except Exception as e:
            print(f"Errore lettura file storico {f_path}: {e}")
    if not df_storico_completo_list:
        print(f"ERRORE: Nessun dato storico valido caricato per {nome_campionato_prefix}")
        return pd.DataFrame()
    df_storico_completo = pd.concat(df_storico_completo_list).sort_values(by='data', ascending=False).reset_index(drop=True)

    # 2. Carica tutte le classifiche finali storiche necessarie
    classifiche_storiche_dict = {}
    for f_path in glob.glob(os.path.join(CARTELLA_CLASSIFICHE_STORICHE, f"classifica_{nome_campionato_prefix}_*_finale.csv")):
        try:
            stagione_class = os.path.basename(f_path).split('_')[-2] # es. 2223 da classifica_serie_a_2223_finale.csv
            df_c = pd.read_csv(f_path)
            classifiche_storiche_dict[stagione_class] = df_c.set_index('Squadra')['Pos'].to_dict()
            classifiche_storiche_dict[stagione_class + "_num_squadre"] = len(df_c)
        except Exception as e:
            print(f"Errore lettura classifica storica {f_path}: {e}")

    # 3. Carica la classifica corrente
    df_classifica_corrente = pd.DataFrame()
    path_classifica_corrente = os.path.join(CARTELLA_CLASSIFICHE_CORRENTI, f"classifica_{nome_campionato_prefix}_corrente.csv")
    if os.path.exists(path_classifica_corrente):
        df_classifica_corrente = pd.read_csv(path_classifica_corrente)
    else:
        print(f"ATTENZIONE: Classifica corrente non trovata: {path_classifica_corrente}")
    
    num_squadre_campionato_attuale = len(df_classifica_corrente) if not df_classifica_corrente.empty else 20 # Default

    # 4. Calcola le medie generali del campionato (usando le ultime 2 stagioni per stabilità)
    df_ultime_due_stagioni = pd.concat([pd.read_csv(f) for f in files_partite_storiche[:2]] if len(files_partite_storiche) >=1 else [])
    stat_campionato_generali = {}
    if not df_ultime_due_stagioni.empty:
        for nome_base, col_casa, col_trasferta in STATISTICHE_DA_ANALIZZARE:
             df_ultime_due_stagioni[col_casa] = pd.to_numeric(df_ultime_due_stagioni[col_casa], errors='coerce').fillna(0)
             df_ultime_due_stagioni[col_trasferta] = pd.to_numeric(df_ultime_due_stagioni[col_trasferta], errors='coerce').fillna(0)
        stat_campionato_generali = calcola_statistiche_medie_campionato(df_ultime_due_stagioni) # Funzione definita in precedenza
    stat_campionato_generali['num_squadre_campionato'] = num_squadre_campionato_attuale
    
    # Salva le medie generali del campionato
    nome_file_medie_campionato = f"{nome_campionato_prefix}_medie_campionato_V2.json" # Nuovo nome per V2
    path_medie_campionato = os.path.join(CARTELLA_MEDIE_OUTPUT_V2, nome_file_medie_campionato)
    stat_campionato_serializzabile = {k: (float(v) if isinstance(v, (np.floating, np.integer, np.float64)) else v) for k, v in stat_campionato_generali.items()}
    with open(path_medie_campionato, 'w', encoding='utf-8') as f:
        json.dump(stat_campionato_serializzabile, f, ensure_ascii=False, indent=4)
    print(f"✅ Salvate medie generali campionato V2: {nome_file_medie_campionato}")

    # 5. Estrai le squadre della stagione corrente
    squadre_stagione_corrente = set(df_classifica_corrente['Squadra'].unique()) if not df_classifica_corrente.empty else \
                                set(pd.unique(df_storico_completo[df_storico_completo['stagione_file'] == os.path.basename(files_partite_storiche[0]).replace(f"{nome_campionato_prefix}_", "").replace(".csv","")][['squadra_casa', 'squadra_trasferta']].values.ravel('K')))
    
    if not squadre_stagione_corrente:
        print(f"Nessuna squadra trovata per la stagione corrente di {nome_campionato_prefix}. Salto.")
        return pd.DataFrame()

    lista_record_squadre = []
    for squadra_analisi in squadre_stagione_corrente:
        print(f"  Elaboro squadra: {squadra_analisi}")
        record_squadra = {'squadra': squadra_analisi}
        
        # Posizione attuale
        if not df_classifica_corrente.empty:
            riga_class_corr = df_classifica_corrente[df_classifica_corrente['Squadra'] == squadra_analisi]
            record_squadra['posizione_classifica_attuale'] = int(riga_class_corr['Pos'].iloc[0]) if not riga_class_corr.empty else num_squadre_campionato_attuale // 2
        else:
            record_squadra['posizione_classifica_attuale'] = num_squadre_campionato_attuale // 2

        # A. Statistiche Generali Recenti (19/38 partite, solo lega attuale)
        df_corrente_squadra = df_storico_completo[
            ((df_storico_completo['squadra_casa'] == squadra_analisi) | (df_storico_completo['squadra_trasferta'] == squadra_analisi)) &
            (df_storico_completo['stagione_file'] == os.path.basename(files_partite_storiche[0]).replace(f"{nome_campionato_prefix}_", "").replace(".csv","")) # Solo stagione corrente
        ].sort_values(by='data')
        
        df_precedente_squadra_stessa_lega = pd.DataFrame()
        if len(files_partite_storiche) > 1:
             # Cerco la squadra nella stagione precedente SOLO SE era nella stessa lega
             # Questo richiede di sapere in che lega era la squadra l'anno prima, il che complica.
             # Per ora, semplifichiamo: se era nel file della stagione precedente del *medesimo campionato*, la usiamo.
            df_prec_temp = pd.read_csv(files_partite_storiche[1]) # Carica il file della stagione precedente
            df_precedente_squadra_stessa_lega = df_prec_temp[
                ((df_prec_temp['squadra_casa'] == squadra_analisi) | (df_prec_temp['squadra_trasferta'] == squadra_analisi))
            ].sort_values(by='data')


        df_analisi_generale = pd.DataFrame()
        if len(df_corrente_squadra) >= SOGLIA_PARTITE_STAGIONE_CORRENTE_GENERALE:
            df_analisi_generale = df_corrente_squadra.tail(FINESTRA_MOBILE_PARTITE_GENERALE) # Prendi fino a 38 partite se disponibili
        else:
            partite_da_prec = FINESTRA_MOBILE_PARTITE_GENERALE - len(df_corrente_squadra)
            if partite_da_prec > 0 and not df_precedente_squadra_stessa_lega.empty:
                df_analisi_generale = pd.concat([df_precedente_squadra_stessa_lega.tail(partite_da_prec), df_corrente_squadra])
            else:
                df_analisi_generale = df_corrente_squadra
        
        if len(df_analisi_generale) >= MIN_PARTITE_PER_STAT_COND: # Uso la stessa soglia minima
            for nome_base, col_casa, col_trasferta in STATISTICHE_DA_ANALIZZARE:
                record_squadra.update(calcola_medie_forza_da_df(df_analisi_generale, squadra_analisi, stat_campionato_generali, nome_base, col_casa, col_trasferta, "_generale_recente"))
        
        # Calcolo forma avanzata generale (sulle ultime 7 partite della stagione corrente)
        df_corrente_squadra_per_forma = df_corrente_squadra.copy()
        df_corrente_squadra_per_forma['squadra_in_analisi'] = squadra_analisi
        record_squadra['forma_avanzata_totale'] = calcola_forma_avanzata(df_corrente_squadra_per_forma, df_classifica_corrente)


        # B. Statistiche Condizionali vs Tier e C. vs Rango Simile
        # Usiamo df_storico_completo (ultime N stagioni della stessa lega)
        df_storico_squadra_stessa_lega = df_storico_completo[
            (df_storico_completo['squadra_casa'] == squadra_analisi) | (df_storico_completo['squadra_trasferta'] == squadra_analisi)
        ]

        partite_vs_top, partite_vs_mid, partite_vs_bottom, partite_vs_simile = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        for _, partita_storica in df_storico_squadra_stessa_lega.iterrows():
            stagione_partita = partita_storica['stagione_file']
            classifica_stagione_partita = classifiche_storiche_dict.get(stagione_partita)
            num_squadre_stag_partita = classifiche_storiche_dict.get(stagione_partita + "_num_squadre", 20)

            if not classifica_stagione_partita: continue # Salta se non abbiamo la classifica per quella stagione

            squadra_casa_storica = partita_storica['squadra_casa']
            squadra_trasf_storica = partita_storica['squadra_trasferta']
            
            avversario_storico = squadra_trasf_storica if squadra_casa_storica == squadra_analisi else squadra_casa_storica
            pos_avversario_storico = classifica_stagione_partita.get(avversario_storico, num_squadre_stag_partita // 2)
            tier_avversario = get_tier_squadra(pos_avversario_storico, num_squadre_stag_partita)

            partita_df_temp = pd.DataFrame([partita_storica]) # Per concat

            if tier_avversario == "Top": partite_vs_top = pd.concat([partite_vs_top, partita_df_temp])
            elif tier_avversario == "Mid": partite_vs_mid = pd.concat([partite_vs_mid, partita_df_temp])
            elif tier_avversario == "Bottom": partite_vs_bottom = pd.concat([partite_vs_bottom, partita_df_temp])
            
            # Per Rango Simile
            pos_squadra_analisi_storica = classifica_stagione_partita.get(squadra_analisi, num_squadre_stag_partita // 2)
            if abs(pos_squadra_analisi_storica - pos_avversario_storico) <= POSIZIONI_RANGO_SIMILE and pos_squadra_analisi_storica != pos_avversario_storico:
                partite_vs_simile = pd.concat([partite_vs_simile, partita_df_temp])

        # Calcola e aggiungi stats condizionali se ci sono abbastanza partite
        for tier_nome, df_tier_partite in [("Top", partite_vs_top), ("Mid", partite_vs_mid), ("Bottom", partite_vs_bottom), ("Simile", partite_vs_simile)]:
            if len(df_tier_partite) >= MIN_PARTITE_PER_STAT_COND:
                for nome_base, col_casa, col_trasferta in STATISTICHE_DA_ANALIZZARE:
                    record_squadra.update(calcola_medie_forza_da_df(df_tier_partite, squadra_analisi, stat_campionato_generali, nome_base, col_casa, col_trasferta, f"_VS_{tier_nome}"))
            else: # Popola con NaN o 0/1 per default se non ci sono abbastanza dati
                 for nome_base, _, _ in STATISTICHE_DA_ANALIZZARE:
                    for tipo_val in ['media', 'forza_attacco', 'forza_difesa']:
                        for ruolo in ['fatti_casa', 'subiti_casa', 'fatti_trasferta', 'subiti_trasferta']:
                            if tipo_val == 'media':
                                record_squadra[f'{tipo_val}_{nome_base}_{ruolo}_VS_{tier_nome}'] = 0.0
                            else: # Forza
                                record_squadra[f'{tipo_val}_{nome_base}_{ruolo.split("_")[1]}_VS_{tier_nome}'] = 1.0 # Forza neutra
                    record_squadra[f'num_partite_casa_VS_{tier_nome}'] = 0
                    record_squadra[f'num_partite_trasferta_VS_{tier_nome}'] = 0


        lista_record_squadre.append(record_squadra)

    df_finale_campionato = pd.DataFrame(lista_record_squadre)
    return df_finale_campionato


if __name__ == "__main__":
    svuota_e_crea_cartella(CARTELLA_MEDIE_OUTPUT_V2)

    for nome_file_campionato_attuale in CAMPIONATI_NOMI_FILE.values(): # Iteriamo sui prefissi dei file come "serie_a"
        # Questo nome_file_campionato_attuale (es. "serie_a") sarà usato per cercare
        # i file CSV (serie_a_2324.csv, serie_a_2223.csv ...) e le classifiche storiche.
        df_statistiche_v2 = elabora_statistiche_campionato_V2(nome_file_campionato_attuale)
        
        if not df_statistiche_v2.empty:
            # Riordina colonne per leggibilità se necessario
            # ... (logica di ordinamento colonne, se vuoi) ...
            
            nome_file_output = f"{nome_file_campionato_attuale}_statistiche_avanzate_V2.csv"
            percorso_file_output = os.path.join(CARTELLA_MEDIE_OUTPUT_V2, nome_file_output)
            df_statistiche_v2.to_csv(percorso_file_output, index=False)
            print(f"✅ File V2 salvato: {nome_file_output}")
            
    git_push_medie_v2()