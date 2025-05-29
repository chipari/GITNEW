import os
import json
import glob
import pandas as pd
import numpy as np
import math
from scipy.stats import poisson
import subprocess
import shutil # Aggiunto per svuota_cartella

# === CONFIGURAZIONE GLOBALE ===
PATH_PARTITE_INPUT = "./dati_flashscore"
PATH_ALIAS_SQUADRE = "./alias_squadre.csv"
PATH_STATISTICHE_V2_BASE = "./medie_csv_V2" # Output di CALCOLO_MEDIE_V2.py
PATH_DATI_ARBITRI = "./dati_arbitri"
PATH_CLASSIFICHE_CORRENTI = "./classifiche_csv"
PATH_DATI_CSV_STORICI = "./dati_csv" # Per H2H
PATH_OUTPUT_PRONOSTICI_V2 = "./pronostici_V2"

MAPPA_COMPETIZIONE_DISPLAY_A_FILE_PREFIX = {
    "Serie A": "serie_a",
    "Serie B": "serie_b",
    "Premier League": "premier",
    "Championship": "championship",
    "Ligue 1": "ligue1",
    "Ligue 2": "ligue2",
    "Bundesliga": "bundesliga",
    "2. Bundesliga": "2bundesliga", # Assumendo che NEXT_MATCH.py salvi "2. Bundesliga"
    "LaLiga": "la_liga",             # Assumendo che NEXT_MATCH.py salvi "LaLiga"
    "LaLiga2": "laliga2",            # Assumendo che NEXT_MATCH.py salvi "LaLiga2"
    "Eredivisie": "eredivisie",
    "Jupiler Pro League": "jupiler_league", # Da "Jupiler League" in NEXT_MATCH.py a "jupiler_league"
    "Liga Portugal": "liga_1"             # Da "Liga Portugal" in NEXT_MATCH.py a "liga_1"
}

MAX_GOL_POISSON_FT = 7
MAX_GOL_POISSON_HT = 4

PESO_FORMA_XG = 0.06
PESO_ARBITRO_FALLI_XG_NEG = -0.05
PESO_ARBITRO_FALLI_XG_POS = 0.03
PESO_ARBITRO_RIGORI_XG = 0.04
PESO_CLASSIFICA_TIER_XG = 0.07 # Peso per aggiustamento VS Tier
PESO_CLASSIFICA_SIMILAR_XG = 0.04 # Peso per aggiustamento VS Rango Simile
PESO_H2H_XG = 0.05 # Peso per aggiustamento H2H

MIN_PROB_PER_PRONOSTICO_SECCO_DOMINANTE = 0.52
NO_BET_THRESHOLD_DIFFERENCE = 0.10
NO_BET_THRESHOLD_SINGLE_PROB_1X2 = 0.35

SOGLIE_OVER_UNDER_FT = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
SOGLIE_OVER_UNDER_HT = [0.5, 1.5]
SOGLIE_UO_SQUADRA_STANDARD = [0.5, 1.5, 2.5] # Etichette per U/O squadra

RANGES_MULTIGOL_FT = {
    "0-1": (0, 1), "1-2": (1, 2), "1-3": (1, 3), "1-4": (1, 4), "0-2": (0,2), "0-3": (0,3),
    "2-3": (2, 3), "2-4": (2, 4), "2-5": (2, 5),
    "3-4": (3, 4), "3-5": (3, 5), "3-6": (3, 6),
    "4-5": (4, 5), "4-6": (4, 6), "4+": (4, None), # "None" per indicare "o più"
    "5+": (5, None), "6+": (6, None),
    "Pari": "Pari", "Dispari": "Dispari"
}

TOP_N_RISULTATI_ESATTI = 4

STAT_ALTRE_NOMI_BASE = [('corner','corner'), ('tiri','tiri'), ('tiri_porta','tirinporta'), ('falli','falli'), ('gialli','gialli')] # Corretto in lista di tuple
STAT_ALTRE_SOGLIA_DIFF_1X2 = {'corner': 1.1, 'tiri': 1.5, 'tiri_porta': 0.75, 'falli': 1.2, 'gialli': 0.65}

STAT_ALTRE_SOGLIE_OU = {
    'corner': [7.5, 8.5, 9.5, 10.5, 11.5, 12.5],
    'tiri': [19.5, 21.5, 23.5, 25.5, 27.5, 29.5],
    'tiri_porta': [6.5, 7.5, 8.5, 9.5, 10.5, 11.5],
    'falli': [19.5, 21.5, 22.5, 23.5, 25.5, 27.5],
    'gialli': [2.5, 3.5, 4.5, 5.5, 6.5]
}

# --- COSTANTI MANCANTI DA AGGIUNGERE ---
PERC_TIER_TOP = 0.35  # Es. 35% -> 7 squadre su 20
PERC_TIER_BOTTOM = 0.25 # Es. 25% -> 5 squadre su 20
POSIZIONI_RANGO_SIMILE = 2 # +/- 2 posizioni per "Rango Simile"
MIN_PARTITE_PER_STAT_COND = 5 # Minimo partite per usare una statistica condizionale (era 7, ridotto)
# --- FINE COSTANTI MANCANTI ---

# === FUNZIONI DI UTILITÀ ===
def svuota_cartella(cartella):
    if not os.path.exists(cartella):
        os.makedirs(cartella); print(f"Cartella '{cartella}' creata.")
        return
    for f in os.listdir(cartella):
        path = os.path.join(cartella, f)
        try:
            if os.path.isfile(path) or os.path.islink(path): os.unlink(path)
            elif os.path.isdir(path): shutil.rmtree(path)
        except Exception as e: print(f'Errore eliminazione {path}. Motivo: {e}')
    print(f"🧹 Cartella '{cartella}' svuotata.")

import subprocess # Assicurati che subprocess sia importato

# ... (dopo svuota_cartella) ...

def git_push_pronostici_v2(cartella_da_aggiungere: str, messaggio_commit: str = "Aggiornati pronostici V2"):
    try:
        subprocess.run(["git", "add", cartella_da_aggiungere], check=True)
        # Controlla se ci sono modifiche da committare
        result_diff = subprocess.run(["git", "diff", "--staged", "--quiet"])
        
        if result_diff.returncode == 1: # Ci sono modifiche staged
            subprocess.run(["git", "commit", "-m", messaggio_commit], check=True)
            print("🚀 Commit per pronostici V2 eseguito.")
            subprocess.run(["git", "push"], check=True)
            print("✅ Push su GitHub per pronostici V2 completato.")
        else:
            print("✅ Nessuna nuova modifica nei pronostici V2 da committare.")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore durante il processo Git per pronostici V2: {e.output.decode() if hasattr(e, 'output') and e.output else e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else str(e)}")
    except Exception as e:
        print(f"❌ Errore imprevisto durante il push Git per pronostici V2: {e}")
# def git_push(): # Lasciato commentato
#     pass

# === FUNZIONI DI CARICAMENTO DATI V2 ===
def carica_alias_squadre(percorso: str) -> dict:
    try:
        df = pd.read_csv(percorso); return dict(zip(df['nome_flashscore'], df['nome_csv']))
    except FileNotFoundError: print(f"ERRORE: File alias squadre non trovato: {percorso}"); return {}

