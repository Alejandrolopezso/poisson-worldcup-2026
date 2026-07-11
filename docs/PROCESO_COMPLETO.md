# Pulso + Poisson — Proceso Completo del Proyecto
## Predicción Estadística Mundial 2026
### De los datos crudos al modelo predictivo

---

## ÍNDICE

1. Descripción del proyecto
2. Stack tecnológico
3. Fuentes de datos y scraping
4. Limpieza y preparación de datos
5. Modelo PowerScore en Power BI
6. Modelo Poisson en Python
7. Simulación Monte Carlo
8. Outputs generados
9. Resultados clave
10. Estructura de archivos

---

## 1. DESCRIPCIÓN DEL PROYECTO

**Pulso + Poisson** es un proyecto de analítica deportiva que combina tres capas:

- **Capa descriptiva**: un índice llamado **PowerScore** construido en Power BI que mide la fortaleza de cada selección combinando ranking FIFA, valor de mercado de la plantilla y forma reciente ajustada por calidad de rivales.
- **Capa predictiva**: un modelo de distribución de Poisson implementado en Python que predice resultados de los 72 partidos de fase de grupos del Mundial 2026.
- **Simulación estocástica**: una simulación Monte Carlo de 10,000 iteraciones que replica el formato real del torneo (48 equipos, 12 grupos, 32 clasifican) para estimar probabilidades de avance por ronda, incluyendo eliminatorias hasta la final.

El proyecto cubre el ciclo completo de ciencia de datos: obtención de datos (web scraping), limpieza, modelado estadístico, simulación y visualización.

---

## 2. STACK TECNOLÓGICO

| Herramienta | Uso |
|---|---|
| Python 3.14 | Scraping, limpieza, modelo Poisson, Monte Carlo |
| pandas | Manipulación de datos y DataFrames |
| numpy | Cálculos matriciales y simulación aleatoria |
| scipy.stats | Distribución de Poisson (poisson.pmf) |
| openpyxl | Lectura y escritura de archivos Excel |
| requests / BeautifulSoup | Web scraping |
| Power BI Desktop | Modelo de datos, DAX, visualizaciones |
| VS Code | Editor de código Python |

Entorno Python instalado con uv en `C:\Users\danis\.local\bin\python3.14.exe`

Comando de ejecución (siempre desde la carpeta archive):
```
cd "C:\Users\danis\Documents\Fifa World Cup 26\archive"
C:\Users\danis\.local\bin\python3.14.exe Poisson.py
```

---

## 3. FUENTES DE DATOS Y SCRAPING

### Script: Scraping_transfermarkt.py
- Fuente: Transfermarkt.es
- Datos extraídos: valor de mercado de la plantilla de cada selección (en millones de euros), edad promedio, confederación
- Proceso: requests + BeautifulSoup para parsear tablas HTML
- Output: `RankingAllTeams.xlsx` con 211 selecciones y su valor de mercado

### Script: Ultimos 5 partidos.py
- Fuente: https://www.promiedos.com.ar/
- Datos extraídos: últimos 5 partidos de cada una de las 48 selecciones del Mundial 2026
- Columnas: seleccion, ranking_seleccion, fecha, local_visitante, rival, resultado, ranking_rival
- Output inicial: `5UltimosPartidos.xlsx` en español con 240 filas

### Script: PythonFifa.py
- Fuente: FIFA.com / rankings oficiales
- Datos extraídos: ranking FIFA actual, confederación, entrenador, mejor resultado histórico
- Output: `wc_2026_teams.csv` con las 48 selecciones y metadata

### Datos obtenidos manualmente / fuentes externas

| Archivo | Fuente | Contenido |
|---|---|---|
| wc_2026_fixtures.csv | FIFA.com | Calendario completo de 104 partidos |
| wc_all_editions.csv | Kaggle / Wikipedia | Historial de ediciones del Mundial |
| wc_all_matches.csv | Kaggle | Histórico de todos los partidos |
| wc_top_scorers.csv | Kaggle | Goleadores históricos |

