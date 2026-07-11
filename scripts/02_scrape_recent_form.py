import requests
from bs4 import BeautifulSoup
import csv
import time
import openpyxl

BASE_URL = "https://www.promiedos.com.ar"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"
}

RUTA_EXCEL = r"C:\Users\danis\Documents\Fifa World Cup 26\archive\RAKNIN.xlsx"
RUTA_CSV   = r"C:\Users\danis\Documents\Fifa World Cup 26\archive\mundial_2026_partidos.csv"


# --- Leer rankings desde tu Excel ---
def cargar_rankings(ruta_excel):
    rankings = {}
    wb = openpyxl.load_workbook(ruta_excel, read_only=True)
    ws = wb.active
    for row in ws.iter_rows(min_row=3, values_only=True):
        ranking = row[1]
        pais    = row[2]
        if ranking and pais:
            pais    = str(pais).strip().replace('\xa0', '')
            ranking = str(ranking).strip().replace('\xa0', '')
            try:
                rankings[pais] = int(ranking)
            except:
                pass
    print(f"Rankings cargados: {len(rankings)} países")
    return rankings


# --- Extraer URLs de todos los equipos ---
def obtener_equipos():
    url = f"{BASE_URL}/league/fifa-world-cup/fjda/equipos"
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    equipos = {}
    for link in soup.select("a[href*='/team/']"):
        nombre = link.text.strip()
        href   = link["href"]
        if nombre and href:
            equipos[nombre] = BASE_URL + href
    return equipos


# --- Extraer últimos 5 partidos de un equipo ---
def obtener_partidos(nombre, url, rankings):
    try:
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        tablas = soup.find_all("table")
        if len(tablas) < 2:
            return []

        partidos = []
        for fila in tablas[1].find_all("tr")[1:]:
            celdas = fila.find_all("td")
            if len(celdas) >= 4:
                fecha     = celdas[0].text.strip()
                lv        = celdas[1].text.strip()
                rival     = celdas[2].text.strip()
                resultado = celdas[3].text.strip()
                partidos.append({
                    "seleccion":         nombre,
                    "ranking_seleccion": rankings.get(nombre, "N/A"),
                    "fecha":             fecha,
                    "local_visitante":   lv,
                    "rival":             rival,
                    "resultado":         resultado,
                    "ranking_rival":     rankings.get(rival, "N/A"),
                })
        return partidos
    except Exception as e:
        print(f"  Error con {nombre}: {e}")
        return []


