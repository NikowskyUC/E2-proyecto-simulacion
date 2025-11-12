from simulacion_E2_ICS2133 import resultados
import numpy as np
import scipy.stats as st
import matplotlib.pyplot as plt
import pandas as pd

# Fijamos alpha en 0.05
ALPHA = 0.05

promedios_resultados_metricas = {
    'Proporcion Llamadas Perdidas': 0,
    'Proporcion Pedidos Tardíos': 0,
    'Proporcion Tardíos Normal': 0,
    'Proporcion Tardíos Premium': 0,
    'Tiempo Medio para Procesar un Pedido (min)': 0,
    'Tiempo Medio para Procesar un Pedido Normal (min)': 0,
    'Tiempo Medio para Procesar un Pedido Premium (min)': 0,
    'Utilidad': 0
}

def mann_whitney_test(sim, real, nombre):

    stat, p = st.mannwhitneyu(sim, real, alternative="two-sided")
    
    print(f"Métrica: {nombre}")
    print(f"Estadístico U: {stat:.2f}")
    print(f"Valor-p: {p:.5f}")

    if p > (1 - ALPHA):
        print(f"Los datos son válidos con un nivel de confianza del {1 - ALPHA}")
    else:
        print(f"Los datos no son válidos con el nivel de confianza de {1 - ALPHA}")

    print()

def ks_test(sim, real, nombre):

    stat, p = st.ks_2samp(sim, real, alternative="two-sided")

    print(f"Métrica: {nombre} (KS)")
    print(f"Estadístico D: {stat:.4f}")
    print(f"Valor-p: {p:.5f}")

    if p > (1 - ALPHA):
        print(f"Los datos son válidos con un nivel de confianza del {1 - ALPHA}")
    else:
        print(f"Los datos no son válidos con el nivel de confianza de {1 - ALPHA}")
    print()


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

# CITA CHATGPT: "Tengo una lista con numeros arrays, necesito pasarlos a numeros normales"
def to_1d_numeric(seq):
    # Toma una lista que puede contener listas/arrays/escalars y la “aplana” a 1D float
    chunks = []
    for v in seq:
        if v is None:
            continue
        a = np.atleast_1d(v).astype(float, copy=False)
        chunks.append(a.ravel())
    if not chunks:
        return np.array([], dtype=float)
    return np.concatenate(chunks)
# FIN CITA CHATGPT

# Realizamos las pruebas estadísticas
for nombre in titulos_metricas:
    reales = to_1d_numeric(datos_reales[nombre])
    validacion = to_1d_numeric(datos_validacion[nombre])

    print(f"=== Métrica: {nombre} ===")
    print("Prueba de Mann-Whitney U:")
    mann_whitney_test(reales, validacion, nombre)
    print()

    print(f"=== Métrica: {nombre} ===")
    print("Prueba de KS:")
    ks_test(reales, validacion, nombre)
    print()
    print()

    # Recolectamos los datos de todas las replicas promedio por si nos sirve de algo en un futuro :)
    promedios_resultados_metricas[nombre] = round(float(np.mean(reales)), 2)