def carica_dati_arbitro_safe(nome_arbitro: str, percorso_dati_arbitri: str) -> dict:
    # (Identica alla versione precedente, con fallback e conversione tipi)
    dati_default_arbitro = {
        "falli_pg": 22.0, "gialli_pg": 4.0, "rossi_pg": 0.15, "rigori_pg": 0.20,
        "presenze": 0, "falli_per_contrasto": 0.0, "gialli_tot":0, "rossi_tot":0,
        "nome_arbitro_originale": nome_arbitro if nome_arbitro else "Non Trovato",
        'statistiche_trovate': False
    }
    if not nome_arbitro or not isinstance(nome_arbitro, str): return dati_default_arbitro
    nome_arbitro_normalizzato = nome_arbitro.replace(' ', '').replace('.', '').lower()
    if not nome_arbitro_normalizzato: return dati_default_arbitro
    try:
        for file_name in os.listdir(percorso_dati_arbitri):
            if nome_arbitro_normalizzato in file_name.lower().replace('_',''):
                with open(os.path.join(percorso_dati_arbitri, file_name), 'r', encoding='utf-8') as f:
                    dati_json = json.load(f); out = {}
                    for chiave, default_val in dati_default_arbitro.items():
                        if chiave == "nome_arbitro_originale": continue
                        try:
                            val_json = dati_json.get(chiave)
                            if val_json is None: out[chiave] = default_val
                            elif isinstance(default_val, float): out[chiave] = float(val_json)
                            elif isinstance(default_val, int): out[chiave] = int(val_json)
                            else: out[chiave] = val_json
                        except (ValueError, TypeError): out[chiave] = default_val
                    out['nome_arbitro_originale'] = dati_json.get('nome_arbitro', nome_arbitro)
                    out['statistiche_trovate'] = True
                    return out
    except FileNotFoundError: print(f"ATTENZIONE: Cartella dati arbitri non trovata: {percorso_dati_arbitri}.")
    except Exception as e: print(f"ATTENZIONE: Errore caricamento dati arbitro {nome_arbitro}: {e}.")
    return dati_default_arbitro

def carica_statistiche_squadra_V2(nome_squadra_std: str, file_prefix_campionato: str, percorso_base: str) -> dict:
    file_path = os.path.join(percorso_base, f"{file_prefix_campionato}_statistiche_avanzate_V2.csv")
    try:
        df = pd.read_csv(file_path)
        squadra_stats = df[df['squadra'] == nome_squadra_std]
        if not squadra_stats.empty: return squadra_stats.iloc[0].fillna(0).to_dict()
        else: print(f"ATTENZIONE: Squadra '{nome_squadra_std}' non trovata in {file_path}")
    except FileNotFoundError: print(f"ERRORE CRITICO: File V2 statistiche squadre non trovato: {file_path}.")
    except Exception as e: print(f"Errore caricamento V2 statistiche per {nome_squadra_std} da {file_path}: {e}")
    return {}

def carica_medie_generali_campionato_V2(file_prefix_campionato: str, percorso_base: str) -> dict:
    file_path = os.path.join(percorso_base, f"{file_prefix_campionato}_medie_campionato_V2.json")
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: print(f"ERRORE CRITICO: File V2 medie campionato non trovato: {file_path}.")
    except Exception as e: print(f"Errore caricamento V2 medie campionato da {file_path}: {e}")
    return {}

def carica_classifica_corrente(file_prefix_campionato: str, percorso_base_classifiche: str) -> pd.DataFrame:
    file_path = os.path.join(percorso_base_classifiche, f"classifica_{file_prefix_campionato}_corrente.csv")
    try:
        return pd.read_csv(file_path)
    except FileNotFoundError: print(f"ATTENZIONE: File classifica corrente non trovato: {file_path}")
    except Exception as e: print(f"Errore caricamento classifica corrente da {file_path}: {e}")
    return pd.DataFrame()

def get_h2h_stats(squadra_casa_std: str, squadra_trasf_std: str, num_partite_h2h: int,
                  nome_file_campionato_attuale:str, alias_dict: dict) -> dict:
    """Estrae statistiche H2H dalle ultime N partite tra le due squadre."""
    h2h_summary = {"partite_analizzate": 0, "vittorie_casa": 0, "pareggi": 0, "vittorie_trasferta": 0,
                   "media_gol_casa": 0, "media_gol_trasferta": 0, "media_gol_totali": 0}
    partite_considerate = []
    
    # Cerca nei file CSV storici (assumendo che CSV.py li abbia scaricati)
    # Dovrebbe cercare solo nei file del campionato corretto.
    # Per semplicità, iteriamo su tutti i file CSV nella cartella dati_csv
    # e filtriamo quelli che appartengono allo stesso campionato delle squadre
    # (Questa parte potrebbe essere ottimizzata se sapessimo il campionato storico degli H2H)

    all_csv_files = sorted(glob.glob(os.path.join(PATH_DATI_CSV_STORICI, f"{nome_file_campionato_attuale}_*.csv")), reverse=True)

    for file_csv in all_csv_files: # Considera più stagioni per H2H
        try:
            df_match = pd.read_csv(file_csv)
            # Assicurati che le colonne dei nomi squadra e gol esistano
            if not all(col in df_match.columns for col in ['squadra_casa', 'squadra_trasferta', 'gol_casa', 'gol_trasferta']):
                continue
            
            # Filtra partite H2H
            h2h_matches = df_match[
                ((df_match['squadra_casa'] == squadra_casa_std) & (df_match['squadra_trasferta'] == squadra_trasf_std)) |
                ((df_match['squadra_casa'] == squadra_trasf_std) & (df_match['squadra_trasferta'] == squadra_casa_std))
            ]
            partite_considerate.extend(h2h_matches.to_dict('records'))
        except Exception as e:
            print(f"    Errore lettura H2H da {file_csv}: {e}")
            continue
            
    if not partite_considerate: return h2h_summary
    
    # Ordina per data (se la colonna 'data' è presente e formattata correttamente)
    try:
        df_partite_considerate = pd.DataFrame(partite_considerate)
        df_partite_considerate['data'] = pd.to_datetime(df_partite_considerate['data'], errors='coerce')
        df_partite_considerate.sort_values(by='data', ascending=False, inplace=True)
        partite_considerate = df_partite_considerate.head(num_partite_h2h).to_dict('records')
    except KeyError: # Colonna 'data' mancante o formato errato
        partite_considerate = partite_considerate[:num_partite_h2h] # Prendi le più recenti trovate


    if not partite_considerate: return h2h_summary

    h2h_summary["partite_analizzate"] = len(partite_considerate)
    gol_casa_tot = 0
    gol_trasf_tot = 0

    for p in partite_considerate:
        gc = int(p['gol_casa'])
        gt = int(p['gol_trasferta'])
        if p['squadra_casa'] == squadra_casa_std: # La squadra di casa attuale era in casa
            gol_casa_tot += gc
            gol_trasf_tot += gt
            if gc > gt: h2h_summary["vittorie_casa"] += 1
            elif gt > gc: h2h_summary["vittorie_trasferta"] += 1
            else: h2h_summary["pareggi"] += 1
        else: # La squadra di casa attuale era in trasferta
            gol_casa_tot += gt # Gol della squadra "casa" di oggi
            gol_trasf_tot += gc # Gol della squadra "trasferta" di oggi
            if gt > gc: h2h_summary["vittorie_casa"] += 1
            elif gc > gt: h2h_summary["vittorie_trasferta"] += 1
            else: h2h_summary["pareggi"] += 1
            
    h2h_summary["media_gol_casa"] = round(gol_casa_tot / len(partite_considerate), 2)
    h2h_summary["media_gol_trasferta"] = round(gol_trasf_tot / len(partite_considerate), 2)
    h2h_summary["media_gol_totali"] = round((gol_casa_tot + gol_trasf_tot) / len(partite_considerate), 2)
    
    return h2h_summary


# === MOTORE POISSON E FUNZIONI DI CALCOLO V2 ===

def get_tier_squadra(posizione: int, num_squadre: int) -> str:
    if num_squadre == 0: return "Mid" 
    num_top = math.ceil(PERC_TIER_TOP * num_squadre)
    num_bottom = math.ceil(PERC_TIER_BOTTOM * num_squadre)
    if posizione <= num_top: return "Top"
    elif posizione > (num_squadre - num_bottom): return "Bottom"
    else: return "Mid"