---

## 4. LIMPIEZA Y PREPARACIÓN DE DATOS

### Script: limpieza_matches.py

#### Problema 1 — Excel convertía marcadores a fechas
Al abrir el CSV en Excel, valores como "1-2" se convertían automáticamente a fechas ("2-ene"). Solución: importar via Datos → Desde texto/CSV especificando la columna resultado como texto.

#### Problema 2 — Uzbekistán faltante
El scraping inicial obtuvo solo 47 selecciones (Uzbekistán no tenía datos disponibles en las fuentes consultadas). Se buscaron y agregaron manualmente sus 5 últimos partidos.

#### Problema 3 — 4 filas sin resultado
Austria vs Guatemala, Qatar vs Sudán, Qatar vs Argentina, Qatar vs Serbia eran partidos programados pero no jugados al momento del scraping. Se eliminaron y se reemplazaron con partidos anteriores de esas selecciones.

#### Problema 4 — Traducción de nombres (ES a EN)
El dataset original estaba en español (Alemania, Francia, etc.) y los archivos de fixtures estaban en inglés (Germany, France). Se construyó un diccionario de 213 entradas ES a EN para estandarizar nombres. De 240 filas, 231 coincidieron exactamente; 9 se resolvieron manualmente: Austria vs Chipre, Qatar (3 partidos) y Uzbekistán (5 partidos).

#### Problema 5 — Bug crítico de orientación del marcador (el más importante)
El dataset almacenaba el marcador como "local-visitante" en todos los casos. Cuando una selección jugó como visitante (local_visitante = 'V'), el marcador estaba invertido desde su perspectiva.

Descubierto al verificar los datos de Francia: aparecía con 4 derrotas y 1 victoria cuando en realidad tenía 4 victorias y 1 derrota (verificado cruzando con promiedos.com.ar). El impacto era enorme: Francia pasaba de PowerScore alto a uno artificialmente bajo, y los goles calculados eran completamente incorrectos.

La corrección fue recuperar el archivo original en español (`5UltimosPartidos.xlsx`) que tenía la columna `local_visitante`, traducirlo usando el diccionario ES-EN y mergear con el dataset en inglés. De 240 filas, 231 coincidieron exactamente por nombre de equipo; las 9 restantes se resolvieron manualmente.

Dataset final: `5LastMatch.xlsx` (hoja `mundial_2026_partidos`) — 240 filas × 7 columnas:
- team, team_rank, date, venue, opponent, score, opponent_rank
- venue: L = local, V = visitante

#### Corrección del calendario de fixtures
En `wc_2026_fixtures.csv`, el Grupo C jornada 2 (2026-06-19) tenía Brazil vs Scotland y Morocco vs Haiti, que era un duplicado de la jornada 3. Se corrigió manualmente a Brazil vs Haiti y Morocco vs Scotland. Este bug hacía que Brasil nunca enfrentara a Haití en las simulaciones, afectando completamente las predicciones del Grupo C.

#### Parseo de valores de mercado
El archivo RankingAllTeams.xlsx almacenaba valores en formato español ("1,52 mil mill. €" → 1,520 millones €). Se implementó la función `parse_market_value()` en Python.

---

## 5. MODELO POWERSCORE EN POWER BI

### Modelo de datos

Relaciones entre tablas:
- `mundial_2026_partidos` ↔ `wc_2026_teams` (muchos a uno, por team)
- `wc_2026_teams` ↔ `RankingAllTeams` (uno a uno, por team/country)

Problema: Power BI no permite cambiar la dirección de filtro en relaciones 1:1. Causó el error "Failed to move the data reader to the next row" en un visual scatter. Solución: cambiar la medida `Avg Opponent Rank` para usar AVERAGEX con VALUE() en vez de AVERAGE() sobre la columna de texto.

### Columnas calculadas DAX (mundial_2026_partidos)

