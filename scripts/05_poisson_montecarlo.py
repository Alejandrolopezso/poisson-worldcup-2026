"""
Pulso + Poisson - Modelo predictivo del Mundial 2026
======================================================

Este script construye un modelo predictivo para la fase de grupos del
Mundial 2026, combinando dos capas de informacion:

1. Forma reciente: promedio de goles a favor/en contra de cada seleccion en
   sus ultimos 5 partidos (con correccion de orientacion local/visitante),
   ajustado por la fuerza del rival enfrentado en cada partido.
2. Perfil de largo plazo: ranking FIFA historico y valor de mercado de la
   plantilla, sobre el universo de 211 selecciones.

Estas dos capas se combinan mediante regularizacion bayesiana (shrinkage):
cada seleccion se ajusta hacia SU PROPIO nivel esperado de largo plazo, en
lugar de hacia un promedio generico. Esto evita que muestras pequenas (5
partidos) generen estimaciones poco realistas -- por ejemplo, una seleccion
que no recibio goles en sus ultimos 5 partidos no deberia considerarse
"imbatible" de forma literal.

A partir de las fuerzas de ataque/defensa resultantes, se modela el numero
de goles esperado de cada partido con una distribucion de Poisson, y se
ejecuta una simulacion Monte Carlo (10,000 iteraciones) que replica el
formato real de 48 equipos (2 primeros de cada grupo + 8 mejores terceros)
para estimar la probabilidad de avance a octavos de cada seleccion.

Inputs
------
- recent_form_240_matches.xlsx : ultimos 5 partidos de cada seleccion
- market_values_211_teams.xlsx : ranking FIFA y valor de mercado (211 selecciones)
- wc_2026_teams.csv         : las 48 selecciones del Mundial 2026 (ranking FIFA)
- wc_2026_fixtures.csv      : calendario de partidos

Outputs
-------
- poisson_predictions.csv         : predicciones de los 72 partidos de fase de grupos
- qualification_probabilities.csv : probabilidad de avance a octavos por seleccion
- match_score_heatmap.csv         : matriz de probabilidades por marcador (0-6 x 0-6)
"""

import pandas as pd
import numpy as np
from scipy.stats import poisson
from collections import Counter
from pathlib import Path

# ============================================================
# RUTAS (relativas a la raiz del repositorio)
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent   # raiz del repo
DATA_DIR = BASE_DIR / 'data'
OUTPUT_DIR = BASE_DIR / 'outputs'
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# CONFIGURACION
# ============================================================
N_REAL = 5          # partidos reales considerados por seleccion
K_SHRINK = 3        # "partidos virtuales" usados para la regularizacion
MAX_GOALS = 6       # maximo de goles considerados en la distribucion de Poisson
N_SIMS = 10000      # numero de simulaciones Monte Carlo
RANDOM_SEED = 42

np.random.seed(RANDOM_SEED)


# ============================================================
# 1. DATOS BASE: ultimos 5 partidos y goles a favor / en contra
# ============================================================
# El dataset original almacena el marcador como "local-visitante". Cuando la
# seleccion jugo como visitante (venue == 'V'), el orden esta invertido
# respecto a su propia perspectiva, por lo que se corrige aqui.

df = pd.read_excel(DATA_DIR / 'recent_form_240_matches.xlsx', sheet_name='mundial_2026_partidos')

df[['g1', 'g2']] = df['score'].str.split('-', expand=True).astype(int)
df['GoalsFor'] = df.apply(lambda r: r['g2'] if r['venue'] == 'V' else r['g1'], axis=1)
df['GoalsAgainst'] = df.apply(lambda r: r['g1'] if r['venue'] == 'V' else r['g2'], axis=1)

# OpponentStrength: 0 (rival mas debil, rank 211) a 1 (rival mas fuerte, rank 1).
# Rivales sin ranking ("N/A", ej. selecciones juveniles) se tratan como nivel
# neutral (0.5), de forma que no afecten el ajuste.
def opponent_strength(rank):
    if str(rank) == 'N/A':
        return 0.5
    return (212 - float(rank)) / 211

df['OpponentStrength'] = df['opponent_rank'].apply(opponent_strength)

# Goles ajustados por la fuerza del rival enfrentado: anotarle a un rival
# fuerte pesa mas para el ataque; recibir goles de un rival debil pesa mas
# (negativamente) para la defensa. Rango del multiplicador: 0.5x - 1.5x.
df['adj_gf'] = df['GoalsFor'] * (0.5 + df['OpponentStrength'])
df['adj_ga'] = df['GoalsAgainst'] * (1.5 - df['OpponentStrength'])


# ============================================================
# 2. FUERZA DE ATAQUE / DEFENSA - FORMA RECIENTE (AJUSTADA POR RIVAL)
# ============================================================
# Promedio de goles a favor/en contra (ya ajustados por la fuerza del rival)
# por seleccion, regularizado (shrinkage) hacia el promedio general de goles
# de la liga para atenuar muestras pequenas de solo 5 partidos.

team_stats = df.groupby('team').agg(
    avg_gf=('adj_gf', 'mean'),
    avg_ga=('adj_ga', 'mean')
).reset_index()

