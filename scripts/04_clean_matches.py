# ============================================================
# ARCHIVO: 04_clean_matches.py
# Proyecto: Pulso + Poisson - Modelo de Prediccion Mundial 2026
# Descripcion: Explora y valida el historial de partidos
#              mundialistas (wc_all_matches.csv) para calcular
#              promedios de goles y detectar anomalias.
# ============================================================

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent   # raiz del repo
DATA_DIR = BASE_DIR / 'data'

# --- CARGA ---
matches = pd.read_csv(DATA_DIR / 'wc_all_matches.csv')

# --- REVISION GENERAL ---
print("=== COLUMNAS DISPONIBLES ===")
print(matches.columns.tolist())

print("\n=== VALORES NULOS ===")
print(matches.isnull().sum())

print("\n=== TIPOS DE DATO ===")
print(matches.dtypes)

print("\n=== VALORES UNICOS EN STAGE ===")
print(matches['stage'].value_counts())

print("\n=== RANGO DE ANIOS ===")
print(f"Desde: {matches['year'].min()}")
print(f"Hasta: {matches['year'].max()}")

print("\n=== GOLES MAXIMOS EN UN PARTIDO ===")
print(f"Mayor score1: {matches['score1'].max()}")
print(f"Mayor score2: {matches['score2'].max()}")
print(matches[matches['score1'] == matches['score1'].max()])

# --- REVISION PROFUNDA ---
print("\n=== ANIOS DISPONIBLES ===")
print(matches['year'].value_counts().sort_index())

print("\n=== ULTIMOS 10 PARTIDOS DEL DATASET ===")
print(matches.tail(10).to_string())

print("\n=== PARTIDOS POR ANIO RECIENTE ===")
recientes = matches[matches['year'] >= 2018]
print(recientes[['year', 'stage', 'team1', 'score1', 'score2', 'team2']].to_string())
