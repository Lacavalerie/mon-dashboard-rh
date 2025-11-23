import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import time

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="RH Cockpit Pro", layout="wide", initial_sidebar_state="expanded")

# --- DESIGN "LOGICIEL PRO" (Inspiré image 3) ---
st.markdown("""
    <style>
    /* Fond général gris clair pro */
    .stApp { background-color: #F0F2F6; }
    
    /* Sidebar bleu corporate */
    [data-testid="stSidebar"] { background-color: #2C3E50; }
    [data-testid="stSidebar"] * { color: white !important; }
    
    /* Blocs (Cards) avec ombre et fond blanc */
    .css-1r6slb0, .stDataFrame, .stPlotlyChart {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    
    /* KPIs style "Tuiles" */
    .kpi-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #3498DB; /* Bleu pro */
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-align: center;
    }
    .kpi-value { font-size: 24px; font-weight: bold; color: #2C3E50; }
    .kpi-label { font-size: 12px; color: #7F8C8D; text-transform: uppercase; }
    
    /* Titres */
    h1, h2, h3 { color: #2C3E50 !important; font-family: 'Arial', sans-serif; }
    
    /* Header personnalisé */
    .header-bar {
        background-color: #34495E;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
        color: white;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def connect_google_sheet():
    try:
        secrets = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(secrets, scopes=scope)
        client = gspread.authorize(creds)
        return client.open("Dashboard_Data") 
    except Exception as e:
        st.error(f"⚠️ Erreur Google : {e}")
        st.stop()

def save_data_to_google(df, worksheet_name):
    try:
        sheet = connect_google_sheet()
        ws = sheet.worksheet(worksheet_name)
        df_to_save = df.copy()
        # Conversion dates pour JSON
        for col in df_to_save.columns:
            if pd.api.types.is_datetime64_any_dtype(df_to_save[col]):
                df_to_save[col] = df_to_save[col].dt.strftime('%d/%m/%Y')
        ws.clear()
        ws.update([df_to_save.columns.values.tolist()] + df_to_save.values.tolist())
        st.toast(f"✅ {worksheet_name} sauvegardé !", icon="💾")
        time.sleep(1)
        st.cache_data.clear()
        st.rerun()
    except Exception as e: st.error(f"Erreur sauvegarde : {e}")

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
def check_login():
    if st.session_state['u'] == "admin" and st.session_state['p'] == "rh123": st.session_state['logged_in'] = True
    else: st.error("Erreur")
def logout(): st.session_state['logged_in'] = False; st.rerun()

if not st.session_state['logged_in']:
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        st.title("🔒 Connexion")
        st.text_input("ID", key="u")
        st.text_input("MDP", type="password", key="p")
        st.button("Entrer", on_click=check_login)
    st.stop()

# --- FONCTIONS MÉTIER ---
def create_pdf(emp, form_hist):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"FICHE : {emp['Nom']}", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Poste : {emp['Poste']} ({emp.get('CSP', 'N/A')})", ln=True)
    pdf.cell(200, 10, txt=f"Service : {emp['Service']}", ln=True)
    pdf.ln(5)
    pdf.cell(200, 10, txt=f"Salaire Base : {emp.get('Salaire (€)', 0):.0f} EUR", ln=True)
    pdf.ln(5)
    pdf.cell(200, 10, txt="FORMATIONS :", ln=True)
    if not form_hist.empty:
        for i, row in form_hist.iterrows():
            try: pdf.cell(200, 10, txt=f"- {row['Type Formation']} ({row['Coût Formation (€)']} EUR)", ln=True)
            except: pdf.cell(200, 10, txt="- (Erreur encodage)", ln=True)
    else:
        pdf.cell(200, 10, txt="Aucune.", ln=True)
    return pdf.output(dest='S').encode('latin-1')

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

# --- CHARGEMENT ---
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = connect_google_sheet()
        data = {}
        for name in ['Données Sociales', 'Salaires', 'Formation', 'Recrutement', 'Finances']:
            df = pd.DataFrame(sheet.worksheet(name).get_all_records())
            df.columns = [c.strip() for c in df.columns]
            data[name] = df

        # Corrections
        if 'Primes(€)' in data['Salaires'].columns: data['Salaires'].rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        if 'Cout Formation (€)' in data['Formation'].columns: data['Formation'].rename(columns={'Cout Formation (€)': 'Coût Formation (€)'}, inplace=True)
        if 'Coût Formation' in data['Formation'].columns: data['Formation'].rename(columns={'Coût Formation': 'Coût Formation (€)'}, inplace=True)

        # Fusion
        df_global = pd.merge(data['Données Sociales'], data['Salaires'], on='Nom', how='left')
        
        # Formation (Agrégée)
        data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
        form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
        df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
        df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)

        # Recrutement
        data['Recrutement']['Coût Recrutement (€)'] = data['Recrutement']['Coût Recrutement (€)'].apply(clean_currency)
        
        # Nettoyage
        for col in ['Salaire (€)', 'Primes (€)']:
            if col in df_global.columns: df_global[col] = df_global[col].apply(clean_currency)
        
        df_global = calculer_donnees(df_global)
        return df_global, data['Recrutement'], data['Formation'], data
    except Exception as e:
        st.error(f"Erreur Load : {e}")
        return None, None, None, None

rh, rec, form_detail, raw_data = load_data()

# --- INTERFACE ---
if rh is not None:
    
    with st.sidebar:
        st.markdown("### 🧭 NAVIGATION")
        menu = st.radio("", ["Vue d'ensemble", "Fiches Salariés", "Recrutement", "Simulation", "Administration"], label_visibility="collapsed")
        
        st.markdown("---")
        st.markdown("### 🔽 FILTRES")
        services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
        selected_service = st.selectbox("Service", services)
        
        rh_f = rh[rh['Service'] == selected_service] if selected_service != 'Tous' else rh

    # --- 1. DASHBOARD (VUE D'ENSEMBLE) ---
    if menu == "Vue d'ensemble":
        st.markdown("<div class='header-bar'>VUE D'ENSEMBLE RH</div>", unsafe_allow_html=True)
        
        # KPIs
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        cout_form = rh_f['Coût Formation (€)'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='kpi-card'><div class='kpi-value'>{nb}</div><div class='kpi-label'>Effectif</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-value'>{ms/1000:.0f} k€</div><div class='kpi-label'>Masse Salariale</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card'><div class='kpi-value'>{age:.0f} ans</div><div class='kpi-label'>Âge Moyen</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='kpi-card'><div class='kpi-value'>{cout_form:,.0f} €</div><div class='kpi-label'>Formation</div></div>", unsafe_allow_html=True)
        
        # Graphs
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Répartition CSP")
            if 'CSP' in rh_f.columns:
                fig = px.pie(rh_f, names='CSP', hole=0.6, color_discrete_sequence=px.colors.sequential.Blues)
                st.plotly_chart(fig, use_container_width=True)
        with g2:
            st.subheader("Pyramide des Âges")
            if 'Âge' in rh_f.columns:
                rh_f['Tranche'] = pd.cut(rh_f['Âge'], bins=[20,30,40,50,60,70], labels=["20-30","30-40","40-50","50-60","60+"]).astype(str)
                fig = px.bar(rh_f.groupby(['Tranche', 'Sexe']).size().reset_index(name='Nb'), x='Nb', y='Tranche', color='Sexe', orientation='h')
                st.plotly_chart(fig, use_container_width=True)

    # --- 2. FICHES SALARIÉS ---
    elif menu == "Fiches Salariés":
        st.markdown("<div class='header-bar'>DOSSIERS INDIVIDUELS</div>", unsafe_allow_html=True)
        
        col_list, col_detail = st.columns([1, 3])
        with col_list:
            st.subheader("Annuaire")
            search = st.text_input("🔍 Chercher", placeholder="Nom...")
            liste = sorted(rh_f['Nom'].unique().tolist())
            if search: liste = [n for n in liste if search.lower() in n.lower()]
            choix = st.radio("Nom", liste, label_visibility="collapsed")

        with col_detail:
            if choix:
                emp = rh[rh['Nom'] == choix].iloc[0]
                
                # Header Fiche
                c_titre, c_pdf = st.columns([3, 1])
                c_titre.subheader(f"👤 {emp['Nom']}")
                
                # Historique spécifique à l'employé
                hist = form_detail[form_detail['Nom'] == choix] if not form_detail.empty else pd.DataFrame()
                
                try:
                    pdf = create_pdf(emp, hist)
                    c_pdf.download_button("📥 PDF", data=pdf, file_name=f"{emp['Nom']}.pdf", mime="application/pdf")
                except: c_pdf.error("Erreur PDF")

                # Infos
                i1, i2, i3 = st.columns(3)
                i1.info(f"**Poste :** {emp['Poste']}")
                i2.info(f"**Service :** {emp['Service']}")
                i3.info(f"**Contrat :** {emp.get('CSP', 'N/A')}")

                st.markdown("#### 💰 Rémunération")
                s1, s2, s3 = st.columns(3)
                s1.metric("Salaire Base", f"{emp.get('Salaire (€)', 0):,.0f} €")
                s2.metric("Primes", f"{emp.get('Primes (€)', 0):,.0f} €")
                s3.metric("Total Brut", f"{(emp.get('Salaire (€)', 0)+emp.get('Primes (€)', 0)):,.0f} €")

                st.markdown("#### 🎓 Formations")
                if not hist.empty:
                    st.dataframe(hist[['Type Formation', 'Coût Formation (€)']], hide_index=True, use_container_width=True)
                else:
                    st.info("Aucune formation enregistrée.")

    # --- 3. RECRUTEMENT ---
    elif menu == "Recrutement":
        st.markdown("<div class='header-bar'>SUIVI RECRUTEMENT</div>", unsafe_allow_html=True)
        k1, k2 = st.columns(2)
        k1.metric("Budget Engagé", f"{rec['Coût Recrutement (€)'].sum():,.0f} €")
        k2.metric("Postes", len(rec))
        st.dataframe(rec, use_container_width=True)

    # --- 4. SIMULATION ---
    elif menu == "Simulation":
        st.markdown("<div class='header-bar'>SIMULATEUR BUDGÉTAIRE</div>", unsafe_allow_html=True)
        augm = st.slider("Hausse Générale (%)", 0.0, 10.0, 2.0, 0.1)
        ms_actuelle = rh_f['Salaire (€)'].sum() * 12 * 1.45
        impact = ms_actuelle * (augm/100)
        st.metric("Impact Financier", f"+ {impact:,.0f} €", delta="Coût Annuel", delta_color="inverse")

    # --- 5. ADMINISTRATION (UPLOAD & CRUD) ---
    elif menu == "Administration":
        st.markdown("<div class='header-bar'>CENTRE DE GESTION</div>", unsafe_allow_html=True)
        
        # UPLOAD EXCEL (NOUVEAU)
        with st.expander("📤 Importer des données depuis Excel (Upload)"):
            uploaded_file = st.file_uploader("Choisir un fichier Excel", type=['xlsx'])
            if uploaded_file is not None:
                try:
                    # On lit l'Excel uploadé
                    new_data = pd.read_excel(uploaded_file)
                    st.write("Aperçu :", new_data.head())
                    table_cible = st.selectbox("Dans quel onglet envoyer ?", ["Données Sociales", "Salaires", "Formation", "Recrutement"])
                    
                    if st.button("Valider l'import"):
                        save_data_to_google(new_data, table_cible)
                except Exception as e:
                    st.error(f"Erreur lecture fichier : {e}")

        st.markdown("---")
        
        # EDIT DATA
        st.subheader("Édition Manuelle")
        choix_table = st.selectbox("Table", ["Données Sociales", "Salaires", "Formation", "Recrutement"])
        
        # Sélection du bon dataframe
        if choix_table == "Données Sociales": df_edit = raw_data['Données Sociales']
        elif choix_table == "Salaires": df_edit = raw_data['Salaires']
        elif choix_table == "Formation": df_edit = raw_data['Formation']
        elif choix_table == "Recrutement": df_edit = raw_data['Recrutement']
        
        edited = st.data_editor(df_edit, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 Sauvegarder les modifications"):
            save_data_to_google(edited, choix_table)
