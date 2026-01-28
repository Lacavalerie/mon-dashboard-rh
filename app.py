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
st.set_page_config(page_title="H&C Manager Pro V90", layout="wide")

# --- DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .card { background-color: #1f2937; padding: 25px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 25px; }
    .kpi-val { font-size: 32px; font-weight: 800; color: #f9fafb; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }
    h1, h2, h3, p, div, label { color: #FFFFFF !important; }
    div.stButton > button { background-color: #38bdf8 !important; color: #0e1117 !important; font-weight: bold !important; border: none !important; border-radius: 8px !important; }
    .login-logo { font-size: 90px; font-weight: 900; color: #38bdf8 !important; text-align: center; line-height: 1; }
    .login-subtitle { font-size: 24px; color: #9ca3af !important; letter-spacing: 3px; text-align: center; text-transform: uppercase; }
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

def clean_df(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df

def save_data(df, sheet_name, worksheet_name):
    try:
        sh = connect_gs(sheet_name)
        ws = sh.worksheet(worksheet_name)
        df_save = df.copy().fillna("")
        for col in df_save.columns:
            if pd.api.types.is_datetime64_any_dtype(df_save[col]):
                df_save[col] = df_save[col].dt.strftime('%d/%m/%Y')
        ws.clear()
        ws.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.toast(f"✅ {worksheet_name} sauvegardé !")
        time.sleep(1); st.cache_data.clear(); st.rerun()
    except Exception as e: st.error(f"Erreur : {e}")

# --- AUTHENTIFICATION ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<h1 class='login-logo'>H&C</h1><p class='login-subtitle'>Manager Pro</p>", unsafe_allow_html=True)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.button("SE CONNECTER", use_container_width=True):
            if u == "admin" and p == "rh123": st.session_state['logged_in'] = True; st.rerun()
            else: st.error("Erreur d'identifiants")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='color: #38bdf8; text-align: center; font-weight: 900;'>H&C ADMIN</h2>", unsafe_allow_html=True)
    app_mode = option_menu("ESPACE", ["Ressources Humaines", "Gestion Commerciale"], icons=['people-fill', 'briefcase-fill'], default_index=0)
    
    if app_mode == "Ressources Humaines":
        menu = ["Dashboard", "Formation", "Recrutement", "Salariés", "Admin RH"]
        icons = ["speedometer2", "mortarboard", "bullseye", "person-badge", "database-gear"]
        target = "Dashboard_Data"
    else:
        menu = ["Dashboard Sales", "Admin Sales"]
        icons = ["graph-up-arrow", "database-lock"]
        target = "Commercial_Data"
    selected = option_menu(None, menu, icons=icons, default_index=0)
    if st.button("🚪 Déconnexion", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()

# --- CHARGEMENT ---
sh = connect_gs(target)
raw = {}
if sh:
    for ws in sh.worksheets():
        try: raw[ws.title] = clean_df(pd.DataFrame(ws.get_all_records()))
        except: raw[ws.title] = pd.DataFrame()
else: st.error("Fichier introuvable"); st.stop()

# --- LOGIQUE RH ---
if app_mode == "Ressources Humaines":
    df_soc = raw.get('Données Sociales', pd.DataFrame())
    df_sal = raw.get('Salaires', pd.DataFrame())
    df_gl = pd.merge(df_soc, df_sal, on='Nom', how='left') if not df_soc.empty and not df_sal.empty else df_soc

    if selected == "Dashboard":
        st.title("📊 BI - Ressources Humaines")
        
        # Calcul Masse Salariale par Service
        if 'Salaire (€)' in df_gl.columns and 'Service' in df_gl.columns:
            df_gl['Salaire_Num'] = df_gl['Salaire (€)'].apply(to_num)
            ms_total = df_gl['Salaire_Num'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div class='card'><div class='kpi-val'>{len(df_soc)}</div><div class='kpi-lbl'>Effectif</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='card'><div class='kpi-val'>{ms_total:,.0f} €</div><div class='kpi-lbl'>Masse Salariale / Mois</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='card'><div class='kpi-val'>{(ms_total*12*1.45)/1000:,.0f} k€</div><div class='kpi-lbl'>Budget Annuel Chargé</div></div>", unsafe_allow_html=True)

            # --- RÉPONSE À TA QUESTION : QUEL SERVICE A LA PLUS GROSSE MASSE SALARIALE ? ---
            st.markdown("<div class='card'><h3>Répartition de la Masse Salariale par Service</h3>", unsafe_allow_html=True)
            ms_svc = df_gl.groupby('Service')['Salaire_Num'].sum().reset_index().sort_values('Salaire_Num', ascending=False)
            fig_ms = px.bar(ms_svc, x='Service', y='Salaire_Num', color='Service', text_auto='.2s', color_discrete_sequence=px.colors.sequential.Blues_r)
            fig_ms.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#374151"))
            st.plotly_chart(fig_ms, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Formation":
        st.title("🎓 Pilotage de la Formation")
        df_f = raw.get('Formation', pd.DataFrame())
        if not df_f.empty:
            df_f['Cout_Num'] = df_f['Coût Formation (€)'].apply(to_num)
            
            c1, c2 = st.columns(2)
            c1.markdown(f"<div class='card'><div class='kpi-val'>{df_f['Cout_Num'].sum():,.0f} €</div><div class='kpi-lbl'>Budget Consommé</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='card'><div class='kpi-val'>{len(df_f)}</div><div class='kpi-lbl'>Nombre d'actions</div></div>", unsafe_allow_html=True)

            # Graphique Formation par Service
            st.markdown("<div class='card'><h3>Investissement Formation par Service</h3>", unsafe_allow_html=True)
            # On fusionne avec les données sociales pour avoir le service si non présent
            if 'Service' not in df_f.columns:
                df_f = pd.merge(df_f, df_soc[['Nom', 'Service']], on='Nom', how='left')
            
            form_svc = df_f.groupby('Service')['Cout_Num'].sum().reset_index()
            st.plotly_chart(px.pie(form_svc, values='Cout_Num', names='Service', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.dataframe(df_f[['Nom', 'Type Formation', 'Coût Formation (€)', 'Service']], use_container_width=True)

    elif selected == "Recrutement":
        st.title("🎯 Gestion du Recrutement")
        df_r = raw.get('Recrutement', pd.DataFrame())
        if not df_r.empty:
            df_r['Cout_Rec_Num'] = df_r['Coût Recrutement (€)'].apply(to_num)
            
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div class='card'><div class='kpi-val'>{len(df_r)}</div><div class='kpi-lbl'>Postes Ouverts</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='card'><div class='kpi-val'>{df_r['Nombre Candidats'].sum()}</div><div class='kpi-lbl'>Candidatures Reçues</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='card'><div class='kpi-val'>{df_r['Cout_Rec_Num'].sum():,.0f} €</div><div class='kpi-lbl'>Coût Total Recrutement</div></div>", unsafe_allow_html=True)
            
            st.markdown("<div class='card'><h3>Pipeline de Recrutement</h3>", unsafe_allow_html=True)
            fig_rec = px.bar(df_r, x='Poste', y='Nombre Candidats', color='Canal Sourcing', barmode='group')
            fig_rec.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig_rec, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Salariés":
        st.title("👤 Fiches Salariés")
        choix = st.selectbox("Choisir un collaborateur", sorted(df_soc['Nom'].unique().tolist()))
        if choix:
            p = df_gl[df_gl['Nom'] == choix].iloc[0]
            st.markdown(f"<div class='card' style='border-left: 5px solid #38bdf8;'><h2>{p['Nom']}</h2><p>{p.get('Poste','-')} • {p.get('Service','-')}</p></div>", unsafe_allow_html=True)
            st.table(df_soc[df_soc['Nom'] == choix].T)

# --- ADMINISTRATION ---
if "Admin" in selected:
    st.title(f"🛠️ Gestion des bases")
    tabs = st.tabs([t.replace('_', ' ') for t in raw.keys()])
    for i, t_name in enumerate(raw.keys()):
        with tabs[i]:
            edited = st.data_editor(raw[t_name], num_rows="dynamic", use_container_width=True, key=f"ed_{t_name}")
            if st.button(f"💾 SAUVEGARDER {t_name.upper()}", use_container_width=True):
                save_data(edited, target, t_name)
