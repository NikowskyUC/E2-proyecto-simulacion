from simulacion_E2_ICS2133 import resultados
import numpy as np
import scipy.stats as st
import matplotlib.pyplot as plt
import pandas as pd



# Fijamos alpha en 0.05
ALPHA = 0.05


def mann_whitney_test(sim, real, nombre):
    sim_ = sim[~np.isnan(sim)]
    real_ = real[~np.isnan(real)]

    if len(sim_) == 0 or len(real_) == 0:
        print(f"[Mann-Whitney] {nombre}: datos insuficientes (n_sim={len(sim_)}, n_real={len(real_)})")
        return np.nan, np.nan

    u_stat, p_val = st.mannwhitneyu(sim_, real_, alternative='two-sided')
    conclusion = "NO hay evidencia de diferencia (no rechazo H0)" if p_val >= 0.05 else "HAY evidencia de diferencia (rechazo H0)"
    print(f"[Mann-Whitney] {nombre}: U={u_stat:.1f}, p={p_val:.4f} → {conclusion}")
    return u_stat, p_val


def ic_diferencia_medias_welch(sim, real, nombre, alpha=0.05):
    sim_ = sim[~np.isnan(sim[nombre])]
    real_ = real[~np.isnan(real[nombre])]
    n1, n2 = len(sim_), len(real_)
    if n1 < 2 or n2 < 2:
        print(f"[IC Welch 95%] {nombre}: datos insuficientes (n_sim={n1}, n_real={n2})")
        return (np.nan, np.nan, np.nan, False)

    m1, m2 = np.mean(sim_), np.mean(real_)
    v1 = np.var(sim_, ddof=1) if n1 > 1 else 0.0
    v2 = np.var(real_, ddof=1) if n2 > 1 else 0.0

    se = np.sqrt(v1/n1 + v2/n2)
    if se == 0:
        diff = m1 - m2
        lo = hi = diff
        contiene_cero = (diff == 0.0)
    else:
        df = (v1/n1 + v2/n2)**2 / ((v1**2)/((n1**2)*(n1-1)) + (v2**2)/((n2**2)*(n2-1)))
        tcrit = st.t.ppf(1 - alpha/2, df)
        diff = m1 - m2
        lo, hi = diff - tcrit*se, diff + tcrit*se
        contiene_cero = (lo <= 0.0 <= hi)

    concl = "compatible (0 dentro del IC)" if contiene_cero else "difiere (0 fuera del IC)"
    print(f"[IC Welch 95%] {nombre}: diff={diff:.4f}, IC=({lo:.4f}, {hi:.4f}) → {concl}")
    return (diff, lo, hi, contiene_cero)

# Leemos los datos que nos entregan 
datos_validacion = pd.read_csv('E2-proyecto-simulacion/validar_pizzeria.csv').to_dict(orient='list')

titulos_metricas = ['Proporcion Llamadas Perdidas', 'Proporcion Pedidos Tardíos', 'Proporcion Tardíos Normal',
        'Proporcion Tardíos Premium', 'Tiempo Medio para Procesar un Pedido (min)',
        'Tiempo Medio para Procesar un Pedido Normal (min)', 'Tiempo Medio para Procesar un Pedido Premium (min)',
        'Utilidad']

# Formeteamos los datos reales para que queden como los del .csv

datos_reales = {
    'Proporcion Llamadas Perdidas':[],
    'Proporcion Pedidos Tardíos':[],
    'Proporcion Tardíos Normal':[],
    'Proporcion Tardíos Premium':[],
    'Tiempo Medio para Procesar un Pedido (min)':[],
    'Tiempo Medio para Procesar un Pedido Normal (min)':[],
    'Tiempo Medio para Procesar un Pedido Premium (min)':[],
    'Utilidad':[]
}

for resultado in resultados:
    datos_reales[titulos_metricas[0]].append(resultado[titulos_metricas[0]])
    datos_reales[titulos_metricas[1]].append(resultado[titulos_metricas[1]])
    datos_reales[titulos_metricas[2]].append(resultado[titulos_metricas[2]])
    datos_reales[titulos_metricas[3]].append(resultado[titulos_metricas[3]])
    datos_reales[titulos_metricas[4]].append(resultado[titulos_metricas[4]])
    datos_reales[titulos_metricas[5]].append(resultado[titulos_metricas[5]])
    datos_reales[titulos_metricas[6]].append(resultado[titulos_metricas[6]])
    datos_reales[titulos_metricas[7]].append(resultado[titulos_metricas[7]])




# Realizamos las pruebas estadísticas
mann_whitney_test(datos_reales, datos_validacion, titulos_metricas[0])