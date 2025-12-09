"""
Script para verificar que la reducción de varianza tan alta se debe a que
Utilidad = Ingresos - Costos, y estamos usando Ingresos como variable de control
"""
from simulacion_E3_multivc import replicas_simulación
import numpy as np

n_replicas = 100
tiempo_horas = 168

print("="*80)
print("VERIFICACIÓN: ¿Por qué la reducción de varianza es tan alta?")
print("="*80)
print("\nHipótesis: Utilidad = Ingresos - Costos")
print("Si usamos Ingresos como variable de control con c₁ ≈ 1,")
print("efectivamente estamos 'fijando' los ingresos en E[Ingresos]")
print("y solo queda la variabilidad de los Costos.\n")

# Ejecutar simulación sin variables de control
print("Ejecutando simulación para obtener datos brutos...\n")
resultados, stats = replicas_simulación(n_replicas, tiempo_horas, usar_variable_control=False)

# Extraer ingresos, costos y utilidades
utilidades = []
ingresos = []
costos = []

for resultado in resultados:
    utilidades.append(resultado['Utilidad'])
    ingresos.append(resultado['Ingresos'])
    costos.append(resultado['Ingresos'] - resultado['Utilidad'])  # Costos = Ingresos - Utilidad

utilidades = np.array(utilidades)
ingresos = np.array(ingresos)
costos = np.array(costos)

print("="*80)
print("ANÁLISIS DE VARIANZAS")
print("="*80)

var_utilidad = np.var(utilidades, ddof=1)
var_ingresos = np.var(ingresos, ddof=1)
var_costos = np.var(costos, ddof=1)
cov_ingresos_costos = np.cov(ingresos, costos, ddof=1)[0, 1]

print(f"\nVarianzas observadas:")
print(f"  Var(Utilidad) = {var_utilidad:,.2f}")
print(f"  Var(Ingresos) = {var_ingresos:,.2f}")
print(f"  Var(Costos)   = {var_costos:,.2f}")
print(f"  Cov(Ingresos, Costos) = {cov_ingresos_costos:,.2f}")

# Verificar la fórmula: Var(U) = Var(I) + Var(C) - 2*Cov(I,C)
# donde U = Utilidad, I = Ingresos, C = Costos
var_utilidad_teorica = var_ingresos + var_costos - 2*cov_ingresos_costos
print(f"\nVerificación de Var(Utilidad) = Var(Ingresos) + Var(Costos) - 2*Cov(I,C):")
print(f"  Var(Utilidad) calculada directamente = {var_utilidad:,.2f}")
print(f"  Var(Utilidad) desde componentes      = {var_utilidad_teorica:,.2f}")
print(f"  Diferencia: {abs(var_utilidad - var_utilidad_teorica):,.2f}")

# Correlaciones
corr_utilidad_ingresos = np.corrcoef(utilidades, ingresos)[0, 1]
corr_utilidad_costos = np.corrcoef(utilidades, costos)[0, 1]
corr_ingresos_costos = np.corrcoef(ingresos, costos)[0, 1]

print(f"\nCorrelaciones:")
print(f"  Corr(Utilidad, Ingresos) = {corr_utilidad_ingresos:.4f}")
print(f"  Corr(Utilidad, Costos)   = {corr_utilidad_costos:.4f}")
print(f"  Corr(Ingresos, Costos)   = {corr_ingresos_costos:.4f}")

# Proporción de varianza explicada
prop_ingresos = var_ingresos / var_utilidad * 100
prop_costos = var_costos / var_utilidad * 100

print(f"\nContribución a la varianza de Utilidad:")
print(f"  Ingresos: {prop_ingresos:.1f}%")
print(f"  Costos:   {prop_costos:.1f}%")
print(f"  (La suma puede ser > 100% por la covarianza)")

print("\n" + "="*80)
print("CONCLUSIÓN")
print("="*80)
print(f"\nCuando usamos Ingresos como variable de control con c₁ ≈ 1:")
print(f"  - Eliminamos la varianza de los Ingresos ({var_ingresos:,.0f})")
print(f"  - Solo queda aproximadamente la varianza de los Costos ({var_costos:,.0f})")
print(f"  - Reducción esperada: {(1 - var_costos/var_utilidad)*100:.1f}%")
print(f"\nEsto explica por qué obtenemos ~99.6% de reducción de varianza.")
print(f"Es un resultado válido pero refleja la estructura del problema:")
print(f"Utilidad = Ingresos - Costos, y conocemos E[Ingresos] teórico.\n")
