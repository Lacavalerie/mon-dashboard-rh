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
st.set_page_config(page_title="RH Cockpit V75", layout="wide", initial_sidebar_state="expanded")

# --- INITIALISATION AUTOMATIQUE (SANS LOGIN) ---
if 'company_name' not in st.session_state: st.session_state['company_name'] = "H&C CONSEIL"
if 'current_sheet' not in st.session_state: st.session_state['current_sheet'] = "Dashboard_Data"
if 'username' not in st.session_state: st.session_state['username'] = "Admin"

# --- DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    h1, h2, h3, p, div, label, span, li { color: #FFFFFF !important; }
    
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
    
    div.stButton > button:first-child {
        background-color: #3b82f6;
        color: white;
        border: none;
    }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS UTILES ---
def calculer_turnover(df):
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
        # On utilise le fichier défini par défaut au début
        return client.open(st.session_state['current_sheet']) 
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
        
        df_to_save = df_to_save.fillna("")
        ws.clear()
        ws.update([df_to_save.columns.values.tolist()] + df_to_save.values.tolist())
        st.toast(f"✅ {worksheet_name} sauvegardé !", icon="💾")
        time.sleep(1)
        st.cache_data.clear()
        st.rerun()
    except Exception as e: st.error(f"Erreur sauvegarde : {e}")

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

def create_pdf(emp, form_hist):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"FICHE : {emp['Nom']}", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Poste : {emp['Poste']}", ln=True)
    pdf.ln(5)
    pdf.cell(200, 10, txt=f"Salaire : {emp.get('Salaire (€)', 0)} EUR", ln=True)
    return pdf.output(dest='S').encode('latin-1')


# --- CHARGEMENT ---
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = connect_google_sheet()
        data = {}
        for name in ['Données Sociales', 'Salaires', 'Formation', 'Recrutement', 'Finances', 'Temps & Projets']:
            try:
                df = pd.DataFrame(sheet.worksheet(name).get_all_records())
                df.columns = [c.strip() for c in df.columns]
                data[name] = df
            except:
                data[name] = pd.DataFrame()

        if not data['Salaires'].empty and 'Primes(€)' in data['Salaires'].columns: 
            data['Salaires'].rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        
        if not data['Données Sociales'].empty and not data['Salaires'].empty:
            df_global = pd.merge(data['Données Sociales'], data['Salaires'], on='Nom', how='left')
        else:
            df_global = data['Données Sociales']
        
        if not data['Formation'].empty:
            data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
            form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
            df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
            df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)
            form_detail_enrichi = pd.merge(data['Formation'], data['Données Sociales'][['Nom', 'Service', 'CSP']], on='Nom', how='left')
        else:
            df_global['Coût Formation (€)'] = 0
            form_detail_enrichi = pd.DataFrame()

        if not data['Recrutement'].empty and 'Coût Recrutement (€)' in data['Recrutement'].columns:
            data['Recrutement']['Coût Recrutement (€)'] = data['Recrutement']['Coût Recrutement (€)'].apply(clean_currency)
        
        for col in ['Salaire (€)', 'Primes (€)']:
            if col in df_global.columns: df_global[col] = df_global[col].apply(clean_currency)
        
        df_global = calculer_donnees(df_global)
        return df_global, data['Recrutement'], form_detail_enrichi, data['Temps & Projets'], data
    except Exception as e:
        st.error(f"Erreur Load : {e}")
        return None, None, None, None, None

rh, rec, form_detail, temps_projets, raw_data = load_data()