league_avg_goals = df['GoalsFor'].mean()

team_stats['avg_gf'] = (team_stats['avg_gf'] * N_REAL + league_avg_goals * K_SHRINK) / (N_REAL + K_SHRINK)
team_stats['avg_ga'] = (team_stats['avg_ga'] * N_REAL + league_avg_goals * K_SHRINK) / (N_REAL + K_SHRINK)

team_stats['attack'] = team_stats['avg_gf'] / league_avg_goals
team_stats['defense'] = team_stats['avg_ga'] / league_avg_goals


# ============================================================
# 3. PERFIL DE LARGO PLAZO - RankScore y MarketScore
# ============================================================
# RankScore y MarketScore replican las metricas usadas en el dashboard de
# Power BI: posicion relativa de cada seleccion en el ranking FIFA y en el
# valor de mercado de su plantilla, sobre el universo de 211 selecciones.

ranking_all = pd.read_excel(DATA_DIR / 'market_values_211_teams.xlsx', header=1)
ranking_all = ranking_all.dropna(axis=1, how='all')
ranking_all.columns = [str(c).strip() for c in ranking_all.columns]

ranking_all['rank'] = pd.to_numeric(
    ranking_all['rank'].astype(str).str.replace('\xa0', '', regex=False).str.strip(),
    errors='coerce'
)


def parse_market_value(txt):
    """Convierte strings como '1,52 mil mill. EUR' o '782,50 mill. EUR' a millones de euros."""
    txt = str(txt)
    if ' ' not in txt:
        return 0.0
    num_part, _ = txt.split(' ', 1)
    if ',' in num_part:
        int_part, dec_part = num_part.split(',')
        num_val = float(int_part + '.' + dec_part)
    else:
        num_val = float(num_part)
    if 'mil mill' in txt:
        return num_val * 1000
    elif 'mill' in txt:
        return num_val
    else:
        return num_val / 1000


ranking_all['market_value_numeric'] = ranking_all['market_value'].apply(parse_market_value)

min_rank = ranking_all['rank'].min()
max_rank = ranking_all['rank'].max()
total_teams = len(ranking_all)

wc_teams = pd.read_csv(DATA_DIR / 'wc_2026_teams.csv')

# RankScore: posicion relativa en el ranking FIFA (0-100, 100 = mejor ranking)
wc_teams['RankScore'] = (max_rank - wc_teams['fifa_rank']) / (max_rank - min_rank) * 100

# MarketScore: percentil de valor de mercado de la plantilla (0-100, 100 = mas valiosa)
mv_lookup = ranking_all.set_index('country')['market_value_numeric']
wc_teams['MarketValue'] = wc_teams['team'].map(mv_lookup)


def market_score(mv):
    mv_rank = (ranking_all['market_value_numeric'] > mv).sum() + 1
    return (total_teams - mv_rank) / (total_teams - 1) * 100


wc_teams['MarketScore'] = wc_teams['MarketValue'].apply(market_score)


# ============================================================
# 4. MODELO FINAL - forma reciente + perfil de largo plazo
# ============================================================
# En lugar de regularizar todos los equipos hacia el mismo promedio
# generico, cada seleccion se ajusta hacia SU PROPIO nivel esperado
# (LongTermStrength), derivado de su ranking FIFA y valor de mercado. Si la
# forma reciente y el perfil de largo plazo coinciden, el ajuste es pequeno;
# si difieren -- por ejemplo, una racha excepcional con muestra pequena -- el
# modelo la atenua hacia un valor mas representativo de la calidad del equipo.
#
# El rango del prior (0.3 - 1.7) es deliberadamente mas amplio que el rango
# 0.5 - 1.5 usado originalmente, para que la brecha entre selecciones de
# elite y selecciones debiles se refleje con mas fuerza en los lambdas.

wc_teams['LongTermStrength'] = wc_teams['RankScore'] * 0.5 + wc_teams['MarketScore'] * 0.5

C = 1.0  # controla la amplificacion por calidad (mayor = goleadas mas marcadas)
wc_teams['quality_multiplier'] = np.exp((wc_teams['LongTermStrength'] / 100 - 0.5) * C)

team_stats = team_stats.merge(
    wc_teams[['team', 'quality_multiplier', 'LongTermStrength']],
    on='team'
)

team_stats['attack_final'] = team_stats['attack'] * team_stats['quality_multiplier']
team_stats['defense_final'] = team_stats['defense'] / team_stats['quality_multiplier']

stats_dict = team_stats.set_index('team')[['attack_final', 'defense_final']].to_dict('index')


# ============================================================
# 5. CALENDARIO - fase de grupos (72 partidos con equipos definidos)
# ============================================================
fixtures = pd.read_csv(DATA_DIR / 'wc_2026_fixtures.csv')
all_teams = set(team_stats['team'])
group_matches = fixtures[
    fixtures['team1'].isin(all_teams) & fixtures['team2'].isin(all_teams)
].copy()


# ============================================================
# 6. MODELO DE POISSON - matriz de probabilidades por partido
# ============================================================
# Para cada partido, se calcula el numero esperado de goles (lambda) de cada
# seleccion a partir de su fuerza de ataque y la fuerza de defensa del rival.
# La distribucion de Poisson genera una matriz de probabilidades para cada
# combinacion de marcador (0-6 x 0-6), que se reutiliza en las secciones 6, 7 y 8.

