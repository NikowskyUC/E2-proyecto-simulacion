# from simulacion_E2_ICS2133 import resultados
import numpy as np
import scipy.stats as st
import matplotlib.pyplot as plt
import pandas as pd



# Fijamos alpha en 0.05
ALPHA = 0.05


def u_test(x, y):
    Z = np.concatenate((x, y))
    Z_sorted = np.sort(Z)
    rank = Z.argsort().argsort() + 1
    R = np.sum(rank[:len(x)])

    mu_x = len(x)*(len(Z)+1)/2
    sd_x = np.sqrt(len(x)*len(y)*(len(Z)+1)/12)

    estadistico = (R-mu_x)/sd_x
    
    if st.norm.cdf(estadistico)>=0.5:
        p_value = 2*(1-st.norm.cdf(estadistico))
    else:
        p_value = 2*(st.norm.cdf(estadistico))

    print(f"p_value: {p_value}")
    print(f"estadistico: {estadistico}")
    print(f"R: {R}")
    return p_value, estadistico, R

def intervalo_t_pareado(x,y,alpha):
    n=len(x)
    z = x-y
    z_mean = np.mean(z)
    z_var = np.var(z)
    intervalo=[z_mean-st.t.ppf(1 - alpha / 2, df=n - 1)*np.sqrt(z_var/n),z_mean+st.t.ppf(1 - alpha / 2, df=n - 1)*np.sqrt(z_var/n)]
    
    print(f"Intervalo al {alpha} de confianza: [{intervalo[0]},{intervalo[1]}]")
    return intervalo

# Leemos los datos que nos entregan 
datos_validacion = pd.read_csv('validar_pizzeria.csv').to_dict(orient='list')




titulos_metricas = ['Proporcion Llamadas Perdidas', 'Proporcion Pedidos Tardíos', 'Proporcion Tardíos Normal',
        'Proporcion Tardíos Premium', 'Tiempo Medio para Procesar un Pedido (min)',
        'Tiempo Medio para Procesar un Pedido Normal (min)', 'Tiempo Medio para Procesar un Pedido Premium (min)',
        'Utilidad']

for i in titulos_metricas:
    print(datos_validacion[i])

