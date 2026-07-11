import pandas as pd

url = "https://www.transfermarkt.co/vereins-statistik/wertvollstenationalmannschaften/marktwertetop?kontinent_id=0&plus=1"

tablas = pd.read_html(url, storage_options={"User-Agent": "Mozilla/5.0"})
df = tablas[1]

# Filas útiles: las que tienen número en '#' O número en 'País'
filas_data = []

for i in range(0, len(df)-1, 2):  # saltar de 2 en 2, ignorar filas duplicadas
    fila = df.iloc[i]
    
    # Fila 0 tiene estructura normal
    if pd.notna(fila['#']):
        filas_data.append({
            'pais': fila['País'],
            'confederacion': fila['Confederación'],
            'edad_promedio': fila['ø-Edad'],
            'valor_mercado': fila['Valor de mercado']
        })
    # Resto tiene estructura desplazada
    else:
        filas_data.append({
            'pais': fila['Confederación'],
            'confederacion': fila['Integrantes de la primera plantilla'],
            'edad_promedio': fila['ø-Edad'],
            'valor_mercado': fila['Valor de mercado']
        })

df_limpio = pd.DataFrame(filas_data)

# Limpiar valor de mercado
def limpiar_valor(valor):
    if pd.isna(valor):
        return None
    valor = str(valor).replace('€','').replace(' ','').replace(',','.')
    if 'milmill.' in valor:
        return float(valor.replace('milmill.','')) * 1_000_000_000
    elif 'mill.' in valor:
        return float(valor.replace('mill.','')) * 1_000_000
    return None

df_limpio['valor_mercado_eur'] = df_limpio['valor_mercado'].apply(limpiar_valor)
df_limpio['edad_promedio'] = pd.to_numeric(df_limpio['edad_promedio'], errors='coerce')
df_limpio = df_limpio.drop(columns=['valor_mercado'])

print(df_limpio.shape)
print(df_limpio.to_string())

df_limpio.to_csv('transfermarkt_valores.csv', index=False)
print("\n✅ Guardado como transfermarkt_valores.csv")