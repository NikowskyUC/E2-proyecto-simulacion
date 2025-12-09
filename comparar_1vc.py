"""
Probar con UNA sola variable de control: Total Pizzas
Para evitar la redundancia de usar Pizzas y Pedidos (correlación 0.90)
"""
from simulacion_E3_variablecontrol import replicas_simulación

n_replicas_base = 80
n_replicas_vc = 100  # 20 calibración + 80 estimación
tiempo_horas = 168

print("="*80)
print("COMPARACIÓN: UNA VARIABLE DE CONTROL (Total Pizzas)")
print("="*80)
print(f"\nCaso Base: {n_replicas_base} réplicas")
print(f"Variable Control: {n_replicas_vc} réplicas (20% calibración + 80% estimación)\n")

# Caso base
print("Ejecutando CASO BASE...")
_, stats_base = replicas_simulación(n_replicas_base, tiempo_horas, usar_variable_control=False)

# Con variable de control
print("\nEjecutando con VARIABLE DE CONTROL (Pizzas)...")
_, stats_vc = replicas_simulación(n_replicas_vc, tiempo_horas, usar_variable_control=True)

# Comparación
reduccion = (stats_base['varianza'] - stats_vc['varianza']) / stats_base['varianza'] * 100
factor = stats_base['varianza'] / stats_vc['varianza']

print("\n" + "="*80)
print("COMPARACIÓN FINAL")
print("="*80)
print(f"\nCaso Base ({n_replicas_base} réplicas):")
print(f"  Varianza: {stats_base['varianza']:,.2f}")
print(f"  Desv. Std: ${stats_base['std']:,.2f}")

print(f"\nUna Variable de Control ({stats_vc['n_replicas']} réplicas de estimación):")
print(f"  Varianza: {stats_vc['varianza']:,.2f}")
print(f"  Desv. Std: ${stats_vc['std']:,.2f}")
print(f"  Correlación: {stats_vc['correlacion']:.4f}")
print(f"  Coeficiente c: {stats_vc['coeficiente']:.4f}")

print(f"\n{'REDUCCIÓN':^80}")
print("="*80)
print(f"  Reducción de varianza: {reduccion:.2f}%")
print(f"  Factor de reducción: {factor:.2f}x")
print("="*80)
