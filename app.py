import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
from streamlit_option_menu import option_menu

# --- CONFIGURATION ---
st.set_page_config(page_title="H&C Manager Pro V87", layout="wide")

# --- DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .card { background-color: #1f2937; padding: 25px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 25px; }
    .kpi-val { font-size: 32px; font-weight: 800; color: #f9fafb; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; }
    h1, h2, h3, p, div { color: #FFFFFF !important; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def connect_gs(sheet_name):
    try:
        secrets = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(secrets, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open(sheet_name)
    except: return None

def clean_col(df):
    """Nettoie les noms de colonnes pour éviter les erreurs de frappe"""
    df.columns = [c.strip().replace('  ', ' ') for c in df.columns]
    return df

def to_num(val):
    if isinstance(val, str): val = val.replace('€','').replace(' ','').replace(',','.')
    try: return float(val)
    except: return 0

# --- AUTHENTIFICATION ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        st.title("🚀 Connexion")
        u = st.text_input("ID")
        p = st.text_input("MDP", type="password")
        if st.button("Entrer"):
            if u == "admin" and p == "rh123":
                st.session_state['logged_in'] = True
                st.rerun()
    st.stop()

# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    app_mode = option_menu("ESPACE", ["Ressources Humaines", "Gestion Commerciale"], icons=['people', 'briefcase'], default_index=0)
    st.markdown("---")
    if app_mode == "Ressources Humaines":
        menu = ["Dashboard", "Formation", "Admin RH"]
        target = "Dashboard_Data"
    else:
        menu = ["Dashboard Sales", "Admin Sales"]
        target = "Commercial_Data"
    selected = option_menu(None, menu, default_index=0)

# --- CHARGEMENT ---
sh = connect_gs(target)
raw = {}
if sh:
    tabs = ['Données Sociales', 'Salaires', 'Formation'] if app_mode == "Ressources Humaines" else ['Ventes', 'Pipeline']
    for t in tabs:
        try:
            df = pd.DataFrame(sh.worksheet(t).get_all_records())
            raw[t] = clean_col(df)
        except: raw[t] = pd.DataFrame()

# --- AFFICHAGE RH ---
if app_mode == "Ressources Humaines" and not raw['Données Sociales'].empty:
    df_rh = raw['Données Sociales']
    df_sal = raw['Salaires']
    df_gl = pd.merge(df_rh, df_sal, on='Nom', how='left')
    
    if selected == "Dashboard":
        st.title("📊 BI - Ressources Humaines")
        # KPIs
        c1, c2 = st.columns(2)
        sal_total = df_gl['Salaire (€)'].apply(to_num).sum() if 'Salaire (€)' in df_gl.columns else 0
        c1.markdown(f"<div class='card'><div class='kpi-val'>{len(df_rh)}</div><div class='kpi-lbl'>Effectif</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{sal_total:,.0f} €</div><div class='kpi-lbl'>Masse Salariale</div></div>", unsafe_allow_html=True)
        
        # Graphique Pyramide (SÉCURISÉ)
        st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
        if 'Date Naissance' in df_rh.columns and 'Sexe' in df_rh.columns:
            df_rh['Date Naissance'] = pd.to_datetime(df_rh['Date Naissance'], dayfirst=True, errors='coerce')
            df_rh['Âge'] = df_rh['Date Naissance'].apply(lambda x: (datetime.now() - x).days // 365 if pd.notnull(x) else 0)
            fig = px.histogram(df_rh, x='Âge', color='Sexe', nbins=10, barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        else: st.warning("Vérifiez que les colonnes 'Date Naissance' et 'Sexe' existent.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Formation":
        st.title("🎓 Pilotage Formation")
        df_f = raw['Formation']
        if not df_f.empty:
            # Correction des noms de colonnes au cas où
            if 'Coût Formation (€)' not in df_f.columns and 'Cout Formation' in df_f.columns:
                df_f.rename(columns={'Cout Formation': 'Coût Formation (€)'}, inplace=True)
            
            cout = df_f['Coût Formation (€)'].apply(to_num).sum() if 'Coût Formation (€)' in df_f.columns else 0
            st.metric("Budget Consommé", f"{cout:,.0f} €")
            st.dataframe(df_f, use_container_width=True)
        else: st.error("Onglet 'Formation' vide ou introuvable.")

# --- AFFICHAGE SALES ---
elif app_mode == "Gestion Commerciale" and not raw['Ventes'].empty:
    st.title("📈 Performance Commerciale")
    df_v = raw['Ventes']
    ca = df_v['Montant HT'].apply(to_num).sum() if 'Montant HT' in df_v.columns else 0
    st.metric("Chiffre d'Affaires HT", f"{ca:,.0f} €")
    st.plotly_chart(px.bar(df_v, x='Client', y='Montant HT', color='Produit'))

# --- ADMIN ---
if "Admin" in selected:
    st.title("🛠️ Gestion BDD")
    for t_name, df_val in raw.items():
        st.subheader(t_name)
        st.data_editor(df_val, use_container_width=True, key=f"editor_{t_name}")