def calcola_expected_goals_v2(stats_team: dict, stats_opponent: dict,
                              media_fatti_ruolo_campionato: float,
                              ruolo_team: str, # "casa" o "trasferta"
                              tier_opponent: str, # "Top", "Mid", "Bottom"
                              rank_simile_opponent: bool, # True se l'avversario è di rango simile
                              stat_base_name: str = "gol") -> float:
    if not all([stats_team, stats_opponent]): return 0.5 

    # 1. Forza Generale Recente (fallback primario)
    forza_att_generale = stats_team.get(f'forza_attacco_{stat_base_name}_{ruolo_team}_generale_recente', 1.0)
    ruolo_opponent = "trasferta" if ruolo_team == "casa" else "casa"
    forza_dif_generale_opp = stats_opponent.get(f'forza_difesa_{stat_base_name}_{ruolo_opponent}_generale_recente', 1.0)
    
    xg = forza_att_generale * forza_dif_generale_opp * media_fatti_ruolo_campionato

    # 2. Aggiustamento Tier Opponent (se dati condizionali validi)
    num_partite_vs_tier = stats_team.get(f'num_partite_{ruolo_team}_VS_{tier_opponent}', 0)
    if num_partite_vs_tier >= MIN_PARTITE_PER_STAT_COND:
        forza_att_vs_tier = stats_team.get(f'forza_attacco_{stat_base_name}_{ruolo_team}_VS_{tier_opponent}', forza_att_generale)
        # Usiamo la forza difesa generale dell'avversario come base, perché non abbiamo forza_dif_opponent_VS_mio_tier
        xg_tier_adj = forza_att_vs_tier * forza_dif_generale_opp * media_fatti_ruolo_campionato
        # Media ponderata tra xG generale e xG vs Tier (più peso a vs Tier se più partite)
        peso_tier = min(1.0, num_partite_vs_tier / 10.0) * PESO_CLASSIFICA_TIER_XG # Es. max 10% di aggiustamento
        xg = xg * (1 - peso_tier) + xg_tier_adj * peso_tier


    # 3. Aggiustamento Rango Simile (se dati condizionali validi e non sovrapposto a tier)
    # Questo aggiustamento è più specifico, applichiamolo dopo quello del tier
    if rank_simile_opponent:
        num_partite_vs_simile = stats_team.get(f'num_partite_{ruolo_team}_VS_Simile', 0)
        if num_partite_vs_simile >= MIN_PARTITE_PER_STAT_COND:
            forza_att_vs_simile = stats_team.get(f'forza_attacco_{stat_base_name}_{ruolo_team}_VS_Simile', forza_att_generale)
            xg_simile_adj = forza_att_vs_simile * forza_dif_generale_opp * media_fatti_ruolo_campionato
            peso_simile = min(1.0, num_partite_vs_simile / 10.0) * PESO_CLASSIFICA_SIMILAR_XG
            xg = xg * (1 - peso_simile) + xg_simile_adj * peso_simile
            
    return max(0.05, xg)


def aggiusta_xg_h2h_forma_arbitro(xg_casa: float, xg_trasferta: float,
                                  stats_casa: dict, stats_trasferta: dict,
                                  h2h_stats: dict, dati_arbitro: dict) -> tuple[float, float]:
    xg_c, xg_t = xg_casa, xg_trasferta

    # Aggiustamento H2H (se ci sono partite analizzate)
    if h2h_stats.get("partite_analizzate", 0) >= 2: # Almeno 2 partite H2H
        diff_gol_h2h = h2h_stats["media_gol_casa"] - h2h_stats["media_gol_trasferta"]
        # Se la squadra di casa ha dominato H2H, aumenta un po' il suo xG e viceversa
        xg_c += diff_gol_h2h * PESO_H2H_XG
        xg_t -= diff_gol_h2h * PESO_H2H_XG # Aggiustamento simmetrico

    # Aggiustamento Forma
    forma_casa = stats_casa.get('forma_avanzata_totale', 0.5)
    forma_trasferta = stats_trasferta.get('forma_avanzata_totale', 0.5)
    xg_c = xg_c * (1 + (forma_casa - 0.5) * PESO_FORMA_XG)
    xg_t = xg_t * (1 + (forma_trasferta - 0.5) * PESO_FORMA_XG)

    # Aggiustamento Arbitro
    falli_pg_arbitro = dati_arbitro.get("falli_pg", 21.5) 
    if falli_pg_arbitro > 24.5:
        adj_factor = 1.0 + PESO_ARBITRO_FALLI_XG_NEG 
        xg_c *= adj_factor; xg_t *= adj_factor
    elif falli_pg_arbitro < 18.5: 
        adj_factor = 1.0 + PESO_ARBITRO_FALLI_XG_POS
        xg_c *= adj_factor; xg_t *= adj_factor
        
    rigori_pg_arbitro = dati_arbitro.get("rigori_pg", 0.20)
    xg_c += rigori_pg_arbitro * PESO_ARBITRO_RIGORI_XG
    xg_t += rigori_pg_arbitro * PESO_ARBITRO_RIGORI_XG

    return max(0.05, xg_c), max(0.05, xg_t)

# Le funzioni genera_matrice_probabilita_poisson, get_pronostico_secco..., estrai_pronostici_da_matrice
# calcola_expected_valore_stat, normalizza_linea_stat, formatta_pronostico_uo_stat,
# genera_pronostici_altre_stat, intervallo_multigol_da_xg, genera_pronostici_tempi_specifici
# sono state definite nei messaggi precedenti e rimangono sostanzialmente le stesse
# (con piccoli aggiustamenti se necessari, come il TOP_N_RISULTATI_ESATTI a 4)
# Le includo qui per completezza, assicurandomi che usino le costanti corrette.

def genera_matrice_probabilita_poisson(xg_casa: float, xg_trasferta: float, max_gol: int) -> np.array:
    prob_casa = np.array([poisson.pmf(i, xg_casa) for i in range(max_gol + 1)])
    prob_trasferta = np.array([poisson.pmf(i, xg_trasferta) for i in range(max_gol + 1)])
    prob_casa[-1] = max(0, 1 - np.sum(prob_casa[:-1]))
    prob_trasferta[-1] = max(0, 1 - np.sum(prob_trasferta[:-1]))
    matrice = np.outer(prob_casa, prob_trasferta)
    return matrice

def get_pronostico_secco_1x2(p1, px, p2, soglia_no_bet_diff=NO_BET_THRESHOLD_DIFFERENCE, soglia_dominanza=0.15, min_prob_valida=NO_BET_THRESHOLD_SINGLE_PROB_1X2):
    if max(p1,px,p2) < min_prob_valida: return "No bet"
    # Pareggio se molto equilibrato e P(X) è alta
    if abs(p1 - p2) < soglia_no_bet_diff and px > p1 - soglia_no_bet_diff and px > p2 - soglia_no_bet_diff and px > 0.28: return "X"
    if p1 > px + soglia_dominanza and p1 > p2 + soglia_dominanza and p1 > MIN_PROB_PER_PRONOSTICO_SECCO_DOMINANTE : return "1"
    if p2 > px + soglia_dominanza and p2 > p1 + soglia_dominanza and p2 > MIN_PROB_PER_PRONOSTICO_SECCO_DOMINANTE : return "2"
    # Casi meno netti
    if p1 > px and p1 > p2 and p1 > 0.40 : return "1" 
    if p2 > px and p2 > p1 and p2 > 0.40 : return "2"
    if px > p1 and px > p2 and px > 0.35 : return "X" 
    return "No bet" # Se nessuna condizione forte è soddisfatta

def get_pronostico_secco_uo(p_over, p_under, soglia_no_bet_diff=NO_BET_THRESHOLD_DIFFERENCE, min_prob_valida_forte=MIN_PROB_PER_PRONOSTICO_SECCO_DOMINANTE-0.03):
    if max(p_over,p_under) < min_prob_valida_forte-0.1 : return "No bet" # Se entrambe le prob sono basse
    if abs(p_over - p_under) < soglia_no_bet_diff : return "No bet" 
    return "Over" if p_over > p_under else "Under"

