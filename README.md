# ⚽ Pulso + Poisson — Predicción Estadística del Mundial 2026

Modelo predictivo del **FIFA World Cup 2026** que combina un índice de fortaleza construido en Power BI (**PowerScore**), un modelo de goles basado en la **distribución de Poisson** en Python y una **simulación Monte Carlo de 10,000 torneos completos** con el bracket oficial FIFA.

> 🏆 **Campeón más probable: Bélgica (3.38%)** — y ninguna selección supera el 3.5%: el Mundial más abierto de la historia.

---

## 📌 Resultados clave

| # | Hallazgo |
|---|---|
| 1 | **Corea del Sur es el 5° favorito al título (1.37%)**, por encima de Brasil, España, Francia e Inglaterra |
| 2 | **La paradoja alemana:** Alemania lidera la probabilidad de llegar a semis (23%) pero solo alcanza la final en 4.4% de las simulaciones |
| 3 | **Francia es #1 en PowerScore (100.0), pero no es la favorita** — el bracket redistribuye las probabilidades |
| 4 | El **Grupo D** es el más impredecible: solo 9.1% de certeza en su orden final |
| 5 | **Colombia (0.45%)** supera a Francia, Inglaterra y Países Bajos en probabilidad de título |

Cruce más probable de 16avos: **Argentina vs España (30.8%)**. Final más frecuente: **Alemania vs Corea del Sur (3.9%)**.

---

## 🧠 Metodología (3 capas)

### 1. PowerScore (Power BI + DAX)
Índice de fortaleza 0–100 por selección:

```
PowerScore = MarketScore × 0.40 + RankScore × 0.35 + FormScore × 0.25
```

- **MarketScore**: percentil del valor de mercado de la plantilla (universo de 211 selecciones, Transfermarkt)
- **RankScore**: ranking FIFA normalizado
- **FormScore**: últimos 5 partidos con puntos ajustados por la calidad del rival

### 2. Modelo Poisson (Python)
Cada partido se modela estimando los goles esperados (λ) de cada equipo:

```
λ_equipo1 = attack_final[equipo1] × defense_final[equipo2] × league_avg_goals
```

Pipeline: corrección de orientación local/visitante → ajuste ofensivo/defensivo por fuerza del rival → regularización (shrinkage) por muestra corta → multiplicador exponencial de calidad estructural (calibrado con C=1.0) → matriz 7×7 de probabilidades de marcador por partido.

### 3. Simulación Monte Carlo
- **10,000 iteraciones** del torneo completo (seed=42)
- Formato real 2026: 48 equipos, 12 grupos, clasifican los 2 primeros + los 8 mejores terceros
- Eliminatorias con el **bracket oficial FIFA (M73–M104)**, con asignación dinámica de mejores terceros
- Output: probabilidad de cada selección de alcanzar cada ronda

---

## 📂 Estructura del repositorio

```
poisson-worldcup-2026/
├── scripts/
│   ├── 01_scrape_market_values.py    # Scraping de valores de mercado (Transfermarkt)
│   ├── 02_scrape_recent_form.py      # Scraping de forma reciente (últimos 5 partidos)
│   ├── 03_scrape_fifa_rankings.py    # Scraping de ranking y metadata FIFA
│   ├── 04_clean_matches.py           # Limpieza y estandarización de datos
│   └── 05_poisson_montecarlo.py      # Modelo Poisson + simulación Monte Carlo
├── data/
│   ├── recent_form_240_matches.xlsx  # Dataset limpio: 240 partidos con venue
│   ├── market_values_211_teams.xlsx  # 211 selecciones con valor de mercado
│   ├── wc_2026_teams.csv             # 48 selecciones del Mundial
│   └── wc_2026_fixtures.csv          # Calendario oficial (corregido)
│   ├── wc_all_matches.csv            # Histórico de partidos mundialistas
├── outputs/
│   ├── poisson_predictions.csv       # 72 predicciones de fase de grupos
│   ├── qualification_probabilities.csv
│   ├── knockout_probabilities.csv    # Probabilidades por ronda
│   ├── match_score_heatmap.csv       # 3,528 probabilidades de marcador
│   ├── bracket_most_likely.csv
│   ├── bracket_16avos.csv
│   ├── team_master.csv
│   └── group_certainty.csv
├── docs/
│   ├── PROCESO_COMPLETO.md           # Documentación completa del proceso
│   └── Forecast_FIFA_World_Cup_2026-Alejandro_Lopez_S.pdf   # Presentación del proyecto
└── README.md
```

## ▶️ Cómo ejecutar

```bash
# Requisitos
pip install pandas numpy scipy openpyxl requests beautifulsoup4

# Ejecutar el modelo (desde la raíz del proyecto)
python scripts/05_poisson_montecarlo.py
```

Los CSV de salida usan **punto como separador decimal**. En Power BI con configuración regional en español, importar con locale `en-US` en Power Query.

---

## 🧹 La parte que nadie ve: la batalla de los datos

El 80% del trabajo fue de ingeniería de datos, no de modelado. Bugs encontrados y corregidos:

- **Marcador invertido:** el dataset guardaba los resultados siempre como local-visitante; para los partidos de visitante el marcador quedaba al revés. Francia aparecía con 4 derrotas cuando tenía 4 victorias.
- **Partido fantasma:** el calendario oficial descargado duplicaba una jornada del Grupo C — Brasil nunca enfrentaba a Haití en las simulaciones.
- **Selección invisible:** Uzbekistán no aparecía en ninguna fuente de scraping; sus datos se reconstruyeron manualmente.
- **Traducción ES→EN:** diccionario de 213 nombres de selecciones para unificar fuentes en dos idiomas.

## ⚠️ Limitaciones del modelo

- La forma reciente usa solo 5 partidos por selección (mitigado con shrinkage)
- No considera lesiones, convocatorias ni alineaciones
- Los empates en eliminatorias se resuelven con penales al 50/50
- El valor de mercado mide plantillas de club, no química de selección
- La matriz de marcadores modela hasta 6 goles por equipo

## 🛠️ Stack

`Python 3.14` · `pandas` · `numpy` · `scipy` · `BeautifulSoup` · `openpyxl` · `Power BI` · `DAX`

## 📊 Fuentes de datos

[Transfermarkt](https://www.transfermarkt.es/) (valores de mercado) · [Promiedos](https://www.promiedos.com.ar/) (forma reciente) · [FIFA](https://www.fifa.com/) (ranking y calendario) · Kaggle (históricos)

---

## 👤 Autor

**Alejandro López** — Data Analyst · Analítica Deportiva
📎   Linkedin ([https://www.linkedin.com/in/alejodata](https://www.linkedin.com/in/daniel-alejandro-lopez-sotelo-445958310/))

> Proyecto con fines educativos y de portafolio. Las probabilidades son resultado de simulación estadística, no consejo de apuestas.

