import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Configuration
st.set_page_config(page_title="Dashboard V32: Métiers & Annuaire", layout="wide")

# --- DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #1a2639; }
    [data-testid="stSidebar"] { background-color: #111b2b; }
    h1, h2, h3, p, div, label, span, li { color: #FFFFFF !important; }
    [data-testid="stMetric"] {
        background-color: #2d3e55;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #4ade80;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; }
    .smic-alert {
        background-color: #7f1d1d;
        color: white;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #ef4444;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Pilotage Stratégique : RH & Finances")

# --- FONCTIONS ---
def clean_chart(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        xaxis=dict(showgrid=False, color="white"),
        yaxis=dict(showgrid=True, gridcolor="#444444", color="white")
    )
    return fig

def calculer_donnees_rh(df):
    today = datetime.now()
    if 'Date Naissance' in df.columns:
        df['Date Naissance'] = pd.to_datetime(df['Date Naissance'], dayfirst=True, errors='coerce')
        df['Âge'] = (today - df['Date Naissance']).dt.days // 365
    if 'Date Entrée' in df.columns:
        df['Date Entrée'] = pd.to_datetime(df['Date Entrée'], dayfirst=True, errors='coerce')
        df['Ancienneté (ans)'] = (today - df['Date Entrée']).dt.days / 365
    if 'Service' in df.columns and 'Salaire (€)' in df.columns:
        moyennes = df.groupby('Service')['Salaire (€)'].mean().reset_index()
        moyennes = moyennes.rename(columns={'Salaire (€)': 'Moyenne Svc'})
        df = pd.merge(df, moyennes, on='Service', how='left')
        df['Écart Svc'] = df['Salaire (€)'] - df['Moyenne Svc']
    return df

# --- CHARGEMENT ---
@st.cache_data
def charger_donnees():
    try:
        df_social = pd.read_excel('Test_Dashboard.xlsx', sheet_name='Données Sociales')
        df_sal = pd.read_excel('Test_Dashboard.xlsx', sheet_name='Salaires')
        df_form = pd.read_excel('Test_Dashboard.xlsx', sheet_name='Formation')
        df_rec = pd.read_excel('Test_Dashboard.xlsx', sheet_name='Recrutement')
        df_fin = pd.read_excel('Test_Dashboard.xlsx', sheet_name='Finances')

        for df in [df_social, df_sal, df_form, df_rec, df_fin]:
            df.columns = df.columns.str.strip()

        if 'Primes(€)' in df_sal.columns: df_sal.rename(columns={'Primes(€)': 'Primes (€)'}, inplace=True)
        if 'Cout Formation (€)' in df_form.columns: df_form.rename(columns={'Cout Formation (€)': 'Coût Formation (€)'}, inplace=True)
        if 'Type de Formation' in df_form.columns: df_form.rename(columns={'Type de Formation': 'Type Formation'}, inplace=True)

        if 'Nom' in df_social.columns and 'Nom' in df_sal.columns:
            df_global = pd.merge(df_social, df_sal, on='Nom', how='left')
        else: return None, None, None, None

        if 'Nom' in df_form.columns and 'Coût Formation (€)' in df_form.columns:
            df_formation_detail = pd.merge(df_form, df_social[['Nom', 'Service', 'CSP']], on='Nom', how='left')
            form_group = df_form.groupby('Nom')['Coût Formation (€)'].sum().reset_index()
            df_global = pd.merge(df_global, form_group, on='Nom', how='left')
            df_global['Coût Formation (€)'] = df_global['Coût Formation (€)'].fillna(0)
        else:
            df_global['Coût Formation (€)'] = 0
            df_formation_detail = pd.DataFrame()

        for col in ['Date Ouverture Poste', 'Date Clôture Poste']:
            if col in df_rec.columns: df_rec[col] = pd.to_datetime(df_rec[col], dayfirst=True, errors='coerce')

        # Nettoyage pour éviter les crashs
        if 'Primes (€)' in df_global.columns: df_global['Primes (€)'] = df_global['Primes (€)'].fillna(0)
        if 'Salaire (€)' in df_global.columns: df_global['Salaire (€)'] = df_global['Salaire (€)'].fillna(0)
        if 'Au SMIC' not in df_global.columns: df_global['Au SMIC'] = 'Non'
        if 'Évaluation (1-5)' not in df_global.columns: df_global['Évaluation (1-5)'] = 0
        else: df_global['Évaluation (1-5)'] = df_global['Évaluation (1-5)'].fillna(0)

        df_global = calculer_donnees_rh(df_global)
        return df_global, df_fin, df_rec, df_formation_detail

    except Exception as e:
        st.error(f"Erreur : {e}")
        return None, None, None, None

rh, fin, rec, form_detail = charger_donnees()

if rh is not None:
    
    # FILTRES
    st.sidebar.header("Filtres")
    liste_services = ['Tous'] + sorted(rh['Service'].unique().tolist()) if 'Service' in rh.columns else ['Tous']
    filtre_service = st.sidebar.selectbox("Service", liste_services)
    rh_f = rh[rh['Service'] == filtre_service] if filtre_service != 'Tous' else rh
    
    if not form_detail.empty and 'Service' in form_detail.columns and filtre_service != 'Tous':
        form_f = form_detail[form_detail['Service'] == filtre_service]
    else:
        form_f = form_detail

    # ONGLETS
    tab_metier, tab_fiche, tab_rem, tab_form, tab_budget, tab_simul = st.tabs([
        "📂 Métiers & Annuaire", "🔍 Fiche Employé", "📈 Rémunération & Talents", "🎓 Formation", "💰 Budget", "🔮 Simulation"
    ])

    # --- 1. MÉTIERS (MODIFIÉ) ---
    with tab_metier:
        st.header("Cartographie des Métiers")
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.subheader("Répartition Hiérarchique")
            # MODIFICATION ICI : On utilise CSP -> Poste (plus logique)
            if 'CSP' in rh_f.columns and 'Poste' in rh_f.columns:
                fig_sun = px.sunburst(
                    rh_f, 
                    path=['CSP', 'Poste'], # On groupe d'abord par CSP, puis par Poste
                    values='Salaire (€)', 
                    title="Masse Salariale par CSP > Poste",
                    color='CSP', 
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                st.plotly_chart(clean_chart(fig_sun), use_container_width=True)
            else:
                st.warning("Vérifiez vos colonnes CSP et Poste.")

        with c2:
            st.subheader("Effectifs par Catégorie")
            if 'CSP' in rh_f.columns:
                df_csp = rh_f['CSP'].value_counts().reset_index()
                df_csp.columns = ['CSP', 'Effectif']
                fig_bar = px.bar(df_csp, x='CSP', y='Effectif', color='CSP', text_auto=True, color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(clean_chart(fig_bar), use_container_width=True)

        # --- AJOUT : ANNUAIRE PAR MÉTIER ---
        st.markdown("---")
        st.subheader("🕵️‍♂️ Qui fait quoi ? (Annuaire Interactif)")
        
        # Filtre rapide interne à l'onglet
        col_search1, col_search2 = st.columns(2)
        choix_csp = col_search1.multiselect("Filtrer par CSP", rh_f['CSP'].unique())
        choix_poste = col_search2.multiselect("Filtrer par Poste", rh_f['Poste'].unique())
        
        # Filtrage dynamique du tableau
        df_annuaire = rh_f.copy()
        if choix_csp:
            df_annuaire = df_annuaire[df_annuaire['CSP'].isin(choix_csp)]
        if choix_poste:
            df_annuaire = df_annuaire[df_annuaire['Poste'].isin(choix_poste)]
            
        # Affichage du tableau propre
        st.dataframe(
            df_annuaire[['Nom', 'Poste', 'CSP', 'Service', 'Email'] if 'Email' in df_annuaire.columns else ['Nom', 'Poste', 'CSP', 'Service']],
            use_container_width=True,
            hide_index=True
        )

    # --- 2. FICHE ---
    with tab_fiche:
        st.header("Dossier Individuel")
        liste_employes = sorted(rh_f['Nom'].unique().tolist())
        choix_employe = st.selectbox("Salarié :", liste_employes)
        if choix_employe:
            emp = rh[rh['Nom'] == choix_employe].iloc[0]
            col_id1, col_id2, col_id3, col_id4 = st.columns(4)
            col_id1.info(f"**{emp['Nom']}**")
            col_id2.info(f"{emp['Poste']} ({emp.get('CSP', '')})")
            col_id3.info(f"Service : {emp['Service']}")
            col_id4.info(f"Ancienneté : {emp.get('Ancienneté (ans)', 0):.1f} ans")
            
            st.markdown("---")
            c1, c2 = st.columns([2,1])
            with c1:
                sal = emp.get('Salaire (€)', 0)
                # Sécurisation si Primes Futures n'existe pas
                prime_fut = emp.get('Primes Futures (€)', 0) if pd.notna(emp.get('Primes Futures (€)')) else 0
                prime_act = emp.get('Primes (€)', 0)
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Salaire Base", f"{sal:,.0f} €")
                k2.metric("Primes Actu.", f"{prime_act:,.0f} €")
                k3.metric("Primes Futures", f"{prime_fut:,.0f} €", delta="Prévu")

                st.plotly_chart(clean_chart(px.bar(x=['Actuel', 'Projeté'], y=[sal+prime_act, sal+prime_act+prime_fut], title="Trajectoire Salariale", text_auto=True)), use_container_width=True)
            with c2:
                st.subheader("Alertes")
                if str(emp.get('Au SMIC', 'No')).lower() == 'oui': st.markdown('<div class="smic-alert">⚠️ Au SMIC</div>', unsafe_allow_html=True)
                else: st.success("Salaire > SMIC")

            st.markdown("---")
            st.subheader("🎓 Historique Formations")
            if not form_detail.empty:
                hist = form_detail[form_detail['Nom'] == choix_employe]
                if not hist.empty: st.dataframe(hist[['Type Formation', 'Coût Formation (€)']], hide_index=True, use_container_width=True)
                else: st.info("Aucune formation.")

    # --- 3. STRATÉGIE REM ---
    with tab_rem:
        st.header("Rémunération & Talents")
        k1, k2, k3 = st.columns(3)
        k1.metric("Salaire Moyen", f"{rh_f['Salaire (€)'].mean():,.0f} €")
        k2.metric("Masse Salariale", f"{rh_f['Salaire (€)'].sum():,.0f} €")
        if 'Sexe' in rh_f.columns:
            df_s = rh_f.groupby('Sexe')['Salaire (€)'].mean()
            ecart = ((df_s.get('Homme', 0) - df_s.get('Femme', 0)) / df_s.get('Homme', 1)) * 100 if 'Homme' in df_s else 0
            k3.metric("Index H/F", f"{ecart:.1f} %", delta="Cible 0%", delta_color="inverse")

        st.markdown("---")
        st.subheader("🎯 Matrice des Talents")
        if 'Évaluation (1-5)' in rh_f.columns and 'Salaire (€)' in rh_f.columns:
            fig_talents = px.scatter(rh_f, x="Évaluation (1-5)", y="Salaire (€)", size="Primes (€)", color="CSP", hover_name="Nom", text="Nom", title="Performance vs Salaire")
            fig_talents.add_hline(y=rh_f['Salaire (€)'].mean(), line_dash="dot", line_color="white")
            fig_talents.add_vline(x=rh_f['Évaluation (1-5)'].mean(), line_dash="dot", line_color="white")
            fig_talents.update_traces(textposition='top center')
            st.plotly_chart(clean_chart(fig_talents), use_container_width=True)

    # --- 4. FORMATION ---
    with tab_form:
        st.header("Formation")
        if not form_f.empty:
            budget_form = form_f['Coût Formation (€)'].sum()
            st.metric("Budget Consommé", f"{budget_form:,.0f} €")
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                if 'Type Formation' in form_f.columns:
                    st.plotly_chart(clean_chart(px.pie(form_f.groupby('Type Formation')['Coût Formation (€)'].sum().reset_index(), values='Coût Formation (€)', names='Type Formation', hole=0.4, title="Par Thème")), use_container_width=True)
            with c_f2:
                if 'CSP' in form_f.columns:
                    st.plotly_chart(clean_chart(px.bar(form_f.groupby('CSP')['Coût Formation (€)'].sum().reset_index(), x='CSP', y='Coût Formation (€)', title="Par CSP", color='Coût Formation (€)')), use_container_width=True)
        else: st.info("Aucune donnée.")

    # --- 5. BUDGET ---
    with tab_budget:
        st.header("Consolidation")
        ms = rh_f['Salaire (€)'].sum() * 12 * 1.45
        form = rh_f['Coût Formation (€)'].sum()
        rec_c = rec['Coût Recrutement (€)'].sum()
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Global", f"{ms+form+rec_c:,.0f} €")
        k2.metric("Salaires", f"{ms:,.0f} €")
        k3.metric("Formation", f"{form:,.0f} €")
        k4.metric("Recrutement", f"{rec_c:,.0f} €")
        st.plotly_chart(clean_chart(px.pie(names=['Salaires', 'Formation', 'Recrutement'], values=[ms, form, rec_c], title="Répartition")), use_container_width=True)

    # --- 6. SIMULATION ---
    with tab_simul:
        st.header("Simulation")
        augm = st.sidebar.slider("Hausse (%)", 0.0, 100.0, 0.0, 0.5)
        cout = rh_f['Salaire (€)'].sum() * (augm/100) * 12 * 1.45
        st.metric("Impact", f"{cout:,.0f} €", delta="Surcoût", delta_color="inverse")
        marge = fin['Flux'].sum() if 'Flux' in fin.columns else 0
        fig = go.Figure(go.Waterfall(measure=["relative", "relative", "total"], x=["Actuel", "Coût", "Futur"], y=[marge, -cout, marge-cout]))
        st.plotly_chart(clean_chart(fig), use_container_width=True)