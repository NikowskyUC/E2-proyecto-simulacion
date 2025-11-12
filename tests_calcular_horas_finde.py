from simulacion_E2_ICS2133 import Pizzeria
import simpy as sp

def main():
    env = sp.Environment()
    p = Pizzeria(env)
    casos = [24, 36, 48, 72]
    print('horas_trabajo_finde =', p.horas_trabajo_finde)
    for t in casos:
        horas = p.calcular_horas_finde(t)
        print(f'tiempo={t}h -> horas_finde={horas}')

if __name__ == '__main__':
    main()