def build_score_matrix(team1, team2):
    lam1 = stats_dict[team1]['attack_final'] * stats_dict[team2]['defense_final'] * league_avg_goals
    lam2 = stats_dict[team2]['attack_final'] * stats_dict[team1]['defense_final'] * league_avg_goals
    p1 = poisson.pmf(np.arange(MAX_GOALS + 1), lam1)
    p2 = poisson.pmf(np.arange(MAX_GOALS + 1), lam2)
    return lam1, lam2, np.outer(p1, p2)


# ============================================================
# 7. PREDICCIONES POR PARTIDO - resumen (72 filas)
# ============================================================
# De la matriz de probabilidades se derivan: marcador mas probable,
# probabilidades de victoria/empate/derrota, y mercados Over/Under y BTTS.

results = []
for _, row in group_matches.iterrows():
    t1, t2 = row['team1'], row['team2']
    lam1, lam2, matrix = build_score_matrix(t1, t2)

    p_win1 = np.sum(np.tril(matrix, -1))
    p_draw = np.sum(np.diag(matrix))
    p_win2 = np.sum(np.triu(matrix, 1))

    idx = np.unravel_index(np.argmax(matrix), matrix.shape)
    likely_score = f"{idx[0]}-{idx[1]}"

    total_goals = np.add.outer(np.arange(MAX_GOALS + 1), np.arange(MAX_GOALS + 1))
    p_over15 = matrix[total_goals > 1.5].sum()
    p_over25 = matrix[total_goals > 2.5].sum()
    p_btts = matrix[1:, 1:].sum()

    results.append({
        'group': row['group'], 'team1': t1, 'team2': t2, 'date': row['date'],
        'lambda1': round(lam1, 2), 'lambda2': round(lam2, 2),
        'likely_score': likely_score,
        'p_win1': round(p_win1 * 100, 1),
        'p_draw': round(p_draw * 100, 1),
        'p_win2': round(p_win2 * 100, 1),
        'p_over15': round(p_over15 * 100, 1),
        'p_over25': round(p_over25 * 100, 1),
        'p_btts': round(p_btts * 100, 1)
    })

predictions = pd.DataFrame(results)
predictions.to_csv(OUTPUT_DIR / 'poisson_predictions.csv', index=False)


# ============================================================
# 8. SIMULACION MONTE CARLO - probabilidad de avance a octavos
# ============================================================
# Se simula la fase de grupos completa N_SIMS veces. En cada simulacion, el
# resultado de cada partido se muestrea de su distribucion de Poisson
# (lambda1, lambda2). Se construye la tabla de cada grupo (puntos, diferencia
# de gol, goles a favor) y se determina quien avanza: los 2 primeros de cada
# grupo, mas las 8 mejores selecciones que terminaron en 3er lugar (formato
# real del Mundial 2026 de 48 equipos).

group_fixtures = {}
for g in group_matches['group'].unique():
    matches = group_matches[group_matches['group'] == g]
    fixtures_g = []
    for _, row in matches.iterrows():
        t1, t2 = row['team1'], row['team2']
        lam1, lam2, _ = build_score_matrix(t1, t2)
        fixtures_g.append((t1, t2, lam1, lam2))
    group_fixtures[g] = fixtures_g

advance_count = {t: 0 for t in all_teams}
first_count = {t: 0 for t in all_teams}
group_order_count = {g: Counter() for g in group_fixtures.keys()}

for _ in range(N_SIMS):
    third_place_pool = []
    for g, matches in group_fixtures.items():
        teams_in_group = set([m[0] for m in matches] + [m[1] for m in matches])
        table = {t: {'pts': 0, 'gf': 0, 'ga': 0} for t in teams_in_group}

        for t1, t2, lam1, lam2 in matches:
            g1 = np.random.poisson(lam1)
            g2 = np.random.poisson(lam2)
            table[t1]['gf'] += g1; table[t1]['ga'] += g2
            table[t2]['gf'] += g2; table[t2]['ga'] += g1
            if g1 > g2:
                table[t1]['pts'] += 3
            elif g2 > g1:
                table[t2]['pts'] += 3
            else:
                table[t1]['pts'] += 1; table[t2]['pts'] += 1

        ranked = sorted(
            table.items(),
            key=lambda x: (x[1]['pts'], x[1]['gf'] - x[1]['ga'], x[1]['gf']),
            reverse=True
        )

        order = tuple(team for team, _ in ranked)
        group_order_count[g][order] += 1

        for i, (team, stats) in enumerate(ranked):
            if i == 0:
                first_count[team] += 1
            if i < 2:
                advance_count[team] += 1
            if i == 2:
                third_place_pool.append((team, stats['pts'], stats['gf'] - stats['ga'], stats['gf']))

    third_place_pool.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
    for team, _, _, _ in third_place_pool[:8]:
        advance_count[team] += 1

