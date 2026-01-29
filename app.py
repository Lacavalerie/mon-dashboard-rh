import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import re
from streamlit_option_menu import option_menu

# --- CONFIGURATION ---
st.set_page_config(page_title="H&C Manager Pro V95", layout="wide")

# --- DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .card { background-color: #1f2937; padding: 25px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 25px; }
    .kpi-val { font-size: 32px; font-weight: 800; color: #38bdf8; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }
    .alert-card { background-color: #450a0a; border: 1px solid #ef4444; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    h1, h2, h3, p, div, label { color: #FFFFFF !important; }
    div.stButton > button { background-color: #38bdf8 !important; color: #0e1117 !important; font-weight: bold !important; border-radius: 8px !important; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def to_num(val):
    if pd.isna(val) or val == "": return 0
    if isinstance(val, (int, float)): return float(val)
    cleaned = re.sub(r'[^0-9,-]', '', str(val)).replace(',', '.')
    try: return float(cleaned)
    except: return 0

def connect_gs(sheet_name):
    try:
        secrets = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(secrets, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open(sheet_name)
    except: return None

# --- AUTHENTIFICATION ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<h1 style='text-align:center; color:#38bdf8 !important; font-size:80px;'>H&C</h1>", unsafe_allow_html=True)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        u = st.text_input("Identifiant"); p = st.text_input("Mot de passe", type="password")
        if st.button("SE CONNECTER", use_container_width=True):
            if u == "admin" and p == "rh123": st.session_state['logged_in'] = True; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    app_mode = option_menu("ESPACE", ["RH", "Commercial"], icons=['people', 'briefcase'], default_index=0)
    menu = ["Dashboard", "Formation", "Recrutement", "Admin RH"] if app_mode == "RH" else ["Pipeline CRM", "Historique Ventes", "Admin Sales"]
    target = "Dashboard_Data" if app_mode == "RH" else "Commercial_Data"
    selected = option_menu(None, menu, default_index=0)
    if st.button("🚪 Déconnexion"): st.session_state['logged_in'] = False; st.rerun()

# --- CHARGEMENT ---
sh = connect_gs(target)
raw = {}
if sh:
    for ws in sh.worksheets():
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        raw[ws.title] = df
else: st.stop()

# --- LOGIQUE RH ---
if app_mode == "RH":
    df_soc = raw.get('Données Sociales', pd.DataFrame())
    df_sal = raw.get('Salaires', pd.DataFrame())
    df_gl = pd.merge(df_soc, df_sal, on='Nom', how='left') if not df_soc.empty and not df_sal.empty else df_soc

    if selected == "Dashboard":
        st.title("📊 BI - Ressources Humaines")
        
        # KPIs
        ms_val = df_gl['Salaire (€)'].apply(to_num).sum() if 'Salaire (€)' in df_gl.columns else 0
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{len(df_soc)}</div><div class='kpi-lbl'>Effectif</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{ms_val:,.0f} €</div><div class='kpi-lbl'>Masse Salariale / Mois</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><div class='kpi-val'>2.4%</div><div class='kpi-lbl'>Absentéisme</div></div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
            if 'Date Naissance' in df_soc.columns:
                df_soc['Date Naissance'] = pd.to_datetime(df_soc['Date Naissance'], dayfirst=True, errors='coerce')
                df_soc['Âge'] = df_soc['Date Naissance'].apply(lambda x: (datetime.now() - x).days // 365 if pd.notnull(x) else 0)
                st.plotly_chart(px.histogram(df_soc, x='Âge', color='Sexe', barmode='group', color_discrete_map={'Homme':'#38bdf8','Femme':'#ec4899'}), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown("<div class='card'><h3>Masse Salariale par Service</h3>", unsafe_allow_html=True)
            if 'Service' in df_gl.columns:
                df_gl['Sal_N'] = df_gl['Salaire (€)'].apply(to_num)
                ms_svc = df_gl.groupby('Service')['Sal_N'].sum().reset_index().sort_values('Sal_N', ascending=False)
                st.plotly_chart(px.bar(ms_svc, x='Service', y='Sal_N', color='Service'), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Formation":
        st.title("🎓 Pilotage Formation")
        df_f = raw.get('Formation', pd.DataFrame())
        if not df_f.empty:
            df_f['Cout_N'] = df_f['Coût Formation (€)'].apply(to_num)
            df_f_svc = pd.merge(df_f, df_soc[['Nom', 'Service']], on='Nom', how='left') if 'Nom' in df_f.columns and not df_soc.empty else df_f
            
            st.markdown("<div class='card'><h3>Budget par Service</h3>", unsafe_allow_html=True)
            if 'Service' in df_f_svc.columns:
                st.plotly_chart(px.pie(df_f_svc, values='Cout_N', names='Service', hole=0.5), use_container_width=True)
            else: st.info("Assurez-vous que les noms correspondent entre 'Formation' et 'Données Sociales'.")
            st.markdown("</div>", unsafe_allow_html=True)
            st.dataframe(df_f, use_container_width=True)

    elif selected == "Recrutement":
        st.title("🎯 Recrutement")
        df_r = raw.get('Recrutement', pd.DataFrame())
        if not df_r.empty:
            st.markdown("<div class='card'><h3>Candidats par Canal</h3>", unsafe_allow_html=True)
            st.plotly_chart(px.bar(df_r, x='Poste', y='Nombre Candidats', color='Canal Sourcing'), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# --- LOGIQUE COMMERCIAL (CRM) ---
elif app_mode == "Commercial":
    df_v = raw.get('Ventes', pd.DataFrame())
    df_p = raw.get('Pipeline', pd.DataFrame())

    if selected == "Pipeline CRM":
        st.title("🎯 Pipeline & Prévisions")
        if not df_p.empty:
            df_p['Montant_N'] = df_p['Montant estimé'].apply(to_num)
            df_p['Prob_N'] = df_p['Probabilité (%)'].apply(to_num) / 100
            df_p['Pondéré'] = df_p['Montant_N'] * df_p['Prob_N']
            
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div class='card'><div class='kpi-val'>{df_p['Montant_N'].sum():,.0f} €</div><div class='kpi-lbl'>Volume Pipe</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='card'><div class='kpi-val' style='color:#10b981;'>{df_p['Pondéré'].sum():,.0f} €</div><div class='kpi-lbl'>CA Pondéré</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='card'><div class='kpi-val'>{len(df_p)}</div><div class='kpi-lbl'>Deals</div></div>", unsafe_allow_html=True)

            colA, colB = st.columns([2, 1])
            with colA:
                st.markdown("<div class='card'><h3>Entonnoir de Vente</h3>", unsafe_allow_html=True)
                if 'Étape' in df_p.columns:
                    ordre_logique = ["Prospection", "Qualification", "Proposition", "Négociation"]
                    df_funnel = df_p.groupby('Étape')['Montant_N'].sum().reset_index()
                    df_funnel['Étape'] = pd.Categorical(df_funnel['Étape'], categories=ordre_logique, ordered=True)
                    df_funnel = df_funnel.sort_values('Étape')
                    fig_f = px.funnel(df_funnel, x='Montant_N', y='Étape', color_discrete_sequence=['#38bdf8'])
                    st.plotly_chart(fig_f, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with colB:
                st.markdown("<div class='card'><h3>🚀 Relances</h3>", unsafe_allow_html=True)
                urgents = df_p[df_p['Prob_N'] >= 0.7].sort_values('Montant_N', ascending=False)
                for _, row in urgents.iterrows():
                    st.markdown(f"<div class='alert-card'><b>{row['Nom opportunité']}</b><br/>{row['Client']} — {row['Montant_N']:,.0f} €</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Historique Ventes":
        st.title("📊 Analyse du CA")
        if not df_v.empty:
            df_v['Total_HT'] = df_v['Montant HT'].apply(to_num)
            st.plotly_chart(px.bar(df_v, x='Client', y='Total_HT', color='Produit'))
            st.dataframe(df_v, use_container_width=True)

# --- ADMIN ---
if "Admin" in selected:
    st.title("🛠️ Administration")
    tabs = st.tabs(list(raw.keys()))
    for i, t_name in enumerate(raw.keys()):
        with tabs[i]:
            st.data_editor(raw[t_name], num_rows="dynamic", use_container_width=True)