```
GoalsFor =
VAR g1 = VALUE(LEFT([score], FIND("-",[score])-1))
VAR g2 = VALUE(MID([score], FIND("-",[score])+1, 10))
RETURN IF([venue]="V", g2, g1)

OpponentStrength =
VAR r = [opponent_rank]
RETURN IF(r="N/A", BLANK(), (212-VALUE(r))/211)

QualityPoints =
SWITCH([ResultFixed],
  "Won",  1 + 2*[OpponentStrength],
  "Draw", ([OpponentStrength]-0.5)*2,
  "Lost", -(3-2*[OpponentStrength]))
```

### Columnas calculadas DAX (wc_2026_teams)

```
RankScore =
VAR minRank = CALCULATE(MIN('RankingAllTeams'[rank]), ALL('RankingAllTeams'))
VAR maxRank = CALCULATE(MAX('RankingAllTeams'[rank]), ALL('RankingAllTeams'))
RETURN (maxRank - [fifa_rank]) / (maxRank - minRank) * 100

MarketScore =
VAR currentMV = [MarketValue]
VAR totalTeams = COUNTROWS(ALL('RankingAllTeams'))
VAR mvRank = COUNTROWS(FILTER(ALL('RankingAllTeams'), [market_value_numeric] > currentMV)) + 1
RETURN (totalTeams - mvRank) / (totalTeams - 1) * 100

FormScore = ([TotalQualityPoints] + 15) / 30 * 100
PowerScore = [MarketScore]*0.40 + [RankScore]*0.35 + [FormScore]*0.25
```

### Ponderación del PowerScore

| Componente | Peso | Justificación |
|---|---|---|
| MarketScore | 40% | Mejor predictor único según estudios de analítica deportiva |
| RankScore | 35% | Ranking FIFA históricamente estable y confiable |
| FormScore | 25% | Forma reciente ajustada por rivales (señal más ruidosa con solo 5 partidos) |

### Top 10 PowerScore

France 100.0 / Spain 99.3 / England 99.0 / Portugal 98.3 / Argentina 98.1 / Brazil 97.6 / Germany 96.9 / Netherlands 96.9 / Belgium 96.0 / Morocco 95.7

---

## 6. MODELO POISSON EN PYTHON

### Fundamento teórico

El modelo de Poisson asume que el número de goles sigue una distribución de Poisson con parámetro lambda, donde:

```
lambda_equipo1 = attack_final[equipo1] × defense_final[equipo2] × league_avg_goals
lambda_equipo2 = attack_final[equipo2] × defense_final[equipo1] × league_avg_goals
```

La probabilidad de cada marcador (i-j) es el producto de las probabilidades individuales de Poisson.

### Pipeline del modelo

**Paso 1 — Corrección de orientación**
```python
df['GoalsFor'] = df.apply(lambda r: r['g2'] if r['venue'] == 'V' else r['g1'], axis=1)
```

**Paso 2 — Ajuste por calidad del rival**
Anotarle a un rival fuerte vale más; recibir goles de un rival débil penaliza más:
```python
df['adj_gf'] = df['GoalsFor'] * (0.5 + df['OpponentStrength'])
df['adj_ga'] = df['GoalsAgainst'] * (1.5 - df['OpponentStrength'])
```
Donde OpponentStrength = (212 - rank) / 211 (0 = rival más débil, 1 = más fuerte). Para rivales sin ranking (ej. sub-20): 0.5 (neutral).

**Paso 3 — Regularización (shrinkage)**
Con solo 5 partidos por equipo, los valores extremos no son confiables. Se aplica shrinkage hacia el promedio de la liga (N_REAL=5, K_SHRINK=3):
```python
avg_gf = (avg_gf * 5 + league_avg_goals * 3) / 8
```

**Paso 4 — Réplica de RankScore y MarketScore en Python**
Mismas fórmulas que en DAX, sobre el universo de 211 selecciones.