qualification = pd.DataFrame({
    'team': list(all_teams),
    'p_first_in_group': [first_count[t] / N_SIMS * 100 for t in all_teams],
    'p_advance_r32': [advance_count[t] / N_SIMS * 100 for t in all_teams],
})
qualification = qualification.merge(wc_teams[['team', 'group']], on='team')
qualification = qualification.sort_values('p_advance_r32', ascending=False)
qualification.to_csv(OUTPUT_DIR / 'qualification_probabilities.csv', index=False)


# ============================================================
# 9. MATRIZ DE MARCADORES - para heatmap por partido
# ============================================================
# Exporta la probabilidad de cada combinacion de marcador posible (0-6 x 0-6)
# por partido, en formato "largo" -- listo para un visual de tipo matriz en
# Power BI con formato condicional de color.

heatmap_rows = []
for match_id, (_, row) in enumerate(group_matches.iterrows(), start=1):
    t1, t2 = row['team1'], row['team2']
    _, _, matrix = build_score_matrix(t1, t2)

    for g1 in range(MAX_GOALS + 1):
        for g2 in range(MAX_GOALS + 1):
            heatmap_rows.append({
                'match_id': match_id,
                'group': row['group'],
                'team1': t1, 'team2': t2,
                'match_label': f"{t1} vs {t2}",
                'goals_team1': g1,
                'goals_team2': g2,
                'probability': round(matrix[g1, g2] * 100, 2)
            })

heatmap_df = pd.DataFrame(heatmap_rows)
heatmap_df.to_csv(OUTPUT_DIR / 'match_score_heatmap.csv', index=False)


# ============================================================
# RESUMEN DE EJECUCION
# ============================================================
print("Modelo ejecutado correctamente.")
print(f" - Promedio de goles por partido (liga): {league_avg_goals:.3f}")
print(f" - Predicciones de fase de grupos: {len(predictions)} partidos -> poisson_predictions.csv")
print(f" - Probabilidades de clasificacion: {len(qualification)} selecciones -> qualification_probabilities.csv")
print(f" - Matriz de marcadores: {len(heatmap_df)} filas -> match_score_heatmap.csv")

print("\nTop 5 - Mayor probabilidad de avanzar a octavos:")
print(qualification.head(5)[['team', 'group', 'p_advance_r32']].to_string(index=False))

print("\nTabla mas probable por grupo:")
for g, counter in group_order_count.items():
    order, count = counter.most_common(1)[0]
    pct = count / N_SIMS * 100
    print(f"  Grupo {g}: {order[0]} > {order[1]} > {order[2]} > {order[3]}  ({pct:.1f}%)")

# --- Verificacion: comparar casos discutidos (Francia-Irak, partidos de Brasil) ---
print("\nVerificacion - Francia vs Irak:")
print(predictions[(predictions['team1'] == 'France') & (predictions['team2'] == 'Iraq')][
    ['team1', 'team2', 'lambda1', 'lambda2', 'likely_score', 'p_win1', 'p_draw', 'p_win2']
].to_string(index=False))

print("\nVerificacion - Partidos de Brasil:")
print(predictions[(predictions['team1'] == 'Brazil') | (predictions['team2'] == 'Brazil')][
    ['team1', 'team2', 'lambda1', 'lambda2', 'likely_score', 'p_win1', 'p_draw', 'p_win2']
].to_string(index=False))

print("\nVerificacion - Colombia vs DR Congo:")
print(predictions[(predictions['team1'] == 'Colombia') & (predictions['team2'] == 'DR Congo')][
    ['team1', 'team2', 'lambda1', 'lambda2', 'likely_score', 'p_win1', 'p_draw', 'p_win2']
].to_string(index=False))

# --- Verificacion: partidos con potencial de goleada (favorito claro vs rival debil) ---
print("\nVerificacion - Partidos con potencial de goleada:")
casos = [
    ('Spain', 'Cape Verde'),
    ('Brazil', 'Haiti'),
    ('Argentina', 'Jordan'),
    ('Belgium', 'New Zealand'),
    ('France', 'Iraq'),
]

for t1, t2 in casos:
    fila = predictions[(predictions['team1'] == t1) & (predictions['team2'] == t2)]
    if fila.empty:
        fila = predictions[(predictions['team1'] == t2) & (predictions['team2'] == t1)]
    print(fila[['team1', 'team2', 'lambda1', 'lambda2', 'likely_score', 'p_win1', 'p_draw', 'p_win2', 'p_over25']].to_string(index=False))

    # ============================================================
# 10. SIMULACION ELIMINATORIAS - CRUCES OFICIALES FIFA 2026
# ============================================================
# Cruces de 16avos segun el bracket oficial publicado por FIFA.
# Los terceros son dinamicos: dependen de cuales grupos produzcan
# los 8 mejores terceros en cada simulacion.
# En caso de empate: penales simulados con probabilidad 50/50.

def simulate_knockout_match(t1, t2):
    """Simula un partido eliminatorio. Retorna el ganador."""
    if not t1 or not t2:
        return t1 or t2
    lam1 = stats_dict[t1]['attack_final'] * stats_dict[t2]['defense_final'] * league_avg_goals
    lam2 = stats_dict[t2]['attack_final'] * stats_dict[t1]['defense_final'] * league_avg_goals
    g1 = np.random.poisson(lam1)
    g2 = np.random.poisson(lam2)
    if g1 > g2:
        return t1
    elif g2 > g1:
        return t2
    else:
        return t1 if np.random.random() < 0.5 else t2

