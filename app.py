import streamlit as st
import pandas as pd
import duckdb
import sqlite3
import os
import altair as alt

st.set_page_config(page_title="Inventario Ristorante", layout="wide")

# Percorsi database
DB_PATH = "inventario.db"

# Creazione DB se non esiste
if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    pd.read_csv("prodotti_magazzino.csv").to_sql("prodotti_magazzino", conn, if_exists="replace", index=False)
    pd.read_csv("menu.csv").to_sql("menu", conn, if_exists="replace", index=False)
    conn.close()

# Connessione DuckDB via SQLite
con = duckdb.connect()
con.execute(f"INSTALL sqlite; LOAD sqlite;")
con.execute(f"ATTACH DATABASE '{DB_PATH}' AS db;")

# Sidebar con navigazione
st.sidebar.title("📂 Menu Navigazione")
section = st.sidebar.radio("Vai a:", ["🏠 Home", "📊 Analytics", "📦 Prodotti Magazzino", "🍽️ Menu", "🧾 Vendite"])

# Upload vendite sempre visibile
st.sidebar.markdown("---")
st.sidebar.subheader("📤 Carica Vendite")
uploaded_vendite = st.sidebar.file_uploader("Carica vendite.csv", type=["csv"])

if uploaded_vendite:
    df_vendite = pd.read_csv(uploaded_vendite)
    df_vendite.to_sql("vendite", sqlite3.connect(DB_PATH), if_exists="replace", index=False)
    st.sidebar.success("✅ Vendite caricate nel database")

# HOME
if section == "🏠 Home":
    st.title("Benvenuto nel Sistema di Gestione Magazzino")
    st.markdown("""
    Questo MVP (Minimum Viable Product) è progettato per aiutare i ristoratori a tenere sotto controllo l'inventario del magazzino in modo automatizzato, efficiente e visuale.

    ### 🧠 Come funziona:
    1. Ogni piatto del menu è associato a una ricetta che definisce i prodotti utilizzati e le relative quantità.
    2. L'utente carica giornalmente un file `vendite.csv` con le quantità vendute per ogni piatto.
    3. L'applicazione calcola automaticamente il consumo degli ingredienti in base alle vendite.
    4. L'inventario viene aggiornato e vengono segnalati i prodotti che hanno superato la soglia di riordino.

    ### 🔍 Cosa puoi fare:
    - **Caricare vendite** da file CSV (colonne: `data`, `piatto`, `quantità_venduta`)
    - **Monitorare il magazzino** con stato aggiornato in tempo reale
    - **Analizzare dati** con grafici dinamici e tabelle interattive
    - **Gestire ricette** nel menu e aggiornare prodotti e soglie

    ⚠️ Assicurati di caricare prima i file `prodotti_magazzino.csv` e `menu.csv` per ottenere risultati corretti.

    📥 Carica le vendite giornaliere dalla **barra laterale** e guarda come l'inventario si aggiorna in automatico!
    """)

# ANALYTICS
elif section == "📊 Analytics":
    st.title("📈 Reportistica e Analisi")
    st.markdown("### 🔍 Panoramica delle vendite e dell'inventario")

    try:
        vendite_df = con.execute("SELECT * FROM db.vendite").fetchdf()
    except Exception:
        st.warning("⚠️ Nessuna vendita disponibile nel database. Carica un file nella sidebar.")
        vendite_df = pd.DataFrame(columns=["data", "piatto", "quantità_venduta"])

    menu_df = con.execute("SELECT * FROM db.menu").fetchdf()
    total_sales = vendite_df["quantità_venduta"].sum()
    unique_dishes = vendite_df["piatto"].nunique()
    most_sold = vendite_df.groupby("piatto")["quantità_venduta"].sum().sort_values(ascending=False).reset_index()
    top_dish = most_sold.iloc[0] if not most_sold.empty else {"piatto": "N/A", "quantità_venduta": 0}

    col1, col2, col3 = st.columns(3)
    col1.metric("🍽️ Totale Piatti Venduti", total_sales)
    col2.metric("📋 Piatti Diversi Venduti", unique_dishes)
    col3.metric("🏆 Piatto più venduto", f"{top_dish['piatto']} ({top_dish['quantità_venduta']})")

    # Tabelle piatti più ordinati e consumo
    consumo_df = vendite_df.merge(menu_df, on="piatto")
    consumo_df["consumo_totale"] = consumo_df["quantità_venduta"] * consumo_df["quantità_prodotto"]
    consumo_totale_df = consumo_df.groupby("prodotto")["consumo_totale"].sum().reset_index()

    st.markdown("### 📋 Tabelle Analitiche")
    t1, t2 = st.columns(2)
    with t1:
        st.subheader("📌 Piatti più Ordinati")
        st.dataframe(most_sold, height=300)
    with t2:
        st.subheader("🔎 Consumo Ingredienti")
        st.dataframe(consumo_totale_df, height=300)

    # Grafico consumo
    st.markdown("### 📊 Visualizzazioni")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("🍅 Ingredienti più Utilizzati")
        chart = alt.Chart(consumo_totale_df).mark_bar(color='#1f77b4').encode(
            x=alt.X("prodotto", sort="-y"),
            y="consumo_totale",
            tooltip=["prodotto", "consumo_totale"]
        ).properties(width=350, height=300)
        st.altair_chart(chart, use_container_width=True)
    with g2:
        st.subheader("🍽️ Piatti più Ordinati")
        chart_dishes = alt.Chart(most_sold).mark_bar(color='#ff7f0e').encode(
            x=alt.X("piatto", sort="-y"),
            y="quantità_venduta",
            tooltip=["piatto", "quantità_venduta"]
        ).properties(width=350, height=300)
        st.altair_chart(chart_dishes, use_container_width=True)

    # Grafico prodotti sotto soglia
    st.markdown("### 🚨 Prodotti da Riordinare")
    try:
        inventario_df = con.execute("SELECT * FROM db.prodotti_magazzino").fetchdf()
        consumo_df = vendite_df.merge(menu_df, on="piatto")
        consumo_df["consumo_totale"] = consumo_df["quantità_venduta"] * consumo_df["quantità_prodotto"]
        consumo_totale_df = consumo_df.groupby("prodotto")["consumo_totale"].sum().reset_index()
        inventario_df = inventario_df.merge(consumo_totale_df, on="prodotto", how="left").fillna(0)
        inventario_df["quantità_aggiornata"] = inventario_df["quantità_attuale"] - inventario_df["consumo_totale"]
        inventario_df["sotto_soglia"] = inventario_df["quantità_aggiornata"] < inventario_df["soglia_riordino"]
        sotto_df = inventario_df[inventario_df["sotto_soglia"] == True]
        if not sotto_df.empty:
            soglia_chart = alt.Chart(sotto_df).mark_bar(color='#d62728').encode(
                x=alt.X("prodotto", sort="-y"),
                y="quantità_aggiornata",
                tooltip=["prodotto", "quantità_aggiornata", "soglia_riordino"]
            ).properties(width=800)
            st.altair_chart(soglia_chart, use_container_width=True)
        else:
            st.success("✅ Nessun prodotto sotto soglia.")
    except Exception:
        st.info("ℹ️ Nessun dato disponibile per i prodotti da riordinare.")
    

