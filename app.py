import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import time
from streamlit_option_menu import option_menu # LE NOUVEAU MENU STYLE WORKDAY

# Configuration
st.set_page_config(page_title="RH Cockpit V63", layout="wide", initial_sidebar_state="expanded")

# --- DESIGN STYLE "WORKDAY DARK" ---
st.markdown("""
    <style>
    /* Fond général */
    .stApp { background-color: #0e1117; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #161b22; }
    
    /* Cartes (Tuiles Workday) */
    .workday-card {
        background-color: #1f2937;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #374151;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
        transition: transform 0.2s;
    }
    .workday-card:hover {
        transform: translateY(-5px);
        border-color: #3b82f6;
    }
    .card-value { font-size: 28px; font-weight: bold; color: #ffffff; }
    .card-label { font-size: 14px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }
    
    /* Titres */
    h1, h2, h3 { color: #ffffff !important; font-family: 'Segoe UI', sans-serif; }
    
    /* Enlever les marges du haut */
    .block-container { padding-top: 2rem; }
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

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
def check_login():
    if st.session_state['u'] == "admin" and st.session_state['p'] == "rh123": st.session_state['logged_in'] = True
    else: st.error("Erreur")
def logout(): st.session_state['logged_in'] = False; st.rerun()

if not st.session_state['logged_in']:
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        st.title("🔒 Connexion RH")
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

def clean_chart(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), xaxis=dict(showgrid=False, color="white"), yaxis=dict(showgrid=True, gridcolor="#444444", color="white"))
    return fig

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
        
        # Formation (Agrégée pour global)
        data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
        form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
        df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
        df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)
        
        # Detail formation avec Service (Fusion)
        form_detail_enrichi = pd.merge(data['Formation'], data['Données Sociales'][['Nom', 'Service', 'CSP']], on='Nom', how='left')

        # Recrutement
        data['Recrutement']['Coût Recrutement (€)'] = data['Recrutement']['Coût Recrutement (€)'].apply(clean_currency)
        
        # Nettoyage
        for col in ['Salaire (€)', 'Primes (€)']:
            if col in df_global.columns: df_global[col] = df_global[col].apply(clean_currency)
        
        df_global = calculer_donnees(df_global)
        return df_global, data['Recrutement'], form_detail_enrichi, data
    except Exception as e:
        st.error(f"Erreur Load : {e}")
        return None, None, None, None

rh, rec, form_detail, raw_data = load_data()

# --- INTERFACE ---
if rh is not None:
    
    # NAVIGATION STYLE WORKDAY
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50) # Placeholder Logo
        st.markdown("### **HR COCKPIT**")
        
        selected = option_menu(
            menu_title=None,
            options=["Dashboard", "Salariés", "Formation", "Recrutement", "Simulation", "Admin"],
            icons=["speedometer2", "people", "mortarboard", "bullseye", "calculator", "gear"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "#161b22"},
                "icon": {"color": "orange", "font-size": "18px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#2d3e55"},
                "nav-link-selected": {"background-color": "#3b82f6"},
            }
        )
        
        st.markdown("---")
        services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
        selected_service = st.selectbox("Filtrer par Service", services)
        rh_f = rh[rh['Service'] == selected_service] if selected_service != 'Tous' else rh
        
        # Filtrer formation aussi
        form_f = form_detail[form_detail['Service'] == selected_service] if selected_service != 'Tous' else form_detail

    # --- 1. DASHBOARD ---
    if selected == "Dashboard":
        st.title(f"Vue d'ensemble ({selected_service})")
        
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        cout_form = rh_f['Coût Formation (€)'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='workday-card'><div class='card-value'>{nb}</div><div class='card-label'>Collaborateurs</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='workday-card'><div class='card-value'>{ms/1000:.0f} k€</div><div class='card-label'>Masse Salariale</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='workday-card'><div class='card-value'>{age:.0f} ans</div><div class='card-label'>Âge Moyen</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='workday-card'><div class='card-value'>{cout_form:,.0f} €</div><div class='card-label'>Budget Formation</div></div>", unsafe_allow_html=True)
        
        st.markdown("### 📊 Indicateurs Clés")
        g1, g2 = st.columns(2)
        with g1:
            if 'CSP' in rh_f.columns:
                st.plotly_chart(clean_chart(px.pie(rh_f, names='CSP', hole=0.6, title="Répartition CSP", color_discrete_sequence=px.colors.sequential.Blues)), use_container_width=True)
        with g2:
            if 'Âge' in rh_f.columns:
                st.plotly_chart(clean_chart(px.histogram(rh_f, x='Âge', nbins=10, title="Pyramide des Âges", color_discrete_sequence=['#3b82f6'])), use_container_width=True)

    # --- 2. SALARIÉS ---
    elif selected == "Salariés":
        st.title("🗂️ Gestion des Talents")
        
        col_list, col_detail = st.columns([1, 3])
        with col_list:
            st.markdown("##### 🔍 Annuaire")
            search = st.text_input("Rechercher", placeholder="Nom...")
            liste = sorted(rh_f['Nom'].unique().tolist())
            if search: liste = [n for n in liste if search.lower() in n.lower()]
            choix = st.radio("Employés", liste, label_visibility="collapsed")

        with col_detail:
            if choix:
                emp = rh[rh['Nom'] == choix].iloc[0]
                
                # Entête Fiche
                with st.container():
                    c_img, c_info, c_btn = st.columns([1, 3, 1])
                    c_img.markdown("### 👤")
                    c_info.markdown(f"## {emp['Nom']}")
                    c_info.caption(f"{emp['Poste']} • {emp['Service']}")
                    
                    hist = form_detail[form_detail['Nom'] == choix] if not form_detail.empty else pd.DataFrame()
                    try: c_btn.download_button("📄 Export PDF", data=create_pdf(emp, hist), file_name=f"{emp['Nom']}.pdf", mime="application/pdf")
                    except: pass
                
                st.markdown("---")
                
                # Blocs Infos
                k1, k2, k3 = st.columns(3)
                k1.markdown(f"<div class='workday-card'><div class='card-value'>{emp.get('Salaire (€)', 0):,.0f} €</div><div class='card-label'>Salaire Fixe</div></div>", unsafe_allow_html=True)
                k2.markdown(f"<div class='workday-card'><div class='card-value'>{emp.get('Primes (€)', 0):,.0f} €</div><div class='card-label'>Primes</div></div>", unsafe_allow_html=True)
                k3.markdown(f"<div class='workday-card'><div class='card-value'>{emp.get('Ancienneté (ans)', 0):.1f} ans</div><div class='card-label'>Ancienneté</div></div>", unsafe_allow_html=True)
                
                st.markdown("### 📜 Parcours de Formation")
                if not hist.empty:
                    st.dataframe(hist[['Type Formation', 'Coût Formation (€)']], hide_index=True, use_container_width=True)
                else:
                    st.info("Aucune formation sur la période.")

    # --- 3. FORMATION (NOUVEAU & COMPLET) ---
    elif selected == "Formation":
        st.title("🎓 Pilotage de la Formation")
        
        # Sous-menu (Tabs)
        tab_global, tab_detail = st.tabs(["🌍 Vue Globale", "🔎 Suivi Individuel"])
        
        with tab_global:
            # KPIs Formation
            budget_total = form_f['Coût Formation (€)'].sum()
            nb_actions = len(form_f)
            nb_salaries_formes = form_f['Nom'].nunique()
            
            fk1, fk2, fk3 = st.columns(3)
            fk1.markdown(f"<div class='workday-card'><div class='card-value'>{budget_total:,.0f} €</div><div class='card-label'>Budget Consommé</div></div>", unsafe_allow_html=True)
            fk2.markdown(f"<div class='workday-card'><div class='card-value'>{nb_actions}</div><div class='card-label'>Actions de formation</div></div>", unsafe_allow_html=True)
            fk3.markdown(f"<div class='workday-card'><div class='card-value'>{nb_salaries_formes}</div><div class='card-label'>Salariés Formés</div></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            fg1, fg2 = st.columns(2)
            with fg1:
                st.subheader("Budget par Thème")
                if 'Type Formation' in form_f.columns:
                    st.plotly_chart(clean_chart(px.pie(form_f, names='Type Formation', values='Coût Formation (€)', hole=0.5)), use_container_width=True)
            with fg2:
                st.subheader("Budget par CSP")
                if 'CSP' in form_f.columns:
                    st.plotly_chart(clean_chart(px.bar(form_f.groupby('CSP')['Coût Formation (€)'].sum().reset_index(), x='CSP', y='Coût Formation (€)')), use_container_width=True)

        with tab_detail:
            st.subheader("Historique Complet")
            st.dataframe(form_f, use_container_width=True)

    # --- 4. RECRUTEMENT ---
    elif selected == "Recrutement":
        st.title("🎯 Talent Acquisition")
        k1, k2 = st.columns(2)
        total_rec = rec['Coût Recrutement (€)'].sum()
        k1.markdown(f"<div class='workday-card'><div class='card-value'>{total_rec:,.0f} €</div><div class='card-label'>Investissement Recrutement</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='workday-card'><div class='card-value'>{len(rec)}</div><div class='card-label'>Postes Ouverts</div></div>", unsafe_allow_html=True)
        
        st.markdown("### Pipeline")
        st.dataframe(rec, use_container_width=True)

    # --- 5. SIMULATION ---
    elif selected == "Simulation":
        st.title("🔮 Prospective Salariale")
        augm = st.slider("Hypothèse d'augmentation (%)", 0.0, 10.0, 2.0, 0.1)
        ms_actuelle = rh_f['Salaire (€)'].sum() * 12 * 1.45
        impact = ms_actuelle * (augm/100)
        st.metric("Impact Financier", f"+ {impact:,.0f} €", delta="Surcoût", delta_color="inverse")
        st.plotly_chart(clean_chart(go.Figure(go.Waterfall(measure=["relative", "relative", "total"], x=["Actuel", "Impact", "Futur"], y=[ms_actuelle, impact, ms_actuelle+impact]))), use_container_width=True)

    # --- 6. ADMIN ---
    elif selected == "Admin":
        st.title("⚙️ Administration des Données")
        
        with st.expander("📤 Importer un fichier Excel (Mass update)"):
            up = st.file_uploader("Fichier .xlsx", type=['xlsx'])
            if up:
                df_up = pd.read_excel(up)
                st.write(df_up.head())
                table = st.selectbox("Cible", ["Données Sociales", "Salaires", "Formation"])
                if st.button("Envoyer"): save_data_to_google(df_up, table)

        st.markdown("---")
        choix_table = st.selectbox("Éditer en direct :", ["Données Sociales", "Salaires", "Formation", "Recrutement"])
        
        if choix_table == "Données Sociales": df = raw_data['Données Sociales']
        elif choix_table == "Salaires": df = raw_data['Salaires']
        elif choix_table == "Formation": df = raw_data['Formation']
        elif choix_table == "Recrutement": df = raw_data['Recrutement']
        
        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 Sauvegarder les modifications"): save_data_to_google(edited, choix_table)
