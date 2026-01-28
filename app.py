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
st.set_page_config(page_title="H&C Manager Pro V88", layout="wide")

# --- DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .card { background-color: #1f2937; padding: 25px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 25px; }
    .kpi-val { font-size: 32px; font-weight: 800; color: #f9fafb; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; }
    h1, h2, h3, p, div, label { color: #FFFFFF !important; }
    div.stButton > button { background-color: #3b82f6 !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def to_num(val):
    """Transforme '2 000,00 €' en 2000.0 proprement"""
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
    """Nettoie les noms de colonnes (enlève espaces invisibles)"""
    df.columns = [str(c).strip() for c in df.columns]
    return df

def save_data(df, sheet_name, worksheet_name):
    try:
        sh = connect_gs(sheet_name)
        ws = sh.worksheet(worksheet_name)
        df_save = df.copy().fillna("")
        # Formatage des dates pour Google Sheets
        for col in df_save.columns:
            if pd.api.types.is_datetime64_any_dtype(df_save[col]):
                df_save[col] = df_save[col].dt.strftime('%d/%m/%Y')
        ws.clear()
        ws.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.toast(f"✅ {worksheet_name} synchronisé !")
        time.sleep(1); st.cache_data.clear(); st.rerun()
    except Exception as e: st.error(f"Erreur sauvegarde : {e}")

# --- AUTHENTIFICATION ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        st.title("🚀 Connexion")
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if u == "admin" and p == "rh123":
                st.session_state['logged_in'] = True; st.rerun()
            else: st.error("Identifiants incorrects")
    st.stop()

# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    app_mode = option_menu("ESPACE", ["Ressources Humaines", "Gestion Commerciale"], icons=['people', 'briefcase'], default_index=0)
    st.markdown("---")
    if app_mode == "Ressources Humaines":
        menu = ["Dashboard", "Salariés", "Formation", "Temps & Projets", "Admin RH"]
        target = "Dashboard_Data"
    else:
        menu = ["Dashboard Sales", "Admin Sales"]
        target = "Commercial_Data"
    selected = option_menu(None, menu, default_index=0)
    
    if st.button("🚪 Déconnexion"):
        st.session_state['logged_in'] = False; st.rerun()

# --- CHARGEMENT DES DONNÉES ---
sh = connect_gs(target)
raw = {}
if sh:
    # On récupère tous les onglets présents dans le fichier
    for worksheet in sh.worksheets():
        try:
            df = pd.DataFrame(worksheet.get_all_records())
            raw[worksheet.title] = clean_df(df)
        except: raw[worksheet.title] = pd.DataFrame()
else:
    st.warning(f"Le fichier '{target}' est introuvable. Vérifiez le partage avec le robot.")
    st.stop()

# --- LOGIQUE RH ---
if app_mode == "Ressources Humaines":
    # Fusion des données sociales et salaires
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

        # Graphique Pyramide
        st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
        if 'Date Naissance' in df_soc.columns and 'Sexe' in df_soc.columns:
            df_soc['Date Naissance'] = pd.to_datetime(df_soc['Date Naissance'], dayfirst=True, errors='coerce')
            df_soc['Âge'] = df_soc['Date Naissance'].apply(lambda x: (datetime.now() - x).days // 365 if pd.notnull(x) else 0)
            fig = px.histogram(df_soc, x='Âge', color='Sexe', nbins=10, barmode='group', color_discrete_map={'Homme':'#3b82f6','Femme':'#ec4899'})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Salariés":
        st.title("👤 Fiches Individuelles")
        noms = sorted(df_soc['Nom'].unique().tolist())
        choix = st.selectbox("Choisir un collaborateur", noms)
        if choix:
            perso = df_gl[df_gl['Nom'] == choix].iloc[0]
            st.markdown(f"<div class='card'><h2>{perso['Nom']}</h2><p>{perso.get('Poste','-')} • {perso.get('Service','-')}</p></div>", unsafe_allow_html=True)
            st.write("### Détails complets")
            st.table(df_soc[df_soc['Nom'] == choix].T)

    elif selected == "Formation":
        st.title("🎓 Suivi Formation")
        df_f = raw.get('Formation', pd.DataFrame())
        if not df_f.empty:
            total_f = df_f['Coût Formation (€)'].apply(to_num).sum() if 'Coût Formation (€)' in df_f.columns else 0
            st.metric("Budget Total Consommé", f"{total_f:,.0f} €")
            st.dataframe(df_f, use_container_width=True)
            if 'Type Formation' in df_f.columns:
                fig = px.pie(df_f, values=df_f['Coût Formation (€)'].apply(to_num), names='Type Formation', hole=0.5)
                st.plotly_chart(fig)

    elif selected == "Temps & Projets":
        st.title("⏳ Analyse du Temps")
        df_t = raw.get('Temps & Projets', pd.DataFrame())
        if not df_t.empty:
            df_t['Heures Travaillées'] = df_t['Heures Travaillées'].apply(to_num)
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(px.pie(df_t, values='Heures Travaillées', names='Projet', title="Répartition par Projet"))
            with c2:
                st.plotly_chart(px.bar(df_t, x='Nom', y='Heures Travaillées', color='Projet', title="Heures par Collaborateur"))

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
        # Funnel basé sur le montant par client/opportunité
        fig = px.funnel(df_p, x=df_p['Montant estimé'].apply(to_num), y='Client', color='Client')
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# --- ADMINISTRATION (TOUTES LES COLONNES) ---
if "Admin" in selected:
    st.title(f"🛠️ Gestion des bases : {target}")
    tabs = st.tabs(list(raw.keys()))
    for i, t_name in enumerate(raw.keys()):
        with tabs[i]:
            st.info(f"Modifiez les données ci-dessous. Toutes les colonnes sont incluses.")
            edited = st.data_editor(raw[t_name], num_rows="dynamic", use_container_width=True, key=f"editor_{t_name}")
            if st.button(f"💾 Sauvegarder {t_name}"):
                save_data(edited, target, t_name)
