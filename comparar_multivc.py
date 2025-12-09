"""
Script para comparar múltiples variables de control vs caso base
IMPORTANTE: Usa 20% de réplicas para calibración y 80% para estimación
para evitar sesgo optimista en el cálculo de los coeficientes.
"""
from simulacion_E3_multivc import replicas_simulación

# Parámetros
# Para comparación justa: mismo número de réplicas efectivas
n_replicas_base = 80   # Réplicas para caso base
n_replicas_vc = 100     # Total para VC: 20 calibración + 80 estimación
tiempo_horas = 168      # 1 semana

print("="*80)
print("COMPARACIÓN: MÚLTIPLES VARIABLES DE CONTROL")
print("="*80)
print(f"\nParámetros:")
print(f"  - Caso Base: {n_replicas_base} réplicas")
print(f"  - Variables de Control: {n_replicas_vc} réplicas")
print(f"    * Calibración: {int(0.4 * n_replicas_vc)} réplicas (40%)")
print(f"    * Estimación: {int(0.6 * n_replicas_vc)} réplicas (60%)")
print(f"  - Variables de control (SIN usar Ingresos):")
print(f"    * X1 = Total pizzas producidas, E[X1] = 1589 pizzas")
print(f"    * X2 = Tiempo promedio cocción, E[X2] = 12.43 min")
print(f"    * X3 = Tiempo promedio despacho, E[X3] = 6.75 min\n")

# Caso 1: Sin reducción de varianza (caso base)
print("\n" + "="*80)
print("EJECUTANDO CASO BASE (sin reducción de varianza)...")
print("="*80 + "\n")
_, stats_base = replicas_simulación(n_replicas_base, tiempo_horas, usar_variable_control=False)

# Caso 2: Con múltiples variables de control
print("\n" + "="*80)
print("EJECUTANDO CON MÚLTIPLES VARIABLES DE CONTROL...")
print("="*80 + "\n")
_, stats_mvc = replicas_simulación(n_replicas_vc, tiempo_horas, usar_variable_control=True)

# Comparación
print("\n" + "="*80)
print("COMPARACIÓN DE RESULTADOS")
print("="*80)

print(f"\n{'Método':<40} {'Réplicas':<12} {'Media':<20} {'Varianza':<25} {'Desv. Std':<15}")
print("-"*110)
print(f"{'Caso Base':<40} {n_replicas_base:<12} ${stats_base['media']:>15,.2f}   {stats_base['varianza']:>20,.2f}   ${stats_base['std']:>12,.2f}")
print(f"{'Múltiples VC (estimación)':<40} {stats_mvc['n_replicas']:<12} ${stats_mvc['media']:>15,.2f}   {stats_mvc['varianza']:>20,.2f}   ${stats_mvc['std']:>12,.2f}")
print("-"*110)

# Calcular reducción de varianza
reduccion_varianza = (stats_base['varianza'] - stats_mvc['varianza']) / stats_base['varianza'] * 100
factor_reduccion = stats_base['varianza'] / stats_mvc['varianza']

print(f"\n{'MEJORA CON MÚLTIPLES VARIABLES DE CONTROL':^80}")
print("="*80)
print(f"  Reducción de varianza: {reduccion_varianza:.2f}%")
print(f"  Factor de reducción: {factor_reduccion:.2f}x")
print(f"  Interpretación: Para lograr la misma precisión que {n_replicas_base} réplicas base,")
print(f"                  solo necesitas ~{n_replicas_base/factor_reduccion:.0f} réplicas de estimación con VC")
print(f"                  (más {stats_mvc['n_calib']} réplicas para calibración = {n_replicas_base/factor_reduccion + stats_mvc['n_calib']:.0f} total)")

print(f"\n  Coeficientes de control óptimos (calibrados con {stats_mvc['n_calib']} réplicas):")
print(f"    c1 (Pizzas) = {stats_mvc['coeficientes']['c1_pizzas']:.4f}")
print(f"    c2 (Cocción) = {stats_mvc['coeficientes']['c2_coccion']:.4f}")
print(f"    c3 (Despacho) = {stats_mvc['coeficientes']['c3_despacho']:.4f}")

print("\n  Diagnóstico de correlaciones (en datos de calibración):")
print(f"    Corr(Utilidad, Pizzas) = {stats_mvc['correlaciones']['Y_X1']:.4f}")
print(f"    Corr(Utilidad, Cocción) = {stats_mvc['correlaciones']['Y_X2']:.4f}")
print(f"    Corr(Utilidad, Despacho) = {stats_mvc['correlaciones']['Y_X3']:.4f}")
print(f"    Corr(Pizzas, Cocción) = {stats_mvc['correlaciones']['X1_X2']:.4f}")
print(f"    Corr(Pizzas, Despacho) = {stats_mvc['correlaciones']['X1_X3']:.4f}")
print(f"    Corr(Cocción, Despacho) = {stats_mvc['correlaciones']['X2_X3']:.4f}")

print("\n  Valores observados en calibración vs estimación:")
print(f"    E[Pizzas] teórico         = {stats_mvc['E_pizzas']}")
print(f"    E[Pizzas] calibración     = {stats_mvc['X1_mean_calib']:.2f}")
print(f"    E[Pizzas] estimación      = {stats_mvc['X1_mean_estim']:.2f}")
print(f"    E[Cocción] teórico        = {stats_mvc['E_tiempo_coccion']:.2f} min")
print(f"    E[Cocción] calibración    = {stats_mvc['X2_mean_calib']:.2f} min")
print(f"    E[Cocción] estimación     = {stats_mvc['X2_mean_estim']:.2f} min")
print(f"    E[Despacho] teórico       = {stats_mvc['E_tiempo_despacho']:.2f} min")
print(f"    E[Despacho] calibración   = {stats_mvc['X3_mean_calib']:.2f} min")
print(f"    E[Despacho] estimación    = {stats_mvc['X3_mean_estim']:.2f} min")
print("="*80 + "\n")

# Guardar resultados en CSV
import pandas as pd

resultados = {
    'Método': ['Caso Base', 'Múltiples VC'],
    'N_Replicas': [n_replicas_base, stats_mvc['n_replicas']],
    'N_Total_VC': ['-', stats_mvc['n_total']],
    'N_Calibracion': ['-', stats_mvc['n_calib']],
    'Media': [stats_base['media'], stats_mvc['media']],
    'Varianza': [stats_base['varianza'], stats_mvc['varianza']],
    'Desv_Std': [stats_base['std'], stats_mvc['std']],
    'Reduccion_Varianza_%': [0, reduccion_varianza],
    'Factor_Reduccion': [1.0, factor_reduccion]
}

df = pd.DataFrame(resultados)
archivo_salida = 'comparacion_multivc_corregido.csv'
df.to_csv(archivo_salida, index=False)
print(f"Resultados guardados en: {archivo_salida}\n")
