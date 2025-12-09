"""
Script para comparar la varianza con y sin variables antitéticas
"""
from simulacion_E3_antiteticas import replicas_simulación

# Parámetros
n_replicas = 100  # 100 réplicas totales
tiempo_horas = 168  # 1 semana

print("="*80)
print("COMPARACIÓN DE MÉTODOS DE REDUCCIÓN DE VARIANZA")
print("="*80)
print(f"\nParámetros:")
print(f"  - Tiempo de simulación: {tiempo_horas} horas (1 semana)")
print(f"  - Número de réplicas: {n_replicas}")
print(f"  - Métrica de interés: Utilidad\n")

# Caso 1: Sin reducción de varianza (caso base)
print("\n" + "🔹"*40)
print("EJECUTANDO CASO BASE (sin reducción de varianza)...")
print("🔹"*40 + "\n")
resultados_base, stats_base = replicas_simulación(n_replicas, tiempo_horas, usar_antiteticas=False)

# Caso 2: Con variables antitéticas
print("\n" + "🔸"*40)
print("EJECUTANDO CON VARIABLES ANTITÉTICAS...")
print("🔸"*40 + "\n")
resultados_anti, stats_anti = replicas_simulación(n_replicas, tiempo_horas, usar_antiteticas=True)

# Comparación
print("\n" + "="*80)
print("COMPARACIÓN DE RESULTADOS")
print("="*80)

print(f"\n{'Método':<30} {'Media':<20} {'Varianza':<20} {'Desv. Std':<20}")
print("-"*80)
print(f"{'Caso Base':<30} ${stats_base['media']:>15,.2f}   {stats_base['varianza']:>15,.2f}   ${stats_base['std']:>15,.2f}")
print(f"{'Variables Antitéticas':<30} ${stats_anti['media']:>15,.2f}   {stats_anti['varianza']:>15,.2f}   ${stats_anti['std']:>15,.2f}")
print("-"*80)

# Calcular reducción de varianza
reduccion_varianza = (stats_base['varianza'] - stats_anti['varianza']) / stats_base['varianza'] * 100
factor_reduccion = stats_base['varianza'] / stats_anti['varianza']

print(f"\n{'MEJORA CON VARIABLES ANTITÉTICAS':^80}")
print("="*80)
print(f"  Reducción de varianza: {reduccion_varianza:.2f}%")
print(f"  Factor de reducción: {factor_reduccion:.2f}x")
print(f"  Interpretación: Para lograr la misma precisión que {n_replicas} réplicas base,")
print(f"                  solo necesitas {n_replicas/factor_reduccion:.0f} réplicas con variables antitéticas")
print("="*80 + "\n")

# Guardar resultados en archivo
import pandas as pd

df_comparacion = pd.DataFrame({
    'Método': ['Caso Base', 'Variables Antitéticas'],
    'Media': [stats_base['media'], stats_anti['media']],
    'Varianza': [stats_base['varianza'], stats_anti['varianza']],
    'Desviación Estándar': [stats_base['std'], stats_anti['std']],
    'N': [stats_base['n_replicas'], stats_anti['n_pares']]
})

df_comparacion.to_csv('comparacion_varianza.csv', index=False)
print("✅ Resultados guardados en 'comparacion_varianza.csv'\n")