# Regla oficial FIFA para asignar terceros a los cruces segun
# los grupos de los que provienen los 8 mejores terceros.
# Fuente: bracket oficial FIFA 2026.
THIRD_PLACE_RULES = {
    # slot: {frozenset de grupos posibles: grupo asignado}
    # M74: 1E vs mejor tercero de A/B/C/D/F
    'M74': ['A', 'B', 'C', 'D', 'F'],
    # M77: 1I vs mejor tercero de C/D/F/G/H
    'M77': ['C', 'D', 'F', 'G', 'H'],
    # M79: 1A vs mejor tercero de C/E/F/H/I
    'M79': ['C', 'E', 'F', 'H', 'I'],
    # M80: 1L vs mejor tercero de E/H/I/J/K
    'M80': ['E', 'H', 'I', 'J', 'K'],
    # M81: 1D vs mejor tercero de B/E/F/I/J
    'M81': ['B', 'E', 'F', 'I', 'J'],
    # M82: 1G vs mejor tercero de A/E/H/I/J
    'M82': ['A', 'E', 'H', 'I', 'J'],
    # M85: 1B vs mejor tercero de E/F/G/I/J
    'M85': ['E', 'F', 'G', 'I', 'J'],
    # M87: 1K vs mejor tercero de D/E/I/J/L
    'M87': ['D', 'E', 'I', 'J', 'L'],
}

def assign_third(thirds_by_group, eligible_groups):
    """
    De los terceros disponibles en thirds_by_group,
    asigna el mejor que provenga de uno de los grupos elegibles.
    """
    candidates = [(g, thirds_by_group[g]) for g in eligible_groups if g in thirds_by_group]
    if not candidates:
        return None
    # El "mejor" ya viene ordenado por pts/GD/GF desde el Monte Carlo
    return candidates[0][1]

# Contadores por ronda
round_count = {t: {'r16': 0, 'r8': 0, 'r4': 0, 'r2': 0, 'r_final': 0, 'champion': 0} for t in all_teams}
champions = Counter()
bracket_r16 = Counter()
bracket_r8 = Counter()
bracket_r4 = Counter()
bracket_final_counter = Counter()

np.random.seed(RANDOM_SEED)

for _ in range(N_SIMS):

    # ---- Reproducir fase de grupos ----
    third_place_pool = []
    group_results = {}

    for g, matches in group_fixtures.items():
        teams_in_group = set([m[0] for m in matches] + [m[1] for m in matches])
        table = {t: {'pts': 0, 'gf': 0, 'ga': 0} for t in teams_in_group}

        for t1, t2, lam1, lam2 in matches:
            g1 = np.random.poisson(lam1)
            g2 = np.random.poisson(lam2)
            table[t1]['gf'] += g1; table[t1]['ga'] += g2
            table[t2]['gf'] += g2; table[t2]['ga'] += g1
            if g1 > g2:
                table[t1]['pts'] += 3
            elif g2 > g1:
                table[t2]['pts'] += 3
            else:
                table[t1]['pts'] += 1; table[t2]['pts'] += 1

        ranked = sorted(
            table.items(),
            key=lambda x: (x[1]['pts'], x[1]['gf'] - x[1]['ga'], x[1]['gf']),
            reverse=True
        )
        group_results[g] = [team for team, _ in ranked]
        third_place_pool.append((
            ranked[2][1]['pts'],
            ranked[2][1]['gf'] - ranked[2][1]['ga'],
            ranked[2][1]['gf'],
            g,
            ranked[2][0]
        ))

    # ---- Seleccionar los 8 mejores terceros ----
    third_place_pool.sort(reverse=True)
    best_thirds_ordered = third_place_pool[:8]  # lista ordenada de mejor a peor
    # Diccionario: grupo -> equipo (solo los 8 clasificados)
    thirds_by_group = {entry[3]: entry[4] for entry in best_thirds_ordered}

    # ---- Armar clasificados ----
    q = {}  # q[grupo][posicion] = equipo
    for g in group_fixtures.keys():
        q[g] = {1: group_results[g][0], 2: group_results[g][1]}

    # ---- 16avos de final (cruces oficiales FIFA) ----
    # Terceros dinamicos: se asigna el mejor tercero disponible
    # del pool de grupos elegibles para cada cruce
    thirds_used = set()

    def get_third(eligible):
        for entry in best_thirds_ordered:
            g = entry[3]
            team = entry[4]
            if g in eligible and g not in thirds_used:
                thirds_used.add(g)
                return team
        return None

    r16 = {
        'M73': (q['A'][2], q['B'][2]),
        'M74': (q['E'][1], get_third(['A','B','C','D','F'])),
        'M75': (q['F'][1], q['C'][2]),
        'M76': (q['C'][1], q['F'][2]),
        'M77': (q['I'][1], get_third(['C','D','F','G','H'])),
        'M78': (q['E'][2], q['I'][2]),
        'M79': (q['A'][1], get_third(['C','E','F','H','I'])),
        'M80': (q['L'][1], get_third(['E','H','I','J','K'])),
        'M81': (q['D'][1], get_third(['B','E','F','I','J'])),
        'M82': (q['G'][1], get_third(['A','E','H','I','J'])),
        'M83': (q['K'][2], q['L'][2]),
        'M84': (q['H'][1], q['J'][2]),
        'M85': (q['B'][1], get_third(['E','F','G','I','J'])),
        'M86': (q['J'][1], q['H'][2]),
        'M87': (q['K'][1], get_third(['D','E','I','J','L'])),
        'M88': (q['D'][2], q['G'][2]),
    }

    r16_winners = {}
    for match, (t1, t2) in r16.items():
        if t1 and t2:
            w = simulate_knockout_match(t1, t2)
            r16_winners[match] = w
            round_count[w]['r16'] += 1
            bracket_r16[tuple(sorted([t1, t2]))] += 1

    # ---- Octavos de final (cruces oficiales) ----
    # M89: W74 vs W77 | M90: W73 vs W75
    # M91: W76 vs W78 | M92: W79 vs W80
    # M93: W81 vs W82 | M94: W83 vs W84
    # M95: W85 vs W86 | M96: W87 vs W88
    r8_pairs = [
        (r16_winners.get('M74'), r16_winners.get('M77')),
        (r16_winners.get('M73'), r16_winners.get('M75')),
        (r16_winners.get('M76'), r16_winners.get('M78')),
        (r16_winners.get('M79'), r16_winners.get('M80')),
        (r16_winners.get('M81'), r16_winners.get('M82')),
        (r16_winners.get('M83'), r16_winners.get('M84')),
        (r16_winners.get('M85'), r16_winners.get('M86')),
        (r16_winners.get('M87'), r16_winners.get('M88')),
    ]

    r8_winners = []
    for t1, t2 in r8_pairs:
        if t1 and t2:
            w = simulate_knockout_match(t1, t2)
            round_count[w]['r8'] += 1
            bracket_r8[tuple(sorted([t1, t2]))] += 1
            r8_winners.append(w)

    # ---- Cuartos de final ----
    r4_winners = []
    for i in range(0, len(r8_winners) - 1, 2):
        t1, t2 = r8_winners[i], r8_winners[i+1]
        w = simulate_knockout_match(t1, t2)
        round_count[w]['r4'] += 1
        bracket_r4[tuple(sorted([t1, t2]))] += 1
        r4_winners.append(w)

    # ---- Semifinales ----
    r2_winners = []
    for i in range(0, len(r4_winners) - 1, 2):
        t1, t2 = r4_winners[i], r4_winners[i+1]
        w = simulate_knockout_match(t1, t2)
        round_count[w]['r2'] += 1
        bracket_final_counter[tuple(sorted([t1, t2]))] += 1
        r2_winners.append(w)

