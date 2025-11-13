

import numpy as np
import simpy as sp
import math
import pandas as pd

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
        self.horno = sp.PriorityResource(env, capacity=self.capacidad_horno)

        self.capacidad_estacion_embalaje = 3
        self.estacion_embalaje = sp.PriorityResource(env, capacity=self.capacidad_estacion_embalaje)

        # Empleados
        self.cantidad_trabajadores = 5
        self.trabajadores = sp.PriorityResource(env, capacity=self.cantidad_trabajadores)

        self.cantidad_repartidores = 6
        self.repartidores = sp.PriorityResource(env, capacity=self.cantidad_repartidores)

        # Inventarios
        self.salsa_de_tomate = sp.Container(env, init=15000, capacity=15000) # en ml
        self.queso_mozzarella = sp.Container(env, init=1000, capacity=1000) # en unidades
        self.pepperoni = sp.Container(env, init=800, capacity=800) # en unidades
        self.mix_carnes = sp.Container(env, init=600, capacity=600) # en unidades

        self.inventarios = [self.salsa_de_tomate, self.queso_mozzarella,
                       self.pepperoni, self.mix_carnes]
        self.nombres_inventarios = {self.salsa_de_tomate: 'salsa de tomate',
                                    self.queso_mozzarella: 'queso mozzarella',
                                    self.pepperoni: 'pepperoni',
                                    self.mix_carnes: 'mix de carnes'}
        self.en_reposicion = {inventario: False for inventario in self.inventarios}
        self.umbral_reposicion = {self.salsa_de_tomate: 3000,
                                  self.queso_mozzarella: 200,
                                  self.pepperoni: 300,
                                  self.mix_carnes: 100}

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
        self.costos_fijos_semanales = (self.costo_fijo_lineas_telefonicas +
                                     self.costo_fijo_espacio_preparacion +
                                     self.costo_fijo_horno +
                                     self.costo_fijo_embalaje)
        
        # Es actualmente fin de semana?
        self.finde = False
        
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
        
        self.llamadas_normales_perdidas = 0
        self.llamadas_premium_perdidas = 0
        
        self.pedidos_tardios_normales_finde = 0
        self.pedidos_tardios_normales_semana = 0
        self.pedidos_tardios_premium_finde = 0
        self.pedidos_tardios_premium_semana = 0
        
        self.tiempos_procesamiento_normales_finde = []
        self.tiempos_procesamiento_normales_semana = []
        self.tiempos_procesamiento_premium_finde = []
        self.tiempos_procesamiento_premium_semana = []
        
        self.pizzas_queso = 0
        self.pizzas_pepperoni = 0
        self.pizzas_carnes = 0
        
        self.compensacion = 0
        
        self.horas_extras = 0
        # Última hora de finalización por día (day -> hora del día en que terminó el último pedido)
        self.ultima_hora_fin_por_dia = {}
        
        self.ingresos = 0 
        
        self.costos = 0 

        self.salario_hora_empleado = 4000
        self.salario_hora_repartidor = 3000
        self.horas_trabajo_dia_normal = 13
        self.horas_trabajo_finde = 15 
        
        
        # Métricas
        self.proporcion_llamadas_perdidas = 0
        
        self.proporcion_pedidos_tardios_normales_finde = 0
        self.proporcion_pedidos_tardios_normales_semana = 0
        self.proporcion_pedidos_tardios_premium_finde = 0
        self.proporcion_pedidos_tardios_premium_semana = 0
        
        self.tiempo_promedio_procesamiento_normales_finde = 0
        self.tiempo_promedio_procesamiento_normales_semana = 0
        self.tiempo_promedio_procesamiento_premium_finde = 0
        self.tiempo_promedio_procesamiento_premium_semana = 0
        
        self.utilidad = self.ingresos - self.costos

    
    def iniciar_simulacion(self, tiempo_horas, seed, logs=False):
        self.tiempo_limite = tiempo_horas + 10 # Se suma 10 para iniciar simulacion a las 10 AM
        self.logs = logs
        self.log_data = ''

        self.rng = np.random.default_rng(seed)

        if self.logs:
            self.log(f'Iniciando simulación por {tiempo_horas} horas con semilla {seed}')
        

        self.ultima_atencion = None
        self.evento_termino_simulacion = self.env.event()
        self.pedidos_activos = []  # Lista para rastrear todos los pedidos en proceso

        self.env.process(self.llegada_llamadas())
        self.env.process(self.revisar_inventario_salsa())
        self.env.process(self.revisar_inventarios())

        try:
            self.env.run(until=self.evento_termino_simulacion)
        except RuntimeError:
            # Si no hay más eventos programados, la simulación termina naturalmente
            if self.logs:
                self.log('Simulación terminó sin eventos pendientes.')

        if self.logs:
            self.log('Simulación terminada.')
            self.log(f'Tiempo de simulación: {self.env.now - 10} horas')
    
    
    
    def obtener_metricas(self):
        # Calculamos métricas

        # Calcular horas extras una vez por día usando la última finalización registrada
        self.horas_extras = 0
        for dia, hora_fin in self.ultima_hora_fin_por_dia.items():
            es_finde = (dia % 7) in [5, 6]
            if es_finde and 10 > hora_fin > 1:
                self.horas_extras += hora_fin
            elif (not es_finde) and (hora_fin > 23 or hora_fin < 10):
                self.horas_extras += (hora_fin - 23) if hora_fin > 23 else (hora_fin + 1)

        # Calcular horas de jornada efectivas durante la simulación
        # Nota: self.tiempo_limite se definió como tiempo_horas + 10 en iniciar_simulacion
        tiempo_simulacion_horas = getattr(self, 'tiempo_limite', 10) - 10
        horas_normales = self.calcular_horas_normales(tiempo_simulacion_horas)
        horas_finde = self.calcular_horas_finde(tiempo_simulacion_horas)
        horas_jornada_total = horas_normales + horas_finde

        # Semanas completas (redondeo hacia arriba). Si el tiempo_horas es 0 -> 0 semanas
        semanas = int(math.ceil(tiempo_simulacion_horas / 168.0)) if tiempo_simulacion_horas > 0 else 0

        # Costos por salario: asumir que cada trabajador/repartidor está contratado
        # para cubrir la jornada completa (modelo previo), por lo que multiplicamos
        # horas_jornada_total por la cantidad de empleados.
        costo_trabajadores = self.salario_hora_empleado * horas_jornada_total * self.cantidad_trabajadores
        costo_repartidores = self.salario_hora_repartidor * horas_jornada_total * self.cantidad_repartidores

        self.costos = (
            10_000 * self.llamadas_perdidas
            + 0.3 * 7_000 * self.pizzas_queso
            + 0.3 * 9_000 * self.pizzas_pepperoni
            + 0.3 * 12_000 * self.pizzas_carnes
            + self.costos_fijos_semanales * semanas
            + self.compensacion
            + costo_trabajadores
            + costo_repartidores
            + 1.4 * self.salario_hora_empleado * self.horas_extras * self.cantidad_trabajadores
            + 1.4 * self.salario_hora_repartidor * self.horas_extras * self.cantidad_repartidores
        )

        self.proporcion_llamadas_perdidas = self.llamadas_perdidas / self.llamadas_totales
        
        self.proporcion_pedidos_tardios_normales = (self.pedidos_tardios_normales_finde + self.pedidos_tardios_normales_semana) / self.pedidos_normales_totales
        self.proporcion_pedidos_tardios_premium = (self.pedidos_tardios_premium_finde + self.pedidos_tardios_premium_semana) / self.pedidos_premium_totales


        self.proporcion_pedidos_tardios = (self.pedidos_tardios_normales_finde + self.pedidos_tardios_normales_semana + self.pedidos_tardios_premium_finde + self.pedidos_tardios_premium_semana) / (self.pedidos_normales_totales + self.pedidos_premium_totales)
        
        # Tiempos en minutos
        self.tiempo_promedio_procesamiento_normales = np.mean(self.tiempos_procesamiento_normales_semana + self.tiempos_procesamiento_normales_finde) * 60
        self.tiempo_promedio_procesamiento_premium = np.mean(self.tiempos_procesamiento_premium_finde + self.tiempos_procesamiento_premium_semana) * 60 
        self.tiempo_promedio_procesamiento = np.mean(self.tiempos_procesamiento_premium_semana + self.tiempos_procesamiento_premium_finde + self.tiempos_procesamiento_normales_semana + self.tiempos_procesamiento_normales_finde) * 60
        
        self.utilidad = self.ingresos - self.costos
        
        return {
            'Proporcion Llamadas Perdidas': self.proporcion_llamadas_perdidas,
            'Proporcion Pedidos Tardíos': self.proporcion_pedidos_tardios,
            'Proporcion Tardíos Normal': self.proporcion_pedidos_tardios_normales,
            'Proporcion Tardíos Premium': self.proporcion_pedidos_tardios_premium,
            'Tiempo Medio para Procesar un Pedido (min)': self.tiempo_promedio_procesamiento,
            'Tiempo Medio para Procesar un Pedido Normal (min)': self.tiempo_promedio_procesamiento_normales,
            'Tiempo Medio para Procesar un Pedido Premium (min)': self.tiempo_promedio_procesamiento_premium,
            'Utilidad': self.utilidad
        }
    
    def log(self, mensaje):
        print(mensaje)
        self.log_data += mensaje + '\n'

    
    def obtener_tiempo_proxima_llamada(self, now): # retorna tiempo en horas
        # Tasa de llamadas por hora según el horario del día
        hora_y_minuto_del_dia = now % 24 # Ejemplo: 14.5 -> 14:30 hrs
        hora_del_dia = math.floor(hora_y_minuto_del_dia) # Hora sin minutos
        dia = now // 24 # Día desde el inicio de la simulación (empieza en 0)

         # Diferenciar entre días laborables y fines de semana
        es_finde = (dia % 7) in [5, 6]  # Sábado y domingo
        self.finde = es_finde
        
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

        return tiempo_proxima_llamada # unidades en horas

    
    def llegada_llamadas(self):
        yield self.env.timeout(10)  # Iniciar simulación a las 10 AM
        cliente = 0
        
        while True:
            # Verificar si ya alcanzamos el tiempo límite ANTES de esperar
            if self.env.now >= self.tiempo_limite:
                if self.logs:
                    self.log(f'{self.env.now}: Se ha alcanzado el tiempo límite de la simulación. No se aceptan más llamadas.')
                # Esperar a que todos los pedidos activos terminen
                if self.pedidos_activos:
                    pedidos_pendientes = [p for p in self.pedidos_activos if not p.triggered]
                    if pedidos_pendientes:
                        if self.logs:
                            self.log(f'{self.env.now}: Esperando a que terminen {len(pedidos_pendientes)} pedidos activos...')
                        try:
                            yield sp.AllOf(self.env, pedidos_pendientes)
                            if self.logs:
                                self.log(f'{self.env.now}: Todos los pedidos activos han terminado.')
                        except:
                            if self.logs:
                                self.log(f'{self.env.now}: No hay más eventos, asumiendo que pedidos terminaron.')
                if not self.evento_termino_simulacion.triggered:
                    self.evento_termino_simulacion.succeed()
                break
            
            # Esperamos a que llegue el siguiente cliente
            tiempo_proxima_llamada = self.obtener_tiempo_proxima_llamada(self.env.now)
            if self.env.now + tiempo_proxima_llamada >= self.tiempo_limite:
                if self.logs:
                    self.log(f'{self.env.now}: La próxima llamada excede el tiempo límite de la simulación. Avanzando al tiempo límite.')
                yield self.env.timeout(self.tiempo_limite - self.env.now)
                continue
            else: 
                yield self.env.timeout(tiempo_proxima_llamada)
            
            # Actualizamos métricas
            cliente += 1
            self.llamadas_totales += 1
            
            # Vemos si este cliente es premium o no
            premium = self.rng.choice(a=[True, False], p=[3/20, 17/20])
            if premium:
                self.pedidos_premium_totales += 1
                prioridad = 1
                if self.logs:
                    self.log(f'{self.env.now}: Cliente {cliente} es premium')
            else:
                self.pedidos_normales_totales += 1
                prioridad = 2
                if self.logs:
                    self.log(f'{self.env.now}: Cliente {cliente} es común')


                if self.logs:
                    self.log(f'{self.env.now}: Cliente {cliente} intenta llamar')

            

            # Revisamos que exista una línea disponible.
            if self.lineas_telefonicas.count < 3:
                # Procedemos a atender la llamada
                pedido = self.env.process(self.atender_llamada(cliente, prioridad, premium))
                self.pedidos_activos.append(pedido)
                if self.logs:
                    self.log(f'{self.env.now}: Cliente {cliente} es atendido por teléfono')

            else:
                # Rechazamos la llamada
                self.llamadas_perdidas += 1
                if self.logs:
                    self.log(f'{self.env.now}: No hay lineas disponibles. Cliente {cliente} es rechazado')
                
                if premium:
                    self.llamadas_premium_perdidas += 1
                else:
                    self.llamadas_normales_perdidas += 1
                
        
    def atender_llamada(self, cliente, prioridad, premium):
        # Vemos si este cliente es premium o no
        premium = self.rng.choice(a=[True, False], p=[3/20, 17/20])
        if premium:
            self.pedidos_premium_totales += 1
            prioridad = 1
            if self.logs:
                self.log(f'{self.env.now}: Cliente {cliente} es premium')
        else:
            self.pedidos_normales_totales += 1
            prioridad = 2
            if self.logs:
                self.log(f'{self.env.now}: Cliente {cliente} es común')

        # Generamos el tiempo que toma la atención por teléfono.
        beta = self.rng.gamma(shape=4, scale=0.5, size=1)/60    
        with self.lineas_telefonicas.request() as linea:
            yield self.env.timeout(beta) # Esperamos
        
        if self.logs:
            self.log(f'{self.env.now}: Se terminó de anteder al cliente {cliente} por teléfono')
        # Empezamos a medir el tiempo de la orden
        inicio_tiempo_orden = self.env.now
        
        
        # Vemos la cantidad de pizzas a preparar
        if premium:
            cantidad_pizzas_a_preparar = self.rng.choice(a=[1,2,3,4], p=[0.3,0.4,0.2,0.1])
        else:
            cantidad_pizzas_a_preparar = self.rng.choice(a=[1,2,3,4], p=[0.6, 0.2, 0.15, 0.05])
        if self.logs: 
            self.log(f'{self.env.now}: Cliente {cliente} ordena {cantidad_pizzas_a_preparar} pizzas')
        # Tipo de pizza a preparar:
        # 1. Queso
        # 2. Pepperoni
        # 3. Todas carnes
        tipos_pizzas = []
        for i in range(cantidad_pizzas_a_preparar):
            if premium:
                tipo_pizza = self.rng.choice(a=[1,2,3], p=[0.3,0.6,0.1])
                tipos_pizzas.append(tipo_pizza)
                if self.logs:
                    self.log(f'{self.env.now}: Pizza {i+1} del cliente {cliente} es tipo {tipo_pizza}')
            else:
                tipo_pizza = self.rng.choice(a=[1,2,3], p=[0.1,0.4,0.5])
                tipos_pizzas.append(tipo_pizza)
                if self.logs:
                    self.log(f'{self.env.now}: Pizza {i+1} del cliente {cliente} es tipo {tipo_pizza}')
            
            
        # Procedemos a preparar la pizza y calcular el valor de la orden
        lista_de_procesos_pizzas = []
        valor_orden = 0
        for i in range(cantidad_pizzas_a_preparar):
            lista_de_procesos_pizzas.append(self.env.process(self.preparar_pizza(cliente, premium, i+1, prioridad, tipos_pizzas[i], inicio_tiempo_orden)))
            
            if tipos_pizzas[i]==1:
                valor_orden += 7_000
            elif tipos_pizzas[i]==2:
                valor_orden += 9_000
            else:
                valor_orden += 12_000
                
        
            
        # Esperamos a que todas las pizzas estén listas (preparadas, cocinadas y embaladas) para proceder al despacho.
        yield sp.AllOf(self.env, lista_de_procesos_pizzas)
        if self.logs:
            self.log(f'{self.env.now}: Todas las pizzas del cliente {cliente} están listas. Se procede al despacho')
        
        
        yield self.env.process(self.despacho(cliente, premium, prioridad, inicio_tiempo_orden, valor_orden))
        
        # Nota: el cálculo de horas extras se hace una sola vez por día en obtener_metricas.
        
            
        
        
    def preparar_pizza(self, cliente, premium, num_pizza, prioridad, tipo_pizza, inicio_tiempo_orden):
        # Actualizamos métricas
        if tipo_pizza==1:
            self.pizzas_queso += 1
        elif tipo_pizza==2:
            self.pizzas_pepperoni += 1
        elif tipo_pizza==3:
            self.pizzas_carnes += 1
        
        with self.estacion_preparacion.request(priority=prioridad) as estacion_request:
            yield estacion_request

            with self.trabajadores.request(priority=prioridad) as trabajador_request:
                yield trabajador_request

                if self.logs:
                    self.log(f'{self.env.now}: Se comienza a preparar la pizza {num_pizza} del cliente {cliente}')

                # Vemos cuanta salsa se añadirá
                xi_1 = self.rng.exponential(scale = 250)
                if xi_1 > self.salsa_de_tomate.level:
                    if self.logs:
                        self.log(f'{self.env.now}: No hay suficiente salsa de tomate para la pizza {num_pizza} del cliente {cliente}. Iniciando reposición.')
                    yield self.env.process(self.proceso_reposicion(self.salsa_de_tomate))
                # Agregamos Salsa
                gamma_1 = self.rng.beta(a = 5, b = 2.2)/60
                yield self.env.timeout(gamma_1) # Esperamos a que se ponga la salsa
                # Descontamos la salsa
                yield self.salsa_de_tomate.get(xi_1)
                
                # Vemos cuanto queso se añadirá
                xi_2 = self.rng.negative_binomial(n = 25, p = 0.52)
                if xi_2 > self.queso_mozzarella.level:
                    if self.logs:
                        self.log(f'{self.env.now}: No hay suficiente queso mozzarella para la pizza {num_pizza} del cliente {cliente}. Iniciando reposición.')  
                    yield self.env.process(self.proceso_reposicion(self.queso_mozzarella))
                # Agregamos queso
                gamma_2 = self.rng.triangular(left = 0.9, mode = 1, right = 1.2)/60
                yield self.env.timeout(gamma_2) # Esperamos a que se ponga el queso
                # Descontamos queso
                yield self.queso_mozzarella.get(xi_2)
                
                # Agregamos Pepperoni si pizza es de pepperoni o mix de carnes
                if tipo_pizza==2 or tipo_pizza==3:
                    # Vemos cuanto pepperoni se añadirá
                    xi_3 = self.rng.poisson(lam = 20)
                    if xi_3 > self.pepperoni.level:
                        if self.logs:
                            self.log(f'{self.env.now}: No hay suficiente pepperoni para la pizza {num_pizza} del cliente {cliente}. Iniciando reposición.')
                        yield self.env.process(self.proceso_reposicion(self.pepperoni))
                    # Agregamos pepperoni
                    gamma_3 = self.rng.lognormal(mean=0.5, sigma=0.25)/60
                    yield self.env.timeout(gamma_3) # Esperamos a que se ponga el pepperoni
                    # Descontamos pepperoni
                    yield self.pepperoni.get(xi_3)
                    
                # Agregamos Mix
                if tipo_pizza==3:
                    # Vemos cuanta carne se añadirá
                    xi_4 = self.rng.binomial(n = 16, p = 0.42)
                    if xi_4 > self.mix_carnes.level:
                        if self.logs:
                            self.log(f'{self.env.now}: No hay suficiente mix de carnes para la pizza {num_pizza} del cliente {cliente}. Iniciando reposición.')
                        yield self.env.process(self.proceso_reposicion(self.mix_carnes))
                    # Agregamos mix
                    gamma_4 = self.rng.uniform(low = 1, high = 1.8)/60
                    yield self.env.timeout(gamma_4) # Esperamos a que se ponga el mix
                    # Descontamos Mix
                    yield self.mix_carnes.get(xi_4+0.000001)
        if self.logs:
            self.log(f'{self.env.now}: Se terminó de preparar la pizza {num_pizza} del cliente {cliente}, solicitando horno...')
        # Procedemos a hornear la pizza
        yield self.env.process(self.hornear(cliente, premium, prioridad, num_pizza, inicio_tiempo_orden))
        
        
    def hornear(self, cliente, premium,  prioridad, num_pizza, inicio_tiempo_orden):
        with self.horno.request(priority=prioridad) as horno_request:
            yield horno_request
            if self.logs:
                self.log(f'{self.env.now}: La pizza {num_pizza} del cliente {cliente} está en el horno.')
            delta = self.rng.lognormal(mean=2.5, sigma=0.2)/60
            yield self.env.timeout(delta)
            if self.logs:
                self.log(f'{self.env.now}: La pizza {num_pizza} del cliente {cliente} salió del horno, solicitando embalaje.')
        
        yield self.env.process(self.embalar(cliente, premium, prioridad, num_pizza, inicio_tiempo_orden))
            
            
    def embalar(self, cliente, premium, prioridad, num_pizza, inicio_tiempo_orden):
        with self.estacion_embalaje.request(priority=prioridad) as embalaje_request:
            yield embalaje_request
            
            with self.trabajadores.request(priority=prioridad) as trabajador_request:
                yield trabajador_request
                if self.logs:
                    self.log(f'{self.env.now}: La pizza {num_pizza} del cliente {cliente} está siendo embalada.')
                epsilon = self.rng.triangular(left = 1.1, mode = 2, right = 2.3)/60
                yield self.env.timeout(epsilon)
                if self.logs:
                    self.log(f'{self.env.now}: La pizza {num_pizza} del cliente {cliente} ha sido embalada.')
                    
                # Dejamos de medir tiempo de reposición
                fin_tiempo_orden = self.env.now

                # Registramos tiempo total del pedido
                if premium and  self.finde:
                    self.tiempos_procesamiento_premium_finde.append(fin_tiempo_orden-inicio_tiempo_orden)
                elif premium and (not self.finde):
                    self.tiempos_procesamiento_premium_semana.append(fin_tiempo_orden-inicio_tiempo_orden)
                elif (not premium) and self.finde:
                    self.tiempos_procesamiento_normales_finde.append(fin_tiempo_orden-inicio_tiempo_orden)
                else:
                    self.tiempos_procesamiento_normales_semana.append(fin_tiempo_orden-inicio_tiempo_orden)

            
        
    def despacho(self, cliente, premium, prioridad, inicio_tiempo_orden, valor_orden):
        with self.repartidores.request(priority=prioridad) as repartidor_request:
            yield repartidor_request
            if self.logs:
                self.log(f'{self.env.now}: El repartidor procede a llevar el pedido del cliente {cliente}.')
            
            # Esperamos el tiempo que toma ir del local al domicilio.
            tiempo_local_domicilio = self.rng.gamma(shape = 7.5, scale = 0.9)/60
            yield self.env.timeout(tiempo_local_domicilio)
            if self.logs:
                self.log(f'{self.env.now}: Llega el repartidor al domicilio del cliente {cliente}.')
                
            # Dejamos de medir tiempo de reposición
            fin_tiempo_orden = self.env.now
            
           
            # Registrar la hora de finalización asociada al día de la jornada laboral.
            # Si un pedido termina antes de las 10:00 (hora < 10), pertenece a la
            # jornada que comenzó el día anterior (p. ej. termina a 01:30 -> jornada del día anterior).
            dia_fin = int(fin_tiempo_orden // 24)
            hora_fin = fin_tiempo_orden % 24
            # asignar al día de la jornada (si hora < 10 -> día anterior)
            dia_jornada = dia_fin if hora_fin >= 10 else max(dia_fin - 1, 0)
            prev = self.ultima_hora_fin_por_dia.get(dia_jornada, -1)
            if hora_fin > prev:
                self.ultima_hora_fin_por_dia[dia_jornada] = hora_fin
                
            # Registramos si el pedido tuvo un retraso.
            retraso = fin_tiempo_orden - inicio_tiempo_orden > 1
            if retraso:
                # Pedido retrasado: será gratis para el cliente
                if premium:
                    self.compensacion += 0.2 * valor_orden
                    if self.logs:
                        self.log(f'{self.env.now}: El pedido del cliente {cliente} tuvo un retraso. Se aplica compensación de ${0.2*valor_orden}.')

                if premium and self.finde:
                    self.pedidos_tardios_premium_finde += 1
                elif premium and (not self.finde):
                    self.pedidos_tardios_premium_semana += 1
                elif (not premium) and self.finde:
                    self.pedidos_tardios_normales_finde += 1
                else:
                    self.pedidos_tardios_normales_semana += 1
            else:
                # Pedido entregado a tiempo: sumar ingresos normalmente
                self.ingresos += valor_orden
            
            # Esperamos el tiempo que toma ir del domicilio al local.
            tiempo_domicilio_local = self.rng.gamma(shape = 7.5, scale = 0.9)/60
            yield self.env.timeout(tiempo_domicilio_local)
            if self.logs:
                self.log(f'{self.env.now}: Llega el repartidor del cliente {cliente} al local.')
                

    def revisar_inventario_salsa(self):
        yield self.env.timeout(10) # Iniciar simulación a las 10 AM 
        
        while True:
            if self.env.now >= self.tiempo_limite:
                break
            yield self.env.timeout(0.5) # Revisamos cada 30 minutos
            if self.env.now >= self.tiempo_limite:
                break
            if self.trabajadores.count < self.cantidad_trabajadores:
                with self.trabajadores.request() as trabajador_request:
                    yield trabajador_request
                    if self.salsa_de_tomate.level < self.umbral_reposicion[self.salsa_de_tomate] and not self.en_reposicion[self.salsa_de_tomate]:
                        if self.logs:
                            self.log(f'{self.env.now}: Nivel de salsa de tomate bajo ({self.salsa_de_tomate.level} ml). Iniciando reposición.')
                        self.env.process(self.proceso_reposicion(self.salsa_de_tomate))

    def revisar_inventarios(self):
        yield self.env.timeout(10) # Iniciar simulación a las 10 AM

        while True:
            if self.env.now >= self.tiempo_limite:
                break
            yield self.env.timeout(3/4)
            if self.env.now >= self.tiempo_limite:
                break
            if self.logs:
                self.log(f'{self.env.now}: Revisión periódica de inventarios.')
            if self.trabajadores.count < self.cantidad_trabajadores:
                with self.trabajadores.request() as trabajador_request:
                    yield trabajador_request
                    for inventario in self.inventarios:
                        if inventario == self.salsa_de_tomate:
                            continue  # La salsa de tomate se revisa en otro proceso
                        if inventario.level < self.umbral_reposicion[inventario] and not self.en_reposicion[inventario]:
                            if self.logs:
                                self.log(f'{self.env.now}: Nivel de {self.nombres_inventarios[inventario]} bajo ({inventario.level}). Iniciando reposición.')
                            yield self.env.process(self.proceso_reposicion(inventario))
                        else:
                            if self.logs:
                                self.log(f'{self.env.now}: Nivel de {self.nombres_inventarios[inventario]} suficiente ({inventario.level}). No se requiere reposición.')
            else:
                if self.logs:
                    self.log(f'{self.env.now}: No hay trabajadores disponibles para revisar inventarios, se omite esta revisión.')

    def proceso_reposicion(self, inventario):
        cantidad_a_reponer = inventario.capacity - inventario.level
        tiempo_reposicion = self.obtener_tiempo_reposicion(inventario)
        self.en_reposicion[inventario] = True
        yield self.env.timeout(tiempo_reposicion)
        yield inventario.put(cantidad_a_reponer)

        self.en_reposicion[inventario] = False
    
    def obtener_tiempo_reposicion(self, inventario):
        if inventario == self.salsa_de_tomate:
            tiempo = self.rng.weibull(a=1.2) * 10 / 60 # En horas
        elif inventario == self.queso_mozzarella:
            tiempo = self.rng.lognormal(mean=1.58, sigma=0.25) / 60
        elif inventario == self.pepperoni:
            tiempo = self.rng.weibull(a=1.3) * 3.9 / 60
        elif inventario == self.mix_carnes:
            tiempo = self.rng.exponential(scale=5) / 60
        
        return tiempo

    def generar_reporte_logs(self, nombre_archivo):
        with open(nombre_archivo, 'w') as f:
            f.write(self.log_data)

    def calcular_horas_normales(self, tiempo_horas: float) -> float:
        # Esta funcion calcula la cantidad de horas laborales normales (sin horas extra)
        # Que caben dentro del tiempo limite de la simulacion en dias normales
        if tiempo_horas <= 0:
            return 0.0

        horas = 0.0
        # número de días que la simulación puede cubrir (ceil para cubrir parcial último día)
        max_dias = int(math.ceil(tiempo_horas / 24.0))
        for k in range(max_dias):
            # día de la semana: 0 = lunes, ..., 6 = domingo
            dia_semana = k % 7
            # sólo contar días normales (lunes-viernes => 0-4)
            if dia_semana > 4:
                continue
            inicio_jornada = k * 24.0
            fin_jornada = inicio_jornada + float(self.horas_trabajo_dia_normal)  # 10:00 -> 23:00 => 13 horas
            # overlap entre [inicio_jornada, fin_jornada) y [0, tiempo_horas)
            comienzo = max(inicio_jornada, 0.0)
            termino = min(fin_jornada, tiempo_horas)
            if termino > comienzo:
                horas += termino - comienzo

        return horas
    
    def calcular_horas_finde(self, tiempo_horas: float) -> float:
        # Esta funcion calcula la cantidad de horas laborales normales (sin horas extra)
        # Que caben dentro del tiempo limite de la simulacion en fines de semana
        if tiempo_horas <= 0:
            return 0.0

        horas = 0.0
        max_dias = int(math.ceil(tiempo_horas / 24.0))
        for k in range(max_dias):
            dia_semana = k % 7  # 0 = lunes, ..., 6 = domingo
            # Sólo contar sábados y domingos
            if dia_semana not in [5, 6]:
                continue
            inicio_jornada = k * 24.0  # corresponde a 10:00 del día k
            fin_jornada = inicio_jornada + float(self.horas_trabajo_finde)
            # overlap entre [inicio_jornada, fin_jornada) y [0, tiempo_horas)
            comienzo = max(inicio_jornada, 0.0)
            termino = min(fin_jornada, tiempo_horas)
            if termino > comienzo:
                horas += termino - comienzo

        return horas





    


# In[233]:


def u_test(x,y):
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
    
    print(f"Media muestras: {np.mean(x)}")
    print(f"Intervalo al {alpha} de confianza: [{intervalo[0]},{intervalo[1]}]")
    if intervalo[0]<=0 and 0<= intervalo[1]:
        print('La diferencia no es significativa')
    else:
        print('La diferencia es significativa. Las muestras son diferentes')
    return intervalo




### Obtenemos muestras
Pedidos_Ingresados = []
Proporcion_Llamadas_Perdidas = []
Proporcion_Pedidos_Tardios = []
Proporcion_Tardios_Normal = []
Proporcion_Tardios_Premium = []
Tiempo_Medio_para_Procesar_un_Pedido = []
Tiempo_Medio_para_Procesar_un_Pedido_normal = []
Tiempo_Medio_para_Procesar_un_Pedido_premium = []
utilidad = []

prop_llamadas_normales = []
prop_llamadas_premium = []

tardios_normales_finde = []
tardios_normales_semana = []
tardios_premium_finde = []
tardios_premium_semana = []

tiempo_medio_normales_finde = []
tiempo_medio_normales_semana = []
tiempo_medio_premium_finde = []
tiempo_medio_premium_semana = []


for i in range(200):
    print('Muestra', 1, 'cargando.')
    env = sp.Environment()
    pizzeria = Pizzeria(env)
    pizzeria.iniciar_simulacion(168, i, logs=False)
    pizzeria.obtener_metricas()
    
    Pedidos_Ingresados.append(pizzeria.llamadas_totales - pizzeria.llamadas_perdidas)
    Proporcion_Llamadas_Perdidas.append(pizzeria.llamadas_perdidas / pizzeria.llamadas_totales)
    Proporcion_Pedidos_Tardios.append(pizzeria.proporcion_pedidos_tardios)
    Proporcion_Tardios_Normal.append(pizzeria.proporcion_pedidos_tardios_normales)
    Proporcion_Tardios_Premium.append(pizzeria.proporcion_pedidos_tardios_premium)
    Tiempo_Medio_para_Procesar_un_Pedido.append(pizzeria.tiempo_promedio_procesamiento)
    Tiempo_Medio_para_Procesar_un_Pedido_normal.append(pizzeria.tiempo_promedio_procesamiento_normales)
    Tiempo_Medio_para_Procesar_un_Pedido_premium.append(pizzeria.tiempo_promedio_procesamiento_premium)
    utilidad.append(pizzeria.utilidad)
    
    prop_llamadas_normales.append(pizzeria.llamadas_normales_perdidas/(pizzeria.llamadas_totales))
    prop_llamadas_premium.append(pizzeria.llamadas_premium_perdidas/(pizzeria.llamadas_totales))
    
    pedidos_totales = (pizzeria.pedidos_normales_totales + pizzeria.pedidos_premium_totales)
    
    tardios_normales_finde.append(pizzeria.pedidos_tardios_normales_finde/pedidos_totales)
    tardios_normales_semana.append(pizzeria.pedidos_tardios_normales_semana/pedidos_totales)
    tardios_premium_finde.append(pizzeria.pedidos_tardios_premium_finde/pedidos_totales)
    tardios_premium_semana.append(pizzeria.pedidos_tardios_premium_semana/pedidos_totales)
    
    tiempo_medio_normales_finde.append(np.mean(pizzeria.tiempos_procesamiento_normales_finde))
    tiempo_medio_normales_semana.append(np.mean(pizzeria.tiempos_procesamiento_normales_semana))
    tiempo_medio_premium_finde.append(np.mean(pizzeria.tiempos_procesamiento_premium_finde))
    tiempo_medio_premium_semana.append(np.mean(pizzeria.tiempos_procesamiento_premium_semana))
    




# CITA CHATGPT: "Tengo una lista con numeros arrays, necesito pasarlos a numeros normales"
def to_1d_numeric(seq):
    # Toma una lista que puede contener listas/arrays/escalars y la “aplana” a 1D float
    chunks = []
    for v in seq:
        if v is None:
            continue
        a = np.atleast_1d(v).astype(float, copy=False)
        chunks.append(a.ravel())
    if not chunks:
        return np.array([], dtype=float)
    return np.concatenate(chunks)
# FIN CITA CHATGPT

utilidad = to_1d_numeric(utilidad)

resultados = [np.array(Pedidos_Ingresados), 
              np.array(Proporcion_Llamadas_Perdidas), 
              np.array(Proporcion_Pedidos_Tardios), 
              np.array(Proporcion_Tardios_Normal), 
              np.array(Proporcion_Tardios_Premium), 
              np.array(Tiempo_Medio_para_Procesar_un_Pedido), 
              np.array(Tiempo_Medio_para_Procesar_un_Pedido_normal), 
              np.array(Tiempo_Medio_para_Procesar_un_Pedido_premium), 
              np.array(utilidad)]

datos_validacion = pd.read_csv('validar_pizzería.csv')

L = ['Pedidos Ingresados', 'Proporcion Llamadas Perdidas', 'Proporcion Pedidos Tardíos', 
    'Proporcion Tardíos Normal', 'Proporcion Tardíos Premium', 'Tiempo Medio para Procesar un Pedido (min)', 
    'Tiempo Medio para Procesar un Pedido Normal (min)', 'Tiempo Medio para Procesar un Pedido Premium (min)', 'Utilidad']


###########################################################################
# Parte 2

print('\nPARTE 2\n')
# Realizamos test de validación 
import scipy.stats as st
alpha = 0.05

for i in range(len(L)):
    x = resultados[i]
    y = np.array(datos_validacion[L[i]])

    print(f'Validación {L[i]}\n')
    print(f'U-test\n')
    u_test(x, y)
    print(f'\nIntervalos de confiaza\n')
    intervalo_t_pareado(x, y, alpha)
    print('\n==============================================================\n')


##################################################################################################
# Parte 3


print('\nPARTE 3.a.i\n')

# Realizamos una función que nos permite calcular estimadores e intervalos de confianza

def estimador_e_intervalo(sample, name):
    estimador=np.mean(sample)
    var=np.var(sample)

    inetrvalo = [estimador-1.96*np.sqrt(var**2/100), estimador+1.96*np.sqrt(var**2/100)]

    print(f"Estimador de {name} es:{estimador}" )
    print(f"El intervalo de {name} es: [{inetrvalo[0]},{inetrvalo[1]}]" )


# In[251]:

# 3.a.i
muestra_prop_llamadas_comunes = prop_llamadas_normales
muestra_prop_llamadas_premium = prop_llamadas_premium

estimador_e_intervalo(muestra_prop_llamadas_comunes, 'proporción de llamadas perdidas de clientes comunes')
print(' ')
estimador_e_intervalo(muestra_prop_llamadas_premium, 'proporción de llamadas perdidas de clientes premium')


print('\nPARTE 3.a.ii\n')
# 3.a.ii
muestra_prop_atrasados_comunes_semana = tardios_normales_semana
muestra_prop_atrasados_comunes_finde = tardios_normales_finde
muestra_prop_atrasados_premium_semana = tardios_premium_semana
muestra_prop_atrasados_premium_finde = tardios_premium_finde

estimador_e_intervalo(muestra_prop_llamadas_comunes, 'proporción de pedidos atrasados de clientes comunes en día de semana')
print(' ')
estimador_e_intervalo(muestra_prop_llamadas_comunes, 'proporción de pedidos atrasados de clientes comunes en fin de semana')
print(' ')
estimador_e_intervalo(muestra_prop_llamadas_comunes, 'proporción de pedidos atrasados de clientes premium en día de semana')
print(' ')
estimador_e_intervalo(muestra_prop_llamadas_comunes, 'proporción de pedidos atrasados de clientes premium en fin de semana')

print('\nPARTE 3.a.iii\n')
# 3.a.iii
def quartiles(sample, name):
    sample_sorted = np.sort(sample)
    
    estimador_25 = sample_sorted[24]
    estimador_50 = sample_sorted[49]
    estimador_75 = sample_sorted[74]

    r_25= int(np.ceil(25-1.96*np.sqrt(25*0.75)))
    r_50= int(np.ceil(50-1.96*np.sqrt(50*0.5)))
    r_75= int(np.ceil(75-1.96*np.sqrt(75*0.25)))

    s_25= int(np.ceil(25+1.96*np.sqrt(25*0.75)))
    s_50= int(np.ceil(50+1.96*np.sqrt(50*0.5)))
    s_75= int(np.ceil(75+1.96*np.sqrt(75*0.25)))

    print(f"Estimador del percentil 25 de {name} es: {estimador_25}" )
    print(f"Estimador del percentil 50 de {name} es: {estimador_50}" )
    print(f"Estimador del percentil 75 de {name} es: {estimador_75}" )
    
    print(f"Intervalo del percentil 25 de {name} es: [{sample_sorted[r_25]},{sample_sorted[s_25]}]" )
    print(f"Intervalo del percentil 50 de {name} es: [{sample_sorted[r_50]},{sample_sorted[s_50]}]" )
    print(f"Intervalo del percentil 75 de {name} es: [{sample_sorted[r_75]},{sample_sorted[s_75]}]" )


print('\nPARTE 3.b.i\n')
# 3.b.i
muestra_tiempo_medio_comun_semana = np.array(tiempo_medio_normales_semana)*60
muestra_tiempo_medio_comun_finde = np.array(tiempo_medio_normales_finde)*60
muestra_tiempo_medio_premium_semana = np.array(tiempo_medio_premium_semana)*60
muestra_tiempo_medio_premium_finde = np.array(tiempo_medio_premium_finde)*60

quartiles(muestra_tiempo_medio_comun_semana, 'tiempo medio de un pedido de un cliente comun en día de semana')
print(' ')
quartiles(muestra_tiempo_medio_comun_finde, 'tiempo medio de un pedido de un cliente comun en fin de semana')
print(' ')
quartiles(muestra_tiempo_medio_premium_semana, 'tiempo medio de un pedido de un cliente premium en día de semana')
print(' ')
quartiles(muestra_tiempo_medio_premium_finde, 'tiempo medio de un pedido de un cliente premium en fin de semana')


# In[277]:


def procedimiento_analítico(alpha, gamma_ajustado, n0, sample):
    n=n0
    
    sample = sample[:n]
    
    mean = abs(np.mean(sample))
    var = np.var(sample)
    
    largo_medio = st.t.ppf(1 - alpha / 2, df=n - 1)*np.sqrt(var/n)
    
    valor = 1000
    print(valor, largo_medio, mean)
    
    while valor>=gamma_ajustado:
        n += 1

        largo_medio = st.t.ppf(1 - alpha / 2, df=n - 1)*np.sqrt(var/n)

        valor = largo_medio/mean
    
        #print(f'n={n} | Valor: {valor}')
        
    print("n = ", n, 'mean=', mean, 'Largo medio=', largo_medio)

    return n


procedimiento_analítico(0.05, 0.1, 5, utilidad)

