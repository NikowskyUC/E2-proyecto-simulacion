import numpy as np
import simpy as sp
import math
from scipy import stats

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

        inventarios = [self.salsa_de_tomate, self.queso_mozzarella,
                       self.pepperoni, self.mix_carnes]
        self.en_reposicion = {inventario: False for inventario in inventarios}

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
        
        self.ingresos = 0 
        
        self.costos = 0 
        
        
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
        self.tiempo_limite = tiempo_horas
        self.logs = logs
        self.log_data = ''

        self.rng = np.random.default_rng(seed)

        if self.logs:
            self.log(f'Iniciando simulación por {tiempo_horas} horas con semilla {seed}')
        
        self.env.process(self.llegada_llamadas())

        self.env.run(until=tiempo_horas)
        
        
        # Calculamos métricas
        self.ingresos = 7_000*self.pizzas_queso + 9_000*self.pizzas_pepperoni + 12_000*self.pizzas_carnes
        
        self.costos = (10_000*self.llamadas_perdidas + 
        0.3*7_000*self.pizzas_queso + 0.3*9_000*self.pizzas_pepperoni + 0.3*12_000*self.pizzas_carnes + 
        self.costos_fijos + 
        self.compensacion + 
        (4_000*13*5+4_000*15*2)*5 + (3_000*13*5+3_000*15*2)*6 + 
        (1.4*4_000*13*5+1.4*4_000*15*2)*self.horas_extras + (1.4*3_000*13*5+1.4*3_000*15*2)*self.horas_extras)
        
        self.proporcion_llamadas_perdidas = self.llamadas_perdidas / self.llamadas_totales
        
        self.proporcion_pedidos_tardios_normales_finde = self.pedidos_tardios_normales_finde / self.llamadas_totales
        self.proporcion_pedidos_tardios_normales_semana = self.pedidos_tardios_normales_semana / self.llamadas_totales
        self.proporcion_pedidos_tardios_premium_finde = self.pedidos_tardios_premium_finde  / self.llamadas_totales
        self.proporcion_pedidos_tardios_premium_semana = self.pedidos_tardios_premium_semana / self.llamadas_totales
        
        self.tiempo_promedio_procesamiento_normales_finde = np.mean(self.tiempos_procesamiento_normales_finde)
        self.tiempo_promedio_procesamiento_normales_semana = np.mean(self.tiempos_procesamiento_normales_semana)
        self.tiempo_promedio_procesamiento_premium_finde = np.mean(self.tiempos_procesamiento_premium_finde)
        self.tiempo_promedio_procesamiento_premium_semana = np.mean(self.tiempos_procesamiento_premium_semana)
        
        self.utilidad = self.ingresos - self.costos
        
    
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
                print('hola')
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
        cliente = 0
        
        while True:
            # Actualizamos métricas
            cliente += 1
            self.llamadas_totales += 1
            
            
            if self.logs:
                self.log(f'{self.env.now}: Llega cliente {cliente}')

            
            
            # Revisamos que exista una línea disponible.
            if self.lineas_telefonicas.count < 3:
                # Procedemos a atender la llamada
                proceso_atender_llamada = self.env.process(self.atender_llamada(cliente))
                if self.logs:
                    self.log(f'{self.env.now}: Cliente {cliente} es atendido por teléfono')

            else:
                # Rechazamos la llamada
                self.llamadas_perdidas += 1
                if self.logs:
                    self.log(f'{self.env.now}: No hay lineas disponibles. Cliente {cliente} es rechazado')

                
            # Esperamos a que llegue el siguiente cliente
            tiempo_proxima_llamada = self.obtener_tiempo_proxima_llamada(self.env.now)
            yield self.env.timeout(tiempo_proxima_llamada)    
        
    def atender_llamada(self, cliente):
        # Vemos si este cliente es premium o no
        premium = np.random.choice(a=[True, False], p=[3/20, 17/20])
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
        beta = np.random.gamma(shape=4, scale=0.5, size=1)/60    
        with self.lineas_telefonicas.request() as linea:
            yield self.env.timeout(beta) # Esperamos
            
        # Empezamos a medir el tiempo de la orden
        inicio_tiempo_orden = self.env.now
        
        
        # Vemos la cantidad de pizzas a preparar
        if premium:
            cantidad_pizzas_a_preparar = np.random.choice(a=[1,2,3,4], p=[0.3,0.4,0.2,0.1])
        else:
            cantidad_pizzas_a_preparar = np.random.choice(a=[1,2,3,4], p=[0.6, 0.2, 0.15, 0.05])
        
        # Tipo de pizza a preparar:
        # 1. Queso
        # 2. Pepperoni
        # 3. Todas carnes
        tipos_pizzas = []
        for i in range(cantidad_pizzas_a_preparar):
            if premium:
                tipos_pizzas.append(np.random.choice(a=[1,2,3], p=[0.3,0.6,0.1]))
            else:
                tipos_pizzas.append(np.random.choice(a=[1,2,3], p=[0.1,0.4,0.5]))
            
        # Procedemos a preparar la pizza y calcular el valor de la orden
        lista_de_procesos_pizzas = []
        valor_orden = 0
        for i in range(cantidad_pizzas_a_preparar):
            lista_de_procesos_pizzas.append(self.env.process(self.preparar_pizza(cliente, premium, i+1, prioridad, tipos_pizzas[i])))
            
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
        
        
        self.env.process(self.despacho(cliente, premium, prioridad, inicio_tiempo_orden, valor_orden))
        
        # Registramos horas extras
        if self.finde and self.env.now//24 >= 1:
            self.horas_extras += self.env.now//24 - 1 
        elif (not self.finde) and self.env.now//24 >= 23:
            self.horas_extras += self.env.now//24 - 23 
            
        
        
    def preparar_pizza(self, cliente, premium, num_pizza, prioridad, tipo_pizza):
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

                # Vemos cuanta salsa se añadirá
                xi_1 = np.random.exponential(scale = 250)
                '''if xi_1 > self.salsa_de_tomate.level:
                    yield self.env.process(self.proceso_reposicion(self.salsa_de_tomate))'''
                # Agregamos Salsa
                gamma_1 = np.random.beta(a = 5, b = 2.2)/60
                yield self.env.timeout(gamma_1) # Esperamos a que se ponga la salsa
                # Descontamos la salsa
                yield self.salsa_de_tomate.get(xi_1)
                
                # Vemos cuanto queso se añadirá
                xi_2 = np.random.negative_binomial(n = 25, p = 0.52)
                '''if xi_2 > self.queso_mozzarella.level:
                    yield self.env.process(self.proceso_reposicion(self.queso_mozzarella))'''
                # Agregamos queso
                gamma_2 = np.random.triangular(left = 0.9, mode = 1, right = 1.2)/60
                yield self.env.timeout(gamma_2) # Esperamos a que se ponga el queso
                # Descontamos queso
                yield self.queso_mozzarella.get(xi_2)
                
                # Agregamos Pepperoni si pizza es de pepperoni o mix de carnes
                if tipo_pizza==2 or tipo_pizza==3:
                    # Vemos cuanto pepperoni se añadirá
                    xi_3 = np.random.poisson(lam = 20)
                    '''if xi_3 > self.pepperoni.level:
                        yield self.env.process(self.proceso_reposicion(self.pepperoni))'''
                    # Agregamos pepperoni
                    gamma_3 = np.random.lognormal(mean=0.5, sigma=0.25)/60
                    yield self.env.timeout(gamma_3) # Esperamos a que se ponga el pepperoni
                    # Descontamos pepperoni
                    yield self.pepperoni.get(xi_3)
                    
                # Agregamos Mix
                if tipo_pizza==3:
                    # Vemos cuanta carne se añadirá
                    xi_4 = np.random.binomial(n = 16, p = 0.42)
                    '''if xi_4 > self.mix_carnes.level:
                        yield self.env.process(self.proceso_reposicion(self.mix_carnes))'''
                    # Agregamos mix
                    gamma_4 = np.random.uniform(low = 1, high = 1.8)/60
                    yield self.env.timeout(gamma_4) # Esperamos a que se ponga el mix
                    # Descontamos Mix
                    yield self.mix_carnes.get(xi_4)
                    
        # Procedemos a hornear la pizza
        self.env.process(self.hornear(cliente, premium, prioridad, num_pizza))
        
        
    def hornear(self, cliente, premium,  prioridad, num_pizza):
        with self.horno.request(priority=prioridad) as horno_request:
            yield horno_request
            delta = np.random.lognormal(mean=2.5, sigma=0.2)/60
            yield self.env.timeout(delta)
        
        self.env.process(self.embalar(cliente, premium, prioridad, num_pizza))
            
            
    def embalar(self, cliente, premium, prioridad, num_pizza):
        with self.estacion_embalaje.request(priority=prioridad) as embalaje_request:
            yield embalaje_request
            
            with self.trabajadores.request(priority=prioridad) as trabajador_request:
                yield trabajador_request
                epsilon = np.random.triangular(left = 1.1, mode = 2, right = 2.3)/60
                yield self.env.timeout(epsilon)
                
            
        
    def despacho(self, cliente, premium, prioridad, inicio_tiempo_orden, valor_orden):
        with self.repartidores.request(priority=prioridad) as repartidor_request:
            yield repartidor_request
            if self.logs:
                self.log(f'{self.env.now}: El repartidor procede a llevar el pedido del cliente {cliente}.')
            
            # Esperamos el tiempo que toma ir del local al domicilio.
            tiempo_local_domicilio = np.random.gamma(shape = 7.5, scale = 0.9)/60
            yield self.env.timeout(tiempo_local_domicilio)
            if self.logs:
                self.log(f'{self.env.now}: Llega el repartidor al domicilio del cliente {cliente}.')
                
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
                
            # Registramos si el pedido tuvo un retraso.
            if fin_tiempo_orden-inicio_tiempo_orden<=1:
                self.compensacion += 0.2*valor_orden
                
                if premium and self.finde:
                    self.pedidos_tardios_premium_finde += 1
                elif premium and (not self.finde):
                    self.pedidos_tardios_premium_semana += 1
                elif (not premium) and self.finde:
                    self.pedidos_tardios_normales_finde +=1 
                else:
                    self.pedidos_tardios_normales_semana +=1
            
            # Esperamos el tiempo que toma ir del domicilio al local.
            tiempo_domicilio_local = np.random.gamma(shape = 7.5, scale = 0.9)/60
            yield self.env.timeout(tiempo_domicilio_local)
            if self.logs:
                self.log(f'{self.env.now}: Llega el repartidor al local.')
                

    """def proceso_reposicion(self, inventario):
        cantidad_a_reponer = inventario.capacity - inventario.level
        tiempo_reposicion = self.obtener_tiempo_reposicion(inventario)
        yield self.env.timeout(tiempo_reposicion)
        yield inventario.put(cantidad_a_reponer)

        self.en_reposicion[inventario] = False"""



env = sp.Environment()
pizzeria = Pizzeria(env)
pizzeria.iniciar_simulacion(72, 1, logs=True)