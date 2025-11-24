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
st.set_page_config(page_title="RH Cockpit Pro V71", layout="wide", initial_sidebar_state="expanded")

# --- DESIGN (Final Épuré) ---
st.markdown("""
    <style>
    /* Fond très sombre pour le contraste pro */
    .stApp { background-color: #0e1117; }
    /* Sidebar sombre */
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    h1, h2, h3, p, div, label, span, li { color: #FFFFFF !important; }
    
    /* STYLE DES CARTES (Éléments délimités) */
    .card {
        background-color: #1f2937;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #374151; 
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        margin-bottom: 25px;
    }
    .kpi-val { font-size: 32px; font-weight: 800; color: #f9fafb; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;}
    .alert-box { background-color: rgba(127, 29, 29, 0.5); color: #fca5a5 !important; padding: 15px; border-radius: 8px; border: 1px solid #ef4444; }
    [data-testid="stDataFrame"] { background-color: transparent !important; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS UTILES ---
def calculer_turnover(df):
    """Calcule le taux de turnover (Départs / Effectif total) * 100"""
    if 'Statut' in df.columns:
        departures = (df['Statut'] == 'Sorti').sum()
        active_staff = (df['Statut'] == 'Actif').sum()
        total = departures + active_staff
        return (departures / total) * 100 if total > 0 else 0.0
    return 0.0

def connect_google_sheet():
    try:
        secrets = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(secrets, scopes=scope)
        client = gspread.authorize(creds)
        # On utilise le nom du sheet du client connecté
        return client.open(st.session_state.get('current_sheet', "Dashboard_Data")) 
    except Exception as e:
        st.error(f"⚠️ Erreur Google : {e}")
        st.stop()

def save_data_to_google(df, worksheet_name):
    try:
        sheet = connect_google_sheet()
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

# ... (Autres fonctions métier et chart) ...

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

# --- GESTION LOGIN (Ajout BDD Clients) ---
CLIENTS_DB = {
    "admin": {"password": "rh123", "sheet_name": "Dashboard_Data", "company_name": "H&C CONSEIL"},
    "client_a": {"password": "passwordA", "sheet_name": "Dashboard_Client_A", "company_name": "Client A - RH"},
}

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'current_sheet' not in st.session_state: st.session_state['current_sheet'] = ""
if 'company_name' not in st.session_state: st.session_state['company_name'] = ""

def check_login():
    u = st.session_state['u']; p = st.session_state['p']
    if u in CLIENTS_DB and CLIENTS_DB[u]['password'] == p:
        st.session_state['logged_in'] = True
        st.session_state['current_user'] = u
        st.session_state['current_sheet'] = CLIENTS_DB[u]['sheet_name']
        st.session_state['company_name'] = CLIENTS_DB[u]['company_name']
    else: st.error("Identifiant ou mot de passe incorrect")

def logout(): st.session_state['logged_in'] = False; st.cache_data.clear(); st.rerun()

if not st.session_state['logged_in']:
    st.markdown("<div style='text-align: center; margin-bottom: 50px;'> <img src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png' width='100'> <h1 style='color: white; margin-top: 20px;'>H&C PORTAIL RH</h1> <p style='color: #94a3b8; font-size: 18px;'>Accès Client Sécurisé</p></div>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("🔒 Authentification")
        st.text_input("Identifiant", key="u")
        st.text_input("Mot de passe", type="password", key="p")
        st.button("Entrer", on_click=check_login, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("Infos Démo"): st.write("ID : admin / MDP : rh123")
    st.stop()


# --- CHARGEMENT ---
@st.cache_data(ttl=60)
def load_data(sheet_name):
    try:
        sheet = connect_google_sheet()
        data = {}
        for name in ['Données Sociales', 'Salaires', 'Formation', 'Recrutement', 'Finances', 'Temps & Projets']: # NOUVELLE FEUILLE AJOUTÉE
            df = pd.DataFrame(sheet.worksheet(name).get_all_records())
            df.columns = [c.strip() for c in df.columns]
            data[name] = df

        if 'Primes(€)' in data['Salaires'].columns: data['Salaires'].rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        df_global = pd.merge(data['Données Sociales'], data['Salaires'], on='Nom', how='left')
        
        # Formation
        data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
        form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
        df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
        df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)
        form_detail_enrichi = pd.merge(data['Formation'], data['Données Sociales'][['Nom', 'Service', 'CSP']], on='Nom', how='left')

        # Nettoyage Général
        for col in ['Salaire (€)', 'Primes (€)', 'Coût Recrutement (€)']:
            if col in data['Recrutement'].columns: data['Recrutement'][col] = data['Recrutement'][col].apply(clean_currency)
        for col in ['Salaire (€)', 'Primes (€)']:
            if col in df_global.columns: df_global[col] = df_global[col].apply(clean_currency)
        
        df_global = calculer_donnees(df_global)
        return df_global, data['Recrutement'], form_detail_enrichi, data['Temps & Projets'], data
    except Exception as e:
        st.error(f"Erreur Load : {e}")
        return None, None, None, None, None

rh, rec, form_detail, temps_projets, raw_data = load_data(st.session_state.get('current_sheet', "Dashboard_Data"))

# --- INTERFACE (Après Login) ---
if rh is not None:
    
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1077/1077114.png", width=60)
        st.markdown(f"### {st.session_state.get('company_name', 'Mode Démo')}")
        
        selected = option_menu(
            menu_title=None,
            options=["Dashboard", "Salariés", "Formation", "Recrutement", "Temps & Projets", "Simulation", "Gestion BDD"],
            icons=["speedometer2", "people", "mortarboard", "bullseye", "clock", "calculator", "database"],
            menu_icon="cast", default_index=0
        )
        st.markdown("---")
        services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
        selected_service = st.selectbox("Filtrer par Service", services)
        rh_f = rh[rh['Service'] == selected_service] if selected_service != 'Tous' else rh
        form_f = form_detail[form_detail['Service'] == selected_service] if selected_service != 'Tous' else form_detail
        
        st.markdown("---")
        if st.button("🚪 Déconnexion", use_container_width=True): logout()

    # 1. DASHBOARD
    if selected == "Dashboard":
        st.title(f"Vue d'ensemble ({selected_service})")
        
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        taux_turnover = calculer_turnover(rh_f) # Utilise la fonction de turnover
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{nb}</div><div class='kpi-lbl'>Collaborateurs</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{taux_turnover:.1f}%</div><div class='kpi-lbl'>Taux de Turnover</div></div>", unsafe_allow_html=True) 
        c3.markdown(f"<div class='card'><div class='kpi-val'>{ms/1000:.0f} k€</div><div class='kpi-lbl'>Masse Salariale</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='card'><div class='kpi-val'>{age:.0f} ans</div><div class='kpi-lbl'>Âge Moyen</div></div>", unsafe_allow_html=True)
        
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("<div class='card'><h3>Répartition CSP</h3>", unsafe_allow_html=True)
            if 'CSP' in rh_f.columns:
                st.plotly_chart(clean_chart(px.pie(rh_f, names='CSP', hole=0.6, color_discrete_sequence=['#3b82f6', '#10b981', '#f59e0b', '#a855f7'])), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with g2:
            st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
            if 'Âge' in rh_f.columns and 'Sexe' in rh_f.columns:
                rh_f['Tranche'] = pd.cut(rh_f['Âge'], bins=[20,30,40,50,60,70], labels=["20-30","30-40","40-50","50-60","60+"]).astype(str)
                pyr = rh_f.groupby(['Tranche', 'Sexe']).size().reset_index(name='Nb')
                pyr['Nb'] = pyr.apply(lambda x: -x['Nb'] if x['Sexe']=='Homme' else x['Nb'], axis=1)
                fig = px.bar(pyr, x='Nb', y='Tranche', color='Sexe', orientation='h', color_discrete_map={'Homme': '#3b82f6', 'Femme': '#ec4899'})
                fig.update_layout(xaxis=dict(tickvals=[-5, 0, 5], ticktext=['5', '0', '5']))
                st.plotly_chart(clean_chart(fig), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)


    # 2. SALARIÉS
    elif selected == "Salariés":
        st.title("🗂️ Gestion des Talents")
        col_list, col_detail = st.columns([1, 3])
        with col_list:
            st.markdown("<div class='card'><h3>Annuaire</h3>", unsafe_allow_html=True)
            search = st.text_input("Rechercher", placeholder="Nom...")
            liste = sorted(rh_f['Nom'].unique().tolist())
            if search: liste = [n for n in liste if search.lower() in n.lower()]
            choix = st.selectbox("Sélectionner un employé", liste)
            st.markdown("</div>", unsafe_allow_html=True)

        with col_detail:
            if choix:
                emp = rh[rh['Nom'] == choix].iloc[0]
                # ... (Contenu Fiche) ...
                st.markdown(f"""<div class='card' style='border-left: 5px solid #38bdf8;'><h2 style='margin:0; color:#f3f4f6 !important;'>{emp['Nom']}</h2><p style='color:#94a3b8 !important;'>{emp['Poste']} • {emp['Service']} • {emp.get('CSP', '')}</p></div>""", unsafe_allow_html=True)
                hist = form_detail[form_detail['Nom'] == choix] if not form_detail.empty else pd.DataFrame()
                try: st.download_button("📄 Télécharger PDF", data=create_pdf(emp, hist), file_name=f"{emp['Nom']}.pdf", mime="application/pdf")
                except: pass
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("<div class='card'><h3>💰 Rémunération</h3>", unsafe_allow_html=True)
                    st.metric("Salaire Fixe", f"{emp.get('Salaire (€)', 0):,.0f} €")
                    st.metric("Primes", f"{emp.get('Primes (€)', 0):,.0f} €")
                    st.metric("Total Brut", f"{(emp.get('Salaire (€)', 0)+emp.get('Primes (€)', 0)):,.0f} €")
                    if str(emp.get('Au SMIC', 'No')).lower() == 'oui': st.markdown('<div class="alert-box">⚠️ Attention : Salaire au niveau du SMIC</div>', unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown("<div class='card'><h3>🎓 Parcours Formation</h3>", unsafe_allow_html=True)
                    if not hist.empty: st.dataframe(hist[['Type Formation', 'Coût Formation (€)']], hide_index=True, use_container_width=True)
                    else: st.info("Aucune formation.")
                    st.markdown("</div>", unsafe_allow_html=True)

    # 3. FORMATION
    elif selected == "Formation":
        st.title("🎓 Pilotage de la Formation")
        budget_total = form_f['Coût Formation (€)'].sum()
        nb_actions = len(form_f)
        c1, c2 = st.columns(2)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{budget_total:,.0f} €</div><div class='kpi-lbl'>Budget Consommé</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{nb_actions}</div><div class='kpi-lbl'>Actions réalisées</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='card'><h3>Détail des actions</h3>", unsafe_allow_html=True)
        st.dataframe(form_f, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 4. RECRUTEMENT
    elif selected == "Recrutement":
        st.title("🎯 Talent Acquisition")
        total_rec = rec['Coût Recrutement (€)'].sum()
        c1, c2 = st.columns(2)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{total_rec:,.0f} €</div><div class='kpi-lbl'>Investissement</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{len(rec)}</div><div class='kpi-lbl'>Postes Ouverts</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='card'><h3>Pipeline de Recrutement</h3>", unsafe_allow_html=True)
        st.dataframe(rec, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 5. TEMPS & PROJETS (NOUVEL ONGLET - Simple Affichage)
    elif selected == "Temps & Projets":
        st.title("⏳ Suivi des Temps & Projets")
        st.info("Cette page est connectée à la feuille 'Temps & Projets'.")
        
        if temps_projets is not None and not temps_projets.empty:
            st.subheader("Distribution des Heures")
            if 'Heures Travaillées' in temps_projets.columns and 'Projet' in temps_projets.columns:
                temps_projets['Heures Travaillées'] = pd.to_numeric(temps_projets['Heures Travaillées'], errors='coerce').fillna(0)
                df_proj_sum = temps_projets.groupby('Projet')['Heures Travaillées'].sum().reset_index()
                st.plotly_chart(clean_chart(px.bar(df_proj_sum, x='Projet', y='Heures Travaillées', title="Total Heures par Projet")), use_container_width=True)
            
            st.subheader("Données Brutes")
            st.dataframe(temps_projets, use_container_width=True)
        else:
            st.warning("Veuillez remplir la feuille 'Temps & Projets' dans votre Google Sheet.")


    # 6. SIMULATION
    elif selected == "Simulation":
        st.title("🔮 Prospective Salariale")
        st.markdown("<div class='card'><h3>Paramètres</h3>", unsafe_allow_html=True)
        augm = st.slider("Hypothèse d'augmentation (%)", 0.0, 10.0, 2.0, 0.1)
        st.markdown("</div>", unsafe_allow_html=True)
        ms_actuelle = rh_f['Salaire (€)'].sum() * 12 * 1.45
        impact = ms_actuelle * (augm/100)
        st.metric("Impact Financier", f"+ {impact:,.0f} €", delta="Coût Annuel", delta_color="inverse")
        st.plotly_chart(clean_chart(go.Figure(go.Waterfall(measure=["relative", "relative", "total"], x=["Actuel", "Impact", "Futur"], y=[ms_actuelle, impact, ms_actuelle+impact]))), use_container_width=True)

    # 7. GESTION BDD
    elif selected == "Gestion BDD":
        st.title("🛠️ Centre de Gestion des Données")
        st.info(f"Vous modifiez les données du client : {st.session_state.get('company_name', 'Demo')}")
        
        tab_rh, tab_sal, tab_form, tab_rec, tab_temps = st.tabs(["👥 Employés", "💰 Salaires", "🎓 Formation", "🎯 Recrutement", "⏳ Temps & Projets"])
        
        # CRUD EMPLOYES
        with tab_rh:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_rh = st.data_editor(raw_data['Données Sociales'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Employés"): save_data_to_google(edited_rh, 'Données Sociales')
            st.markdown("</div>", unsafe_allow_html=True)
        
        # CRUD SALAIRES
        with tab_sal:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_sal = st.data_editor(raw_data['Salaires'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Salaires"): save_data_to_google(edited_sal, 'Salaires')
            st.markdown("</div>", unsafe_allow_html=True)
        
        # CRUD FORMATION
        with tab_form:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_form = st.data_editor(raw_data['Formation'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Formations"): save_data_to_google(edited_form, 'Formation')
            st.markdown("</div>", unsafe_allow_html=True)
        
        # CRUD RECRUTEMENT
        with tab_rec:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_rec = st.data_editor(raw_data['Recrutement'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Recrutements"): save_data_to_google(edited_rec, 'Recrutement')
            st.markdown("</div>", unsafe_allow_html=True)

        # CRUD TEMPS & PROJETS (NOUVEAU)
        with tab_temps:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_temps = st.data_editor(raw_data['Temps & Projets'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Temps"): save_data_to_google(edited_temps, 'Temps & Projets')
            st.markdown("</div>", unsafe_allow_html=True)
