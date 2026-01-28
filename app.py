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
st.set_page_config(page_title="H&C Manager Pro V89", layout="wide")

# --- DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .card { background-color: #1f2937; padding: 25px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
    .kpi-val { font-size: 32px; font-weight: 800; color: #f9fafb; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }
    h1, h2, h3, p, div, label { color: #FFFFFF !important; }
    div.stButton > button { background-color: #38bdf8 !important; color: #0e1117 !important; font-weight: bold !important; border: none !important; padding: 10px 20px !important; border-radius: 8px !important; }
    div.stButton > button:hover { background-color: #0ea5e9 !important; }
    /* Style spécifique pour le logo de la page de login */
    .login-logo { font-size: 90px; font-weight: 900; color: #38bdf8 !important; margin-bottom: 0; line-height: 1; text-align: center; }
    .login-subtitle { font-size: 24px; color: #9ca3af !important; margin-top: 10px; letter-spacing: 3px; text-align: center; text-transform: uppercase; }
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
    except Exception as e:
        st.error(f"Erreur de connexion au fichier '{sheet_name}' : {e}")
        return None

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
        st.toast(f"✅ {worksheet_name} synchronisé !")
        time.sleep(1); st.cache_data.clear(); st.rerun()
    except Exception as e: st.error(f"Erreur sauvegarde : {e}")

# --- AUTHENTIFICATION (PAGE DE GARDE H&C) ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    # Centrage du formulaire
    st.write("") # Spacer
    st.write("")
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        # --- LE NOUVEAU LOGO TEXTE ---
        st.markdown("<h1 class='login-logo'>H&C</h1>", unsafe_allow_html=True)
        st.markdown("<p class='login-subtitle'>Manager Pro</p>", unsafe_allow_html=True)
        st.write("") # Spacer
        
        # --- FORMULAIRE DANS UNE CARTE ---
        st.markdown("<div class='card' style='padding: 40px;'>", unsafe_allow_html=True)
        u = st.text_input("Identifiant", placeholder="ex: admin")
        p = st.text_input("Mot de passe", type="password", placeholder="••••••")
        st.write("")
        if st.button("SE CONNECTER", use_container_width=True):
            if u == "admin" and p == "rh123":
                st.session_state['logged_in'] = True; st.rerun()
            else: st.error("Identifiants incorrects")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    # Petit logo H&C en haut de la sidebar
    st.markdown("<h2 style='color: #38bdf8 !important; text-align: center; font-weight: 900; letter-spacing: 2px;'>H&C ADMIN</h2>", unsafe_allow_html=True)
    st.markdown("---")
    app_mode = option_menu("ESPACE DE TRAVAIL", ["Ressources Humaines", "Gestion Commerciale"], icons=['people-fill', 'briefcase-fill'], default_index=0, styles={"container": {"background-color": "transparent"}, "nav-link-selected": {"background-color": "#38bdf8"}})
    st.markdown("---")
    if app_mode == "Ressources Humaines":
        menu = ["Dashboard", "Salariés", "Formation", "Temps & Projets", "Admin RH"]
        icons = ["speedometer2", "person-badge", "mortarboard", "clock", "database-gear"]
        target = "Dashboard_Data"
    else:
        menu = ["Dashboard Sales", "Admin Sales"]
        icons = ["graph-up-arrow", "database-lock"]
        target = "Commercial_Data"
    selected = option_menu(None, menu, icons=icons, default_index=0, styles={"container": {"background-color": "transparent"}, "nav-link-selected": {"background-color": "#374151"}})
    
    st.write("")
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state['logged_in'] = False; st.rerun()

# --- CHARGEMENT DES DONNÉES ---
sh = connect_gs(target)
raw = {}
if sh:
    for worksheet in sh.worksheets():
        try:
            df = pd.DataFrame(worksheet.get_all_records())
            raw[worksheet.title] = clean_df(df)
        except: raw[worksheet.title] = pd.DataFrame()
else:
    st.error(f"Impossible de connecter le fichier '{target}'. Vérifiez les accès."); st.stop()

# --- LOGIQUE RH ---
if app_mode == "Ressources Humaines":
    df_soc = raw.get('Données Sociales', pd.DataFrame())
    df_sal = raw.get('Salaires', pd.DataFrame())
    df_gl = pd.merge(df_soc, df_sal, on='Nom', how='left') if not df_soc.empty and not df_sal.empty else df_soc

    if selected == "Dashboard":
        st.title("📊 Cockpit RH")
        c1, c2, c3 = st.columns(3)
        ms = df_gl['Salaire (€)'].apply(to_num).sum() if 'Salaire (€)' in df_gl.columns else 0
        c1.markdown(f"<div class='card'><div class='kpi-val'>{len(df_soc)}</div><div class='kpi-lbl'>Effectif Total</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{ms:,.0f} €</div><div class='kpi-lbl'>Masse Salariale Mensuelle</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><div class='kpi-val'>{(ms*12*1.45)/1000:,.0f} k€</div><div class='kpi-lbl'>Coût Annuel Chargé Est.</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
        if 'Date Naissance' in df_soc.columns and 'Sexe' in df_soc.columns:
            df_soc['Date Naissance'] = pd.to_datetime(df_soc['Date Naissance'], dayfirst=True, errors='coerce')
            df_soc['Âge'] = df_soc['Date Naissance'].apply(lambda x: (datetime.now() - x).days // 365 if pd.notnull(x) else 0)
            fig = px.histogram(df_soc, x='Âge', color='Sexe', nbins=10, barmode='group', color_discrete_map={'Homme':'#38bdf8','Femme':'#ec4899'})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Salariés":
        st.title("👤 Fiches Individuelles")
        noms = sorted(df_soc['Nom'].unique().tolist()) if not df_soc.empty and 'Nom' in df_soc.columns else []
        choix = st.selectbox("Choisir un collaborateur", noms)
        if choix:
            perso = df_gl[df_gl['Nom'] == choix].iloc[0]
            st.markdown(f"<div class='card' style='border-left: 5px solid #38bdf8;'><h2>{perso.get('Nom','-')}</h2><p style='color: #9ca3af !important;'>{perso.get('Poste','-')} • {perso.get('Service','-')}</p></div>", unsafe_allow_html=True)
            st.write("### Détails du contrat")
            st.dataframe(df_gl[df_gl['Nom'] == choix].T, use_container_width=True)

    elif selected == "Formation":
        st.title("🎓 Suivi Formation")
        df_f = raw.get('Formation', pd.DataFrame())
        if not df_f.empty:
            total_f = df_f['Coût Formation (€)'].apply(to_num).sum() if 'Coût Formation (€)' in df_f.columns else 0
            st.metric("Budget Total Consommé", f"{total_f:,.0f} €")
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.dataframe(df_f, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Temps & Projets":
        st.title("⏳ Analyse du Temps")
        df_t = raw.get('Temps & Projets', pd.DataFrame())
        if not df_t.empty and 'Heures Travaillées' in df_t.columns and 'Projet' in df_t.columns:
            df_t['Heures Travaillées'] = df_t['Heures Travaillées'].apply(to_num)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("<div class='card'><h3>Par Projet</h3>", unsafe_allow_html=True)
                st.plotly_chart(px.pie(df_t, values='Heures Travaillées', names='Projet', color_discrete_sequence=px.colors.sequential.Blues_r), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with c2:
                st.markdown("<div class='card'><h3>Par Collaborateur</h3>", unsafe_allow_html=True)
                st.plotly_chart(px.bar(df_t, x='Nom', y='Heures Travaillées', color='Projet'), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

# --- LOGIQUE COMMERCIAL ---
elif app_mode == "Gestion Commerciale":
    st.title("📈 Performance Commerciale")
    df_v = raw.get('Ventes', pd.DataFrame())
    df_p = raw.get('Pipeline', pd.DataFrame())
    
    c1, c2 = st.columns(2)
    ca = df_v['Montant HT'].apply(to_num).sum() if not df_v.empty and 'Montant HT' in df_v.columns else 0
    pipe = df_p['Montant estimé'].apply(to_num).sum() if not df_p.empty and 'Montant estimé' in df_p.columns else 0
    
    c1.markdown(f"<div class='card'><div class='kpi-val'>{ca:,.0f} €</div><div class='kpi-lbl'>CA Réalisé</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><div class='kpi-val'>{pipe:,.0f} €</div><div class='kpi-lbl'>Valeur du Pipeline</div></div>", unsafe_allow_html=True)

    if not df_p.empty and 'Nom opportunité' in df_p.columns:
        st.markdown("<div class='card'><h3>Tunnel de Vente</h3>", unsafe_allow_html=True)
        fig = px.funnel(df_p, x=df_p['Montant estimé'].apply(to_num), y='Client', color='Client')
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# --- ADMINISTRATION ---
if "Admin" in selected:
    st.title(f"🛠️ Gestion des bases : {target.replace('_', ' ')}")
    st.info("Modifiez les données directement dans les tableaux ci-dessous. N'oubliez pas de sauvegarder.")
    tabs = st.tabs([t.replace('_', ' ') for t in raw.keys()])
    for i, t_name in enumerate(raw.keys()):
        with tabs[i]:
            st.markdown(f"<div class='card'>", unsafe_allow_html=True)
            edited = st.data_editor(raw[t_name], num_rows="dynamic", use_container_width=True, key=f"editor_{t_name}")
            st.write("")
            if st.button(f"💾 SAUVEGARDER {t_name.upper()}", use_container_width=True):
                save_data(edited, target, t_name)
            st.markdown("</div>", unsafe_allow_html=True)
