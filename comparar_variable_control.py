"""
Script para comparar la varianza con y sin variable de control
"""
from simulacion_E3_variablecontrol import replicas_simulación

# Parámetros
n_replicas = 100  # 100 réplicas totales
tiempo_horas = 168  # 1 semana

print("="*80)
print("COMPARACIÓN: VARIABLE DE CONTROL")
print("="*80)
print(f"\nParámetros:")
print(f"  - Tiempo de simulación: {tiempo_horas} horas (1 semana)")
print(f"  - Número de réplicas: {n_replicas}")
print(f"  - Métrica de interés: Utilidad")
print(f"  - Variable de control:")
print(f"    * X = Ingresos totales")
print(f"    * E[X] = $14,784,870 (calculado teóricamente)\n")

# Caso 1: Sin reducción de varianza (caso base)
print("\n" + "🔹"*40)
print("EJECUTANDO CASO BASE (sin reducción de varianza)...")
print("🔹"*40 + "\n")
resultados_base, stats_base = replicas_simulación(n_replicas, tiempo_horas, usar_variable_control=False)

# Caso 2: Con variable de control
print("\n" + "🔸"*40)
print("EJECUTANDO CON VARIABLE DE CONTROL...")
print("🔸"*40 + "\n")
resultados_vc, stats_vc = replicas_simulación(n_replicas, tiempo_horas, usar_variable_control=True)

# Comparación
print("\n" + "="*80)
print("COMPARACIÓN DE RESULTADOS")
print("="*80)

print(f"\n{'Método':<30} {'Media':<20} {'Varianza':<20} {'Desv. Std':<20}")
print("-"*80)
print(f"{'Caso Base':<30} ${stats_base['media']:>15,.2f}   {stats_base['varianza']:>15,.2f}   ${stats_base['std']:>15,.2f}")
print(f"{'Variable de Control':<30} ${stats_vc['media']:>15,.2f}   {stats_vc['varianza']:>15,.2f}   ${stats_vc['std']:>15,.2f}")
print("-"*80)

# Calcular reducción de varianza
reduccion_varianza = (stats_base['varianza'] - stats_vc['varianza']) / stats_base['varianza'] * 100
factor_reduccion = stats_base['varianza'] / stats_vc['varianza']

print(f"\n{'MEJORA CON VARIABLE DE CONTROL':^80}")
print("="*80)
print(f"  Reducción de varianza: {reduccion_varianza:.2f}%")
print(f"  Factor de reducción: {factor_reduccion:.2f}x")
print(f"  Interpretación: Para lograr la misma precisión que {n_replicas} réplicas base,")
print(f"                  solo necesitas {n_replicas/factor_reduccion:.0f} réplicas con variable de control")
print("\n  Diagnóstico:")
print(f"    Coeficiente de control: c = {stats_vc['coeficiente']:.4f}")
print(f"    Correlación(Utilidad, Ingresos) = {stats_vc['correlacion']:.4f}")
print(f"    E[Ingresos] teórico = ${stats_vc['E_ingresos']:,.0f}")
print(f"    E[Ingresos] observado = ${stats_vc['X_mean']:,.2f}")
print("="*80 + "\n")

# Guardar resultados en archivo
import pandas as pd

df_comparacion = pd.DataFrame({
    'Método': ['Caso Base', 'Variable de Control'],
    'Media': [stats_base['media'], stats_vc['media']],
    'Varianza': [stats_base['varianza'], stats_vc['varianza']],
    'Desviación Estándar': [stats_base['std'], stats_vc['std']],
    'N': [stats_base['n_replicas'], stats_vc['n_replicas']]
})

df_comparacion.to_csv('comparacion_variable_control.csv', index=False)
print("✅ Resultados guardados en 'comparacion_variable_control.csv'\n")