def get_pronostico_secco_ggng(p_gg, p_ng, soglia_no_bet_diff=NO_BET_THRESHOLD_DIFFERENCE, min_prob_valida_forte=MIN_PROB_PER_PRONOSTICO_SECCO_DOMINANTE-0.03):
    if max(p_gg, p_ng) < min_prob_valida_forte-0.1 : return "NoBet" 
    if abs(p_gg - p_ng) < soglia_no_bet_diff : return "NoBet"
    return "Gol" if p_gg > p_ng else "NoGol"

def estrai_pronostici_da_matrice(matrice: np.array, max_gol_matrice: int, xg_casa: float, xg_trasf:float, per_primo_tempo:bool = False) -> dict:
    pronostici = {}
    p_1, p_x, p_2 = 0.0, 0.0, 0.0
    p_gg, p_ng = 0.0, 0.0
    prob_risultati_esatti_list = []

    for i in range(max_gol_matrice + 1): 
        for j in range(max_gol_matrice + 1): 
            prob = matrice[i, j]
            if prob < 0.00001 and not (i==max_gol_matrice or j==max_gol_matrice): continue 
            if i > j: p_1 += prob
            elif i < j: p_2 += prob
            else: p_x += prob
            if i > 0 and j > 0: p_gg += prob
            else: p_ng += prob
            prob_risultati_esatti_list.append({'risultato': f"{i}-{j}", 'prob': round(prob, 4)})

    pronostici['1X2'] = get_pronostico_secco_1x2(p_1, p_x, p_2)
    pronostici['P(1)'] = round(p_1, 3); pronostici['P(X)'] = round(p_x, 3); pronostici['P(2)'] = round(p_2, 3)
    pronostici['GolNoGol'] = get_pronostico_secco_ggng(p_gg, p_ng)
    pronostici['P(GG)'] = round(p_gg, 3); pronostici['P(NG)'] = round(p_ng, 3)

    soglie_ou_correnti = SOGLIE_OVER_UNDER_HT if per_primo_tempo else SOGLIE_OVER_UNDER_FT
    for soglia in soglie_ou_correnti:
        p_over_s, p_under_s = 0.0, 0.0
        for r_info in prob_risultati_esatti_list: # Ottimizzabile iterando matrice
            g_c, g_t = map(int, r_info['risultato'].split('-'))
            if (g_c + g_t) > soglia: p_over_s += r_info['prob']
            else: p_under_s += r_info['prob']
        pronostici[f'U/O_{soglia}'] = get_pronostico_secco_uo(p_over_s, p_under_s)
        pronostici[f'P(Over_{soglia})'] = round(p_over_s, 3)
        
    if not per_primo_tempo:
        p_1x = p_1 + p_x; p_x2 = p_2 + p_x
        if pronostici['1X2'] == "1": dc_secco = "1X"
        elif pronostici['1X2'] == "2": dc_secco = "X2"
        elif pronostici['1X2'] == "X": dc_secco = "1X" if p_1x > p_x2 else "X2"
        else: 
            if p_1x > 0.68 and p_1x > p_x2 : dc_secco = "1X"
            elif p_x2 > 0.68 and p_x2 > p_1x : dc_secco = "X2"
            else: dc_secco = "NoBet"
        pronostici['DC'] = dc_secco
        pronostici['P(DC_1X)'] = round(p_1x, 3); pronostici['P(DC_X2)'] = round(p_x2, 3)

        prob_risultati_esatti_list = sorted(prob_risultati_esatti_list, key=lambda x: x['prob'], reverse=True)
        pronostici['RisultatoEsatto'] = prob_risultati_esatti_list[0]['risultato'] if prob_risultati_esatti_list else "N/A"
        pronostici['RisultatoEsattoMultiesiti'] = [item['risultato'] for item in prob_risultati_esatti_list[:TOP_N_RISULTATI_ESATTI]]

        # MultiGol FT secco Poisson-driven
        gol_totali_prob_ft = [0.0] * ((max_gol_matrice * 2) + 1)
        for r_info in prob_risultati_esatti_list:
            g_c,g_t = map(int, r_info['risultato'].split('-'))
            idx = g_c+g_t
            if idx < len(gol_totali_prob_ft): gol_totali_prob_ft[idx] += r_info['prob']

        best_mg_ft_range = "NoBet"; max_p_mg_ft = 0.15 # Soglia minima per considerarlo
        for nome_range, limiti in RANGES_MULTIGOL_FT.items():
            if isinstance(limiti, tuple):
                min_g, max_g_range = limiti
                current_p_mg = 0
                if max_g_range is None: # Caso OverX.5
                    if min_g < len(gol_totali_prob_ft):
                        current_p_mg = sum(gol_totali_prob_ft[min_g:])
                else:
                    if min_g < len(gol_totali_prob_ft) and max_g_range < len(gol_totali_prob_ft):
                         current_p_mg = sum(gol_totali_prob_ft[min_g : max_g_range+1])
                    elif min_g < len(gol_totali_prob_ft): # Se max_g_range è fuori, somma fino alla fine
                         current_p_mg = sum(gol_totali_prob_ft[min_g:])

                if current_p_mg > max_p_mg_ft:
                    max_p_mg_ft = current_p_mg
                    best_mg_ft_range = nome_range
        pronostici['multigol_totale'] = best_mg_ft_range 
    return pronostici

def intervallo_multigol_da_xg_team(xg_squadra: float, tipo:str="casa") -> str: # tipo è casa o trasferta
    # Questa funzione è ora solo per team, per 'totale' usiamo il Poisson-driven
    xg_squadra = max(0, xg_squadra)
    if xg_squadra < 0.6: return "0"
    elif xg_squadra < 0.85: return "0-1" # Era 0.75
    elif xg_squadra < 1.35: return "1-2" # Era 1.4
    elif xg_squadra < 1.85: return "1-3" # Era 1.95
    elif xg_squadra < 2.6: return "2-3" # Era 2.7
    elif xg_squadra < 3.3: return "2-4" # Era 3.2
    else: return "3+" # Semplificato
    return "N/A"

def formatta_pronostico_uo_stat_v2(exp_val: float, tipo_stat_label: str, linee_specifiche_stat: list) -> tuple[str, str]:
    """Genera stringhe Over/Under per statistiche, cercando la linea più vicina."""
    if not linee_specifiche_stat: return f"N/A (media: {exp_val:.2f})", f"N/A (media: {exp_val:.2f})"
    
    # Trova la linea più vicina a exp_val dalla lista di linee predefinite per quella statistica
    linea_piu_vicina = min(linee_specifiche_stat, key=lambda x:abs(x-exp_val))
    
    # Decidi se Over o Under è più probabile rispetto a questa linea
    # Per semplicità, se exp_val è > linea_piu_vicina -> Over, altrimenti Under
    # Si potrebbe aggiungere una dead-zone qui se l'exp_val è troppo vicino alla linea
    
    # Per l'output come da tuo esempio: "Over X.Y (media: Z.ZZ)"
    # La linea X.Y sarà la linea_piu_vicina +/- 0.5 o 1.0 a seconda della statistica.
    # Qui usiamo un approccio semplificato: linea_over e linea_under attorno a exp_val
    offset_dinamico = max(0.5, exp_val * 0.1) if exp_val > 0 else 0.5
    
    linea_over_calc = normalizza_linea_stat(exp_val - offset_dinamico)
    linea_under_calc = normalizza_linea_stat(exp_val + offset_dinamico)
    if linea_over_calc < 0: linea_over_calc = min(linee_specifiche_stat) if linee_specifiche_stat else 0.5
    if linea_under_calc <= linea_over_calc: linea_under_calc = linea_over_calc + (linee_specifiche_stat[1] - linee_specifiche_stat[0] if len(linee_specifiche_stat)>1 else 1.0)


    prono_over = f"Over {linea_over_calc:.1f} (media: {exp_val:.2f})"
    prono_under = f"Under {linea_under_calc:.1f} (media: {exp_val:.2f})"
    return prono_over, prono_under