# --- INTERFACE ---
if rh is not None:
    
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1077/1077114.png", width=60)
        st.markdown(f"### {st.session_state['company_name']}") # Nom par défaut
        
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
        
        # Plus de bouton déconnexion ici

    # 1. DASHBOARD
    if selected == "Dashboard":
        st.title(f"Vue d'ensemble ({selected_service})")
        
        taux_turnover = calculer_turnover(rh) 
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{nb}</div><div class='kpi-lbl'>Collaborateurs</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{taux_turnover:.1f}%</div><div class='kpi-lbl'>Turnover</div></div>", unsafe_allow_html=True) 
        c3.markdown(f"<div class='card'><div class='kpi-val'>{ms/1000:.0f} k€</div><div class='kpi-lbl'>Masse Salariale</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='card'><div class='kpi-val'>{age:.0f} ans</div><div class='kpi-lbl'>Âge Moyen</div></div>", unsafe_allow_html=True)
        
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
            liste = sorted(rh_f['Nom'].unique().tolist())
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
                    st.markdown("</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown("<div class='card'><h3>🎓 Parcours Formation</h3>", unsafe_allow_html=True)
                    cols_to_show = []
                    if 'Type Formation' in hist.columns: cols_to_show.append('Type Formation')
                    if 'Coût Formation (€)' in hist.columns: cols_to_show.append('Coût Formation (€)')
                    if not hist.empty and cols_to_show: st.dataframe(hist[cols_to_show], hide_index=True, use_container_width=True)
                    else: st.info("Aucune formation.")
                    st.markdown("</div>", unsafe_allow_html=True)

    # 3. FORMATION
    elif selected == "Formation":
        st.title("🎓 Pilotage Formation")
        if not form_detail.empty and 'Coût Formation (€)' in form_detail.columns:
            f_view = form_detail[form_detail['Service'] == selected_service] if selected_service != 'Tous' else form_detail
            budget_total = f_view['Coût Formation (€)'].sum()
            nb_actions = len(f_view)
            c1, c2 = st.columns(2)
            c1.markdown(f"<div class='card'><div class='kpi-val'>{budget_total:,.0f} €</div><div class='kpi-lbl'>Budget Consommé</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='card'><div class='kpi-val'>{nb_actions}</div><div class='kpi-lbl'>Actions</div></div>", unsafe_allow_html=True)
            st.markdown("<div class='card'><h3>Répartition par Thème</h3>", unsafe_allow_html=True)
            if 'Type Formation' in f_view.columns and not f_view.empty:
                 df_pie = f_view.groupby('Type Formation')['Coût Formation (€)'].sum().reset_index()
                 st.plotly_chart(clean_chart(px.pie(df_pie, values='Coût Formation (€)', names='Type Formation', hole=0.6)), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<div class='card'><h3>Détail</h3>", unsafe_allow_html=True)
            st.dataframe(f_view, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else: st.warning("Pas de données.")

    # 4. RECRUTEMENT
    elif selected == "Recrutement":
        st.title("🎯 Talent Acquisition")
        total_rec = rec['Coût Recrutement (€)'].sum()
        c1, c2 = st.columns(2)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{total_rec:,.0f} €</div><div class='kpi-lbl'>Investissement</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{len(rec)}</div><div class='kpi-lbl'>Postes Ouverts</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='card'><h3>Pipeline</h3>", unsafe_allow_html=True)
        st.dataframe(rec, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 5. TEMPS
    elif selected == "Temps & Projets":
        st.title("⏳ Suivi des Temps")
        if temps_projets is not None and not temps_projets.empty:
            if 'Heures Travaillées' in temps_projets.columns:
                temps_projets['Heures Travaillées'] = pd.to_numeric(temps_projets['Heures Travaillées'], errors='coerce').fillna(0)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='card'><h3>Répartition par Projet</h3>", unsafe_allow_html=True)
                if 'Projet' in temps_projets.columns:
                    df_proj = temps_projets.groupby('Projet')['Heures Travaillées'].sum().reset_index()
                    st.plotly_chart(clean_chart(px.pie(df_proj, values='Heures Travaillées', names='Projet', hole=0.6)), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with col2:
                st.markdown("<div class='card'><h3>Top Collaborateurs</h3>", unsafe_allow_html=True)
                if 'Nom' in temps_projets.columns:
                    df_user = temps_projets.groupby('Nom')['Heures Travaillées'].sum().reset_index().sort_values('Heures Travaillées', ascending=True)
                    st.plotly_chart(clean_chart(px.bar(df_user, x='Heures Travaillées', y='Nom', orientation='h', color='Heures Travaillées')), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<div class='card'><h3>Données Brutes</h3>", unsafe_allow_html=True)
            st.dataframe(temps_projets, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else: st.warning("Veuillez remplir la feuille 'Temps & Projets'.")

    # 6. SIMULATION
    elif selected == "Simulation":
        st.title("🔮 Prospective")
        mode_sim = st.radio("Type :", ["🏢 Globale", "👤 Individuelle"], horizontal=True)
        st.markdown("---")
        if mode_sim == "🏢 Globale":
            st.markdown("<div class='card'><h3>Paramètres</h3>", unsafe_allow_html=True)
            augm = st.slider("Hausse (%)", 0.0, 10.0, 2.0, 0.1)
            st.markdown("</div>", unsafe_allow_html=True)
            ms_actuelle = rh_f['Salaire (€)'].sum() * 12 * 1.45
            impact = ms_actuelle * (augm/100)
            st.metric("Impact Annuel (Chargé)", f"+ {impact:,.0f} €", delta="Surcoût", delta_color="inverse")
            st.plotly_chart(clean_chart(go.Figure(go.Waterfall(measure=["relative", "relative", "total"], x=["Actuel", "Impact", "Futur"], y=[ms_actuelle, impact, ms_actuelle+impact]))), use_container_width=True)
        elif mode_sim == "👤 Individuelle":
             col_sel, col_sim = st.columns([1, 2])
             with col_sel:
                 st.markdown("<div class='card'>", unsafe_allow_html=True)
                 choix_indiv = st.selectbox("Salarié", sorted(rh_f['Nom'].unique().tolist()))
                 emp_sim = rh[rh['Nom'] == choix_indiv].iloc[0]
                 sal_base = emp_sim.get('Salaire (€)', 0)
                 st.info(f"Actuel : **{sal_base:,.0f} €**")
                 type_hausse = st.radio("Type :", ["%", "€"])
                 if type_hausse == "%": val = st.number_input("Valeur %", 0.0, 50.0, 5.0); new_sal = sal_base * (1 + val/100)
                 else: val = st.number_input("Montant €", 0, 5000, 100); new_sal = sal_base + val
                 st.markdown("</div>", unsafe_allow_html=True)
             with col_sim:
                 st.markdown("<div class='card'><h3>Résultats</h3>", unsafe_allow_html=True)
                 diff_mensuelle = new_sal - sal_base
                 cout_patron_annuel = diff_mensuelle * 12 * 1.45
                 m1, m2 = st.columns(2)
                 m1.metric("Nouveau Salaire", f"{new_sal:,.0f} €", delta=f"+{diff_mensuelle:.0f} €")
                 m2.metric("Coût Patronal (An)", f"{cout_patron_annuel:,.0f} €", delta="Impact", delta_color="inverse")
                 st.markdown("</div>", unsafe_allow_html=True)

    # 7. GESTION BDD
    elif selected == "Gestion BDD":
        st.title("🛠️ Centre de Gestion")
        st.info(f"Données : {st.session_state.get('company_name', 'Par défaut')}")
        tab_rh, tab_sal, tab_form, tab_rec, tab_temps = st.tabs(["👥 Employés", "💰 Salaires", "🎓 Formation", "🎯 Recrutement", "⏳ Temps"])
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
        with tab_temps:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            edited_temps = st.data_editor(raw_data['Temps & Projets'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Sauvegarder Temps"): save_data_to_google(edited_temps, 'Temps & Projets')
            st.markdown("</div>", unsafe_