**Paso 5 — Multiplicador exponencial de calidad (C=1.0)**
```python
quality_multiplier = np.exp((LongTermStrength / 100 - 0.5) * 1.0)
attack_final = attack * quality_multiplier
defense_final = defense / quality_multiplier
```
El parámetro C=1.0 fue calibrado para producir goleadas reales en partidos muy desbalanceados (Nueva Zelanda 0-4 vs Bélgica, lambda=4.48) sin distorsionar los partidos parejos. Con C=1.5 o C=3 los valores se comprimían demasiado.

**Paso 6 — Función build_score_matrix**
Genera una matriz 7×7 de probabilidades para todos los marcadores posibles (0-6 goles por equipo).

**Paso 7 — Predicciones**
Para cada uno de los 72 partidos: p_win1, p_draw, p_win2, likely_score, lambda1, lambda2, p_over15, p_over25, p_btts.

---

## 7. SIMULACIÓN MONTE CARLO

### Fase de grupos (10,000 iteraciones, seed=42)

Para cada simulación se juegan los 72 partidos con resultados aleatorios basados en la distribución de Poisson. Se construyen las tablas de grupo, se determinan los 32 clasificados (top 2 de cada grupo + 8 mejores terceros) y se registra el orden final.

### Eliminatorias (cruces oficiales FIFA 2026)

Los 16avos siguen el bracket oficial FIFA (M73-M88), no cruces aleatorios. Los terceros son dinámicos: se asigna el mejor tercero disponible del pool elegible para cada cruce.

Cruces M73 a M88 (bracket oficial):
- M73: 2A vs 2B / M74: 1E vs Mejor 3(A/B/C/D/F)
- M75: 1F vs 2C / M76: 1C vs 2F
- M77: 1I vs Mejor 3(C/D/F/G/H) / M78: 2E vs 2I
- M79: 1A vs Mejor 3(C/E/F/H/I) / M80: 1L vs Mejor 3(E/H/I/J/K)
- M81: 1D vs Mejor 3(B/E/F/I/J) / M82: 1G vs Mejor 3(A/E/H/I/J)
- M83: 2K vs 2L / M84: 1H vs 2J
- M85: 1B vs Mejor 3(E/F/G/I/J) / M86: 1J vs 2H
- M87: 1K vs Mejor 3(D/E/I/J/L) / M88: 2D vs 2G

Rondas siguientes: Octavos (M89-M96), Cuartos, Semifinales, Final. Empates se resuelven con penales al 50/50.

Columnas generadas por ronda: p_r16, p_r8, p_r4, p_semi, p_final, p_champion.

---

## 8. OUTPUTS GENERADOS

| Archivo | Filas | Descripción |
|---|---|---|
| poisson_predictions.csv | 72 | Predicciones fase de grupos |
| qualification_probabilities.csv | 48 | % de clasificar y quedar 1° |
| match_score_heatmap.csv | 3,528 | Probabilidad de cada marcador (0-6)×(0-6) |
| knockout_probabilities.csv | 48 | % de llegar a cada ronda eliminatoria |
| bracket_most_likely.csv | ~35 | Cruces más frecuentes por ronda |
| bracket_16avos.csv | 16 | Bracket oficial con equipos más probables |
| team_master.csv | 48 | CSV maestro para Canva Bulk Create (42 columnas) |
| group_certainty.csv | 12 | Tabla más probable por grupo con % de certeza |

### Importación en Power BI
Los CSV usan punto como separador decimal. En Power BI con configuración española, usar "en-US" en el Editor avanzado (código M) de Power Query.

---

## 9. RESULTADOS CLAVE

### Campeón más probable: Bélgica (3.38%)

Top 5 favoritos para campeón:
1. Belgium (G): 3.38%
2. Germany (E): 2.85%
3. Argentina (J): 2.10%
4. Portugal (K): 1.71%
5. South Korea (A): 1.37%

### Bracket más probable