# ---- Final ----
    if len(r2_winners) >= 2:
        round_count[r2_winners[0]]['r_final'] += 1
        round_count[r2_winners[1]]['r_final'] += 1
        champion = simulate_knockout_match(r2_winners[0], r2_winners[1])
        round_count[champion]['champion'] += 1
        champions[champion] += 1

# ---- Exportar probabilidades por ronda ----
knockout_data = []
for team in all_teams:
    knockout_data.append({
        'team': team,
        'p_r16': round(round_count[team]['r16'] / N_SIMS * 100, 2),
        'p_r8': round(round_count[team]['r8'] / N_SIMS * 100, 2),
        'p_r4': round(round_count[team]['r4'] / N_SIMS * 100, 2),
        'p_final': round(round_count[team]['r2'] / N_SIMS * 100, 2),
        'p_champion': round(round_count[team]['champion'] / N_SIMS * 100, 2),
    })

knockout_df = pd.DataFrame(knockout_data)
knockout_df = knockout_df.merge(wc_teams[['team', 'group']], on='team')
knockout_df = knockout_df.sort_values('p_champion', ascending=False)
knockout_df.to_csv(OUTPUT_DIR / 'knockout_probabilities.csv', index=False)

# ---- Exportar bracket mas probable ----
bracket_data = []
for pair, count in bracket_r16.most_common(16):
    bracket_data.append({'round': 'R16', 'team1': pair[0], 'team2': pair[1],
                         'frequency': round(count/N_SIMS*100, 1)})
for pair, count in bracket_r8.most_common(8):
    bracket_data.append({'round': 'Octavos', 'team1': pair[0], 'team2': pair[1],
                         'frequency': round(count/N_SIMS*100, 1)})
for pair, count in bracket_r4.most_common(4):
    bracket_data.append({'round': 'Cuartos', 'team1': pair[0], 'team2': pair[1],
                         'frequency': round(count/N_SIMS*100, 1)})
for pair, count in bracket_final_counter.most_common(3):
    bracket_data.append({'round': 'Semis', 'team1': pair[0], 'team2': pair[1],
                         'frequency': round(count/N_SIMS*100, 1)})
for team, count in champions.most_common(3):
    bracket_data.append({'round': 'Final', 'team1': team, 'team2': 'CAMPEON',
                         'frequency': round(count/N_SIMS*100, 1)})
    
bracket_df = pd.DataFrame(bracket_data)
bracket_df.to_csv(OUTPUT_DIR / 'bracket_most_likely.csv', index=False)

