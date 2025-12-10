import numpy as np
from simulacion_E3_antiteticas import Pizzeria
import simpy as sp

# Ejecutar 20 pares y ver la correlación
utilidades_normales = []
utilidades_anti = []

print("Ejecutando 20 pares para analizar correlación...")
for i in range(20):
    rng_anti = np.random.default_rng(999999 + i)
    uniformes_coccion = rng_anti.uniform(0, 1, 1700)
    uniformes_despacho_ida = rng_anti.uniform(0, 1, 1000)
    uniformes_despacho_vuelta = rng_anti.uniform(0, 1, 1000)
    uniformes_llamada = rng_anti.uniform(0, 1, 1000)
    uniformes_cantidad_queso = rng_anti.uniform(0, 1, 1700)
    uniformes_tiempo_queso = rng_anti.uniform(0, 1, 1700)
    
    # Normal
    env = sp.Environment()
    pizzeria = Pizzeria(env)
    pizzeria.iniciar_simulacion(168, 2*i, logs=False,
                               uniformes_coccion=uniformes_coccion,
                               uniformes_despacho_ida=uniformes_despacho_ida,
                               uniformes_despacho_vuelta=uniformes_despacho_vuelta,
                               uniformes_llamada=uniformes_llamada,
                               uniformes_cantidad_queso=uniformes_cantidad_queso,
                               uniformes_tiempo_queso=uniformes_tiempo_queso)
    utilidades_normales.append(pizzeria.obtener_metricas()['Utilidad'])
    
    # Antitética
    env = sp.Environment()
    pizzeria = Pizzeria(env)
    pizzeria.iniciar_simulacion(168, 2*i+1, logs=False,
                               uniformes_coccion=1-uniformes_coccion,
                               uniformes_despacho_ida=1-uniformes_despacho_ida,
                               uniformes_despacho_vuelta=1-uniformes_despacho_vuelta,
                               uniformes_llamada=1-uniformes_llamada,
                               uniformes_cantidad_queso=1-uniformes_cantidad_queso,
                               uniformes_tiempo_queso=1-uniformes_tiempo_queso)
    utilidades_anti.append(pizzeria.obtener_metricas()['Utilidad'])
    print(f'Par {i+1}: Normal=${utilidades_normales[-1]:,.0f}, Anti=${utilidades_anti[-1]:,.0f}, Diff=${abs(utilidades_normales[-1]-utilidades_anti[-1]):,.0f}')

utilidades_normales = np.array(utilidades_normales)
utilidades_anti = np.array(utilidades_anti)

correlacion = np.corrcoef(utilidades_normales, utilidades_anti)[0,1]
var_normal = np.var(utilidades_normales, ddof=1)
var_anti = np.var(utilidades_anti, ddof=1)
var_promedios = np.var((utilidades_normales + utilidades_anti)/2, ddof=1)

print(f'\n{"="*70}')
print("ANÁLISIS DE CORRELACIÓN")
print(f'{"="*70}')
print(f'Correlación entre pares: {correlacion:.4f}')
print(f'\nVarianza de réplicas normales: {var_normal:,.2f}')
print(f'Varianza de réplicas antitéticas: {var_anti:,.2f}')
print(f'Varianza promedio individual: {(var_normal + var_anti)/2:,.2f}')
print(f'\nVarianza de promedios de pares: {var_promedios:,.2f}')
print(f'\nTEORÍA:')
print(f'  Var(promedio par) = Var(X)/2 * (1 + ρ)')
print(f'  donde ρ = correlación entre X_normal y X_anti')
print(f'\n  Factor (1 + ρ) = {1 + correlacion:.4f}')
print(f'  Varianza esperada = {(var_normal + var_anti)/4 * (1 + correlacion):,.2f}')
print(f'  Varianza observada = {var_promedios:,.2f}')
print(f'\nCONCLUSIÓN:')
if correlacion < -0.1:
    print(f'  ✓ Correlación NEGATIVA fuerte: Variables antitéticas funcionan bien')
    reduccion = (1 - var_promedios / ((var_normal + var_anti)/4)) * 100
    print(f'  ✓ Reducción de varianza teórica: {(1 - (1+correlacion)/2)*100:.1f}%')
elif correlacion < 0:
    print(f'  ~ Correlación NEGATIVA débil: Variables antitéticas funcionan parcialmente')
    print(f'  ~ Reducción de varianza teórica: {(1 - (1+correlacion)/2)*100:.1f}%')
elif correlacion > 0.1:
    print(f'  ✗ Correlación POSITIVA: Variables antitéticas AUMENTAN varianza')
    print(f'  ✗ Incremento de varianza teórico: {((1+correlacion)/2 - 1)*100:.1f}%')
else:
    print(f'  - Correlación cercana a cero: Variables antitéticas no tienen efecto')
print(f'{"="*70}')