def genera_pronostici_tempi_specifici_v2(xg_casa_1t_adj, xg_trasf_1t_adj, xg_casa_ft_adj, xg_trasf_ft_adj,
                                      pron_1x2_1t_secco, pron_1x2_ft_secco,
                                      matrice_1t, matrice_ft, max_gol_1t, max_gol_ft,
                                      pron_base_1t, pron_ft_principali) -> dict:
    out = {}
    xg_casa_2t = max(0.01, xg_casa_ft_adj - xg_casa_1t_adj)
    xg_trasf_2t = max(0.01, xg_trasf_ft_adj - xg_trasf_1t_adj)
    matrice_2t = genera_matrice_probabilita_poisson(xg_casa_2t, xg_trasf_2t, max_gol_1t)

    # --- CHIAMATA CORRETTA QUI ---
    pron_base_2t = estrai_pronostici_da_matrice(matrice_2t, max_gol_1t, xg_casa_2t, xg_trasf_2t, True) 
    # --- FINE CHIAMATA CORRETTA ---

    for s_ht in SOGLIE_OVER_UNDER_HT: 
        out[f"over_2T_{s_ht}"] = pron_base_2t.get(f"U/O_{s_ht}", "NoBet")

    # ... (resto della funzione come prima) ...
    out["over_1T_0.5_over_2T_0.5"] = "Over" if pron_base_1t.get("U/O_0.5") == "Over" and out.get("over_2T_0.5") == "Over" else "Under"
    out["over_1T_1.5_over_2T_1.5"] = "Over" if pron_base_1t.get("U/O_1.5") == "Over" and out.get("over_2T_1.5") == "Over" else "Under"
    out["over_1T_1.5_over_2T_0.5"] = "Over" if pron_base_1t.get("U/O_1.5") == "Over" and out.get("over_2T_0.5") == "Over" else "Under"
    out["over_1T_0.5_over_2T_1.5"] = "Over" if pron_base_1t.get("U/O_0.5") == "Over" and out.get("over_2T_1.5") == "Over" else "Under"
    
    out["multigol_1T"] = pron_base_1t.get("multigol_totale", intervallo_multigol_da_xg_team(xg_casa_1t_adj + xg_trasf_1t_adj)) 
    out["multigol_2T"] = pron_base_2t.get("multigol_totale", intervallo_multigol_da_xg_team(xg_casa_2t + xg_trasf_2t))
    out["multigol_1T_2T"] = f"{out['multigol_1T']} + {out['multigol_2T']}"

    out["PrimoTempoFinale"] = f"{pron_1x2_1t_secco}/{pron_1x2_ft_secco}"
    
    re_1t_list = []
    # Nota: max_gol_1t è il limite per la matrice_1t
    for i_re in range(min(max_gol_1t + 1, matrice_1t.shape[0])):
        for j_re in range(min(max_gol_1t + 1, matrice_1t.shape[1])):
            re_1t_list.append({'risultato':f"{i_re}-{j_re}", 'prob': matrice_1t[i_re,j_re]})
    re_1t_list = sorted(re_1t_list, key=lambda x: x['prob'], reverse=True)
    re_1t_secco = re_1t_list[0]['risultato'] if re_1t_list else "0-0"
    
    re_ft_secco = pron_ft_principali.get('RisultatoEsatto', "0-0")
    out["RisultatoEsattoParzialeFinale"] = f"{re_1t_secco}/{re_ft_secco}"
    
    def p_squadra_segna_tempo(matrice_tempo, max_g, per_casa=True):
        p_s = 0.0
        if not isinstance(matrice_tempo, np.ndarray): return 0.0 
        # Assicurati che max_g non superi le dimensioni della matrice
        rows, cols = matrice_tempo.shape
        for r_idx in range(min(max_g + 1, rows)):
            for c_idx in range(min(max_g + 1, cols)):
                if per_casa and r_idx > 0: p_s += matrice_tempo[r_idx,c_idx]
                elif not per_casa and c_idx > 0: p_s += matrice_tempo[r_idx,c_idx]
        return p_s

    p_casa_segna_1t = p_squadra_segna_tempo(matrice_1t, max_gol_1t, True)
    p_casa_segna_2t = p_squadra_segna_tempo(matrice_2t, max_gol_1t, True) 
    p_trasf_segna_1t = p_squadra_segna_tempo(matrice_1t, max_gol_1t, False)
    p_trasf_segna_2t = p_squadra_segna_tempo(matrice_2t, max_gol_1t, False)

    def formatta_segna_1t_2t(p1, p2): 
        if p1 > 0.60 and p2 > 0.60 : return "SI" 
        if p1 > 0.40 and p2 > 0.40 : return "PROBABILE" 
        return "NO"
        
    out["casa_segna_1T/2T"] = formatta_segna_1t_2t(p_casa_segna_1t, p_casa_segna_2t)
    out["trasferta_segna_1T/2T"] = formatta_segna_1t_2t(p_trasf_segna_1t, p_trasf_segna_2t)

    vince_casa_1t = pron_base_1t.get("1X2") == "1" 
    # Calcolo P(1), P(X), P(2) per matrice_2t per il secco
    p1_2t, px_2t, p2_2t = 0,0,0
    for r_idx_2t in range(min(max_gol_1t + 1, matrice_2t.shape[0])):
        for c_idx_2t in range(min(max_gol_1t + 1, matrice_2t.shape[1])):
            if r_idx_2t > c_idx_2t: p1_2t += matrice_2t[r_idx_2t, c_idx_2t]
            elif c_idx_2t > r_idx_2t: p2_2t += matrice_2t[r_idx_2t, c_idx_2t]
            else: px_2t += matrice_2t[r_idx_2t, c_idx_2t]
    vince_casa_2t = get_pronostico_secco_1x2(p1_2t, px_2t, p2_2t) == "1"
    out["casa_vince_almeno_un_tempo"] = "SI" if vince_casa_1t or vince_casa_2t else "NO"
    
    vince_trasf_1t = pron_base_1t.get("1X2") == "2"
    vince_trasf_2t = get_pronostico_secco_1x2(p1_2t, px_2t, p2_2t) == "2"
    out["trasferta_vince_almeno_un_tempo"] = "SI" if vince_trasf_1t or vince_trasf_2t else "NO"
    return out

def calcola_prob_standard_uo_squadra(xg_squadra: float, etichetta_linea_float: float, max_gol_poisson_ft: int) -> tuple[float, float]:
    """
    Calcola P(Squadra Gol > etichetta_linea_float) e P(Squadra Gol <= etichetta_linea_float)
    in modo standard. Es: per etichetta_linea_float = 1.5, calcola P(Gol >= 2) e P(Gol <= 1).
    """
    # Per P(Over X.5), la soglia k per la CDF è floor(X.5).
    # P(Over 1.5) -> P(Gol > 1.5) -> P(Gol >= 2) -> 1 - CDF(1)
    k_per_cdf = math.floor(etichetta_linea_float)
    
    p_under_linea_o_uguale_k = poisson.cdf(k_per_cdf, xg_squadra)
    p_over_linea_k = 1.0 - p_under_linea_o_uguale_k
    
    return round(p_over_linea_k, 3), round(p_under_linea_o_uguale_k, 3)

# ... (dopo calcola_prob_standard_uo_squadra e prima di === MAIN ===)

