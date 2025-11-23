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
st.set_page_config(page_title="RH Cockpit Pro", layout="wide", initial_sidebar_state="expanded")

# --- DESIGN "CARTES PRO" (Délimitation visuelle) ---
st.markdown("""
    <style>
    /* Fond général */
    .stApp { background-color: #0f172a; } /* Bleu nuit très sombre */
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #1e293b; border-right: 1px solid #334155; }
    
    /* STYLE DES CARTES (Conteneurs délimités) */
    .card {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #334155; /* Bordure légère */
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        margin-bottom: 20px;
    }
    
    /* Titres dans les cartes */
    .card h3 {
        color: #38bdf8 !important; /* Bleu clair */
        font-size: 18px;
        margin-bottom: 15px;
        border-bottom: 1px solid #334155;
        padding-bottom: 10px;
    }
    
    /* KPIs */
    .kpi-val { font-size: 26px; font-weight: bold; color: white; }
    .kpi-lbl { font-size: 13px; color: #94a3b8; text-transform: uppercase; }

    /* Alertes */
    .alert-box { background-color: #450a0a; color: #fca5a5; padding: 10px; border-radius: 5px; border: 1px solid #ef4444; }
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
        # Conversion dates
        for col in df_to_save.columns:
            if pd.api.types.is_datetime64_any_dtype(df_to_save[col]):
                df_to_save[col] = df_to_save[col].dt.strftime('%d/%m/%Y')
        ws.clear()
        ws.update([df_to_save.columns.values.tolist()] + df_to_save.values.tolist())
        st.toast(f"✅ Données sauvegardées dans {worksheet_name} !", icon="💾")
        time.sleep(1)
        st.cache_data.clear()
        st.rerun()
    except Exception as e: st.error(f"Erreur sauvegarde : {e}")

# Login
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

def clean_chart(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        font=dict(color="white"),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(showgrid=False, color="white"),
        yaxis=dict(showgrid=True, gridcolor="#334155", color="white")
    )
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
        
        # Formation
        data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
        form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
        df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
        df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)
        
        # Detail
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
    
    # NAVIGATION PRO
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50)
        
        selected = option_menu(
            menu_title="RH COCKPIT",
            options=["Dashboard", "Salariés", "Formation", "Recrutement", "Simulation", "Gestion BDD"],
            icons=["speedometer2", "people", "mortarboard", "bullseye", "calculator", "database"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "#161b22"},
                "icon": {"color": "#38bdf8", "font-size": "16px"}, 
                "nav-link": {"font-size": "14px", "text-align": "left", "margin":"0px", "--hover-color": "#2d3e55"},
                "nav-link-selected": {"background-color": "#3b82f6"},
            }
        )
        
        st.markdown("---")
        services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
        selected_service = st.selectbox("Filtrer par Service", services)
        rh_f = rh[rh['Service'] == selected_service] if selected_service != 'Tous' else rh
        form_f = form_detail[form_detail['Service'] == selected_service] if selected_service != 'Tous' else form_detail

    # --- 1. DASHBOARD ---
    if selected == "Dashboard":
        st.title(f"Vue d'ensemble ({selected_service})")
        
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        cout_form = rh_f['Coût Formation (€)'].sum()
        
        # 4 Cartes KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{nb}</div><div class='kpi-lbl'>Collaborateurs</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{ms/1000:.0f} k€</div><div class='kpi-lbl'>Masse Salariale</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><div class='kpi-val'>{age:.0f} ans</div><div class='kpi-lbl'>Âge Moyen</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='card'><div class='kpi-val'>{cout_form:,.0f} €</div><div class='kpi-lbl'>Budget Formation</div></div>", unsafe_allow_html=True)
        
        # Graphiques dans des cartes
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("<div class='card'><h3>Répartition CSP</h3>", unsafe_allow_html=True)
            if 'CSP' in rh_f.columns:
                st.plotly_chart(clean_chart(px.pie(rh_f, names='CSP', hole=0.6, color_discrete_sequence=px.colors.sequential.Blues)), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with g2:
            st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
            if 'Âge' in rh_f.columns:
                st.plotly_chart(clean_chart(px.histogram(rh_f, x='Âge', nbins=10, color_discrete_sequence=['#3b82f6'])), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # --- 2. SALARIÉS (Design Fiche Amélioré) ---
    elif selected == "Salariés":
        st.title("🗂️ Gestion des Talents")
        
        col_list, col_detail = st.columns([1, 3])
        with col_list:
            st.markdown("<div class='card'><h3>Annuaire</h3>", unsafe_allow_html=True)
            search = st.text_input("Rechercher", placeholder="Nom...")
            liste = sorted(rh_f['Nom'].unique().tolist())
            if search: liste = [n for n in liste if search.lower() in n.lower()]
            choix = st.radio("Employés", liste, label_visibility="collapsed")
            st.markdown("</div>", unsafe_allow_html=True)

        with col_detail:
            if choix:
                emp = rh[rh['Nom'] == choix].iloc[0]
                
                # En-tête
                st.markdown(f"""
                <div class='card' style='border-left: 5px solid #38bdf8;'>
                    <h2 style='margin:0; color:white !important;'>{emp['Nom']}</h2>
                    <p style='color:#94a3b8;'>{emp['Poste']} • {emp['Service']} • {emp.get('CSP', '')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Bouton PDF
                hist = form_detail[form_detail['Nom'] == choix] if not form_detail.empty else pd.DataFrame()
                try: st.download_button("📄 Télécharger le Dossier PDF", data=create_pdf(emp, hist), file_name=f"{emp['Nom']}.pdf", mime="application/pdf")
                except: pass
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("<div class='card'><h3>💰 Rémunération</h3>", unsafe_allow_html=True)
                    st.metric("Salaire Fixe", f"{emp.get('Salaire (€)', 0):,.0f} €")
                    st.metric("Primes", f"{emp.get('Primes (€)', 0):,.0f} €")
                    st.metric("Total Brut", f"{(emp.get('Salaire (€)', 0)+emp.get('Primes (€)', 0)):,.0f} €")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                with c2:
                    st.markdown("<div class='card'><h3>🎓 Parcours Formation</h3>", unsafe_allow_html=True)
                    if not hist.empty:
                        st.dataframe(hist[['Type Formation', 'Coût Formation (€)']], hide_index=True, use_container_width=True)
                    else:
                        st.info("Aucune formation.")
                    st.markdown("</div>", unsafe_allow_html=True)

    # --- 3. FORMATION ---
    elif selected == "Formation":
        st.title("🎓 Pilotage de la Formation")
        
        # KPIs
        budget_total = form_f['Coût Formation (€)'].sum()
        nb_actions = len(form_f)
        
        c1, c2 = st.columns(2)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{budget_total:,.0f} €</div><div class='kpi-lbl'>Budget Consommé</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{nb_actions}</div><div class='kpi-lbl'>Actions réalisées</div></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='card'><h3>Détail des actions</h3>", unsafe_allow_html=True)
        st.dataframe(form_f, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- 4. RECRUTEMENT ---
    elif selected == "Recrutement":
        st.title("🎯 Talent Acquisition")
        
        total_rec = rec['Coût Recrutement (€)'].sum()
        
        c1, c2 = st.columns(2)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{total_rec:,.0f} €</div><div class='kpi-lbl'>Investissement</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{len(rec)}</div><div class='kpi-lbl'>Postes Ouverts</div></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='card'><h3>Pipeline de Recrutement</h3>", unsafe_allow_html=True)
        st.dataframe(rec, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- 5. SIMULATION ---
    elif selected == "Simulation":
        st.title("🔮 Prospective Salariale")
        st.markdown("<div class='card'><h3>Paramètres</h3>", unsafe_allow_html=True)
        augm = st.slider("Hypothèse d'augmentation (%)", 0.0, 10.0, 2.0, 0.1)
        st.markdown("</div>", unsafe_allow_html=True)
        
        ms_actuelle = rh_f['Salaire (€)'].sum() * 12 * 1.45
        impact = ms_actuelle * (augm/100)
        
        st.metric("Impact Financier", f"+ {impact:,.0f} €", delta="Coût Annuel", delta_color="inverse")
        st.plotly_chart(clean_chart(go.Figure(go.Waterfall(measure=["relative", "relative", "total"], x=["Actuel", "Impact", "Futur"], y=[ms_actuelle, impact, ms_actuelle+impact]))), use_container_width=True)

    # --- 6. ADMINISTRATION (LE COCKPIT D'ÉDITION) ---
    elif selected == "Gestion BDD":
        st.title("🛠️ Centre de Gestion des Données")
        st.info("Ici, vous pouvez modifier directement toutes les données. Les changements sont sauvegardés dans Google Sheets.")
        
        tab_rh, tab_sal, tab_form, tab_rec = st.tabs(["👥 Employés", "💰 Salaires", "🎓 Formation", "🎯 Recrutement"])
        
        with tab_rh:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_rh = st.data_editor(raw_data['Données Sociales'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Employés"): save_data_to_google(edited_rh, 'Données Sociales')
            st.markdown("</div>", unsafe_allow_html=True)
            
        with tab_sal:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_sal = st.data_editor(raw_data['Salaires'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Salaires"): save_data_to_google(edited_sal, 'Salaires')
            st.markdown("</div>", unsafe_allow_html=True)
            
        with tab_form:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_form = st.data_editor(raw_data['Formation'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Formations"): save_data_to_google(edited_form, 'Formation')
            st.markdown("</div>", unsafe_allow_html=True)
            
        with tab_rec:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_rec = st.data_editor(raw_data['Recrutement'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Recrutements"): save_data_to_google(edited_rec, 'Recrutement')
            st.markdown("</div>", unsafe_allow_html=True)
