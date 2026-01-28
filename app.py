import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import re
from streamlit_option_menu import option_menu

# --- CONFIGURATION ---
st.set_page_config(page_title="H&C Manager Pro V94", layout="wide")

# --- DESIGN & CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .card { background-color: #1f2937; padding: 25px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 25px; }
    .kpi-val { font-size: 32px; font-weight: 800; color: #38bdf8; }
    .kpi-lbl { font-size: 14px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }
    .alert-card { background-color: #450a0a; border: 1px solid #ef4444; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    h1, h2, h3, p, div, label { color: #FFFFFF !important; }
    div.stButton > button { background-color: #38bdf8 !important; color: #0e1117 !important; font-weight: bold !important; border-radius: 8px !important; }
    .login-logo { font-size: 90px; font-weight: 900; color: #38bdf8 !important; text-align: center; line-height: 1; }
    .login-subtitle { font-size: 24px; color: #9ca3af !important; letter-spacing: 3px; text-align: center; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def to_num(val):
    if pd.isna(val) or val == "": return 0
    if isinstance(val, (int, float)): return float(val)
    cleaned = re.sub(r'[^0-9,-]', '', str(val)).replace(',', '.')
    try: return float(cleaned)
    except: return 0

def connect_gs(sheet_name):
    try:
        secrets = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(secrets, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open(sheet_name)
    except: return None

def clean_df(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df

def save_data(df, sheet_name, worksheet_name):
    try:
        sh = connect_gs(sheet_name)
        ws = sh.worksheet(worksheet_name)
        df_save = df.copy().fillna("")
        for col in df_save.columns:
            if pd.api.types.is_datetime64_any_dtype(df_save[col]):
                df_save[col] = df_save[col].dt.strftime('%d/%m/%Y')
        ws.clear()
        ws.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.toast(f"✅ {worksheet_name} synchronisé !"); time.sleep(1); st.cache_data.clear(); st.rerun()
    except Exception as e: st.error(f"Erreur sauvegarde : {e}")

# --- AUTHENTIFICATION ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<h1 class='login-logo'>H&C</h1><p class='login-subtitle'>Manager Pro</p>", unsafe_allow_html=True)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.button("SE CONNECTER", use_container_width=True):
            if u == "admin" and p == "rh123": st.session_state['logged_in'] = True; st.rerun()
            else: st.error("Identifiants incorrects")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    st.markdown("<h2 style='color: #38bdf8; text-align: center; font-weight: 900;'>H&C ADMIN</h2>", unsafe_allow_html=True)
    app_mode = option_menu("ESPACE", ["RH", "Commercial"], icons=['people-fill', 'briefcase-fill'], default_index=0)
    st.markdown("---")
    if app_mode == "RH":
        menu = ["Dashboard", "Formation", "Recrutement", "Admin RH"]
        icons = ["speedometer2", "mortarboard", "bullseye", "database-gear"]
        target = "Dashboard_Data"
    else:
        menu = ["Pipeline CRM", "Historique Ventes", "Admin Sales"]
        icons = ["funnel", "graph-up-arrow", "database-lock"]
        target = "Commercial_Data"
    selected = option_menu(None, menu, icons=icons, default_index=0)
    if st.button("🚪 Déconnexion", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()

# --- CHARGEMENT ---
sh = connect_gs(target)
raw = {}
if sh:
    for ws in sh.worksheets():
        try: raw[ws.title] = clean_df(pd.DataFrame(ws.get_all_records()))
        except: raw[ws.title] = pd.DataFrame()
else: st.error("Fichier introuvable"); st.stop()

# --- ESPACE RH ---
if app_mode == "RH":
    df_soc = raw.get('Données Sociales', pd.DataFrame())
    df_sal = raw.get('Salaires', pd.DataFrame())
    df_gl = pd.merge(df_soc, df_sal, on='Nom', how='left') if not df_soc.empty and not df_sal.empty else df_soc

    if selected == "Dashboard":
        st.title("📊 Cockpit BI - Ressources Humaines")
        df_gl['Sal_N'] = df_gl['Salaire (€)'].apply(to_num)
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='card'><div class='kpi-val'>{len(df_soc)}</div><div class='kpi-lbl'>Effectif</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><div class='kpi-val'>{df_gl['Sal_N'].sum():,.0f} €</div><div class='kpi-lbl'>Masse Salariale / Mois</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><div class='kpi-val'>2.4%</div><div class='kpi-lbl'>Absentéisme</div></div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<div class='card'><h3>Pyramide des Âges</h3>", unsafe_allow_html=True)
            if 'Date Naissance' in df_soc.columns:
                df_soc['Date Naissance'] = pd.to_datetime(df_soc['Date Naissance'], dayfirst=True, errors='coerce')
                df_soc['Âge'] = df_soc['Date Naissance'].apply(lambda x: (datetime.now() - x).days // 365 if pd.notnull(x) else 0)
                st.plotly_chart(px.histogram(df_soc, x='Âge', color='Sexe', barmode='group', color_discrete_map={'Homme':'#38bdf8','Femme':'#ec4899'}), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown("<div class='card'><h3>Masse Salariale / Service</h3>", unsafe_allow_html=True)
            ms_svc = df_gl.groupby('Service')['Sal_N'].sum().reset_index().sort_values('Sal_N', ascending=False)
            st.plotly_chart(px.bar(ms_svc, x='Service', y='Sal_N', color='Service'), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Formation":
        st.title("🎓 Dashboard Formation")
        df_f = raw.get('Formation', pd.DataFrame())
        if not df_f.empty:
            df_f['Cout_N'] = df_f['Coût Formation (€)'].apply(to_num)
            df_f_svc = pd.merge(df_f, df_soc[['Nom', 'Service']], on='Nom', how='left')
            st.markdown("<div class='card'><h3>Budget par Service</h3>", unsafe_allow_html=True)
            st.plotly_chart(px.pie(df_f_svc, values='Cout_N', names='Service', hole=0.5), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.dataframe(df_f, use_container_width=True)

    elif selected == "Recrutement":
        st.title("🎯 Gestion Recrutement")
        df_r = raw.get('Recrutement', pd.DataFrame())
        if not df_r.empty:
            st.markdown("<div class='card'><h3>Candidats par Canal</h3>", unsafe_allow_html=True)
            st.plotly_chart(px.bar(df_r, x='Poste', y='Nombre Candidats', color='Canal Sourcing'), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# --- ESPACE COMMERCIAL ---
elif app_mode == "Commercial":
    df_v = raw.get('Ventes', pd.DataFrame())
    df_p = raw.get('Pipeline', pd.DataFrame())

    if selected == "Pipeline CRM":
        st.title("🎯 Pipeline CRM Stratégique")
        if not df_p.empty:
            df_p['Montant_N'] = df_p['Montant estimé'].apply(to_num)
            df_p['Prob_N'] = df_p['Probabilité (%)'].apply(to_num) / 100
            df_p['Pondéré'] = df_p['Montant_N'] * df_p['Prob_N']
            
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div class='card'><div class='kpi-val'>{df_p['Montant_N'].sum():,.0f} €</div><div class='kpi-lbl'>Volume Total Pipe</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='card'><div class='kpi-val' style='color:#10b981;'>{df_p['Pondéré'].sum():,.0f} €</div><div class='kpi-lbl'>CA Probable (Pondéré)</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='card'><div class='kpi-val'>{len(df_p)}</div><div class='kpi-lbl'>Deals en cours</div></div>", unsafe_allow_html=True)

            colA, colB = st.columns([2, 1])
            with colA:
                st.markdown("<div class='card'><h3>Entonnoir de Vente Logique</h3>", unsafe_allow_html=True)
                if 'Étape' in df_p.columns:
                    # FIX : ORDRE LOGIQUE DU FUNNEL
                    ordre_logique = ["Prospection", "Qualification", "Proposition", "Négociation"]
                    df_funnel = df_p.groupby('Étape')['Montant_N'].sum().reset_index()
                    df_funnel['Étape'] = pd.Categorical(df_funnel['Étape'], categories=ordre_logique, ordered=True)
                    df_funnel = df_funnel.sort_values('Étape')
                    
                    fig_f = px.funnel(df_funnel, x='Montant_N', y='Étape', color_discrete_sequence=['#38bdf8'])
                    fig_f.update_traces(textinfo="value+percent initial")
                    fig_f.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
                    st.plotly_chart(fig_f, use_container_width=True)
                else: st.warning("Ajoutez une colonne 'Étape' (Prospection, Qualification, Proposition, Négociation).")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with colB:
                st.markdown("<div class='card'><h3>🚀 Relances Urgentes</h3>", unsafe_allow_html=True)
                urgents = df_p[df_p['Prob_N'] >= 0.7].sort_values('Montant_N', ascending=False)
                for _, row in urgents.iterrows():
                    st.markdown(f"<div class='alert-card'><b>{row['Nom opportunité']}</b><br/>{row['Client']} — <b>{row['Montant_N']:,.0f} €</b><br/><small>Probabilité : {row['Prob_N']*100:.0f}%</small></div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "Historique Ventes":
        st.title("📊 Analyse du CA")
        if not df_v.empty:
            df_v['Date'] = pd.to_datetime(df_v['Date'], dayfirst=True, errors='coerce')
            df_v['Mois'] = df_v['Date'].dt.strftime('%Y-%m')
            df_mois = df_v.groupby('Mois')['Montant HT'].apply(lambda x: sum(to_num(i) for i in x)).reset_index()
            st.markdown("<div class='card'><h3>Évolution Mensuelle</h3>", unsafe_allow_html=True)
            st.plotly_chart(px.line(df_mois, x='Mois', y='Montant HT', markers=True, color_discrete_sequence=['#38bdf8']), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.dataframe(df_v, use_container_width=True)

# --- ADMINISTRATION ---
if "Admin" in selected:
    st.title(f"🛠️ Administration des Données")
    tabs = st.tabs([t.replace('_', ' ') for t in raw.keys()])
    for i, t_name in enumerate(raw.keys()):
        with tabs[i]:
            edited = st.data_editor(raw[t_name], num_rows="dynamic", use_container_width=True, key=f"ed_{t_name}")
            if st.button(f"💾 SAUVEGARDER {t_name.upper()}", use_container_width=True):
                save_data(edited, target, t_name)
