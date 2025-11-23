import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai

# Configuration
st.set_page_config(page_title="Dashboard V55", layout="wide")

# --- 1. AUTH GOOGLE SHEETS ---
def connect_google_sheet():
    try:
        secrets = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(secrets, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("Dashboard_Data") 
        return sheet
    except Exception as e:
        st.error(f"⚠️ Erreur Google Sheets : {e}")
        st.stop()

# --- 2. IA (VERSION DIAGNOSTIC) ---
def configure_gemini():
    try:
        if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
            api_key = st.secrets["gemini"]["api_key"]
            genai.configure(api_key=api_key)
            return True
        return False
    except: return False

def ask_gemini(prompt):
    # On essaie le modèle standard actuel
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Si ça plante, on renvoie l'erreur exacte pour comprendre
        return f"ERREUR TECHNIQUE : {e}"

# --- 3. LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""

def check_login():
    user = st.session_state['input_user']
    pwd = st.session_state['input_password']
    if user == "admin" and pwd == "rh123":
        st.session_state['logged_in'] = True
        st.session_state['username'] = user
    else: st.error("Erreur login")

def logout():
    st.session_state['logged_in'] = False
    st.rerun()

if not st.session_state['logged_in']:
    st.markdown("""<style>.stApp {background-color: #1a2639;} h1 {color: white; text-align: center;}</style>""", unsafe_allow_html=True)
    st.title("🔒 Portail RH")
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        st.text_input("ID", key="input_user")
        st.text_input("MDP", type="password", key="input_password")
        st.button("Connexion", on_click=check_login)
    st.stop()

# --- 4. DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #1a2639; }
    [data-testid="stSidebar"] { background-color: #111b2b; }
    h1, h2, h3, p, div, label, span, li { color: #FFFFFF !important; }
    [data-testid="stMetric"] { background-color: #2d3e55; border-radius: 8px; border-left: 5px solid #4ade80; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; }
    .smic-alert { background-color: #7f1d1d; color: white; padding: 10px; border-radius: 5px; border: 1px solid #ef4444; }
    .stChatMessage { background-color: #2d3e55; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.write(f"👤 **{st.session_state.get('username', 'Admin')}**")
    if st.button("Déconnexion"): logout()
    st.markdown("---")

st.title("🚀 Pilotage Stratégique : RH & Finances")

# --- 5. FONCTIONS UTILES ---
def create_pdf(emp, form_hist):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"FICHE : {emp['Nom']}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Poste : {emp['Poste']} ({emp.get('CSP', 'N/A')})", ln=True)
    pdf.cell(200, 10, txt=f"Service : {emp['Service']}", ln=True)
    pdf.cell(200, 10, txt=f"Anciennete : {emp.get('Ancienneté (ans)', 0):.1f} ans", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="REMUNERATION", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Salaire Base : {emp.get('Salaire (€)', 0):.0f} EUR", ln=True)
    pdf.cell(200, 10, txt=f"Primes : {emp.get('Primes (€)', 0):.0f} EUR", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="HISTORIQUE FORMATION", ln=True)
    pdf.set_font("Arial", size=12)
    if not form_hist.empty:
        for i, row in form_hist.iterrows():
            txt = f"- {row['Type Formation']} ({row['Coût Formation (€)']} EUR)"
            try: pdf.cell(200, 10, txt=txt.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            except: pdf.cell(200, 10, txt="Erreur encodage", ln=True)
    else:
        pdf.cell(200, 10, txt="Aucune formation.", ln=True)
    return pdf.output(dest='S').encode('latin-1')

def clean_chart(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), xaxis=dict(showgrid=False, color="white"), yaxis=dict(showgrid=True, gridcolor="#444444", color="white"))
    return fig

def clean_currency(val):
    if isinstance(val, str):
        val = val.replace('€', '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    return val

def calculer_donnees_rh(df):
    today = datetime.now()
    if 'Date Naissance' in df.columns:
        df['Date Naissance'] = pd.to_datetime(df['Date Naissance'], errors='coerce')
        df['Âge'] = df['Date Naissance'].apply(lambda x: (today - x).days // 365 if pd.notnull(x) else 0)
    if 'Date Entrée' in df.columns:
        df['Date Entrée'] = pd.to_datetime(df['Date Entrée'], errors='coerce')
        df['Ancienneté (ans)'] = df['Date Entrée'].apply(lambda x: (today - x).days / 365 if pd.notnull(x) else 0)
    if 'Service' in df.columns and 'Salaire (€)' in df.columns:
        moyennes = df.groupby('Service')['Salaire (€)'].mean().reset_index()
        moyennes = moyennes.rename(columns={'Salaire (€)': 'Moyenne Svc'})
        df = pd.merge(df, moyennes, on='Service', how='left')
        df['Écart Svc'] = df['Salaire (€)'] - df['Moyenne Svc']
    return df

# --- 6. CHARGEMENT ---
@st.cache_data(ttl=60)
def charger_donnees():
    try:
        sheet = connect_google_sheet()
        
        df_social = pd.DataFrame(sheet.worksheet('Données Sociales').get_all_records())
        df_sal = pd.DataFrame(sheet.worksheet('Salaires').get_all_records())
        df_form = pd.DataFrame(sheet.worksheet('Formation').get_all_records())
        df_rec = pd.DataFrame(sheet.worksheet('Recrutement').get_all_records())
        df_fin = pd.DataFrame(sheet.worksheet('Finances').get_all_records())

        for df in [df_social, df_sal, df_form, df_rec, df_fin]:
            df.columns = [c.strip() for c in df.columns]

        if 'Primes(€)' in df_sal.columns: df_sal.rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        if 'Cout Formation (€)' in df_form.columns: df_form.rename(columns={'Cout Formation (€)': 'Coût Formation (€)'}, inplace=True)
        if 'Coût Formation' in df_form.columns: df_form.rename(columns={'Coût Formation': 'Coût Formation (€)'}, inplace=True)
        if 'Type de Formation' in df_form.columns: df_form.rename(columns={'Type de Formation': 'Type Formation'}, inplace=True)

        if 'Nom' in df_social.columns and 'Nom' in df_sal.columns:
            df_global = pd.merge(df_social, df_sal, on='Nom', how='left')
        else: return None, None, None, None

        if 'Nom' in df_form.columns and 'Coût Formation (€)' in df_form.columns:
            df_form['Coût Formation (€)'] = df_form['Coût Formation (€)'].apply(clean_currency)
            df_form['Coût Formation (€)'] = pd.to_numeric(df_form['Coût Formation (€)'], errors='coerce').fillna(0)
            df_formation_detail = pd.merge(df_form, df_social[['Nom', 'Service', 'CSP']], on='Nom', how='left')
            form_group = df_form.groupby('Nom')['Coût Formation (€)'].sum().reset_index()
            df_global = pd.merge(df_global, form_group, on='Nom', how='left')
            df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)
        else:
            df_global['Coût Formation (€)'] = 0
            df_formation_detail = pd.DataFrame()

        for col in ['Date Ouverture Poste', 'Date Clôture Poste']:
            if col in df_rec.columns: df_rec[col] = pd.to_datetime(df_rec[col], dayfirst=True, errors='coerce')
        
        cols_num = ['Primes (€)', 'Salaire (€)', 'Primes Futures (€)', 'Évaluation (1-5)']
        for c in cols_num:
            if c in df_global.columns: 
                df_global[c] = df_global[c].apply(clean_currency)
                df_global[c] = pd.to_numeric(df_global[c], errors='coerce').fillna(0)

        if 'Coût Recrutement (€)' in df_rec.columns:
            df_rec['Coût Recrutement (€)'] = df_rec['Coût Recrutement (€)'].apply(clean_currency)
            df_rec['Coût Recrutement (€)'] = pd.to_numeric(df_rec['Coût Recrutement (€)'], errors='coerce').fillna(0)

        if 'Au SMIC' not in df_global.columns: df_global['Au SMIC'] = 'Non'
        if 'Catégorie Métier' not in df_global.columns: df_global['Catégorie Métier'] = 'Non défini'

        df_global = calculer_donnees_rh(df_global)
        return df_global, df_fin, df_rec, df_formation_detail

    except Exception as e:
        st.error(f"Erreur Google Sheets : {e}")
        return None, None, None, None

rh, fin, rec, form_detail = charger_donnees()

if rh is not None:
    
    st.sidebar.header("Filtres")
    liste_services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
    filtre_service = st.sidebar.selectbox("Service", liste_services)
    rh_f = rh[rh['Service'] == filtre_service] if filtre_service != 'Tous' else rh
    if not form_detail.empty and 'Service' in form_detail.columns and filtre_service != 'Tous':
        form_f = form_detail[form_detail['Service'] == filtre_service]
    else: form_f = form_detail

    tab_ia, tab_metier, tab_fiche, tab_rem, tab_form, tab_rec, tab_budget, tab_simul = st.tabs([
        "🤖 Assistant", "📂 Métiers", "🔍 Fiche", "📈 Rémunération", "🎓 Formation", "🎯 Recrutement", "💰 Budget", "🔮 Simulation"
    ])

    with tab_ia:
        st.header("🤖 Assistant Expert RH")
        if configure_gemini():
            st.info("Posez une question RH.")
            if "messages" not in st.session_state: st.session_state.messages = []
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])

            if prompt := st.chat_input("Votre question..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"): st.markdown(prompt)
                
                contexte = f"""
                Tu es un Assistant Expert RH.
                DONNÉES :
                - Effectif : {len(rh)}
                - Masse salariale : {rh['Salaire (€)'].sum():,.0f} €
                - Employés : {rh[['Nom', 'Poste', 'Salaire (€)', 'CSP']].to_string()}
                - Recrutements : {rec[['Poste', 'Coût Recrutement (€)']].to_string() if not rec.empty else 'Aucun'}
                
                Question : {prompt}
                """
                
                reply = ask_gemini(contexte)
                with st.chat_message("assistant"): st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
        else:
            st.warning("⚠️ Clé Gemini non configurée")

    # ... [Les autres onglets restent inchangés par rapport à la V51] ...
    # (Je raccourcis ici pour la clarté, mais garde bien tout le reste du code !)
    
    with tab_metier:
        st.header("Cartographie Métiers")
        c1, c2 = st.columns([1, 1])
        with c1:
            if 'CSP' in rh_f.columns and 'Poste' in rh_f.columns:
                fig_sun = px.sunburst(rh_f, path=['CSP', 'Poste'], values='Salaire (€)', title="Masse Salariale", color='CSP', color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(clean_chart(fig_sun), use_container_width=True)
        with c2:
            st.subheader("Annuaire")
            if 'CSP' in rh_f.columns and 'Poste' in rh_f.columns and 'Nom' in rh_f.columns:
                df_d = rh_f.groupby(['CSP', 'Poste'])['Nom'].apply(lambda x: ', '.join(x)).reset_index()
                st.dataframe(df_d, hide_index=True, use_container_width=True)

    with tab_fiche:
        st.header("Dossier Individuel")
        liste_employes = sorted(rh_f['Nom'].unique().tolist())
        choix_employe = st.selectbox("Salarié :", liste_employes)
        if choix_employe:
            emp = rh[rh['Nom'] == choix_employe].iloc[0]
            col_titre, col_btn = st.columns([3, 1])
            with col_titre: st.subheader(f"👤 {emp['Nom']}")
            with col_btn:
                hist = form_detail[form_detail['Nom'] == choix_employe] if not form_detail.empty else pd.DataFrame()
                try:
                    pdf_data = create_pdf(emp, hist)
                    st.download_button(label="📥 TÉLÉCHARGER PDF", data=pdf_data, file_name=f"Fiche_{emp['Nom']}.pdf", mime="application/pdf", use_container_width=True)
                except Exception as e: st.error(f"Erreur PDF: {e}")
            col_id1, col_id2, col_id3, col_id4 = st.columns(4)
            col_id1.info(f"**Poste :** {emp['Poste']}")
            col_id2.info(f"**Service :** {emp['Service']}")
            col_id3.info(f"**Ancienneté :** {emp.get('Ancienneté (ans)', 0):.1f} ans")
            col_id4.info(f"**CSP :** {emp.get('CSP', 'N/A')}")
            st.markdown("---")
            c1, c2 = st.columns([2, 1])
            with c1:
                sal = emp.get('Salaire (€)', 0)
                prime_act = emp.get('Primes (€)', 0)
                prime_fut = emp.get('Primes Futures (€)', 0)
                k1, k2, k3 = st.columns(3)
                k1.metric("Base", f"{sal:,.0f} €")
                k2.metric("Primes", f"{prime_act:,.0f} €")
                k3.metric("Futur", f"{prime_fut:,.0f} €", delta="Prévu")
                st.plotly_chart(clean_chart(px.bar(x=['Actuel', 'Projeté'], y=[sal+prime_act, sal+prime_act+prime_fut], title="Trajectoire", text_auto=True)), use_container_width=True)
            with c2:
                st.subheader("Statut")
                if str(emp.get('Au SMIC', 'No')).lower() == 'oui': st.markdown('<div class="smic-alert">⚠️ Au SMIC</div>', unsafe_allow_html=True)
                else: st.success("✅ Conforme")
            st.subheader("🎓 Formations")
            if not hist.empty: st.dataframe(hist[['Type Formation', 'Coût Formation (€)']], hide_index=True, use_container_width=True)
            else: st.info("Aucune.")

    with tab_rem:
        st.header("Rémunération")
        k1, k2, k3 = st.columns(3)
        k1.metric("Moyenne", f"{rh_f['Salaire (€)'].mean():,.0f} €")
        k2.metric("Masse", f"{rh_f['Salaire (€)'].sum():,.0f} €")
        if 'Sexe' in rh_f.columns:
            df_s = rh_f.groupby('Sexe')['Salaire (€)'].mean()
            ecart = ((df_s.get('Homme', 0) - df_s.get('Femme', 0)) / df_s.get('Homme', 1)) * 100 if 'Homme' in df_s else 0
            k3.metric("Ecart H/F", f"{ecart:.1f} %")
        st.markdown("---")
        if 'Évaluation (1-5)' in rh_f.columns:
            fig_talents = px.scatter(rh_f, x="Évaluation (1-5)", y="Salaire (€)", size="Primes (€)", color="CSP", hover_name="Nom", text="Nom", title="Talents")
            st.plotly_chart(clean_chart(fig_talents), use_container_width=True)

    with tab_form:
        st.header("Formation")
        if not form_f.empty:
            st.metric("Budget", f"{form_f['Coût Formation (€)'].sum():,.0f} €")
            c1, c2 = st.columns(2)
            with c1:
                if 'Type Formation' in form_f.columns: st.plotly_chart(clean_chart(px.pie(form_f, names='Type Formation', values='Coût Formation (€)', hole=0.4)), use_container_width=True)
            with c2:
                if 'CSP' in form_f.columns: st.plotly_chart(clean_chart(px.bar(form_f.groupby('CSP')['Coût Formation (€)'].sum().reset_index(), x='CSP', y='Coût Formation (€)')), use_container_width=True)
        else: st.info("Pas de données.")

    with tab_rec:
        st.header("Recrutement")
        avg_time = rec['Temps Recrutement (jours)'].mean() if 'Temps Recrutement (jours)' in rec.columns else 0
        if 'Date Clôture Poste' in rec.columns and 'Date Ouverture Poste' in rec.columns:
             rec['Temps'] = (rec['Date Clôture Poste'] - rec['Date Ouverture Poste']).dt.days
             avg_time = rec['Temps'].mean()
        total_cout_rec = rec['Coût Recrutement (€)'].sum() if 'Coût Recrutement (€)' in rec.columns else 0
        nb_candidats = rec['Nombre Candidats'].sum() if 'Nombre Candidats' in rec.columns else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Temps Moyen", f"{avg_time:.0f} jours")
        c2.metric("Coût Total", f"{total_cout_rec:,.0f} €")
        c3.metric("Candidats", f"{nb_candidats:,.0f}")
        st.markdown("---")
        if 'Canal Sourcing' in rec.columns:
            df_src = rec.groupby('Canal Sourcing').size().reset_index(name='Nombre')
            st.plotly_chart(clean_chart(px.bar(df_src, x='Canal Sourcing', y='Nombre', color='Canal Sourcing', title="Sources")), use_container_width=True)

    with tab_budget:
        st.header("Budget")
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        form = rh_f['Coût Formation (€)'].sum()
        rec_c = rec['Coût Recrutement (€)'].sum()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Global", f"{ms+form+rec_c:,.0f} €")
        k2.metric("Salaires", f"{ms:,.0f} €")
        k3.metric("Formation", f"{form:,.0f} €")
        k4.metric("Recrutement", f"{rec_c:,.0f} €")
        st.plotly_chart(clean_chart(px.pie(names=['Salaires', 'Formation', 'Recrutement'], values=[ms, form, rec_c], title="Répartition")), use_container_width=True)

    with tab_simul:
        st.header("Simulation")
        augm = st.sidebar.slider("Hausse (%)", 0.0, 100.0, 0.0, 0.5)
        cout = rh_f['Salaire (€)'].sum() * (augm/100) * 12 * 1.45
        st.metric("Impact", f"{cout:,.0f} €", delta="Surcoût", delta_color="inverse")
        marge = fin['Flux'].sum() if 'Flux' in fin.columns else 0
        st.plotly_chart(clean_chart(go.Figure(go.Waterfall(measure=["relative", "relative", "total"], x=["Actuel", "Coût", "Futur"], y=[marge, -cout, marge-cout], decreasing={"marker":{"color":"#fb923c"}}, increasing={"marker":{"color":"#4ade80"}}, totals={"marker":{"color":"#60a5fa"}}))), use_container_width=True)
