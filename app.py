import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import time
from streamlit_option_menu import option_menu

# --- CONFIGURATION ---
st.set_page_config(page_title="H&C Manager Pro V86", layout="wide", initial_sidebar_state="expanded")

# --- DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    h1, h2, h3, p, div, label, span, li { color: #FFFFFF !important; }
    .card { background-color: #1f2937; padding: 25px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 25px; }
    .card h3 { color: #38bdf8 !important; font-size: 20px; border-bottom: 1px solid #374151; padding-bottom: 12px; }
    .kpi-val { font-size: 32px; font-weight: 800; color: #f9fafb; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }
    div.stButton > button:first-child { background-color: #3b82f6; color: white; border: none; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def connect_gs(sheet_name):
    try:
        secrets = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(secrets, scopes=scope)
        client = gspread.authorize(creds)
        return client.open(sheet_name)
    except: return None

def clean_chart(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), margin=dict(l=10, r=10, t=40, b=10), xaxis=dict(showgrid=False, color="white"), yaxis=dict(showgrid=True, gridcolor="#374151", color="white"), legend=dict(font=dict(color="white")))
    return fig

# --- AUTHENTIFICATION ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

def login():
    if st.session_state['u'] == "admin" and st.session_state['p'] == "rh123":
        st.session_state['logged_in'] = True
    else: st.error("Erreur d'accès")

if not st.session_state['logged_in']:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>🚀 H&C Manager Pro</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,1.5,1])
    with c2:
        st.text_input("Identifiant", key="u")
        st.text_input("Mot de passe", type="password", key="p")
        st.button("Se connecter", on_click=login, use_container_width=True)
    st.stop()

# --- BARRE LATÉRALE ---
with st.sidebar:
    app_mode = option_menu("ESPACE", ["Ressources Humaines", "Gestion Commerciale"], icons=['people-fill', 'briefcase-fill'], menu_icon="cast", default_index=0)
    st.markdown("---")
    
    if app_mode == "Ressources Humaines":
        menu_options = ["Tableau de bord", "Formation", "Recrutement", "Simulations", "Admin RH"]
        menu_icons = ["speedometer2", "mortarboard", "bullseye", "calculator", "database-fill-gear"]
        target_sheet = "Dashboard_Data"
    else:
        menu_options = ["Dashboard Sales", "Pipeline Ventes", "Forecast", "Admin Sales"]
        menu_icons = ["graph-up-arrow", "funnel", "magic", "database-fill-lock"]
        target_sheet = "Commercial_Data"

    selected = option_menu(None, menu_options, icons=menu_icons, default_index=0)
    
    # Filtre de service pour RH uniquement
    selected_service = "Tous"
    if app_mode == "Ressources Humaines":
        selected_service = st.selectbox("Filtrer par Service", ["Tous", "Vente", "Marketing", "IT", "Finance", "RH", "Support"])

# --- CHARGEMENT ---
@st.cache_data(ttl=60)
def load_data_pro(sh_name, mode):
    sh = connect_gs(sh_name)
    if not sh: return None
    data = {}
    tabs = ['Données Sociales', 'Salaires', 'Formation', 'Recrutement'] if mode == "Ressources Humaines" else ['Clients', 'Pipeline', 'Ventes']
    for t in tabs:
        try: data[t] = pd.DataFrame(sh.worksheet(t).get_all_records())
        except: data[t] = pd.DataFrame()
    return data

raw = load_data_pro(target_sheet, app_mode)

# --- LOGIQUE RH ---
if app_mode == "Ressources Humaines" and raw:
    df_rh = raw['Données Sociales']
    df_sal = raw['Salaires']
    df_gl = pd.merge(df_rh, df_sal, on='Nom', how='left')
    
    # Application du filtre Service
    if selected_service != "Tous":
        df_gl = df_gl[df_gl['Service'] == selected_service]

    if selected == "Tableau de bord":
        st.title(f"📊 BI - Ressources Humaines ({selected_service})")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{len(df_gl)}</div><div class='kpi-lbl'>Effectif</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{df_gl['Salaire (€)'].sum():,.0f} €</div><div class='kpi-lbl'>Masse Salariale / Mois</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><div class='kpi-val'>2.4%</div><div class='kpi-lbl'>Absentéisme</div></div>", unsafe_allow_html=True)
        
        # --- RÉACTIVATION GRAPHIQUE PYRAMIDE ---
        st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
        if 'Date Naissance' in df_gl.columns:
            today = datetime.now()
            df_gl['Date Naissance'] = pd.to_datetime(df_gl['Date Naissance'], errors='coerce')
            df_gl['Âge'] = df_gl['Date Naissance'].apply(lambda x: (today - x).days // 365 if pd.notnull(x) else 0)
            df_gl['Tranche'] = pd.cut(df_gl['Âge'], bins=[20,30,40,50,60,70], labels=["20-30","30-40","40-50","50-60","60+"])
            pyr = df_gl.groupby(['Tranche', 'Sexe']).size().reset_index(name='Nb')
            fig = px.bar(pyr, x='Nb', y='Tranche', color='Sexe', orientation='h', barmode='group')
            st.plotly_chart(clean_chart(fig), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# --- LOGIQUE COMMERCIAL ---
elif app_mode == "Gestion Commerciale" and raw:
    if selected == "Dashboard Sales":
        st.title("📈 BI - Performance Commerciale")
        ventes = raw['Ventes']
        pipe = raw['Pipeline']
        
        c1, c2 = st.columns(2)
        ca = ventes['Montant HT'].sum() if not ventes.empty else 0
        p_val = pipe['Montant estimé'].sum() if not pipe.empty else 0
        c1.markdown(f"<div class='card'><div class='kpi-val'>{ca:,.0f} €</div><div class='kpi-lbl'>CA Réalisé</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{p_val:,.0f} €</div><div class='kpi-lbl'>Valeur Pipeline</div></div>", unsafe_allow_html=True)

        # --- RÉACTIVATION FUNNEL ---
        st.markdown("<div class='card'><h3>Tunnel de Vente</h3>", unsafe_allow_html=True)
        if not pipe.empty:
            fig = px.funnel(pipe, x='Montant estimé', y='Client', color='Client')
            st.plotly_chart(clean_chart(fig), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# --- MODE ADMIN (IDENTIQUE POUR LES DEUX) ---
if selected in ["Admin RH", "Admin Sales"]:
    st.title("🛠️ Administration des Données")
    tabs = st.tabs(list(raw.keys()))
    for i, t_name in enumerate(raw.keys()):
        with tabs[i]:
            st.data_editor(raw[t_name], num_rows="dynamic", use_container_width=True)