16avos más frecuente: Argentina vs España (30.8%)
Octavos más frecuente: Francia vs Alemania (15.3%)
Cuartos más frecuente: Alemania vs Corea del Sur (7.0%)
Semifinal más frecuente: Alemania vs Corea del Sur (3.9%)
Final más probable: Alemania vs Corea del Sur (3.9%)

### Hallazgos destacados para el reporte

1. Corea del Sur es el 5° favorito para campeón (1.37%) por encima de Brasil, España, Francia e Inglaterra
2. Alemania tiene 23% de llegar a semis (el más alto), pero solo 4.4% de llegar a la final (bracket exigente)
3. Francia es #1 en PowerScore pero no en probabilidad de campeón (Bélgica PowerScore #9 es el favorito)
4. El Grupo D es el más incierto con solo 9.1% de certeza en el orden final
5. Colombia (0.45% campeón) supera a Francia, Inglaterra y Países Bajos en probabilidad de título
6. USA ganó 4-1 a Paraguay en el primer partido real (el modelo predijo Paraguay favorito con 53%)
7. Bug crítico encontrado y corregido: Grupo C tenía Brazil vs Scotland duplicado en lugar de Brazil vs Haiti

### Partidos con goleada predicha

| Partido | Marcador | Lambda favorito | Victoria favorito |
|---|---|---|---|
| New Zealand vs Belgium | 0-4 | 4.48 | 79.3% |
| Jordan vs Argentina | 0-3 | 3.57 | 82.6% |
| Brazil vs Haiti | 2-0 | 2.38 | 70.5% |
| France vs Iraq | 2-0 | 2.26 | 74.7% |
| Spain vs Cape Verde | 2-0 | 2.02 | 64.2% |

---

## 10. ESTRUCTURA DE ARCHIVOS

```
C:\Users\danis\Documents\Fifa World Cup 26\
|
|-- archive\
|   |-- 5LastMatch.xlsx               (dataset limpio, 240 filas, con venue)
|   |-- RankingAllTeams.xlsx          (211 selecciones con valor de mercado)
|   |-- wc_2026_teams.csv             (48 selecciones del Mundial)
|   |-- wc_2026_fixtures.csv          (calendario, corregido Grupo C)
|   |-- wc_all_editions.csv
|   |-- wc_all_matches.csv
|   |-- wc_top_scorers.csv
|   |
|   |-- Poisson.py                    (script principal del modelo)
|   |-- limpieza_matches.py           (limpieza de datos)
|   |-- Scraping_transfermarkt.py     (scraping valores de mercado)
|   |-- Ultimos 5 partidos.py        (scraping ultimos partidos)
|   |-- PythonFifa.py                 (scraping datos FIFA)
|   |
|   |-- poisson_predictions.csv       (OUTPUT: 72 predicciones)
|   |-- qualification_probabilities.csv
|   |-- match_score_heatmap.csv
|   |-- knockout_probabilities.csv
|   |-- bracket_most_likely.csv
|   |-- bracket_16avos.csv
|   |-- team_master.csv
|   |-- group_certainty.csv
|
|-- FIFAWC2026.pbix                   (archivo Power BI)
```

---

## NOTAS TÉCNICAS IMPORTANTES

- Python no está en el PATH del sistema: siempre usar la ruta completa `C:\Users\danis\.local\bin\python3.14.exe`
- Siempre ejecutar desde la carpeta archive/: el script usa rutas relativas
- Separador decimal en Power BI: los CSV usan punto como decimal; usar "en-US" en el código M de Power Query
- Relaciones 1:1 en Power BI: no se puede cambiar la dirección de filtro, se dejó "Ambas" con solución DAX en la medida Avg Opponent Rank
- Monte Carlo: cada corrida produce pequeñas variaciones en décimas incluso con RANDOM_SEED=42. Las narrativas y conclusiones no cambian.
- Instalación de librerías: usar `--break-system-packages` porque Python fue instalado con uv