# === MOTORE PER ALTRE STATISTICHE (Corner, Tiri, Falli, Gialli) V2 ===
def calcola_expected_valore_stat(stat_base_name: str, 
                                 stats_casa: dict, stats_trasferta: dict, 
                                 medie_campionato: dict) -> tuple[float, float, float]:
    if not all([stats_casa, stats_trasferta, medie_campionato]): 
        # Fallback se mancano dati cruciali
        if stat_base_name == 'corner': return (5.0, 4.0, 9.0)
        if stat_base_name == 'tiri': return (12.0, 10.0, 22.0)
        if stat_base_name == 'tiri_porta': return (4.0, 3.0, 7.0)
        if stat_base_name == 'falli': return (11.0, 11.0, 22.0)
        if stat_base_name == 'gialli': return (2.0, 2.0, 4.0)
        return (1.0, 1.0, 2.0) # Default generico

    # Nomi delle colonne Forza e Medie Campionato
    # Assumiamo che _generale_recente sia il contesto da usare per queste medie "base"
    forza_att_casa_col = f'forza_attacco_{stat_base_name}_casa_generale_recente'
    forza_dif_trasf_col = f'forza_difesa_{stat_base_name}_trasferta_generale_recente'
    media_stat_casa_camp_col = f'media_{stat_base_name}_casa_campionato'

    forza_att_trasf_col = f'forza_attacco_{stat_base_name}_trasferta_generale_recente'
    forza_dif_casa_col = f'forza_difesa_{stat_base_name}_casa_generale_recente'
    media_stat_trasf_camp_col = f'media_{stat_base_name}_trasferta_campionato'

    # Valori di default per Forza (neutra) e Medie (basati su statistiche tipiche)
    default_forza = 1.0
    default_media_casa = 5.0 if 'corner' in stat_base_name else 12.0 if 'tiri' in stat_base_name else 4.0 if 'tiri_porta' in stat_base_name else 2.0 if 'gialli' in stat_base_name else 11.0
    default_media_trasf = 4.0 if 'corner' in stat_base_name else 10.0 if 'tiri' in stat_base_name else 3.0 if 'tiri_porta' in stat_base_name else 2.0 if 'gialli' in stat_base_name else 11.0


    forza_att_casa = stats_casa.get(forza_att_casa_col, default_forza)
    forza_dif_trasf = stats_trasferta.get(forza_dif_trasf_col, default_forza)
    media_stat_casa_camp = medie_campionato.get(media_stat_casa_camp_col, default_media_casa)

    exp_casa = forza_att_casa * forza_dif_trasf * media_stat_casa_camp
    
    forza_att_trasf = stats_trasferta.get(forza_att_trasf_col, default_forza)
    forza_dif_casa = stats_casa.get(forza_dif_casa_col, default_forza)
    media_stat_trasf_camp = medie_campionato.get(media_stat_trasf_camp_col, default_media_trasf)
                
    exp_trasf = forza_att_trasf * forza_dif_casa * media_stat_trasf_camp
                
    exp_totale = exp_casa + exp_trasf
    return round(max(0.1, exp_casa), 2), round(max(0.1, exp_trasf), 2), round(max(0.2, exp_totale), 2)

def normalizza_linea_stat(media: float, step: float = 1.0) -> float: # Già presente, per completezza
    # Arrotonda al più vicino .5, es. 9.7 -> 9.5, 9.8 -> 10.5 (se step=1)
    # Modificato per essere più simile al tuo output: linea_over leggermente sotto, linea_under leggermente sopra
    return math.floor(media) + 0.5 if media > math.floor(media) else math.floor(media) -0.5


def formatta_pronostico_uo_stat_v2(exp_val: float, tipo_stat_label: str, linee_specifiche_stat: list = None) -> tuple[str, str]:
    """Genera stringhe Over/Under per statistiche come da esempio output."""
    
    # Se non ci sono linee specifiche, creiamo linee dinamiche attorno a exp_val
    if linee_specifiche_stat is None or not linee_specifiche_stat:
        # Offset dinamico basato sul valore atteso, ma non troppo piccolo
        offset_dinamico = max(0.5, exp_val * 0.1) if exp_val > 0 else 0.5
        # La linea per l'Over è tipicamente X.5 sotto la media se la media è Y.0, o Y.5 se media è Y.qualcosa
        linea_over_calc = normalizza_linea_stat(exp_val - offset_dinamico)
        if linea_over_calc < 0: linea_over_calc = 0.5

        # La linea per l'Under è tipicamente X.5 sopra la media
        linea_under_calc = normalizza_linea_stat(exp_val + offset_dinamico)
        if linea_under_calc <= linea_over_calc: # Assicura che under sia maggiore di over
             linea_under_calc = linea_over_calc + 1.0
    else:
        # Usa le linee specifiche se fornite (non implementato pienamente qui, semplifico)
        # Trova la linea più vicina a exp_val dalla lista di linee predefinite per quella statistica
        linea_piu_vicina = min(linee_specifiche_stat, key=lambda x:abs(x-exp_val))
        linea_over_calc = linea_piu_vicina - 1.0 if linea_piu_vicina - 1.0 >=0 else 0.5 # Semplificazione
        linea_under_calc = linea_piu_vicina + 1.0 # Semplificazione


    prono_over = f"Over {linea_over_calc:.1f} (media: {exp_val:.2f})"
    prono_under = f"Under {linea_under_calc:.1f} (media: {exp_val:.2f})"
    return prono_over, prono_under

def genera_pronostici_altre_stat_v2(stat_base_name: str, label_output: str,
                                 stats_casa: dict, stats_trasferta: dict, medie_campionato: dict,
                                 dati_arbitro: dict = None) -> dict:
    exp_casa, exp_trasf, exp_tot = calcola_expected_valore_stat(stat_base_name, stats_casa, stats_trasferta, medie_campionato)
    
    # Influenza arbitro per falli e gialli sugli expected values
    # (Questa logica può essere affinata ulteriormente)
    if stat_base_name == 'falli' and dati_arbitro and dati_arbitro.get('statistiche_trovate'):
        falli_pg_arbitro = dati_arbitro.get('falli_pg', exp_tot / 2 if exp_tot > 0 else 11.0) # Stima se arbitro non ha falli_pg
        exp_tot_pond = (exp_tot * 0.7) + (falli_pg_arbitro * 0.3)
        # Ribilancia exp_casa e exp_trasf mantenendo la loro proporzione originale ma con il nuovo totale
        if exp_tot > 0.1 : # Evita divisione per zero
            exp_casa = (exp_casa / exp_tot) * exp_tot_pond
            exp_trasf = (exp_trasf / exp_tot) * exp_tot_pond
        exp_tot = exp_tot_pond

    elif stat_base_name == 'gialli' and dati_arbitro and dati_arbitro.get('statistiche_trovate'):
        gialli_pg_arbitro = dati_arbitro.get('gialli_pg', exp_tot / 2 if exp_tot > 0 else 2.0)
        exp_tot_pond = (exp_tot * 0.6) + (gialli_pg_arbitro * 0.4)
        if exp_tot > 0.1:
            exp_casa = (exp_casa / exp_tot) * exp_tot_pond
            exp_trasf = (exp_trasf / exp_tot) * exp_tot_pond
        exp_tot = exp_tot_pond

    soglia_1x2_val = STAT_ALTRE_SOGLIA_DIFF_1X2.get(stat_base_name, 0.5)
    prono_1x2 = "X" # Default
    if exp_casa > exp_trasf + soglia_1x2_val: prono_1x2 = "1"
    elif exp_trasf > exp_casa + soglia_1x2_val: prono_1x2 = "2"

    linee_specifiche_stat = STAT_ALTRE_SOGLIE_OU.get(stat_base_name) # Prende le linee predefinite
    
    # Per l'U/O totale, usiamo formatta_pronostico_uo_stat_v2
    over_tot_str, under_tot_str = formatta_pronostico_uo_stat_v2(exp_tot, f"{label_output}_tot", linee_specifiche_stat)
    
    # Per U/O squadra, adattiamo le linee (es. dimezzando quelle totali o usando un set diverso)
    # Qui semplifico usando lo stesso formatter ma con exp_casa e exp_trasf
    # e delle linee stimate (potresti voler definire linee specifiche per squadra)
    linee_squadra_stimate = [l/2 for l in linee_specifiche_stat] if linee_specifiche_stat else None
    over_home_str, under_home_str = formatta_pronostico_uo_stat_v2(exp_casa, f"{label_output}_home", linee_squadra_stimate)
    over_away_str, under_away_str = formatta_pronostico_uo_stat_v2(exp_trasf, f"{label_output}_away", linee_squadra_stimate)

    return {
        f"{label_output}_1X2": prono_1x2,
        f"{label_output}_over": over_tot_str, 
        f"{label_output}_under": under_tot_str,
        f"{label_output}_home_over": over_home_str, 
        f"{label_output}_home_under": under_home_str,
        f"{label_output}_away_over": over_away_str, 
        f"{label_output}_away_under": under_away_str,
    }

