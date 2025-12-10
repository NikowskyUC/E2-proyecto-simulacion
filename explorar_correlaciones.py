"""
Script para explorar correlaciones entre posibles variables de control y la Utilidad
"""

import numpy as np
import simpy as sp
from simulacion_E3_reduccion_combinada import Pizzeria
import pandas as pd

# Modificar clase Pizzeria para recoger más variables
class PizzeriaExtendida(Pizzeria):
    def obtener_metricas(self):
        metricas = super().obtener_metricas()
        
        # Agregar más variables potenciales de control
        metricas['Total Llamadas Atendidas'] = self.llamadas_totales - self.llamadas_perdidas
        metricas['Total Pedidos'] = self.pedidos_normales_totales + self.pedidos_premium_totales
        metricas['Proporcion Premium'] = self.pedidos_premium_totales / (self.pedidos_normales_totales + self.pedidos_premium_totales) if (self.pedidos_normales_totales + self.pedidos_premium_totales) > 0 else 0
        metricas['Total Salsa Usada'] = 15000 - self.salsa_de_tomate.level
        metricas['Total Queso Usado'] = 1000 - self.queso_mozzarella.level
        metricas['Total Pepperoni Usado'] = 800 - self.pepperoni.level
        metricas['Total Mix Carnes Usado'] = 600 - self.mix_carnes.level
        metricas['Pizzas Queso'] = self.pizzas_queso
        metricas['Pizzas Pepperoni'] = self.pizzas_pepperoni
        metricas['Pizzas Carnes'] = self.pizzas_carnes
        
        return metricas

# Ejecutar 100 réplicas para obtener datos
print("Ejecutando 100 réplicas para analizar correlaciones...")
print("="*80 + "\n")

tiempo_simulacion = 168
n_replicas = 100

datos = []
for i in range(n_replicas):
    env = sp.Environment()
    pizzeria = PizzeriaExtendida(env)
    pizzeria.iniciar_simulacion(tiempo_simulacion, seed=i, logs=False)
    metricas = pizzeria.obtener_metricas()
    datos.append(metricas)
    
    if (i+1) % 10 == 0:
        print(f"Réplicas completadas: {i+1}/{n_replicas}")

print("\n" + "="*80)
print("ANÁLISIS DE CORRELACIONES CON UTILIDAD")
print("="*80 + "\n")

# Convertir a DataFrame
df = pd.DataFrame(datos)

# Variables candidatas para control (excluir métricas no numéricas y la Utilidad misma)
variables_candidatas = [
    'Total Pizzas',
    'Total Llamadas Atendidas', 
    'Total Pedidos',
    'Proporcion Premium',
    'Total Salsa Usada',
    'Total Queso Usado',
    'Total Pepperoni Usado',
    'Total Mix Carnes Usado',
    'Pizzas Queso',
    'Pizzas Pepperoni',
    'Pizzas Carnes'
]

# Calcular correlaciones con Utilidad
correlaciones = {}
for var in variables_candidatas:
    corr = df['Utilidad'].corr(df[var])
    correlaciones[var] = corr

# Ordenar por valor absoluto de correlación
correlaciones_ordenadas = sorted(correlaciones.items(), key=lambda x: abs(x[1]), reverse=True)

print("Correlaciones con Utilidad (ordenadas por |r|):")
print("-" * 80)
print(f"{'Variable':<40} {'Correlación':>15} {'|r|':>10}")
print("-" * 80)
for var, corr in correlaciones_ordenadas:
    print(f"{var:<40} {corr:>15.4f} {abs(corr):>10.4f}")

# Calcular matriz de correlaciones entre las variables candidatas
print("\n" + "="*80)
print("MATRIZ DE CORRELACIONES ENTRE VARIABLES CANDIDATAS")
print("="*80 + "\n")

matriz_corr = df[variables_candidatas].corr()
print(matriz_corr.round(3))

# Buscar pares de variables con buena correlación con Y y baja entre ellas
print("\n" + "="*80)
print("PARES DE VARIABLES RECOMENDADAS (alta corr con Y, baja corr entre sí)")
print("="*80 + "\n")

umbral_corr_Y = 0.3  # Mínimo |r| con Utilidad
umbral_corr_X = 0.5  # Máximo |r| entre las variables

print(f"Criterios: |corr(Y,Xi)| > {umbral_corr_Y} y |corr(X1,X2)| < {umbral_corr_X}\n")

pares_buenos = []
for i, (var1, corr1) in enumerate(correlaciones_ordenadas):
    if abs(corr1) < umbral_corr_Y:
        continue
    for var2, corr2 in correlaciones_ordenadas[i+1:]:
        if abs(corr2) < umbral_corr_Y:
            continue
        corr_entre_vars = matriz_corr.loc[var1, var2]
        if abs(corr_entre_vars) < umbral_corr_X:
            pares_buenos.append((var1, var2, corr1, corr2, corr_entre_vars))

if pares_buenos:
    print(f"{'Variable 1':<30} {'Variable 2':<30} {'r(Y,X1)':>10} {'r(Y,X2)':>10} {'r(X1,X2)':>10}")
    print("-" * 100)
    for var1, var2, corr1, corr2, corr_x in pares_buenos[:10]:  # Mostrar top 10
        print(f"{var1:<30} {var2:<30} {corr1:>10.4f} {corr2:>10.4f} {corr_x:>10.4f}")
else:
    print("No se encontraron pares que cumplan los criterios.")
    print("\nIntenta reducir los umbrales o usa variables con correlaciones moderadas.")

print("\n" + "="*80)
print("RECOMENDACIONES")
print("="*80)
print("\nBasa tu elección en:")
print("  1. Variables con |r(Y,Xi)| > 0.3 (idealmente > 0.4)")
print("  2. Variables con |r(X1,X2)| < 0.5 (idealmente < 0.3)")
print("  3. Prioriza pares con suma de |r(Y,X1)| + |r(Y,X2)| más alta")
print("="*80 + "\n")

# Guardar resultados
df_corr = pd.DataFrame(correlaciones_ordenadas, columns=['Variable', 'Correlación con Utilidad'])
df_corr['|r|'] = df_corr['Correlación con Utilidad'].abs()
df_corr.to_csv('correlaciones_variables.csv', index=False)

matriz_corr.to_csv('matriz_correlaciones.csv')

print("Resultados guardados en:")
print("  - correlaciones_variables.csv")
print("  - matriz_correlaciones.csv")
