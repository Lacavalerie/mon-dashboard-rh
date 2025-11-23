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
st.set_page_config(page_title="RH Cockpit", layout="wide", initial_sidebar_state="expanded")

# --- CSS PERSONNALISÉ (DESIGN MODERNE) ---
st.markdown("""
    <style>
    /* Fond sombre élégant */
    .stApp { background-color: #0e1117; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    
    /* Cartes KPI (Glassmorphism) */
    .kpi-card {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        text-align: center;
        margin-bottom: 10px;
    }
    .kpi-value { font-size: 28px; font-weight: bold; color: #4ade80; }
    .kpi-label { font-size: 14px; color: #a0a0a0; }
    
    /* Titres */
    h1, h2, h3 { color: #f0f6fc !important; font-family: 'Segoe UI', sans-serif; }
    
    /* Alertes */
    .alert-box { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; padding: 10px; border-radius: 5px; border: 1px solid #ef4444; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES (Connexion, Login, PDF...) ---
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
        for col in df_to_save.columns:
            if pd.api.types.is_datetime64_any_dtype(df_to_save[col]):
                df_to_save[col] = df_to_save[col].dt.strftime('%d/%m/%Y')
        ws.clear()
        ws.update([df_to_save.columns.values.tolist()] + df_to_save.values.tolist())
        st.toast(f"✅ {worksheet_name} mis à jour !", icon="💾")
        time.sleep(1)
        st.cache_data.clear()
        st.rerun()
    except Exception as e: st.error(f"Erreur sauvegarde : {e}")

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
            try: pdf.cell(200, 10, txt=f"- {row['Type Formation']}", ln=True)
            except: pdf.cell(200, 10, txt="- (Erreur encodage titre)", ln=True)
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

# --- CHARGEMENT DONNÉES ---
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = connect_google_sheet()
        data = {}
        for name in ['Données Sociales', 'Salaires', 'Formation', 'Recrutement', 'Finances']:
            df = pd.DataFrame(sheet.worksheet(name).get_all_records())
            df.columns = [c.strip() for c in df.columns]
            data[name] = df

        # Corrections & Typage
        if 'Primes(€)' in data['Salaires'].columns: data['Salaires'].rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        
        # Fusion
        df_global = pd.merge(data['Données Sociales'], data['Salaires'], on='Nom', how='left')
        
        # Formation Aggrégée
        if 'Coût Formation' in data['Formation'].columns: data['Formation'].rename(columns={'Coût Formation': 'Coût Formation (€)'}, inplace=True)
        data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
        
        form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
        df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
        df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)

        # Recrutement
        data['Recrutement']['Coût Recrutement (€)'] = data['Recrutement']['Coût Recrutement (€)'].apply(clean_currency)
        
        # Nettoyage Global
        for col in ['Salaire (€)', 'Primes (€)']:
            if col in df_global.columns: df_global[col] = df_global[col].apply(clean_currency)
        
        df_global = calculer_donnees(df_global)
        return df_global, data['Recrutement'], data['Formation'], data
    except Exception as e:
        st.error(f"Erreur Load : {e}")
        return None, None, None, None

rh, rec, form_detail, raw_data = load_data()

# --- INTERFACE UTILISATEUR ---
if rh is not None:
    
    # BARRE LATÉRALE (NAVIGATION)
    with st.sidebar:
        st.title("📊 Menu")
        menu = st.radio("Navigation", ["🏠 Vue d'ensemble", "👥 Collaborateurs", "🎯 Recrutement", "🔮 Simulation", "⚙️ Administration"])
        
        st.markdown("---")
        st.header("Filtres")
        services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
        selected_service = st.selectbox("Service", services)
        
        # Filtrage Global
        rh_f = rh[rh['Service'] == selected_service] if selected_service != 'Tous' else rh

    # --- PAGE 1 : VUE D'ENSEMBLE (DASHBOARD MACRO) ---
    if menu == "🏠 Vue d'ensemble":
        st.header(f"Tableau de Bord ({selected_service})")
        
        # 1. Ligne de KPIs (Cartes CSS)
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age_moy = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        cout_form = rh_f['Coût Formation (€)'].sum()
        
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f"<div class='kpi-card'><div class='kpi-value'>{nb}</div><div class='kpi-label'>Effectif</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='kpi-card'><div class='kpi-value'>{ms/1000:.0f} k€</div><div class='kpi-label'>Masse Salariale Annuelle</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='kpi-card'><div class='kpi-value'>{age_moy:.0f} ans</div><div class='kpi-label'>Âge Moyen</div></div>", unsafe_allow_html=True)
        k4.markdown(f"<div class='kpi-card'><div class='kpi-value'>{cout_form:,.0f} €</div><div class='kpi-label'>Invest. Formation</div></div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 2. Graphiques Principaux
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Répartition par CSP")
            if 'CSP' in rh_f.columns:
                fig = px.pie(rh_f, names='CSP', hole=0.6, color_discrete_sequence=px.colors.sequential.Teal)
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig, use_container_width=True)
        with g2:
            st.subheader("Pyramide des Âges")
            if 'Âge' in rh_f.columns and 'Sexe' in rh_f.columns:
                rh_f['Tranche'] = pd.cut(rh_f['Âge'], bins=[20,30,40,50,60,70], labels=["20-30","30-40","40-50","50-60","60+"]).astype(str)
                pyr = rh_f.groupby(['Tranche', 'Sexe']).size().reset_index(name='Nb')
                pyr['Nb'] = pyr.apply(lambda x: -x['Nb'] if x['Sexe']=='Homme' else x['Nb'], axis=1)
                fig = px.bar(pyr, x='Nb', y='Tranche', color='Sexe', orientation='h', color_discrete_map={'Homme':'#3b82f6', 'Femme':'#ec4899'})
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig, use_container_width=True)

    # --- PAGE 2 : COLLABORATEURS (FICHE INDIVIDUELLE) ---
    elif menu == "👥 Collaborateurs":
        st.header("Gestion Individuelle")
        
        col_sel, col_fic = st.columns([1, 3])
        
        with col_sel:
            st.subheader("Annuaire")
            search = st.text_input("🔍 Rechercher un nom")
            liste = sorted(rh_f['Nom'].unique().tolist())
            if search: liste = [n for n in liste if search.lower() in n.lower()]
            choix = st.radio("Employés", liste, label_visibility="collapsed")
        
        with col_fic:
            if choix:
                emp = rh[rh['Nom'] == choix].iloc[0]
                
                # En-tête fiche
                c_a, c_b = st.columns([3, 1])
                with c_a: 
                    st.subheader(f"👤 {emp['Nom']}")
                    st.caption(f"{emp['Poste']} | {emp['Service']} | {emp.get('CSP', '')}")
                with c_b:
                    hist = form_detail[form_detail['Nom'] == choix] if not form_detail.empty else pd.DataFrame()
                    try:
                        pdf = create_pdf(emp, hist)
                        st.download_button("📄 PDF", data=pdf, file_name=f"{emp['Nom']}.pdf", mime="application/pdf", use_container_width=True)
                    except: st.error("Erreur PDF")
                
                # Données salariales
                st.markdown("#### Rémunération")
                sal_cols = st.columns(3)
                sal_cols[0].metric("Fixe", f"{emp.get('Salaire (€)', 0):,.0f} €")
                sal_cols[1].metric("Primes", f"{emp.get('Primes (€)', 0):,.0f} €")
                sal_cols[2].metric("Total Brut", f"{(emp.get('Salaire (€)', 0)+emp.get('Primes (€)', 0)):,.0f} €")
                
                if str(emp.get('Au SMIC', 'No')).lower() == 'oui': 
                    st.markdown('<div class="alert-box">⚠️ <b>Alerte SMIC</b> : Vérifier le minimum légal.</div>', unsafe_allow_html=True)

                # Historique Formations
                st.markdown("#### Formations Suivies")
                if not hist.empty:
                    st.dataframe(hist[['Type Formation', 'Coût Formation (€)']], hide_index=True, use_container_width=True)
                else:
                    st.info("Pas d'historique de formation.")

    # --- PAGE 3 : RECRUTEMENT ---
    elif menu == "🎯 Recrutement":
        st.header("Suivi du Recrutement")
        k1, k2 = st.columns(2)
        total_rec = rec['Coût Recrutement (€)'].sum()
        k1.metric("Budget Recrutement", f"{total_rec:,.0f} €")
        k2.metric("Postes Ouverts", len(rec))
        
        st.markdown("### Postes en cours")
        st.dataframe(rec[['Poste', 'Date Ouverture Poste', 'Canal Sourcing', 'Coût Recrutement (€)']], hide_index=True, use_container_width=True)
        
        st.markdown("### Performance des Canaux")
        if 'Canal Sourcing' in rec.columns:
            df_src = rec.groupby('Canal Sourcing').size().reset_index(name='Nb')
            fig = px.bar(df_src, x='Canal Sourcing', y='Nb', color='Canal Sourcing')
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig, use_container_width=True)

    # --- PAGE 4 : SIMULATION ---
    elif menu == "🔮 Simulation":
        st.header("Simulateur Budgétaire")
        
        c_sim1, c_sim2 = st.columns([1, 2])
        with c_sim1:
            st.info("Simulez une augmentation générale.")
            augm = st.slider("Hausse (%)", 0.0, 20.0, 2.0, 0.5)
            
            ms_actuelle = rh_f['Salaire (€)'].sum() * 12 * 1.45
            impact = ms_actuelle * (augm/100)
            
            st.metric("Impact Financier (Annuel)", f"{impact:,.0f} €", delta="Coût Supplémentaire", delta_color="inverse")
            st.metric("Nouveau Budget", f"{(ms_actuelle + impact):,.0f} €")
            
        with c_sim2:
            fig = go.Figure(go.Waterfall(
                measure=["relative", "relative", "total"],
                x=["Budget Actuel", "Hausse", "Budget Projeté"],
                y=[ms_actuelle, impact, ms_actuelle+impact],
                decreasing={"marker":{"color":"#fb923c"}}, increasing={"marker":{"color":"#ef4444"}}, totals={"marker":{"color":"#3b82f6"}}
            ))
            fig.update_layout(title="Projection des Coûts", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig, use_container_width=True)

    # --- PAGE 5 : ADMINISTRATION (CRUD) ---
    elif menu == "⚙️ Administration":
        st.header("🛠️ Centre de Gestion des Données")
        st.warning("⚠️ Les modifications ici sont directement enregistrées dans Google Sheets.")
        
        tab_edit1, tab_edit2, tab_edit3 = st.tabs(["👥 Employés", "💰 Salaires", "🎯 Recrutement"])
        
        with tab_edit1:
            st.subheader("Éditer les Employés")
            edited_rh = st.data_editor(raw_data['Données Sociales'], num_rows="dynamic", use_container_width=True)
            if st.button("Sauvegarder Employés"): save_data_to_google(edited_rh, 'Données Sociales')
            
        with tab_edit2:
            st.subheader("Éditer les Salaires")
            edited_sal = st.data_editor(raw_data['Salaires'], num_rows="dynamic", use_container_width=True)
            if st.button("Sauvegarder Salaires"): save_data_to_google(edited_sal, 'Salaires')
            
        with tab_edit3:
            st.subheader("Éditer les Recrutements")
            edited_rec = st.data_editor(raw_data['Recrutement'], num_rows="dynamic", use_container_width=True)
            if st.button("Sauvegarder Recrutement"): save_data_to_google(edited_rec, 'Recrutement')
