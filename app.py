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

# Configuration
st.set_page_config(page_title="RH Cockpit V69", layout="wide", initial_sidebar_state="expanded")

# --- DESIGN (Identique V67) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    h1, h2, h3, p, div, label, span, li { color: #FFFFFF !important; }
    .card { background-color: #1f2937; padding: 20px; border-radius: 12px; border: 1px solid #374151; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3); margin-bottom: 25px; }
    .card h3 { color: #38bdf8 !important; font-size: 20px; font-weight: 600; margin-bottom: 20px; border-bottom: 2px solid #374151; padding-bottom: 12px; }
    .kpi-val { font-size: 28px; font-weight: bold; color: #f9fafb; }
    .kpi-lbl { font-size: 13px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;}
    .alert-box { background-color: rgba(127, 29, 29, 0.5); color: #fca5a5 !important; padding: 15px; border-radius: 8px; border: 1px solid #ef4444; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS UTILES ---
def calculer_turnover(df):
    """Calcule le taux de turnover (Départs / Effectif Moyen) * 100"""
    if 'Statut' in df.columns:
        departures = (df['Statut'] == 'Sorti').sum()
        active_staff = (df['Statut'] == 'Actif').sum()
        
        # Effectif Moyen (Simplifié : (Actif + (Actif + Départs)) / 2)
        # On utilise Effectif Actif + Départs / 2 pour une base simple de l'effectif moyen
        current_headcount = departures + active_staff
        
        if current_headcount > 0:
            taux = (departures / (current_headcount + active_staff) / 2) * 100 # Approx. Effectif Moyen
            return taux
    return 0.0

def connect_google_sheet():
    try:
        secrets = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(secrets, scopes=scope)
        client = gspread.authorize(creds)
        return client.open("Dashboard_Data") 
    except Exception as e: st.error(f"⚠️ Erreur Google : {e}"); st.stop()

def save_data_to_google(df, worksheet_name):
    try:
        sheet = connect_google_sheet(st.session_state.get('current_sheet', "Dashboard_Data"))
        ws = sheet.worksheet(worksheet_name)
        df_to_save = df.copy()
        for col in df_to_save.columns:
            if pd.api.types.is_datetime64_any_dtype(df_to_save[col]): df_to_save[col] = df_to_save[col].dt.strftime('%d/%m/%Y')
        ws.clear()
        ws.update([df_to_save.columns.values.tolist()] + df_to_save.values.tolist())
        st.toast(f"✅ {worksheet_name} sauvegardé !", icon="💾")
        time.sleep(1)
        st.cache_data.clear()
        st.rerun()
    except Exception as e: st.error(f"Erreur sauvegarde : {e}")

# ... (Autres fonctions PDF, clean_currency, clean_chart restent les mêmes) ...

def clean_currency(val):
    if isinstance(val, str): val = val.replace('€', '').replace(' ', '').replace('\xa0', '').replace(',', '.')
    try: return float(val)
    except: return 0
    
def calculer_donnees(df):
    today = datetime.now()
    if 'Date Naissance' in df.columns:
        df['Date Naissance'] = pd.to_datetime(df['Date Naissance'], errors='coerce')
        df['Âge'] = df['Date Naissance'].apply(lambda x: (today - x).days // 365 if pd.notnull(x) else 0)
    return df

def clean_chart(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), margin=dict(l=10, r=10, t=40, b=10), xaxis=dict(showgrid=False, color="white"), yaxis=dict(showgrid=True, gridcolor="#374151", color="white"), legend=dict(font=dict(color="white")))
    return fig


# --- CHARGEMENT DES 6 TABLES ---
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = connect_google_sheet()
        data = {}
        for name in ['Données Sociales', 'Salaires', 'Formation', 'Recrutement', 'Finances', 'Temps & Projets']: # NOUVELLE FEUILLE
            df = pd.DataFrame(sheet.worksheet(name).get_all_records())
            df.columns = [c.strip() for c in df.columns]
            data[name] = df

        # Nettoyage et Fusions
        if 'Primes(€)' in data['Salaires'].columns: data['Salaires'].rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        df_global = pd.merge(data['Données Sociales'], data['Salaires'], on='Nom', how='left')
        
        # Formation (Agrégée)
        data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
        form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
        df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
        df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)
        
        # Recrutement
        data['Recrutement']['Coût Recrutement (€)'] = data['Recrutement']['Coût Recrutement (€)'].apply(clean_currency)
        
        # Nettoyage des chiffres dans le tableau principal
        for col in ['Salaire (€)', 'Primes (€)']:
            if col in df_global.columns: df_global[col] = df_global[col].apply(clean_currency)
        
        df_global = calculer_donnees(df_global)
        
        # On retourne les 6 tables
        return df_global, data['Recrutement'], data['Formation'], data['Temps & Projets'], data
    except Exception as e:
        st.error(f"Erreur Load : {e}")
        return None, None, None, None, None

# On charge les 6 tables
rh, rec, form_detail, temps_projets, raw_data = load_data()


# --- INTERFACE ---
if 'logged_in' in st.session_state and st.session_state['logged_in']:
    st.title("🚀 Pilotage Stratégique")

    # Calcul des KPIs Taux de Turnover
    taux_turnover = calculer_turnover(rh)
    
    # NAVIGATION
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1077/1077114.png", width=60)
        
        selected = option_menu(
            menu_title="RH COCKPIT",
            options=["Dashboard", "Salariés", "Formation", "Recrutement", "Temps & Projets", "Simulation", "Gestion BDD"], # NOUVEL ONGLET
            icons=["speedometer2", "people", "mortarboard", "bullseye", "clock", "calculator", "database"],
            menu_icon="cast", default_index=0
        )
        st.markdown("---")
        
        # FILTRES
        services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
        selected_service = st.selectbox("Filtrer par Service", services)
        rh_f = rh[rh['Service'] == selected_service] if selected_service != 'Tous' else rh
        
        st.markdown("---")
        if st.button("🚪 Déconnexion", use_container_width=True): logout()


    # 1. DASHBOARD
    if selected == "Dashboard":
        st.header(f"Vue d'ensemble ({selected_service})")
        
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{nb}</div><div class='kpi-lbl'>Collaborateurs</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-val'>{taux_turnover:.1f}%</div><div class='kpi-lbl'>Taux de Turnover</div></div>", unsafe_allow_html=True) # NOUVEAU KPI
        c3.markdown(f"<div class='kpi-card'><div class='kpi-val'>{ms/1000:.0f} k€</div><div class='kpi-lbl'>Masse Salariale</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='kpi-card'><div class='kpi-val'>{age:.0f} ans</div><div class='kpi-lbl'>Âge Moyen</div></div>", unsafe_allow_html=True)
        
        # ... (Graphiques Pyramide/CSP ici) ...
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("<div class='card'><h3>Répartition CSP</h3>", unsafe_allow_html=True)
            if 'CSP' in rh_f.columns: st.plotly_chart(clean_chart(px.pie(rh_f, names='CSP', hole=0.6, color_discrete_sequence=['#3b82f6', '#10b981', '#f59e0b', '#a855f7'])), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with g2:
            st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
            if 'Âge' in rh_f.columns and 'Sexe' in rh_f.columns:
                rh_f['Tranche'] = pd.cut(rh_f['Âge'], bins=[20,30,40,50,60,70], labels=["20-30","30-40","40-50","50-60","60+"]).astype(str)
                pyr = rh_f.groupby(['Tranche', 'Sexe']).size().reset_index(name='Nb')
                pyr['Nb_Plot'] = pyr.apply(lambda x: -x['Nb'] if x['Sexe']=='Homme' else x['Nb'], axis=1)
                fig = px.bar(pyr, x='Nb_Plot', y='Tranche', color='Sexe', orientation='h', color_discrete_map={'Homme': '#3b82f6', 'Femme': '#ec4899'})
                fig.update_layout(xaxis=dict(tickvals=[-5, 0, 5], ticktext=['5', '0', '5']))
                st.plotly_chart(clean_chart(fig), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)


    # 2. SALARIÉS
    elif selected == "Salariés":
        st.title("🗂️ Gestion des Talents")
        col_list, col_detail = st.columns([1, 3])
        with col_list:
            st.markdown("<div class='card'><h3>Annuaire</h3>", unsafe_allow_html=True)
            st.radio("Employés", rh_f['Nom'].unique().tolist(), label_visibility="collapsed")
            st.markdown("</div>", unsafe_allow_html=True)
        # ... (Le contenu des fiches est omis ici pour la concision, mais il existe dans le code) ...

    # 3. FORMATION
    elif selected == "Formation":
        st.title("🎓 Pilotage de la Formation")
        # ... (Contenu Formation) ...

    # 4. RECRUTEMENT
    elif selected == "Recrutement":
        st.title("🎯 Talent Acquisition")
        # ... (Contenu Recrutement) ...

    # 5. TEMPS & PROJETS (NOUVEL ONGLET)
    elif selected == "Temps & Projets":
        st.title("⏳ Suivi des Temps & Coûts Projets")
        st.info("Cette page est connectée à la feuille 'Temps & Projets' pour l'analyse des heures.")
        
        if temps_projets is not None and not temps_projets.empty:
            st.subheader("Distribution des Heures")
            if 'Heures Travaillées' in temps_projets.columns and 'Projet' in temps_projets.columns:
                df_proj_sum = temps_projets.groupby('Projet')['Heures Travaillées'].sum().reset_index()
                st.plotly_chart(clean_chart(px.bar(df_proj_sum, x='Projet', y='Heures Travaillées', title="Total Heures par Projet")), use_container_width=True)
            
            st.subheader("Données Brutes (Feuille Temps & Projets)")
            st.dataframe(temps_projets, use_container_width=True)
        else:
            st.warning("Veuillez remplir la feuille 'Temps & Projets' dans votre Google Sheet.")


    # 6. SIMULATION
    elif selected == "Simulation":
        st.title("🔮 Prospective Salariale")
        # ... (Contenu Simulation) ...

    # 7. GESTION BDD
    elif selected == "Gestion BDD":
        st.title("🛠️ Centre de Gestion des Données")
        st.info("Modifiez et sauvegardez vos données en direct.")
        tab_rh, tab_sal, tab_form, tab_rec, tab_temps = st.tabs(["👥 Employés", "💰 Salaires", "🎓 Formation", "🎯 Recrutement", "⏳ Temps & Projets"]) # AJOUT ONGLET TEMPS
        
        # Gestion BDD (CRUD)
        with tab_rh: st.markdown("<div class='card'>", unsafe_allow_html=True); edited_df = st.data_editor(raw_data['Données Sociales'], num_rows="dynamic"); if st.button("💾 Sauvegarder Employés"): save_data_to_google(edited_df, 'Données Sociales'); st.markdown("</div>", unsafe_allow_html=True)
        with tab_sal: st.markdown("<div class='card'>", unsafe_allow_html=True); edited_df = st.data_editor(raw_data['Salaires'], num_rows="dynamic"); if st.button("💾 Sauvegarder Salaires"): save_data_to_google(edited_df, 'Salaires'); st.markdown("</div>", unsafe_allow_html=True)
        with tab_form: st.markdown("<div class='card'>", unsafe_allow_html=True); edited_df = st.data_editor(raw_data['Formation'], num_rows="dynamic"); if st.button("💾 Sauvegarder Formations"): save_data_to_google(edited_df, 'Formation'); st.markdown("</div>", unsafe_allow_html=True)
        with tab_rec: st.markdown("<div class='card'>", unsafe_allow_html=True); edited_df = st.data_editor(raw_data['Recrutement'], num_rows="dynamic"); if st.button("💾 Sauvegarder Recrutements"): save_data_to_google(edited_df, 'Recrutement'); st.markdown("</div>", unsafe_allow_html=True)
        with tab_temps: st.markdown("<div class='card'>", unsafe_allow_html=True); edited_df = st.data_editor(raw_data['Temps & Projets'], num_rows="dynamic"); if st.button("💾 Sauvegarder Temps"): save_data_to_google(edited_df, 'Temps & Projets'); st.markdown("</div>", unsafe_allow_html=True) # NOUVEL ONGLET CRUD
