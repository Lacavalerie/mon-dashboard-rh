import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Dashboard RH V63", layout="wide")

# --- 1. DESIGN (RETOUR AU BLEU NUIT / DARK MODE) ---
st.markdown("""
    <style>
    /* Fond Bleu Nuit */
    .stApp { background-color: #1a2639; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #111b2b; }
    
    /* Textes en Blanc */
    h1, h2, h3, p, div, label, span, li { color: #FFFFFF !important; }
    
    /* Cartes KPI Sombres avec bordure colorée */
    [data-testid="stMetric"] { 
        background-color: #2d3e55; 
        padding: 15px; 
        border-radius: 8px; 
        border-left: 5px solid #4ade80; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; }
    
    /* Alertes */
    .smic-alert { background-color: #7f1d1d; color: white; padding: 10px; border-radius: 5px; border: 1px solid #ef4444; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FONCTIONS TECHNIQUES ---
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

def clean_chart(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        font=dict(color="white"),
        xaxis=dict(showgrid=False, color="white"),
        yaxis=dict(showgrid=True, gridcolor="#444444", color="white")
    )
    return fig

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

        if 'Primes(€)' in data['Salaires'].columns: data['Salaires'].rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        
        df_global = pd.merge(data['Données Sociales'], data['Salaires'], on='Nom', how='left')
        
        if 'Coût Formation' in data['Formation'].columns: data['Formation'].rename(columns={'Coût Formation': 'Coût Formation (€)'}, inplace=True)
        data['Formation']['Coût Formation (€)'] = data['Formation']['Coût Formation (€)'].apply(clean_currency)
        form_agg = data['Formation'].groupby('Nom')['Coût Formation (€)'].sum().reset_index()
        
        df_global = pd.merge(df_global, form_agg, on='Nom', how='left')
        df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)

        data['Recrutement']['Coût Recrutement (€)'] = data['Recrutement']['Coût Recrutement (€)'].apply(clean_currency)
        
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
        menu = st.radio("", ["Vue d'ensemble", "Fiches Salariés", "Recrutement", "Simulation Avancée", "Administration"], label_visibility="collapsed")
        
        st.markdown("---")
        st.markdown("### 🔽 FILTRES")
        services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
        selected_service = st.selectbox("Service", services)
        
        rh_f = rh[rh['Service'] == selected_service] if selected_service != 'Tous' else rh

    # --- 1. VUE D'ENSEMBLE ---
    if menu == "Vue d'ensemble":
        st.header(f"Tableau de Bord ({selected_service})")
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        nb = len(rh_f)
        age = rh_f['Âge'].mean() if 'Âge' in rh_f.columns else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Effectif", nb)
        c2.metric("Masse Salariale (Chargée)", f"{ms/1000:.0f} k€")
        c3.metric("Âge Moyen", f"{age:.0f} ans")
        
        g1, g2 = st.columns(2)
        with g1:
            if 'CSP' in rh_f.columns:
                st.plotly_chart(clean_chart(px.pie(rh_f, names='CSP', hole=0.6, color_discrete_sequence=px.colors.sequential.Blues)), use_container_width=True)
        with g2:
            if 'Âge' in rh_f.columns:
                rh_f['Tranche'] = pd.cut(rh_f['Âge'], bins=[20,30,40,50,60,70], labels=["20-30","30-40","40-50","50-60","60+"]).astype(str)
                pyr = rh_f.groupby(['Tranche', 'Sexe']).size().reset_index(name='Nb')
                pyr['Nb'] = pyr.apply(lambda x: -x['Nb'] if x['Sexe']=='Homme' else x['Nb'], axis=1)
                st.plotly_chart(clean_chart(px.bar(pyr, x='Nb', y='Tranche', color='Sexe', orientation='h', color_discrete_map={'Homme':'#4f86f7', 'Femme':'#4ade80'})), use_container_width=True)

    # --- 2. FICHES ---
    elif menu == "Fiches Salariés":
        st.header("Gestion Individuelle")
        col_sel, col_fic = st.columns([1, 3])
        with col_sel:
            st.subheader("Annuaire")
            search = st.text_input("🔍 Rechercher")
            liste = sorted(rh_f['Nom'].unique().tolist())
            if search: liste = [n for n in liste if search.lower() in n.lower()]
            choix = st.radio("Nom", liste, label_visibility="collapsed")
        
        with col_fic:
            if choix:
                emp = rh[rh['Nom'] == choix].iloc[0]
                hist = form_detail[form_detail['Nom'] == choix] if not form_detail.empty else pd.DataFrame()
                
                c_a, c_b = st.columns([3, 1])
                c_a.subheader(f"👤 {emp['Nom']}")
                try: c_b.download_button("📥 PDF", data=create_pdf(emp, hist), file_name=f"{emp['Nom']}.pdf", mime="application/pdf")
                except: pass

                i1, i2, i3 = st.columns(3)
                i1.info(f"**Poste :** {emp['Poste']}")
                i2.info(f"**Service :** {emp['Service']}")
                i3.info(f"**Contrat :** {emp.get('CSP', '')}")

                st.markdown("#### 💰 Rémunération")
                s1, s2, s3 = st.columns(3)
                s1.metric("Fixe", f"{emp.get('Salaire (€)', 0):,.0f} €")
                s2.metric("Primes", f"{emp.get('Primes (€)', 0):,.0f} €")
                s3.metric("Total Brut", f"{(emp.get('Salaire (€)', 0)+emp.get('Primes (€)', 0)):,.0f} €")

                st.markdown("#### 🎓 Formations")
                if not hist.empty: st.dataframe(hist[['Type Formation', 'Coût Formation (€)']], hide_index=True, use_container_width=True)
                else: st.info("Aucune formation.")

    # --- 3. RECRUTEMENT ---
    elif menu == "Recrutement":
        st.header("Suivi du Recrutement")
        st.dataframe(rec, use_container_width=True)
        if 'Canal Sourcing' in rec.columns:
            st.plotly_chart(clean_chart(px.bar(rec.groupby('Canal Sourcing').size().reset_index(name='Nb'), x='Canal Sourcing', y='Nb', color='Canal Sourcing')), use_container_width=True)

    # --- 4. SIMULATION AVANCÉE (NOUVEAU) ---
    elif menu == "Simulation Avancée":
        st.header("🔮 Simulateur Stratégique")
        
        # Choix du mode
        mode_sim = st.radio("Niveau de simulation :", ["🏢 Globale (Entreprise/Service)", "👤 Individuelle (Salarié)"], horizontal=True)
        
        st.markdown("---")
        
        if mode_sim == "🏢 Globale (Entreprise/Service)":
            col_param, col_res = st.columns([1, 2])
            
            with col_param:
                st.subheader("Paramètres")
                type_aug = st.radio("Type d'augmentation", ["Pourcentage (%)", "Montant Fixe (€)"])
                
                if type_aug == "Pourcentage (%)":
                    valeur = st.slider("Hausse (%)", 0.0, 10.0, 2.0, 0.1)
                else:
                    valeur = st.number_input("Hausse par salarié (€)", 0, 1000, 100, 50)
                
                charges = st.slider("Charges Patronales estimées (%)", 20, 60, 45)
            
            with col_res:
                st.subheader("Résultats Prévisionnels")
                # Calculs
                nb_sal = len(rh_f)
                ms_actuelle_brut = rh_f['Salaire (€)'].sum() * 12
                ms_actuelle_chargee = ms_actuelle_brut * (1 + charges/100)
                
                if type_aug == "Pourcentage (%)":
                    surcout_brut = ms_actuelle_brut * (valeur/100)
                else:
                    surcout_brut = valeur * nb_sal * 12
                    
                surcout_charge = surcout_brut * (1 + charges/100)
                
                k1, k2 = st.columns(2)
                k1.metric("Coût Annuel Supplémentaire (Chargé)", f"{surcout_charge:,.0f} €", delta="Dépense", delta_color="inverse")
                k2.metric("Nouveau Budget Total", f"{(ms_actuelle_chargee + surcout_charge):,.0f} €")
                
                # Graphique Waterfall
                fig = go.Figure(go.Waterfall(
                    measure=["relative", "relative", "total"],
                    x=["Budget Actuel", "Hausse", "Budget Projeté"],
                    y=[ms_actuelle_chargee, surcout_charge, ms_actuelle_chargee + surcout_charge],
                    decreasing={"marker":{"color":"#fb923c"}}, increasing={"marker":{"color":"#4ade80"}}, totals={"marker":{"color":"#60a5fa"}}
                ))
                st.plotly_chart(clean_chart(fig), use_container_width=True)

        elif mode_sim == "👤 Individuelle (Salarié)":
            col_sel, col_sim = st.columns([1, 2])
            
            with col_sel:
                choix_indiv = st.selectbox("Choisir un salarié", sorted(rh_f['Nom'].unique().tolist()))
                emp_sim = rh[rh['Nom'] == choix_indiv].iloc[0]
                sal_actuel = emp_sim.get('Salaire (€)', 0)
                
                st.info(f"Salaire actuel : **{sal_actuel:,.0f} €**")
                
                type_aug_indiv = st.radio("Appliquer :", ["+ %", "+ €"], horizontal=True)
                if type_aug_indiv == "+ %":
                    val_indiv = st.number_input("Pourcentage", 0.0, 50.0, 5.0, 0.5)
                    nouveau_sal = sal_actuel * (1 + val_indiv/100)
                else:
                    val_indiv = st.number_input("Montant Mensuel", 0, 2000, 200, 50)
                    nouveau_sal = sal_actuel + val_indiv
            
            with col_sim:
                st.subheader(f"Projection pour {choix_indiv}")
                
                gain_brut_mensuel = nouveau_sal - sal_actuel
                gain_brut_annuel = gain_brut_mensuel * 12
                cout_patron_annuel = gain_brut_annuel * 1.45 # Estimation charges
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Nouveau Salaire Brut", f"{nouveau_sal:,.0f} €", delta=f"+{gain_brut_mensuel:.0f} €")
                m2.metric("Gain Annuel Salarié", f"{gain_brut_annuel:,.0f} €")
                m3.metric("Coût Total Entreprise", f"{cout_patron_annuel:,.0f} €", delta="Coût", delta_color="inverse")
                
                # Graphique comparatif
                fig_bar = px.bar(x=['Actuel', 'Projeté'], y=[sal_actuel, nouveau_sal], text_auto=True, title="Comparaison Mensuelle Brute")
                fig_bar.update_traces(marker_color=['#3b82f6', '#4ade80'])
                st.plotly_chart(clean_chart(fig_bar), use_container_width=True)

    # --- 5. ADMINISTRATION ---
    elif menu == "Administration":
        st.header("🛠️ Centre de Gestion")
        with st.expander("📤 Import Excel"):
            up = st.file_uploader("Fichier .xlsx", type=['xlsx'])
            if up:
                df_up = pd.read_excel(up)
                st.write(df_up.head())
                if st.button("Envoyer vers Google Sheets"):
                    save_data_to_google(df_up, st.selectbox("Cible", ["Données Sociales", "Salaires"]))
        
        st.markdown("---")
        tab_ed1, tab_ed2 = st.tabs(["Employés", "Salaires"])
        with tab_ed1:
            ed_rh = st.data_editor(raw_data['Données Sociales'], num_rows="dynamic", use_container_width=True)
            if st.button("Sauver RH"): save_data_to_google(ed_rh, 'Données Sociales')
        with tab_ed2:
            ed_sal = st.data_editor(raw_data['Salaires'], num_rows="dynamic", use_container_width=True)
            if st.button("Sauver Salaires"): save_data_to_google(ed_sal, 'Salaires')