# ---- Resumen ----
print("\n✓ Guardado: knockout_probabilities.csv")
print("✓ Guardado: bracket_most_likely.csv")

# ============================================================
# 10b. BRACKET 16AVOS CON EQUIPOS PROBABLES POR POSICION
# ============================================================
print("\n=== BRACKET 16AVOS - EQUIPOS MAS PROBABLES ===")

pos_lookup = {}
for g in group_fixtures.keys():
    equipos_g = qualification[qualification['group'] == g].sort_values('p_first_in_group', ascending=False)
    pos_lookup[f'{g}1'] = equipos_g.iloc[0]['team']
    pos_lookup[f'{g}2'] = equipos_g.iloc[1]['team']

cruces_16avos = [
    ('M73', f"2°A ({pos_lookup['A2']})", f"2°B ({pos_lookup['B2']})"),
    ('M74', f"1°E ({pos_lookup['E1']})", "Mejor 3° A/B/C/D/F"),
    ('M75', f"1°F ({pos_lookup['F1']})", f"2°C ({pos_lookup['C2']})"),
    ('M76', f"1°C ({pos_lookup['C1']})", f"2°F ({pos_lookup['F2']})"),
    ('M77', f"1°I ({pos_lookup['I1']})", "Mejor 3° C/D/F/G/H"),
    ('M78', f"2°E ({pos_lookup['E2']})", f"2°I ({pos_lookup['I2']})"),
    ('M79', f"1°A ({pos_lookup['A1']})", "Mejor 3° C/E/F/H/I"),
    ('M80', f"1°L ({pos_lookup['L1']})", "Mejor 3° E/H/I/J/K"),
    ('M81', f"1°D ({pos_lookup['D1']})", "Mejor 3° B/E/F/I/J"),
    ('M82', f"1°G ({pos_lookup['G1']})", "Mejor 3° A/E/H/I/J"),
    ('M83', f"2°K ({pos_lookup['K2']})", f"2°L ({pos_lookup['L2']})"),
    ('M84', f"1°H ({pos_lookup['H1']})", f"2°J ({pos_lookup['J2']})"),
    ('M85', f"1°B ({pos_lookup['B1']})", "Mejor 3° E/F/G/I/J"),
    ('M86', f"1°J ({pos_lookup['J1']})", f"2°H ({pos_lookup['H2']})"),
    ('M87', f"1°K ({pos_lookup['K1']})", "Mejor 3° D/E/I/J/L"),
    ('M88', f"2°D ({pos_lookup['D2']})", f"2°G ({pos_lookup['G2']})"),
]

bracket_16avos_data = []
for match, local, visitante in cruces_16avos:
    print(f"  {match}: {local} vs {visitante}")
    bracket_16avos_data.append({
        'match': match,
        'team1_position': local,
        'team2_position': visitante
    })

bracket_16avos_df = pd.DataFrame(bracket_16avos_data)
bracket_16avos_df.to_csv(OUTPUT_DIR / 'bracket_16avos.csv', index=False)
print("\n✓ Guardado: bracket_16avos.csv")

# ============================================================
# AGREGAR p_reach_final Y ACTUALIZAR knockout_probabilities
# ============================================================
# Recalcular con columna separada para llegar a la final
knockout_data_v2 = []
for team in all_teams:
    knockout_data_v2.append({
        'team': team,
        'p_r16':      round(round_count[team]['r16']     / N_SIMS * 100, 2),
        'p_r8':       round(round_count[team]['r8']      / N_SIMS * 100, 2),
        'p_r4':       round(round_count[team]['r4']      / N_SIMS * 100, 2),
        'p_semi':     round(round_count[team]['r2']      / N_SIMS * 100, 2),
        'p_final':    round(round_count[team].get('r_final', 0) / N_SIMS * 100, 2),
        'p_champion': round(round_count[team]['champion'] / N_SIMS * 100, 2),
    })

knockout_df_v2 = pd.DataFrame(knockout_data_v2)
knockout_df_v2 = knockout_df_v2.merge(wc_teams[['team', 'group']], on='team')
knockout_df_v2 = knockout_df_v2.sort_values('p_champion', ascending=False)
knockout_df_v2.to_csv(OUTPUT_DIR / 'knockout_probabilities.csv', index=False)
print("\n✓ Actualizado: knockout_probabilities.csv (con p_semi y p_final separados)")

print("\nTop 10 - Probabilidad de ser CAMPEON:")
print(knockout_df_v2.head(10)[['team', 'group', 'p_r16', 'p_r8', 'p_r4', 'p_semi', 'p_final', 'p_champion']].to_string(index=False))

print("\nFinal mas probable (top 3):")
for pair, count in bracket_final_counter.most_common(3):
    print(f"  {pair[0]} vs {pair[1]}: {count/N_SIMS*100:.1f}%")

print("\nCampeon mas probable (top 5):")
for team, count in champions.most_common(5):
    print(f"  {team}: {count/N_SIMS*100:.1f}%")

print("\nTop 20 - Probabilidad de ser CAMPEON:")
print(knockout_df_v2.head(20)[['team', 'group', 'p_r16', 'p_r8', 'p_r4', 'p_semi', 'p_final', 'p_champion']].to_string(index=False))

