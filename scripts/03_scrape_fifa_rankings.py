import pandas as pd

matches = pd.read_csv('wc_all_matches.csv')
fixtures = pd.read_csv('wc_2026_fixtures.csv')
teams    = pd.read_csv('wc_2026_teams.csv')

print("=== PARTIDOS HISTÓRICOS ===")
print(matches.shape)
print(matches.columns.tolist())
print(matches.head(3))

print("\n=== FIXTURE 2026 ===")
print(fixtures.shape)
print(fixtures.columns.tolist())
print(fixtures.head(3))

print("\n=== EQUIPOS ===")
print(teams.shape)
print(teams.columns.tolist())
print(teams.head(3))

print("=== GOLES POR EQUIPO EN MUNDIALES ===")
# Goles anotados como team1
goles_local = matches.groupby('team1')['score1'].mean()

# Goles anotados como team2  
goles_visita = matches.groupby('team2')['score2'].mean()

# Combinar
goles_promedio = pd.concat([goles_local, goles_visita]).groupby(level=0).mean()
print(goles_promedio.sort_values(ascending=False).head(10))

print("\n=== EQUIPOS EN FIXTURE 2026 QUE TIENEN HISTORIAL ===")
equipos_2026 = set(fixtures['team1'].tolist() + fixtures['team2'].tolist())
equipos_historico = set(matches['team1'].tolist() + matches['team2'].tolist())
con_historial = equipos_2026 & equipos_historico
sin_historial = equipos_2026 - equipos_historico
print(f"Con historial mundialista: {len(con_historial)}")
print(f"Sin historial (debut): {len(sin_historial)}")
print(f"Debutantes: {sin_historial}")
import pandas as pd

teams = pd.read_csv('wc_2026_teams.csv')
print(teams['team'].tolist())