# ... (Il resto dello script, inclusa la funzione main() che chiama genera_pronostici_altre_stat_v2)

# === MAIN ===
def main():
    svuota_cartella(PATH_OUTPUT_PRONOSTICI_V2) # Uso nuova cartella
    alias_dict = carica_alias_squadre(PATH_ALIAS_SQUADRE)
    if not alias_dict:
        print("ERRORE CRITICO: alias_squadre.csv non caricato. Termino."); return

    for file_partita_json in os.listdir(PATH_PARTITE_INPUT):
        if not file_partita_json.endswith(".json"): continue
        print(f"\n▶️  Elaboro: {file_partita_json}...")
        
        with open(os.path.join(PATH_PARTITE_INPUT, file_partita_json), 'r', encoding='utf-8') as f:
            info_partita = json.load(f)

        home_team_fs = info_partita.get("home_team")
        away_team_fs = info_partita.get("away_team")
        arbitro_nome = info_partita.get("arbitro")
        competizione_input = info_partita.get("competizione") # Es. "Italia" o "Serie A"

        if not all([home_team_fs, away_team_fs, competizione_input]):
            print(f"ERRORE: Info partita incomplete in {file_partita_json}. Salto."); continue

        # Determina il prefisso del file per le statistiche
        # Se competizione_input è già un prefisso (es. "serie_a"), usa quello.
        # Altrimenti, prova a mapparlo da nazione.
        # Dentro la funzione main() di PRONOSTICO_V2.py:

    # ... (dopo aver caricato info_partita)
        competizione_display_input = info_partita.get("competizione") # Es. "Serie B"

        if not competizione_display_input:
            print(f"ERRORE: Campo 'competizione' mancante in {file_partita_json}. Salto.")
            continue

        file_prefix_campionato = MAPPA_COMPETIZIONE_DISPLAY_A_FILE_PREFIX.get(competizione_display_input)

        if not file_prefix_campionato:
            print(f"ATTENZIONE: Nessuna mappatura trovata per la competizione '{competizione_display_input}' in MAPPA_COMPETIZIONE_DISPLAY_A_FILE_PREFIX. Salto la partita.")
            continue

        print(f"    Lega identificata per le stats: '{competizione_display_input}' -> Prefisso file: '{file_prefix_campionato}'")
    # ... il resto del caricamento dati userà file_prefix_campionato ...

        home_team_std = alias_dict.get(home_team_fs, home_team_fs)
        away_team_std = alias_dict.get(away_team_fs, away_team_fs)

        stats_casa = carica_statistiche_squadra_V2(home_team_std, file_prefix_campionato, PATH_STATISTICHE_V2_BASE)
        stats_trasf = carica_statistiche_squadra_V2(away_team_std, file_prefix_campionato, PATH_STATISTICHE_V2_BASE)
        medie_campionato = carica_medie_generali_campionato_V2(file_prefix_campionato, PATH_STATISTICHE_V2_BASE)
        dati_arbitro = carica_dati_arbitro_safe(arbitro_nome, PATH_DATI_ARBITRI)
        df_classifica_corrente = carica_classifica_corrente(file_prefix_campionato, PATH_CLASSIFICHE_CORRENTI)


        if not all([stats_casa, stats_trasf, medie_campionato]):
            print(f"ERRORE: Dati V2 (squadre o medie campionato) mancanti per {home_team_std} vs {away_team_std}. Salto."); continue
        
        pronostici_output = {
            "partita_info": {
                "squadra_casa_flashscore": home_team_fs, "squadra_trasferta_flashscore": away_team_fs,
                "squadra_casa_std": home_team_std, "squadra_trasferta_std": away_team_std,
                "arbitro": dati_arbitro.get('nome_arbitro_originale', arbitro_nome),
                "competizione_elaborata": file_prefix_campionato
            },
            "analisi_modello_V2": {},
            "pronostici": {}
        }
        
        # --- LOGICA V2 PER CALCOLO XG ---
        num_squadre_attuali = medie_campionato.get('num_squadre_campionato', 20)
        pos_casa = stats_casa.get('posizione_classifica_attuale', num_squadre_attuali // 2)
        pos_trasf = stats_trasf.get('posizione_classifica_attuale', num_squadre_attuali // 2)
        
        tier_casa = get_tier_squadra(pos_casa, num_squadre_attuali) # Tier della squadra di casa
        tier_trasf = get_tier_squadra(pos_trasf, num_squadre_attuali) # Tier della squadra trasferta

        rank_simile_casa_vs_trasf = abs(pos_casa - pos_trasf) <= POSIZIONI_RANGO_SIMILE
        rank_simile_trasf_vs_casa = rank_simile_casa_vs_trasf # Simmetrico

        # xG FT Base (usando Forza VS Tier dell'avversario)
        xg_casa_ft_base = calcola_expected_goals_v2(stats_casa, stats_trasf, medie_campionato.get('media_gol_casa_campionato',1.5), "casa", tier_trasf, rank_simile_trasf_vs_casa, "gol")
        xg_trasf_ft_base = calcola_expected_goals_v2(stats_trasf, stats_casa, medie_campionato.get('media_gol_trasferta_campionato',1.2), "trasferta", tier_casa, rank_simile_casa_vs_trasf, "gol")
        
        # H2H Stats
        h2h_stats = get_h2h_stats(home_team_std, away_team_std, 6, file_prefix_campionato, alias_dict)
        pronostici_output["analisi_modello_V2"]["H2H_ultime_partite"] = h2h_stats

        # Aggiustamenti finali H2H, Forma, Arbitro
        xg_casa_ft_adj, xg_trasf_ft_adj = aggiusta_xg_h2h_forma_arbitro(xg_casa_ft_base, xg_trasf_ft_base, stats_casa, stats_trasf, h2h_stats, dati_arbitro)
        
        pronostici_output["analisi_modello_V2"]["Expected_Goals_FT"] = {
            "home_base_vs_tier": round(xg_casa_ft_base,2), "away_base_vs_tier": round(xg_trasf_ft_base,2),
            "home_final_adj": round(xg_casa_ft_adj,2), "away_final_adj": round(xg_trasf_ft_adj,2),
            "total_final_adj": round(xg_casa_ft_adj + xg_trasf_ft_adj,2)
        }
        matrice_ft = genera_matrice_probabilita_poisson(xg_casa_ft_adj, xg_trasf_ft_adj, MAX_GOL_POISSON_FT)
        pron_ft_principali = estrai_pronostici_da_matrice(matrice_ft, MAX_GOL_POISSON_FT, xg_casa_ft_adj, xg_trasf_ft_adj, False)
        pronostici_output["pronostici"].update(pron_ft_principali)
        # Il multigol_totale secco ora viene da estrai_pronostici_da_matrice

        # --- Calcoli Primo Tempo (1T) ---
        xg_casa_1t_base = calcola_expected_goals_v2(stats_casa, stats_trasf, medie_campionato.get('media_gol_1T_casa_campionato',0.7), "casa", tier_trasf, rank_simile_trasf_vs_casa, "gol_1T")
        xg_trasf_1t_base = calcola_expected_goals_v2(stats_trasf, stats_casa, medie_campionato.get('media_gol_1T_trasferta_campionato',0.5), "trasferta", tier_casa, rank_simile_casa_vs_trasf, "gol_1T")
        
        # Aggiustamento 1T (solo forma, per semplicità, no H2H o arbitro su 1T xG specifici)
        forma_casa = stats_casa.get('forma_avanzata_totale', 0.5); forma_trasf = stats_trasf.get('forma_avanzata_totale', 0.5)
        xg_casa_1t_adj = xg_casa_1t_base * (1 + (forma_casa - 0.5) * PESO_FORMA_XG * 0.6) # Peso forma ridotto per 1T
        xg_trasf_1t_adj = xg_trasf_1t_base * (1 + (forma_trasf - 0.5) * PESO_FORMA_XG * 0.6)
        xg_casa_1t_adj = max(0.05, min(xg_casa_1t_adj, xg_casa_ft_adj * 0.75)) 
        xg_trasf_1t_adj = max(0.05, min(xg_trasf_1t_adj, xg_trasf_ft_adj * 0.75))

        pronostici_output["analisi_modello_V2"]["Expected_Goals_1T"] = {
             "home_adj": round(xg_casa_1t_adj,2), "away_adj": round(xg_trasf_1t_adj,2), "total_adj": round(xg_casa_1t_adj + xg_trasf_1t_adj,2)
        }
        matrice_1t = genera_matrice_probabilita_poisson(xg_casa_1t_adj, xg_trasf_1t_adj, MAX_GOL_POISSON_HT)
        pron_1t_principali = estrai_pronostici_da_matrice(matrice_1t, MAX_GOL_POISSON_HT, xg_casa_1t_adj, xg_trasf_1t_adj, True)

        for soglia_ht in SOGLIE_OVER_UNDER_HT:
            pronostici_output["pronostici"][f"over_1T_{soglia_ht}"] = pron_1t_principali.get(f"U/O_{soglia_ht}", "NoBet")
            pronostici_output["pronostici"][f"P(Over_1T_{soglia_ht})"] = pron_1t_principali.get(f"P(Over_{soglia_ht})", 0.0)
        pronostici_output["pronostici"]["1X2_PrimoTempo"] = pron_1t_principali.get('1X2', "NoBet") # Aggiunto secco 1X2 1T


        # --- Pronostici sui Tempi Specifici ---
        pronostici_tempi = genera_pronostici_tempi_specifici_v2(
            xg_casa_1t_adj, xg_trasf_1t_adj, xg_casa_ft_adj, xg_trasf_ft_adj,
            pron_1t_principali.get('1X2', "X"), pron_ft_principali.get('1X2', "X"),
            matrice_1t, matrice_ft, MAX_GOL_POISSON_HT, MAX_GOL_POISSON_FT,
            pron_1t_principali, pron_ft_principali
        )
        pronostici_output["pronostici"].update(pronostici_tempi)
        
        # --- Under/Over Squadra e Multigol Squadra ---
        for team_label, xg_team_ft, team_stats_dict in [("Casa", xg_casa_ft_adj, stats_casa), ("Trasferta", xg_trasf_ft_adj, stats_trasf)]:
            for soglia_label_float in SOGLIE_UO_SQUADRA_STANDARD: # es. 0.5, 1.5, 2.5
                p_over_team, _ = calcola_prob_standard_uo_squadra(xg_team_ft, soglia_label_float, MAX_GOL_POISSON_FT)
                secco_team_uo = get_pronostico_secco_uo(p_over_team, 1.0 - p_over_team)
                pronostici_output["pronostici"][f"{team_label} Over/Under {soglia_label_float}"] = secco_team_uo
                pronostici_output["pronostici"][f"P({team_label} Over {soglia_label_float})"] = p_over_team # Aggiunta P% per U/O squadra
            pronostici_output["pronostici"][f"multigol_{team_label.lower()}"] = intervallo_multigol_da_xg_team(xg_team_ft, team_label.lower())
        
        pronostici_output["pronostici"]["multigol_casa_trasferta"] = f"{pronostici_output['pronostici']['multigol_casa']}/{pronostici_output['pronostici']['multigol_trasferta']}"

        # --- Altre Statistiche (Corner, Tiri, etc.) ---
        for stat_base, label_out in STAT_ALTRE_NOMI_BASE:
            prono_stat = genera_pronostici_altre_stat_v2(stat_base, label_out, stats_casa, stats_trasf, medie_campionato, dati_arbitro if stat_base in ['falli','gialli'] else None)
            pronostici_output["pronostici"].update(prono_stat)

        # --- Combo Bets ---
        combo = {}
        _1x2 = pronostici_output["pronostici"].get("1X2", "NoBet")
        _uo15 = pronostici_output["pronostici"].get("U/O_1.5", "No bet")
        _uo25 = pronostici_output["pronostici"].get("U/O_2.5", "No bet")
        _ggng = pronostici_output["pronostici"].get("GolNoGol", "NoBet")
        _mgft_secco = pronostici_output["pronostici"].get("multigol_totale", "NoBet")
        _dc = pronostici_output["pronostici"].get("DC", "NoBet")

        combo["combo_1X2_over_1.5"] = f"{_1x2} + {_uo15}" if "NoBet" not in [_1x2, _uo15] and "No bet" not in [_1x2, _uo15] else "NoBet"
        combo["combo_1X2_over_2.5"] = f"{_1x2} + {_uo25}" if "NoBet" not in [_1x2, _uo25] and "No bet" not in [_1x2, _uo25] else "NoBet"
        combo["combo_1X2_gol_nogol"] = f"{_1x2} + {_ggng}" if "NoBet" not in [_1x2, _ggng] else "NoBet"
        combo["combo_1X2_multigol"] = f"{_1x2} + {_mgft_secco}" if "NoBet" not in [_1x2, _mgft_secco] else "NoBet"
        combo["doppia_chance_gol_nogol"] = f"{_dc} + {_ggng}" if "NoBet" not in [_dc, _ggng] else "NoBet"
        combo["doppia_chance_over_1.5"] = f"{_dc} + {_uo15}" if "NoBet" not in [_dc, _uo15] and "No bet" not in [_dc, _uo15] else "NoBet"
        combo["doppia_chance_over_2.5"] = f"{_dc} + {_uo25}" if "NoBet" not in [_dc, _uo25] and "No bet" not in [_dc, _uo25] else "NoBet"
        combo["doppia_chance_multigol"] = f"{_dc} + {_mgft_secco}" if "NoBet" not in [_dc, _mgft_secco] else "NoBet"
        pronostici_output["pronostici"].update(combo)
        
        # Salva il JSON di output
        output_file_name = os.path.join(PATH_OUTPUT_PRONOSTICI_V2, file_partita_json)
        with open(output_file_name, "w", encoding='utf-8') as out_f:
            json.dump(pronostici_output, out_f, indent=4, ensure_ascii=False)
        print(f"✅ Pronostico V2 salvato: {output_file_name}")

 # Esegui il push su GitHub solo se sono stati creati dei file di pronostico
    if os.path.exists(PATH_OUTPUT_PRONOSTICI_V2) and os.listdir(PATH_OUTPUT_PRONOSTICI_V2):
        print(f"\n📤 Eseguo il push della cartella '{PATH_OUTPUT_PRONOSTICI_V2}' su GitHub...")
        git_push_pronostici_v2(PATH_OUTPUT_PRONOSTICI_V2)
    else:
        print("\nℹ️ Nessun file di pronostico generato, push non necessario.")
if __name__ == "__main__":
    main()