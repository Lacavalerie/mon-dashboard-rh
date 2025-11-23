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

# Configuration de la page
st.set_page_config(page_title="H&C Pilotage RH", layout="wide", initial_sidebar_state="expanded")

# --- CSS PERSONNALISÉ (DESIGN LOGIN PREMIUM & DASHBOARD) ---
st.markdown("""
    <style>
    /* Fond général de l'application une fois connecté */
    .stApp { background-color: #0e1117; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    
    /* Textes généraux en blanc */
    h1, h2, h3, p, div, label, span, li { color: #FFFFFF !important; }
    
    /* --- STYLE SPÉCIFIQUE POUR LA PAGE DE CONNEXION --- */
    
    /* Conteneur du formulaire de login à droite */
    .login-form-container {
        background-color: #161b22; /* Fond sombre légèrement différent du main */
        padding: 40px;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        border: 1px solid #30363d;
    }
    
    /* Titres du login */
    .login-title { font-size: 32px; font-weight: bold; margin-bottom: 10px; color: white; }
    .login-subtitle { font-size: 16px; color: #9ca3af !important; margin-bottom: 30px; }
    
    /* Labels des inputs */
    .login-label { font-size: 14px; font-weight: 600; margin-bottom: 5px; color: #e5e7eb !important; }
    
    /* Customisation des champs de saisie Streamlit (Input boxes) */
    /* C'est un peu technique, on cible les éléments internes de Streamlit */
    div[data-testid="stTextInput"] input {
        background-color: #1f2937 !important; /* Fond très sombre */
        border: 1px solid #374151 !important; /* Bordure grise subtile */
        color: white !important;
        border-radius: 8px !important;
        padding: 10px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #3b82f6 !important; /* Bordure bleue au focus */
        box-shadow: 0 0 0 1px #3b82f6 !important;
    }

    /* Customisation du Gros Bouton Login Bleu */
    .stButton .login-btn {
        width: 100%;
        background-color: #3b82f6 !important; /* Bleu vif */
        color: white !important;
        border: none;
        padding: 12px 24px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        font-weight: bold;
        border-radius: 8px;
        cursor: pointer;
        transition: background-color 0.3s;
    }
    .stButton .login-btn:hover {
        background-color: #2563eb !important; /* Bleu plus foncé au survol */
    }
    
    /* Liens annexes (Forgot password...) */
    .login-links { font-size: 14px; color: #3b82f6 !important; text-decoration: none; }
    .login-footer { font-size: 14px; color: #9ca3af !important; text-align: center; margin-top: 20px; }
    
    /* --- FIN STYLE LOGIN --- */

    /* STYLE DES CARTES DU DASHBOARD (V68) */
    .card {
        background-color: #1f2937;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #374151;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        margin-bottom: 25px;
    }
    .card h3 {
        color: #38bdf8 !important;
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 20px;
        border-bottom: 2px solid #374151;
        padding-bottom: 12px;
    }
    .kpi-val { font-size: 32px; font-weight: 800; color: #f9fafb; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;}
    .alert-box { background-color: rgba(127, 29, 29, 0.5); color: #fca5a5 !important; padding: 15px; border-radius: 8px; border: 1px solid #ef4444; }
    [data-testid="stDataFrame"] { background-color: transparent !important; }
    
    /* Bouton Déconnexion Rouge dans la sidebar */
    [data-testid="stSidebar"] div.stButton > button {
        background-color: #ef4444 !important;
        color: white !important;
        border: none;
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

# --- GESTION LOGIN / LOGOUT ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

def check_login():
    # On vérifie les clés 'login_u' et 'login_p' utilisées dans le nouveau formulaire
    if st.session_state.get('login_u') == "admin" and st.session_state.get('login_p') == "rh123": 
        st.session_state['logged_in'] = True
    else: 
        # On utilise un toast pour l'erreur sur la nouvelle page de login, c'est plus propre
        st.toast("❌ Identifiant ou mot de passe incorrect", icon="⚠️")

def logout():
    st.session_state['logged_in'] = False
    st.cache_data.clear()
    st.rerun()

# =========================================
# NOUVELLE PAGE DE CONNEXION (SPLIT SCREEN)
# =========================================
if not st.session_state['logged_in']:
    # On enlève le padding standard de Streamlit pour que l'image aille plus près des bords
    st.markdown("""<style>.block-container {padding-top: 1rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem;}</style>""", unsafe_allow_html=True)
    
    # Création de 2 colonnes : Image à gauche (60%), Formulaire à droite (40%)
    col_image, col_form_space, col_form = st.columns([1.5, 0.1, 1]) # 1.5 pour l'image, 0.1 espace, 1 pour le form

    with col_image:
        # Image de buildings bleu nuit style "Corporate"
        # J'utilise une image libre de droit Unsplash qui ressemble à ton exemple.
        st.image("https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1000&auto=format&fit=crop", use_container_width=True)

    with col_form:
        # Espaceur vertical pour centrer le formulaire
        st.markdown("<div style='height: 50px;'></div>", unsafe_allow_html=True)
        
        # Conteneur du formulaire stylisé
        st.markdown("<div class='login-form-container'>", unsafe_allow_html=True)
        st.markdown("<div class='login-title'>Login</div>", unsafe_allow_html=True)
        st.markdown("<div class='login-subtitle'>Welcome back! Please login to your account.</div>", unsafe_allow_html=True)
        
        # Champs de saisie avec labels personnalisés
        st.markdown("<div class='login-label'>Email Address</div>", unsafe_allow_html=True)
        # On utilise key='login_u' pour le distinguer
        username = st.text_input("Label caché", placeholder="admin", key="login_u", label_visibility="collapsed")
        
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True) # Espace
        
        st.markdown("<div class='login-label'>Password</div>", unsafe_allow_html=True)
        # On utilise key='login_p'
        password = st.text_input("Label caché", type="password", placeholder="••••••", key="login_p", label_visibility="collapsed")
        
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True) # Espace

        # Checkbox et lien "Forgot Password" sur la même ligne
        c_rem, c_forgot = st.columns([1, 1])
        with c_rem:
            st.checkbox("Remember me")
        with c_forgot:
            st.markdown("<div style='text-align: right;'><a href='#' class='login-links'>Forgot password?</a></div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True) # Espace avant bouton

        # Bouton Login Customisé (hack CSS pour appliquer la classe .login-btn)
        # On utilise un callback pour gérer le clic
        st.markdown('<style>div.stButton > button:first-child { @extend .login-btn; }</style>', unsafe_allow_html=True)
        st.button("Login", on_click=check_login, use_container_width=True, type="primary")

        # Pied de formulaire
        st.markdown("<div class='login-footer'>New User? <a href='#' class='login-links'>Signup</a></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True) # Fin container

    # On arrête tout ici tant qu'on n'est pas connecté
    st.stop()

# =========================================
# APPLICATION PRINCIPALE (Une fois connecté)
# =========================================

# --- PDF & UTILITAIRES ---
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
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e7eb"),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(showgrid=False, color="#e5e7eb"),
        yaxis=dict(showgrid=True, gridcolor="#374151", color="#e5e7eb"),
        legend=dict(font=dict(color="#e5e7eb"))
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

        if 'Primes(€)' in data['Salaires'].columns: data['Salaires'].rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        if 'Cout Formation (€)' in data['Formation'].columns: data['Formation'].rename(columns={'Cout Formation (€)': 'Coût Formation (€)'}, inplace=True)
        if 'Coût Formation' in data['Formation'].columns: data['Formation'].rename(columns={'Coût Formation': 'Coût Formation (€)'}, inplace=True)

        df_global = pd.merge(data['Données Sociales'], data['Salaires'], on='Nom', how='left')
        
        data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
        form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
        df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
        df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)
        
        form_detail_enrichi = pd.merge(data['Formation'], data['Données Sociales'][['Nom', 'Service', 'CSP']], on='Nom', how='left')
        data['Recrutement']['Coût Recrutement (€)'] = data['Recrutement']['Coût Recrutement (€)'].apply(clean_currency)
        
        for col in ['Salaire (€)', 'Primes (€)']:
            if col in df_global.columns: df_global[col] = df_global[col].apply(clean_currency)
        
        df_global = calculer_donnees(df_global)
        return df_global, data['Recrutement'], form_detail_enrichi, data
    except Exception as e:
        st.error(f"Erreur Load : {e}")
        return None, None, None, None

rh, rec, form_detail, raw_data = load_data()

if rh is not None:
    
    with st.sidebar:
        # --- MODIFICATION ICI : LOGO H&C ---
        # Assure-toi que le fichier icon_hc.png est dans le même dossier que app.py
        try:
            st.image("icon_hc.png", width=80)
        except:
            # Fallback si l'image n'est pas trouvée
            st.warning("Image 'icon_hc.png' introuvable.")
            st.image("https://cdn-icons-png.flaticon.com/512/1077/1077114.png", width=60)

        
        selected = option_menu(
            menu_title="H&C PILOTAGE", # Changement du titre du menu
            options=["Dashboard", "Salariés", "Formation", "Recrutement", "Simulation", "Gestion BDD"],
            icons=["speedometer2", "people", "mortarboard", "bullseye", "calculator", "database"],
            menu_icon="cast", default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#38bdf8", "font-size": "16px"}, 
                "nav-link": {"font-size": "14px", "text-align": "left", "margin":"5px", "--hover-color": "#1f2937", "color": "#e5e7eb"},
                "nav-link-selected": {"background-color": "#3b82f6", "color": "white"},
            }
        )
        st.markdown("---")
        
        # FILTRE SERVICE
        services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
        selected_service = st.selectbox("Filtrer par Service", services)
        rh_f = rh[rh['Service'] == selected_service] if selected_service != 'Tous' else rh
        form_f = form_detail[form_detail['Service'] == selected_service] if selected_service != 'Tous' else form_detail
        
        # BOUTON DÉCONNEXION
        st.markdown("---")
        if st.button("🚪 Déconnexion", use_container_width=True):
            logout()

    # 1. DASHBOARD
    if selected == "Dashboard":
        st.title(f"Vue d'ensemble ({selected_service})")
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        cout_form = rh_f['Coût Formation (€)'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{nb}</div><div class='kpi-lbl'>Collaborateurs</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{ms/1000:.0f} k€</div><div class='kpi-lbl'>Masse Salariale</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><div class='kpi-val'>{age:.0f} ans</div><div class='kpi-lbl'>Âge Moyen</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='card'><div class='kpi-val'>{cout_form:,.0f} €</div><div class='kpi-lbl'>Budget Formation</div></div>", unsafe_allow_html=True)
        
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("<div class='card'><h3>Répartition CSP</h3>", unsafe_allow_html=True)
            if 'CSP' in rh_f.columns:
                st.plotly_chart(clean_chart(px.pie(rh_f, names='CSP', hole=0.6, color_discrete_sequence=['#3b82f6', '#10b981', '#f59e0b', '#a855f7'])), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with g2:
            st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
            if 'Âge' in rh_f.columns:
                rh_f['Tranche'] = pd.cut(rh_f['Âge'], bins=[20,30,40,50,60,70], labels=["20-30","30-40","40-50","50-60","60+"]).astype(str)
                pyr = rh_f.groupby(['Tranche', 'Sexe']).size().reset_index(name='Nb')
                pyr['Nb'] = pyr.apply(lambda x: -x['Nb'] if x['Sexe']=='Homme' else x['Nb'], axis=1)
                fig = px.bar(pyr, x='Nb', y='Tranche', color='Sexe', orientation='h', 
                             color_discrete_map={'Homme': '#3b82f6', 'Femme': '#ec4899'})
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

    # 5. SIMULATION
    elif selected == "Simulation":
        st.title("🔮 Prospective Salariale")
        st.markdown("<div class='card'><h3>Paramètres</h3>", unsafe_allow_html=True)
        augm = st.slider("Hypothèse d'augmentation (%)", 0.0, 10.0, 2.0, 0.1)
        st.markdown("</div>", unsafe_allow_html=True)
        ms_actuelle = rh_f['Salaire (€)'].sum() * 12 * 1.45
        impact = ms_actuelle * (augm/100)
        st.metric("Impact Financier", f"+ {impact:,.0f} €", delta="Coût Annuel", delta_color="inverse")
        st.plotly_chart(clean_chart(go.Figure(go.Waterfall(measure=["relative", "relative", "total"], x=["Actuel", "Impact", "Futur"], y=[ms_actuelle, impact, ms_actuelle+impact]))), use_container_width=True)

    # 6. GESTION BDD
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
