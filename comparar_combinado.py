"""
Script de comparación: Caso Base vs Método Combinado (Variables Antitéticas + Variable de Control)

Compara la reducción de varianza al combinar ambos métodos contra el caso base sin reducción.
"""

import numpy as np
import simpy as sp
from simulacion_E3_reduccion_combinada import Pizzeria, replicas_simulación
import pandas as pd

# Parámetros de simulación
tiempo_simulacion = 168  # 1 semana
n_replicas_base = 100
n_replicas_combinado = 100  # 100 réplicas = 50 pares antitéticos, luego aplica VC

print("="*80)
print("COMPARACIÓN: CASO BASE vs MÉTODO COMBINADO")
print("="*80)
print(f"\nParámetros:")
print(f"  - Caso Base: {n_replicas_base} réplicas")
print(f"  - Método Combinado: {n_replicas_combinado} réplicas")
print(f"    * Variables Antitéticas: 50 pares (100 réplicas)")
print(f"    * Variable de Control: Tiempo Promedio de Cocción")
print(f"    * Calibración: 20 réplicas (20%)")
print(f"    * Estimación: 80 réplicas (80%)\n")

# Caso 1: Sin reducción de varianza (caso base)
print("\n" + "="*80)
print("EJECUTANDO CASO BASE (sin reducción de varianza)...")
print("="*80 + "\n")

utilidades_base = []
for i in range(n_replicas_base):
    env = sp.Environment()
    pizzeria = Pizzeria(env)
    pizzeria.iniciar_simulacion(tiempo_simulacion, seed=i, logs=False)
    metricas = pizzeria.obtener_metricas()
    utilidades_base.append(metricas['Utilidad'])
    print(f'Réplica {i+1} completada.')
    print("")
    print("--------------------------------")
    print("")

media_base = np.mean(utilidades_base)
varianza_base = np.var(utilidades_base, ddof=1)
std_base = np.sqrt(varianza_base)

stats_base = {
    'n_replicas': n_replicas_base,
    'media': media_base,
    'varianza': varianza_base,
    'std': std_base
}

print("\n" + "="*80)
print("RESULTADOS CASO BASE")
print("="*80)
print(f"Número de réplicas: {n_replicas_base}")
print(f"Media: ${media_base:,.2f}")
print(f"Varianza: {varianza_base:,.2f}")
print(f"Desviación estándar: ${std_base:,.2f}")
print("="*80 + "\n")

# Caso 2: Método Combinado (Variables Antitéticas + Variable de Control)
print("\n" + "="*80)
print("EJECUTANDO MÉTODO COMBINADO...")
print("="*80 + "\n")

lista_resultados, stats_combinado = replicas_simulación(n_replicas_combinado, tiempo_simulacion)

# Comparación final
print("\n" + "="*80)
print("COMPARACIÓN DE RESULTADOS")
print("="*80 + "\n")

print(f"{'Método':<40} {'Réplicas/Pares':<15} {'Media':<20} {'Varianza':<25} {'Desv. Std':<15}")
print("-"*115)
print(f"{'Caso Base':<40} {n_replicas_base:<15} ${stats_base['media']:>15,.2f}   {stats_base['varianza']:>20,.2f}   ${stats_base['std']:>12,.2f}")
print(f"{'Método Combinado':<40} {stats_combinado['n_pares_estim']:<15} ${stats_combinado['media']:>15,.2f}   {stats_combinado['varianza']:>20,.2f}   ${stats_combinado['std']:>12,.2f}")
print("-"*115)

# Calcular reducción de varianza
reduccion_varianza = (stats_base['varianza'] - stats_combinado['varianza']) / stats_base['varianza'] * 100
factor_reduccion = stats_base['varianza'] / stats_combinado['varianza']

print(f"\n{'MEJORA CON MÉTODO COMBINADO':^80}")
print("="*80)
print(f"  Reducción de varianza: {reduccion_varianza:.2f}%")
print(f"  Factor de reducción: {factor_reduccion:.2f}x")
print(f"  Interpretación: Para lograr la misma precisión que {n_replicas_base} réplicas base,")
print(f"                  solo necesitas ~{n_replicas_base/factor_reduccion:.0f} pares con método combinado")
print(f"                  (más {stats_combinado['n_calib']} réplicas para calibración)")

print(f"\n  Detalles del Método Combinado:")
print(f"    CORRECTAMENTE implementado: VC aplicado DENTRO de cada par antitético")
print(f"    Variables Antitéticas: {stats_combinado['n_pares_antiteticos']} pares")
print(f"    Variable de Control: Tiempo Promedio de Cocción")
print(f"    Coeficiente óptimo: c* = {stats_combinado['c_optimo']:.4f}")
print(f"    Correlación(Utilidad, Tiempo Cocción): {stats_combinado['correlacion_YX']:.4f}")
print(f"    E[Tiempo Cocción] teórico: {stats_combinado['E_coccion']:.2f} minutos")
print(f"    E[Tiempo Cocción] calibración: {stats_combinado['X_mean_calib']:.2f} minutos")
print("="*80 + "\n")

# Guardar resultados en CSV
resultados_comparacion = {
    'Método': ['Caso Base', 'Método Combinado'],
    'Réplicas/Pares': [n_replicas_base, stats_combinado['n_pares_estim']],
    'Media': [stats_base['media'], stats_combinado['media']],
    'Varianza': [stats_base['varianza'], stats_combinado['varianza']],
    'Desviación Estándar': [stats_base['std'], stats_combinado['std']],
    'Reducción Varianza (%)': [0, reduccion_varianza]
}

df_comparacion = pd.DataFrame(resultados_comparacion)
df_comparacion.to_csv('comparacion_combinado.csv', index=False)
print("Resultados guardados en: comparacion_combinado.csv")