# MAGAZZINO
elif section == "📦 Prodotti Magazzino":
    st.title("📦 Inventario Magazzino")

    try:
        magazzino_df = con.execute("SELECT * FROM db.prodotti_magazzino").fetchdf()
    except Exception:
        st.warning("⚠️ Nessun inventario disponibile nel database. Carica un file nella sezione sottostante.")
        magazzino_df = pd.DataFrame(columns=["prodotto", "quantità_attuale", "unità", "soglia_riordino"])

    try:
        vendite_df = con.execute("SELECT * FROM db.vendite").fetchdf()
    except Exception:
        st.warning("⚠️ Nessuna vendita disponibile nel database. Carica un file nella sidebar.")
        vendite_df = pd.DataFrame(columns=["data", "piatto", "quantità_venduta"])

    menu_df = con.execute("SELECT * FROM db.menu").fetchdf()

    # Calcolo consumo
    consumo_df = vendite_df.merge(menu_df, on="piatto")
    consumo_df["consumo_totale"] = consumo_df["quantità_venduta"] * consumo_df["quantità_prodotto"]
    consumo_totale_df = consumo_df.groupby("prodotto")["consumo_totale"].sum().reset_index()

    inventario_df = magazzino_df.merge(consumo_totale_df, on="prodotto", how="left").fillna(0)
    inventario_df["quantità_aggiornata"] = inventario_df["quantità_attuale"] - inventario_df["consumo_totale"]
    inventario_df["sotto_soglia"] = inventario_df["quantità_aggiornata"] < inventario_df["soglia_riordino"]

    st.dataframe(inventario_df[["prodotto", "quantità_aggiornata", "unità", "soglia_riordino", "sotto_soglia"]])

    if inventario_df["sotto_soglia"].any():
        st.warning("⚠️ Alcuni prodotti sono sotto la soglia di riordino!")

    st.subheader("📤 Aggiorna Inventario da CSV")
    upload_inv = st.file_uploader("Carica nuovo prodotti_magazzino.csv", type=["csv"], key="upload_inv")
    if upload_inv:
        df_new_inv = pd.read_csv(upload_inv)
        df_new_inv.to_sql("prodotti_magazzino", sqlite3.connect(DB_PATH), if_exists="replace", index=False)
        st.success("✅ Inventario aggiornato!")

# MENU
elif section == "🍽️ Menu":
    st.title("🍽️ Menu - Ricette Piatti")

    menu_df = con.execute("SELECT * FROM db.menu").fetchdf()
    st.dataframe(menu_df)

    st.subheader("📤 Aggiorna Menu da CSV")
    upload_menu = st.file_uploader("Carica nuovo menu.csv", type=["csv"], key="upload_menu")
    

# VENDITE
elif section == "🧾 Vendite":
    st.title("🧾 Storico Vendite Caricate")
    try:
        vendite_df = con.execute("SELECT * FROM db.vendite").fetchdf()
        st.dataframe(vendite_df)
    except Exception:
        st.info("📭 Nessuna vendita registrata nel sistema.")
    
