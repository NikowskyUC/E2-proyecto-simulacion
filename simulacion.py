import numpy as np
import simpy as sp
import math

logs = False
tiempo_simulacion = 168 # horas

class Pizzeria:

    def __init__(self, env):
        self.env = env

        # Recursos
        self.cantidad_lineas = 3
        self.lineas_telefonicas = sp.PriorityResource(env, capacity=self.cantidad_lineas)

        self.capacidad_estacion_preparacion = 3
        self.estacion_preparacion = sp.PriorityResource(env, capacity=self.capacidad_estacion_preparacion)

        self.capacidad_horno = 10
        self.horno = sp.Resource(env, capacity=self.capacidad_horno)

        self.capacidad_estacion_embalaje = 3
        self.estacion_embalaje = sp.PriorityResource(env, capacity=self.capacidad_estacion_embalaje)

        # Empleados
        self.cantidad_trabajadores = 5
        self.trabajadores = sp.Resource(env, capacity=self.cantidad_trabajadores)

        self.cantidad_repartidores = 6
        self.repartidores = sp.Resource(env, capacity=self.cantidad_repartidores)

        # Inventarios
        self.salsa_de_tomate = sp.Container(env, init=15000, capacity=15000) # en ml
        self.queso_mozzarella = sp.Container(env, init=1000, capacity=1000) # en unidades
        self.pepperoni = sp.Container(env, init=800, capacity=800) # en unidades
        self.mix_carnes = sp.Container(env, init=600, capacity=600) # en unidades

        # Ingresos
        self.precio_pizza_queso = 7000
        self.precio_pizza_pepperoni = 9000
        self.precio_pizza_mix_carnes = 12000

        # Costos
        self.costo_pizza_queso = 7000 * 0.3
        self.costo_pizza_pepperoni = 9000 * 0.3
        self.costo_pizza_mix_carnes = 12000 * 0.3
        self.costo_llamada_perdida = 10000

        self.costo_hora_trabajador = 4000
        self.costo_hora_repartidor = 3000

        self.costo_fijo_lineas_telefonicas = 50000 # semanal
        self.costo_fijo_espacio_preparacion = 60000 # semanal
        self.costo_fijo_horno = 40000 # semanal
        self.costo_fijo_embalaje = 30000 # semanal
        self.costos_fijos = (self.costo_fijo_lineas_telefonicas +
                                     self.costo_fijo_espacio_preparacion +
                                     self.costo_fijo_horno +
                                     self.costo_fijo_embalaje)
        
        # Tasas de llegada de llamadas
        self.tasas_dia_normal ={10: 2,
                                11: 6,
                                12: 12,
                                13: 20,
                                14: 12,
                                15: 14,
                                16: 12,
                                17: 10,
                                18: 9,
                                19: 8,
                                20: 6,
                                21: 4}
        
        self.tasas_finde = {10: 2,
                            11: 8,
                            12: 18,
                            13: 25,
                            14: 25,
                            15: 24,
                            16: 18,
                            17: 12,
                            18: 11,
                            19: 10,
                            20: 9,
                            21: 8,
                            22: 6,
                            23: 4}

        # Medidas auxiliares
        self.llamadas_totales = 0
        self.llamadas_perdidas = 0
        self.pedidos_normales_totales = 0
        self.pedidos_premium_totales = 0
        self.pedidos_tardios_normales = 0
        self.pedidos_tardios_premium = 0
        self.tiempos_procesamiento_normales = []
        self.tiempos_procesamiento_premium = []
        self.ingresos = 0
        self.costos = 0
        
        # Métricas
        self.proporcion_llamadas_perdidas = 0
        self.proporcion_pedidos_tardios_normales = 0
        self.proporcion_pedidos_tardios_premium = 0
        self.tiempo_promedio_procesamiento_normales = 0
        self.tiempo_promedio_procesamiento_premium = 0
        self.utilidad = 0

    
    def iniciar_simulacion(self, tiempo_horas, seed, logs=False):
        self.tiempo_limite = tiempo_horas
        self.logs = logs
        self.log_data = ''

        self.rng = np.random.default_rng(seed)

        if self.logs:
            self.log(f'Iniciando simulación por {tiempo_horas} horas con semilla {seed}')
        
        self.env.process(self.llegada_llamadas())

        self.env.run(until=tiempo_horas)
        
    
    def log(self, mensaje):
        print(mensaje)
        self.log_data += mensaje + '\n'

    
    def obtener_tiempo_proxima_llamada(self, now):
        # Tasa de llamadas por hora según el horario del día
        hora_y_minuto_del_dia = now % 24 # Ejemplo: 14.5 -> 14:30 hrs
        hora_del_dia = math.floor(hora_y_minuto_del_dia) # Hora sin minutos
        dia = now // 24 # Día desde el inicio de la simulación (empieza en 0)

         # Diferenciar entre días laborables y fines de semana
        es_finde = (dia % 7) in [5, 6]  # Sábado y domingo

        if es_finde:
            if hora_del_dia < 10:
                tasa = self.tasas_finde[10]
                tiempo_proxima_llamada = 10 - hora_y_minuto_del_dia + self.rng.exponential(1 / tasa)
                # Avanzar a las 10 hrs + tiempo hasta la proxima llamada con la tasa de las 10 hrs
            else:
                tasa = self.tasas_finde[hora_del_dia] # Tomar tasa correspondiente a la hora actual
                tiempo_proxima_llamada = self.rng.exponential(1 / tasa) 
        else: # Dia normal
            if hora_del_dia < 10:
                tasa = self.tasas_dia_normal[10] 
                tiempo_proxima_llamada = 10 - hora_y_minuto_del_dia + self.rng.exponential(1 / tasa)
            elif hora_del_dia > 21:
                # Se avanza el tiempo al dia siguiente las 10 hrs
                tiempo_para_dia_siguiente = 24 - hora_y_minuto_del_dia + 10
                dia_siguiente = now + tiempo_para_dia_siguiente
                dia_siguiente_es_finde = (dia_siguiente // 24) % 7 in [5, 6]
                if dia_siguiente_es_finde:
                    tasa = self.tasas_finde[10]
                else:
                    tasa = self.tasas_dia_normal[10]
                tiempo_proxima_llamada = tiempo_para_dia_siguiente + self.rng.exponential(1 / tasa)
            else:
                tasa = self.tasas_dia_normal[hora_del_dia] # Tomar tasa correspondiente a la hora actual
                tiempo_proxima_llamada = self.rng.exponential(1 / tasa)

        return tiempo_proxima_llamada

    
    def llegada_llamadas(self):
        while True:
            tiempo_proxima_llamada = self.obtener_tiempo_proxima_llamada(self.env.now)
            yield self.env.timeout(tiempo_proxima_llamada)

            # Añadir logica para manejar la llamada entrante y empezar el proceso de atención
    