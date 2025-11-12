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
        self.ingresos = 7_000*self.pizzas_queso + 9_000*self.pizzas_pepperoni + 12_000*self.pizzas_carnes
        
        self.costos = (10_000*self.llamadas_perdidas + 
        0.3*7_000*self.pizzas_queso + 0.3*9_000*self.pizzas_pepperoni + 0.3*12_000*self.pizzas_carnes + 
        self.costos_fijos + 
        self.compensacion + 
        (4_000*13*5+4_000*15*2)*5 + (3_000*13*5+3_000*15*2)*6 + 
        (1.4*4_000*13*5+1.4*4_000*15*2)*self.horas_extras + (1.4*3_000*13*5+1.4*3_000*15*2)*self.horas_extras)
        
        self.proporcion_llamadas_perdidas = self.llamadas_perdidas / self.llamadas_totales
        
        total_pedidos_tardios = self.pedidos_tardios_normales_finde + self.pedidos_tardios_normales_semana + self.pedidos_tardios_premium_finde + self.pedidos_tardios_premium_semana
        self.proporcion_pedidos_tardios_normales = (self.pedidos_tardios_normales_finde + self.pedidos_tardios_normales_semana) / total_pedidos_tardios
        self.proporcion_pedidos_tardios_premium = (self.pedidos_tardios_premium_finde + self.pedidos_tardios_premium_semana) / total_pedidos_tardios
        self.proporcion_pedidos_tardios = total_pedidos_tardios / self.llamadas_totales
        
        self.tiempo_promedio_procesamiento_normales = np.mean(self.tiempos_procesamiento_normales_semana + self.tiempos_procesamiento_normales_finde)
        self.tiempo_promedio_procesamiento_premium = np.mean(self.tiempos_procesamiento_premium_finde + self.tiempos_procesamiento_premium_semana)
        self.tiempo_promedio_procesamiento = np.mean(self.tiempos_procesamiento_premium_semana + self.tiempos_procesamiento_premium_finde + self.tiempos_procesamiento_normales_semana + self.tiempos_procesamiento_normales_finde)
        
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
            
            
            if self.logs:
                self.log(f'{self.env.now}: Cliente {cliente} intenta llamar')

            

            # Revisamos que exista una línea disponible.
            if self.lineas_telefonicas.count < 3:
                # Procedemos a atender la llamada
                pedido = self.env.process(self.atender_llamada(cliente))
                self.pedidos_activos.append(pedido)
                if self.logs:
                    self.log(f'{self.env.now}: Cliente {cliente} es atendido por teléfono')

            else:
                # Rechazamos la llamada
                self.llamadas_perdidas += 1
                if self.logs:
                    self.log(f'{self.env.now}: No hay lineas disponibles. Cliente {cliente} es rechazado')

                
        
    def atender_llamada(self, cliente):
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
        
        
        yield self.env.process(self.despacho(cliente, premium, prioridad, inicio_tiempo_orden, valor_orden))
        
        # Registramos horas extras
        hora_del_dia = self.env.now % 24
        if self.finde and 10 > hora_del_dia >= 0: # Madrugada
            self.horas_extras += hora_del_dia 
        elif (not self.finde) and (hora_del_dia > 23 or hora_del_dia < 10): # Pasado las 11 PM o madrugada
            self.horas_extras += hora_del_dia - 23 if hora_del_dia > 23 else hora_del_dia + 1 
            
        
        
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
                    yield self.mix_carnes.get(xi_4)
        if self.logs:
            self.log(f'{self.env.now}: Se terminó de preparar la pizza {num_pizza} del cliente {cliente}, solicitando horno...')
        # Procedemos a hornear la pizza
        yield self.env.process(self.hornear(cliente, premium, prioridad, num_pizza))
        
        
    def hornear(self, cliente, premium,  prioridad, num_pizza):
        with self.horno.request(priority=prioridad) as horno_request:
            yield horno_request
            if self.logs:
                self.log(f'{self.env.now}: La pizza {num_pizza} del cliente {cliente} está en el horno.')
            delta = self.rng.lognormal(mean=2.5, sigma=0.2)/60
            yield self.env.timeout(delta)
            if self.logs:
                self.log(f'{self.env.now}: La pizza {num_pizza} del cliente {cliente} salió del horno, solicitando embalaje.')
        
        yield self.env.process(self.embalar(cliente, premium, prioridad, num_pizza))
            
            
    def embalar(self, cliente, premium, prioridad, num_pizza):
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
            if fin_tiempo_orden-inicio_tiempo_orden > 1:

                if premium:
                    self.compensacion += 0.2*valor_orden
                    if self.logs:
                        self.log(f'{self.env.now}: El pedido del cliente {cliente} tuvo un retraso. Se aplica compensación de ${0.2*valor_orden}.')
                
                if premium and self.finde:
                    self.pedidos_tardios_premium_finde += 1
                elif premium and (not self.finde):
                    self.pedidos_tardios_premium_semana += 1
                elif (not premium) and self.finde:
                    self.pedidos_tardios_normales_finde +=1 
                else:
                    self.pedidos_tardios_normales_semana +=1
            
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

def replicas_simulación(iteraciones, tiempo_horas):
    lista_resultados = []
    for i in range(iteraciones):
        np.random.seed(i)
        env = sp.Environment()
        pizzeria = Pizzeria(env)
        pizzeria.iniciar_simulacion(tiempo_horas, i, logs=False)
        lista_resultados.append(pizzeria.obtener_metricas())

        print(f'Replica {i+1} completada.')
        print()
        print(lista_resultados[i])

        print("")
        print("--------------------------------")
        print("")

    return lista_resultados
            


resultados = replicas_simulación(10, tiempo_simulacion)


