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

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="H&C Manager Pro", layout="wide", initial_sidebar_state="expanded")

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
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { color: #9ca3af; }
    .stTabs [data-baseweb="tab--active"] { color: #3b82f6; border-bottom-color: #3b82f6; }
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

def save_data(df, sheet_name, worksheet_name):
    try:
        sh = connect_gs(sheet_name)
        ws = sh.worksheet(worksheet_name)
        df_s = df.copy().fillna("")
        for c in df_s.columns:
            if pd.api.types.is_datetime64_any_dtype(df_s[c]): df_s[c] = df_s[c].dt.strftime('%d/%m/%Y')
        ws.clear()
        ws.update([df_s.columns.values.tolist()] + df_s.values.tolist())
        st.toast("✅ Données synchronisées avec le Cloud !")
        time.sleep(1); st.cache_data.clear(); st.rerun()
    except Exception as e: st.error(f"Erreur : {e}")

def clean_chart(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), margin=dict(l=10, r=10, t=40, b=10), xaxis=dict(showgrid=False, color="white"), yaxis=dict(showgrid=True, gridcolor="#374151", color="white"))
    return fig

# --- AUTHENTIFICATION ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

def login():
    if st.session_state['u'] == "admin" and st.session_state['p'] == "rh123":
        st.session_state['logged_in'] = True
    else: st.error("Identifiant ou mot de passe incorrect.")

if not st.session_state['logged_in']:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>🚀 H&C Manager Pro</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,1.5,1])
    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.text_input("Utilisateur", key="u")
        st.text_input("Mot de passe", type="password", key="p")
        st.button("Se connecter", on_click=login, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- BARRE LATÉRALE (LE SWITCHER) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1077/1077114.png", width=60)
    st.title("Tour de Contrôle")
    
    # LE CHOIX DE L'ESPACE DE TRAVAIL
    app_mode = option_menu(
        "ESPACE", ["Ressources Humaines", "Gestion Commerciale"],
        icons=['people-fill', 'briefcase-fill'],
        menu_icon="cast", default_index=0,
        styles={"container": {"padding": "5px", "background-color": "#1f2937"}, "nav-link": {"font-size": "14px", "text-align": "left", "margin":"0px", "color": "white"}, "nav-link-selected": {"background-color": "#3b82f6"}}
    )
    
    st.markdown("---")
    
    if app_mode == "Ressources Humaines":
        menu_options = ["Tableau de bord", "Fiches Salariés", "Formation", "Recrutement", "Simulations", "Admin RH"]
        menu_icons = ["speedometer2", "person-badge", "mortarboard", "bullseye", "calculator", "database-fill-gear"]
        target_sheet = "Dashboard_Data"
    else:
        menu_options = ["Dashboard Sales", "Clients & Prospects", "Pipeline Ventes", "Performance", "Forecast", "Admin Sales"]
        menu_icons = ["graph-up-arrow", "person-vcard", "funnel", "award", "magic", "database-fill-lock"]
        target_sheet = "Commercial_Data"

    selected = option_menu(None, menu_options, icons=menu_icons, default_index=0)
    
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

# --- CHARGEMENT DES DONNÉES ---
@st.cache_data(ttl=60)
def load_all_data(sh_name, mode):
    sh = connect_gs(sh_name)
    if not sh: return None
    data = {}
    
    if mode == "Ressources Humaines":
        tabs = ['Données Sociales', 'Salaires', 'Formation', 'Recrutement', 'Temps & Projets']
    else:
        tabs = ['Clients', 'Pipeline', 'Ventes']
        
    for t in tabs:
        try: data[t] = pd.DataFrame(sh.worksheet(t).get_all_records())
        except: data[t] = pd.DataFrame()
    return data

raw_data = load_all_data(target_sheet, app_mode)

# --- LOGIQUE MÉTIER RH ---
if app_mode == "Ressources Humaines" and raw_data:
    rh = raw_data['Données Sociales']
    sal = raw_data['Salaires']
    df_gl = pd.merge(rh, sal, on='Nom', how='left') if not rh.empty and not sal.empty else rh

    if selected == "Tableau de bord":
        st.title("📊 BI - Ressources Humaines")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{len(rh)}</div><div class='kpi-lbl'>Effectif Total</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{df_gl['Salaire (€)'].sum():,.0f} €</div><div class='kpi-lbl'>Masse Salariale Mensuelle</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><div class='kpi-val'>2.4%</div><div class='kpi-lbl'>Taux d'Absentéisme</div></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
        # (Logique graphique habituelle)
        st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Admin RH":
        st.title("🛠️ Administration des Données RH")
        tabs = st.tabs(list(raw_data.keys()))
        for i, tab_name in enumerate(raw_data.keys()):
            with tabs[i]:
                edited = st.data_editor(raw_data[tab_name], num_rows="dynamic", use_container_width=True, key=f"edit_{tab_name}")
                if st.button(f"Enregistrer {tab_name}"):
                    save_data(edited, target_sheet, tab_name)

# --- LOGIQUE MÉTIER COMMERCIAL ---
elif app_mode == "Gestion Commerciale" and raw_data:
    clients = raw_data['Clients']
    pipe = raw_data['Pipeline']
    ventes = raw_data['Ventes']

    if selected == "Dashboard Sales":
        st.title("📈 BI - Performance Commerciale")
        c1, c2, c3 = st.columns(3)
        ca_total = ventes['Montant HT'].sum() if not ventes.empty else 0
        pipe_val = pipe['Montant estimé'].sum() if not pipe.empty else 0
        
        c1.markdown(f"<div class='card'><div class='kpi-val'>{ca_total:,.0f} €</div><div class='kpi-lbl'>Chiffre d'Affaires Réalisé</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{pipe_val:,.0f} €</div><div class='kpi-lbl'>Valeur du Pipeline</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><div class='kpi-val'>{len(clients)}</div><div class='kpi-lbl'>Nombre de Clients</div></div>", unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("<div class='card'><h3>Tunnel de Vente</h3>", unsafe_allow_html=True)
            if not pipe.empty:
                # 
                fig = px.funnel(pipe, x='Montant estimé', y='Client', color='Client')
                st.plotly_chart(clean_chart(fig), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col_b:
            st.markdown("<div class='card'><h3>Top Clients</h3>", unsafe_allow_html=True)
            if not ventes.empty:
                df_top = ventes.groupby('Client')['Montant HT'].sum().reset_index().sort_values('Montant HT', ascending=False)
                st.plotly_chart(clean_chart(px.bar(df_top, x='Montant HT', y='Client', orientation='h')), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Forecast":
        st.title("🔮 Prévisionnel de Ventes")
        st.markdown("<div class='card'><h3>Paramètres de Projection</h3>", unsafe_allow_html=True)
        taux_conversion = st.slider("Taux de signature estimé (%)", 0, 100, 30)
        st.markdown("</div>", unsafe_allow_html=True)
        
        prevision = pipe['Montant estimé'].sum() * (taux_conversion/100)
        st.metric("CA Prévisionnel (Signature)", f"{prevision:,.0f} €", delta=f"{taux_conversion}% du pipe")

    elif selected == "Admin Sales":
        st.title("🛠️ Administration Sales")
        tabs = st.tabs(list(raw_data.keys()))
        for i, tab_name in enumerate(raw_data.keys()):
            with tabs[i]:
                edited = st.data_editor(raw_data[tab_name], num_rows="dynamic", use_container_width=True, key=f"edit_sales_{tab_name}")
                if st.button(f"Sauvegarder {tab_name}"):
                    save_data(edited, target_sheet, tab_name)

else:
    st.warning("Veuillez configurer vos fichiers Google Sheets 'Dashboard_Data' et 'Commercial_Data'.")