# --- Datos manuales: equipos sin página en Promiedos ---
def datos_manuales(rankings):
    filas_crudas = [
        ("Japón",18,"31/05/2026","L","Islandia","1-0",75),
        ("Japón",18,"31/03/2026","V","Inglaterra","1-0",4),
        ("Japón",18,"28/03/2026","V","Escocia","1-0",43),
        ("Japón",18,"18/11/2025","L","Bolivia","3-0",76),
        ("Japón",18,"14/11/2025","L","Ghana","2-0",74),

        ("Corea del Sur",25,"04/06/2026","L","El Salvador","1-0",100),
        ("Corea del Sur",25,"31/05/2026","L","Trinidad y Tobago","5-0",102),
        ("Corea del Sur",25,"31/03/2026","V","Austria","0-1",24),
        ("Corea del Sur",25,"28/03/2026","V","Costa de Marfil","0-4",34),
        ("Corea del Sur",25,"18/11/2025","L","Ghana","1-0",74),

        ("Australia",27,"06/06/2026","L","Suiza","1-1",19),
        ("Australia",27,"30/05/2026","V","México","0-1",15),
        ("Australia",27,"31/03/2026","L","Curazao","5-1",82),
        ("Australia",27,"27/03/2026","L","Camerún","1-0",45),
        ("Australia",27,"18/11/2025","V","Colombia","0-3",13),

        ("Irak",57,"09/06/2026","L","Venezuela","0-2",49),
        ("Irak",57,"04/06/2026","V","España","1-1",2),
        ("Irak",57,"29/05/2026","L","Andorra","1-0",173),
        ("Irak",57,"31/03/2026","L","Bolivia","2-1",76),
        ("Irak",57,"12/12/2025","V","Jordania","1-0",63),

        ("Costa de Marfil",34,"04/06/2026","V","Francia","2-1",1),
        ("Costa de Marfil",34,"31/03/2026","L","Escocia","1-0",43),
        ("Costa de Marfil",34,"28/03/2026","V","Corea del Sur","4-0",25),
        ("Costa de Marfil",34,"10/01/2026","V","Egipto","2-3",29),
        ("Costa de Marfil",34,"06/01/2026","L","Burkina Faso","3-0",62),

        ("Arabia Saudita",61,"09/06/2026","L","Senegal","0-0",14),
        ("Arabia Saudita",61,"31/05/2026","V","Ecuador","1-2",23),
        ("Arabia Saudita",61,"31/03/2026","V","Serbia","1-2",39),
        ("Arabia Saudita",61,"27/03/2026","V","Egipto","0-4",29),
        ("Arabia Saudita",61,"18/11/2025","V","Argelia","0-2",28),

        ("Sudáfrica",60,"07/06/2026","V","Jamaica","1-1",71),
        ("Sudáfrica",60,"30/05/2026","L","Nicaragua","0-0",131),
        ("Sudáfrica",60,"01/04/2026","L","Panamá","1-2",33),
        ("Sudáfrica",60,"28/03/2026","L","Panamá","1-1",33),
        ("Sudáfrica",60,"05/01/2026","V","Camerún","1-2",45),

        # Equipos del Mundial cuyo nombre Promiedos no detecta bien
        ("Jordania",63,"07/06/2026","V","Colombia","2-0",13),
        ("Jordania",63,"31/05/2026","V","Suiza","4-1",19),
        ("Jordania",63,"31/03/2026","L","Nigeria","2-2",26),
        ("Jordania",63,"27/03/2026","L","Costa Rica","2-2",51),
        ("Jordania",63,"18/12/2025","L","Marruecos","2-3",8),

        ("Cabo Verde",69,"06/06/2026","L","Bermuda","3-0",166),
        ("Cabo Verde",69,"31/05/2026","L","Serbia","3-0",39),
        ("Cabo Verde",69,"29/03/2026","L","Finlandia","1-1",73),
        ("Cabo Verde",69,"26/03/2026","V","Chile","4-2",54),
        ("Cabo Verde",69,"17/11/2025","V","Egipto","1-1",29),
    ]

    partidos = []
    for sel, rank_sel, fecha, lv, rival, resultado, rank_rival in filas_crudas:
        partidos.append({
            "seleccion":         sel,
            "ranking_seleccion": rank_sel,
            "fecha":             fecha,
            "local_visitante":   lv,
            "rival":             rival,
            "resultado":         resultado,
            "ranking_rival":     rank_rival,
        })
    return partidos


# --- MAIN ---
rankings = cargar_rankings(RUTA_EXCEL)

print("\nObteniendo equipos del Mundial 2026...")
equipos = obtener_equipos()
print(f"Equipos encontrados en Promiedos: {len(equipos)}\n")

# Equipos que ya cubrimos manualmente -> no los pidamos a Promiedos
EXCLUIR = {"Japón","Corea del Sur","Australia","Irak","Arabia Saudita",
           "Costa de Marfil","Sudáfrica","Jordania","Cabo Verde"}

todos_los_partidos = []

for nombre, url in equipos.items():
    if nombre in EXCLUIR:
        continue
    print(f"Extrayendo: {nombre}")
    partidos = obtener_partidos(nombre, url, rankings)
    print(f"  → {len(partidos)} partidos")
    if len(partidos) == 5:
        todos_los_partidos.extend(partidos)
    else:
        print(f"  ⚠ {nombre} no devolvió 5 partidos, se omite (revisar manualmente)")
    time.sleep(1)

print("\nAgregando equipos sin página en Promiedos...")
manuales = datos_manuales(rankings)
todos_los_partidos.extend(manuales)
print(f"  → {len(manuales)} filas manuales agregadas")

# --- Guardar CSV (utf-8-sig corrige los acentos en Excel) ---
with open(RUTA_CSV, "w", newline="", encoding="utf-8-sig") as f:
    campos = ["seleccion","ranking_seleccion","fecha","local_visitante","rival","resultado","ranking_rival"]
    writer = csv.DictWriter(f, fieldnames=campos, delimiter=";")
    writer.writeheader()
    writer.writerows(todos_los_partidos)

print(f"\n✓ Listo. {len(todos_los_partidos)} filas guardadas en '{RUTA_CSV}'")
print(f"  Selecciones totales: {len(set(p['seleccion'] for p in todos_los_partidos))}")