# ============================================================
# 11. CSV MAESTRO POR EQUIPO - para Canva Bulk Create
# ============================================================

team_master = wc_teams[['team', 'group', 'fifa_rank', 'confederation', 'coach', 'best_wc_result', 'debut_2026']].copy()

team_master['market_value_eur_m'] = team_master['team'].map(mv_lookup)

powerscore_lookup = wc_teams.set_index('team')[['RankScore', 'MarketScore', 'LongTermStrength']].to_dict('index')
team_master['RankScore'] = team_master['team'].map(lambda t: round(powerscore_lookup[t]['RankScore'], 1))
team_master['MarketScore'] = team_master['team'].map(lambda t: round(powerscore_lookup[t]['MarketScore'], 1))
team_master['PowerScore'] = team_master['team'].map(lambda t: round(powerscore_lookup[t]['LongTermStrength'], 1))

qual_lookup = qualification.set_index('team')[['p_first_in_group', 'p_advance_r32']].to_dict('index')
team_master['p_first_in_group'] = team_master['team'].map(lambda t: qual_lookup[t]['p_first_in_group'])
team_master['p_advance_r32'] = team_master['team'].map(lambda t: qual_lookup[t]['p_advance_r32'])

ko_lookup = knockout_df.set_index('team')[['p_r16', 'p_r8', 'p_r4', 'p_final', 'p_champion']].to_dict('index')
team_master['p_r16'] = team_master['team'].map(lambda t: ko_lookup[t]['p_r16'])
team_master['p_r8'] = team_master['team'].map(lambda t: ko_lookup[t]['p_r8'])
team_master['p_r4'] = team_master['team'].map(lambda t: ko_lookup[t]['p_r4'])
team_master['p_final'] = team_master['team'].map(lambda t: ko_lookup[t]['p_final'])
team_master['p_champion'] = team_master['team'].map(lambda t: ko_lookup[t]['p_champion'])

for i in range(1, 4):
    team_master[f'match{i}_opponent'] = ''
    team_master[f'match{i}_date'] = ''
    team_master[f'match{i}_lambda_team'] = None
    team_master[f'match{i}_lambda_opp'] = None
    team_master[f'match{i}_score'] = ''
    team_master[f'match{i}_p_win'] = None
    team_master[f'match{i}_p_draw'] = None
    team_master[f'match{i}_p_loss'] = None

for idx, row in team_master.iterrows():
    team = row['team']

    as_home = predictions[predictions['team1'] == team][['team2','date','lambda1','lambda2','likely_score','p_win1','p_draw','p_win2']].copy()
    as_home.columns = ['opponent','date','lam_team','lam_opp','score','p_win','p_draw','p_loss']
    as_home['is_away'] = False

    as_away = predictions[predictions['team2'] == team][['team1','date','lambda2','lambda1','likely_score','p_win2','p_draw','p_win1']].copy()
    as_away.columns = ['opponent','date','lam_team','lam_opp','score','p_win','p_draw','p_loss']
    as_away['is_away'] = True

    team_matches = pd.concat([as_home, as_away]).sort_values('date').reset_index(drop=True)

    for i, match_row in team_matches.iterrows():
        n = i + 1
        if n > 3:
            break
        score = match_row['score']
        if match_row['is_away']:
            parts = score.split('-')
            if len(parts) == 2:
                score = f"{parts[1]}-{parts[0]}"
        team_master.at[idx, f'match{n}_opponent'] = match_row['opponent']
        team_master.at[idx, f'match{n}_date'] = str(match_row['date'])[:10]
        team_master.at[idx, f'match{n}_lambda_team'] = match_row['lam_team']
        team_master.at[idx, f'match{n}_lambda_opp'] = match_row['lam_opp']
        team_master.at[idx, f'match{n}_score'] = score
        team_master.at[idx, f'match{n}_p_win'] = match_row['p_win']
        team_master.at[idx, f'match{n}_p_draw'] = match_row['p_draw']
        team_master.at[idx, f'match{n}_p_loss'] = match_row['p_loss']

team_master.to_csv(OUTPUT_DIR / 'team_master.csv', index=False)
print(f"\n✓ Guardado: team_master.csv ({len(team_master)} equipos x {len(team_master.columns)} columnas)")
print("\nMuestra - Colombia:")
print(team_master[team_master['team'] == 'Colombia'][['team','group','fifa_rank','p_advance_r32','p_champion','match1_opponent','match1_score','match1_p_win','match2_opponent','match2_score','match3_opponent','match3_score']].to_string(index=False))

# Guardar certeza de grupos
group_certainty = []
for g, counter in group_order_count.items():
    order, count = counter.most_common(1)[0]
    group_certainty.append({
        'group': g,
        'most_likely_order': f"{order[0]} > {order[1]} > {order[2]} > {order[3]}",
        'certainty_pct': round(count / N_SIMS * 100, 1)
    })

certainty_df = pd.DataFrame(group_certainty).sort_values('group')
certainty_df.to_csv(OUTPUT_DIR / 'group_certainty.csv', index=False)
print("\n✓ Guardado: group_certainty.csv")
