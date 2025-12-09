import numpy as np
import simpy as sp
import math
from scipy.stats import norm, gamma as gamma_dist, triang, nbinom

logs = True
tiempo_simulacion = 168 # horas
numero_replicas = 1

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
        # NOTA: Conceptualmente salsa es continua (ml) y los demás son discretos (unidades)
        # Sin embargo, usamos Container para todos por eficiencia de simulación
        # Al reponer inventarios discretos, redondeamos la cantidad
        self.salsa_de_tomate = sp.Container(env, init=15000, capacity=15000) # continuo: ml
        self.queso_mozzarella = sp.Container(env, init=1000, capacity=1000) # discreto: unidades
        self.pepperoni = sp.Container(env, init=800, capacity=800) # discreto: unidades  
        self.mix_carnes = sp.Container(env, init=600, capacity=600) # discreto: unidades

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
        
        # Inventarios que son conceptualmente discretos (para redondear en reposición)
        self.inventarios_discretos = {self.queso_mozzarella, self.pepperoni, self.mix_carnes}

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

        self.costo_fijo_lineas_telefonicas = 50000 * 3 # semanal
        self.costo_fijo_espacio_preparacion = 60000 * 3# semanal
        self.costo_fijo_horno = 40000 * 10 # semanal
        self.costo_fijo_embalaje = 30000 * 3 # semanal
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

    
    def iniciar_simulacion(self, tiempo_horas, seed, logs=False, uniformes_coccion=None, uniformes_despacho_ida=None, uniformes_despacho_vuelta=None, uniformes_llamada=None, uniformes_cantidad_queso=None, uniformes_tiempo_queso=None):
        self.tiempo_limite = tiempo_horas + 10 # Se suma 10 para iniciar simulacion a las 10 AM
        self.logs = logs
        self.log_data = ''

        self.rng = np.random.default_rng(seed)
        
        # Variables antitéticas: listas de números uniformes pre-generados
        self.uniformes_coccion = uniformes_coccion if uniformes_coccion is not None else []
        self.uniformes_despacho_ida = uniformes_despacho_ida if uniformes_despacho_ida is not None else []
        self.uniformes_despacho_vuelta = uniformes_despacho_vuelta if uniformes_despacho_vuelta is not None else []
        self.uniformes_llamada = uniformes_llamada if uniformes_llamada is not None else []
        self.uniformes_cantidad_queso = uniformes_cantidad_queso if uniformes_cantidad_queso is not None else []
        self.uniformes_tiempo_queso = uniformes_tiempo_queso if uniformes_tiempo_queso is not None else []
        
        # Contadores para indexar las variables antitéticas
        self.idx_coccion = 0
        self.idx_despacho_ida = 0
        self.idx_despacho_vuelta = 0
        self.idx_llamada = 0
        self.idx_cantidad_queso = 0
        self.idx_tiempo_queso = 0

        if self.logs:
            self.log(f'Iniciando simulación por {tiempo_horas} horas con semilla {seed}')
        

        self.ultima_atencion = None
        self.evento_termino_simulacion = self.env.event()
        self.pedidos_activos = []  # Lista para rastrear todos los pedidos en proceso

        self.evento_inventario_repuesto = {inventario: self.env.event() for inventario in self.inventarios}

        self.env.process(self.llegada_llamadas())
        self.env.process(self.temporizador_revision_salsa())
        self.env.process(self.temporizador_revision_inventarios())

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
                self.horas_extras += hora_fin - 1
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
        time = self.timestamp()
        print(f'{time}: {mensaje}')
        self.log_data += f'{time}: {mensaje}\n'
    
    def timestamp(self):
        horas_totales = int(self.env.now)
        dias = horas_totales // 24 + 1
        horas = horas_totales % 24
        minutos = int((self.env.now - horas_totales) * 60)
        return f'Día {dias}, {horas:02d}:{minutos:02d}'
    
    def obtener_nivel_inventario(self, inventario):
        """Obtiene el nivel actual del inventario (continuo o discreto)"""
        return inventario.level  # Todos usan Container ahora

    def es_finde(self, now):
        dia = now // 24  # Día desde el inicio de la simulación (empieza en 0)
        return (dia % 7) in [5, 6]  # Sábado y domingo

    
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
                if hora_y_minuto_del_dia + tiempo_proxima_llamada > 24:
                    # Se avanza el tiempo al dia siguiente las 10 hrs
                    tiempo_para_dia_siguiente = 24 - hora_y_minuto_del_dia + 10
                    dia_siguiente = now + tiempo_para_dia_siguiente
                    tiempo_proxima_llamada = tiempo_para_dia_siguiente + self.obtener_tiempo_proxima_llamada(dia_siguiente)
                
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
                if hora_y_minuto_del_dia + tiempo_proxima_llamada > 22:
                    # Se avanza el tiempo al dia siguiente las 10 hrs
                    tiempo_para_dia_siguiente = 24 - hora_y_minuto_del_dia + 10
                    dia_siguiente = now + tiempo_para_dia_siguiente
                    tiempo_proxima_llamada = tiempo_para_dia_siguiente + self.obtener_tiempo_proxima_llamada(dia_siguiente)

        return tiempo_proxima_llamada # unidades en horas

    
    def llegada_llamadas(self):
        yield self.env.timeout(10)  # Iniciar simulación a las 10 AM
        cliente = 0
        
        while True:
            # Verificar si ya alcanzamos el tiempo límite ANTES de esperar
            if self.env.now >= self.tiempo_limite:
                if self.logs:
                    self.log(f'Se ha alcanzado el tiempo límite de la simulación. No se aceptan más llamadas.')
                # Esperar a que todos los pedidos activos terminen
                if self.pedidos_activos:
                    pedidos_pendientes = [p for p in self.pedidos_activos if not p.triggered]
                    if pedidos_pendientes:
                        if self.logs:
                            self.log(f'Esperando a que terminen {len(pedidos_pendientes)} pedidos activos...')
                        try:
                            yield sp.AllOf(self.env, pedidos_pendientes)
                            if self.logs:
                                self.log(f'Todos los pedidos activos han terminado.')
                        except:
                            if self.logs:
                                self.log(f'No hay más eventos, asumiendo que pedidos terminaron.')
                if not self.evento_termino_simulacion.triggered:
                    self.evento_termino_simulacion.succeed()
                break
            
            # Esperamos a que llegue el siguiente cliente
            tiempo_proxima_llamada = self.obtener_tiempo_proxima_llamada(self.env.now)
            if self.env.now + tiempo_proxima_llamada >= self.tiempo_limite:
                if self.logs:
                    self.log(f'La próxima llamada excede el tiempo límite de la simulación. Avanzando al tiempo límite.')
                yield self.env.timeout(self.tiempo_limite - self.env.now)
                continue
            else: 
                yield self.env.timeout(tiempo_proxima_llamada)
            
            # Actualizamos métricas
            cliente += 1
            self.llamadas_totales += 1
            
            
            if self.logs:
                self.log(f'Cliente {cliente} intenta llamar')

            

            # Revisamos que exista una línea disponible.
            if self.lineas_telefonicas.count < 3:
                # Procedemos a atender la llamada
                pedido = self.env.process(self.atender_llamada(cliente))
                self.pedidos_activos.append(pedido)
                if self.logs:
                    self.log(f'Cliente {cliente} es atendido por teléfono')

            else:
                # Rechazamos la llamada
                self.llamadas_perdidas += 1
                if self.logs:
                    self.log(f'No hay líneas disponibles. Cliente {cliente} es rechazado')

                
        
    def atender_llamada(self, cliente):
        # Vemos si este cliente es premium o no
        premium = self.rng.choice(a=[True, False], p=[3/20, 17/20])
        if premium:
            self.pedidos_premium_totales += 1
            prioridad = 1
            if self.logs:
                self.log(f'Cliente {cliente} es premium')
        else:
            self.pedidos_normales_totales += 1
            prioridad = 2
            if self.logs:
                self.log(f'Cliente {cliente} es común')

        # Generamos el tiempo que toma la atención por teléfono.
        # Usar variable antitética si está disponible
        if self.idx_llamada < len(self.uniformes_llamada):
            u = self.uniformes_llamada[self.idx_llamada]
            # Transformación inversa para gamma
            beta = gamma_dist.ppf(u, a=4, scale=0.5) / 60
        else:
            beta = self.rng.gamma(shape=4, scale=0.5, size=1)/60
        
        # SIEMPRE incrementar el contador
        self.idx_llamada += 1
        
        with self.lineas_telefonicas.request() as linea:
            yield self.env.timeout(beta) # Esperamos
        
        if self.logs:
            self.log(f'Se terminó de anteder al cliente {cliente} por teléfono')
        # Empezamos a medir el tiempo de la orden
        inicio_tiempo_orden = self.env.now
        
        
        # Vemos la cantidad de pizzas a preparar
        if premium:
            cantidad_pizzas_a_preparar = self.rng.choice(a=[1,2,3,4], p=[0.3,0.4,0.2,0.1])
        else:
            cantidad_pizzas_a_preparar = self.rng.choice(a=[1,2,3,4], p=[0.6, 0.2, 0.15, 0.05])
        if self.logs: 
            self.log(f'Cliente {cliente} ordena {cantidad_pizzas_a_preparar} pizzas')
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
                    self.log(f'Pizza {i+1} del cliente {cliente} es tipo {tipo_pizza}')
            else:
                tipo_pizza = self.rng.choice(a=[1,2,3], p=[0.1,0.4,0.5])
                tipos_pizzas.append(tipo_pizza)
                if self.logs:
                    self.log(f'Pizza {i+1} del cliente {cliente} es tipo {tipo_pizza}')
            
            
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
            self.log(f'Todas las pizzas del cliente {cliente} están listas. Se procede al despacho')
        
        
        yield self.env.process(self.despacho(cliente, premium, prioridad, inicio_tiempo_orden, valor_orden))
        
        # Nota: el cálculo de horas extras se hace una sola vez por día en obtener_metricas.
        
            
        
        
    def preparar_pizza(self, cliente, premium, num_pizza, prioridad, tipo_pizza):
        # Actualizamos métricas
        if tipo_pizza==1:
            self.pizzas_queso += 1
        elif tipo_pizza==2:
            self.pizzas_pepperoni += 1
        elif tipo_pizza==3:
            self.pizzas_carnes += 1
        
        if self.logs:
            self.log(f'Solicitando estación de preparación para la pizza {num_pizza} del cliente {cliente}')

        with self.estacion_preparacion.request(priority=prioridad) as estacion_request:
            yield estacion_request

            with self.trabajadores.request(priority=prioridad) as trabajador_request:
                yield trabajador_request

                if self.logs:
                    self.log(f'Se comienza a preparar la pizza {num_pizza} del cliente {cliente}')

                # Vemos cuanta salsa se añadirá (continua)
                xi_1 = self.rng.exponential(scale = 250)
                if xi_1 > self.obtener_nivel_inventario(self.salsa_de_tomate):
                    if not self.en_reposicion[self.salsa_de_tomate]:
                        if self.logs:
                            self.log(f'No hay suficiente salsa de tomate para la pizza {num_pizza} del cliente {cliente}. Iniciando reposición.')
                        yield self.env.process(self.proceso_reposicion(self.salsa_de_tomate))
                    else: 
                        if self.logs:
                            self.log(f'Esperando reposición de salsa de tomate para la pizza {num_pizza} del cliente {cliente}.')
                        yield self.evento_inventario_repuesto[self.salsa_de_tomate]
                # Agregamos Salsa
                gamma_1 = self.rng.beta(a = 5, b = 2.2)/60
                yield self.env.timeout(gamma_1) # Esperamos a que se ponga la salsa
                # Descontamos la salsa (continuo)
                yield self.salsa_de_tomate.get(xi_1)
                
                # Vemos cuanto queso se añadirá (discreto)
                # Usar variable antitética si está disponible
                if self.idx_cantidad_queso < len(self.uniformes_cantidad_queso):
                    u = self.uniformes_cantidad_queso[self.idx_cantidad_queso]
                    # Transformación inversa para negative binomial
                    xi_2 = int(nbinom.ppf(u, n=25, p=0.52))
                else:
                    xi_2 = self.rng.negative_binomial(n = 25, p = 0.52)
                
                # SIEMPRE incrementar el contador
                self.idx_cantidad_queso += 1
                
                if xi_2 > self.obtener_nivel_inventario(self.queso_mozzarella):
                    if not self.en_reposicion[self.queso_mozzarella]:
                        if self.logs:
                            self.log(f'No hay suficiente queso mozzarella para la pizza {num_pizza} del cliente {cliente}. Iniciando reposición.')  
                        yield self.env.process(self.proceso_reposicion(self.queso_mozzarella))
                    else:
                        if self.logs:
                            self.log(f'Esperando reposición de queso mozzarella para la pizza {num_pizza} del cliente {cliente}.')
                        yield self.evento_inventario_repuesto[self.queso_mozzarella]
                        if self.logs:
                            self.log(f'Reposición de queso mozzarella completada, ahora se puede preparar la pizza {num_pizza} del cliente {cliente}.')
                # Agregamos queso
                # Usar variable antitética si está disponible
                if self.idx_tiempo_queso < len(self.uniformes_tiempo_queso):
                    u = self.uniformes_tiempo_queso[self.idx_tiempo_queso]
                    # Transformación inversa para triangular
                    # Parámetros: left=0.9, mode=1, right=1.2
                    # Normalizar para scipy: c = (mode - left) / (right - left)
                    c = (1 - 0.9) / (1.2 - 0.9)  # = 0.1 / 0.3 = 0.333...
                    gamma_2 = triang.ppf(u, c=c, loc=0.9, scale=0.3) / 60
                else:
                    gamma_2 = self.rng.triangular(left = 0.9, mode = 1, right = 1.2)/60
                
                # SIEMPRE incrementar el contador
                self.idx_tiempo_queso += 1
                
                yield self.env.timeout(gamma_2) # Esperamos a que se ponga el queso
                # Descontamos queso
                yield self.queso_mozzarella.get(xi_2)
                
                # Agregamos Pepperoni si pizza es de pepperoni o mix de carnes
                if tipo_pizza==2 or tipo_pizza==3:
                    # Vemos cuanto pepperoni se añadirá (discreto)
                    xi_3 = self.rng.poisson(lam = 20)
                    if xi_3 > self.obtener_nivel_inventario(self.pepperoni):
                        if not self.en_reposicion[self.pepperoni]:
                            if self.logs:
                                self.log(f'No hay suficiente pepperoni para la pizza {num_pizza} del cliente {cliente}. Iniciando reposición.')
                            yield self.env.process(self.proceso_reposicion(self.pepperoni))
                        else:
                            if self.logs:
                                self.log(f'Esperando reposición de pepperoni para la pizza {num_pizza} del cliente {cliente}.')
                            yield self.evento_inventario_repuesto[self.pepperoni]
                            if self.logs:
                                self.log(f'Reposición de pepperoni completada, ahora se puede preparar la pizza {num_pizza} del cliente {cliente}.')
                    # Agregamos pepperoni
                    gamma_3 = self.rng.lognormal(mean=0.5, sigma=0.25)/60
                    yield self.env.timeout(gamma_3) # Esperamos a que se ponga el pepperoni
                    # Descontamos pepperoni
                    if xi_3 > 0:
                        yield self.pepperoni.get(xi_3)
                    
                # Agregamos Mix
                if tipo_pizza==3:
                    # Vemos cuanta carne se añadirá (discreto)
                    xi_4 = self.rng.binomial(n = 16, p = 0.42)
                    if xi_4 > self.obtener_nivel_inventario(self.mix_carnes):
                        if not self.en_reposicion[self.mix_carnes]:
                            if self.logs:
                                self.log(f'No hay suficiente mix de carnes para la pizza {num_pizza} del cliente {cliente}. Iniciando reposición.')
                            yield self.env.process(self.proceso_reposicion(self.mix_carnes))
                        else:
                            if self.logs:
                                self.log(f'Esperando reposición de mix de carnes para la pizza {num_pizza} del cliente {cliente}.')
                            yield self.evento_inventario_repuesto[self.mix_carnes]
                            if self.logs:
                                self.log(f'Reposición de mix de carnes completada, ahora se puede preparar la pizza {num_pizza} del cliente {cliente}.')
                    # Agregamos mix
                    gamma_4 = self.rng.uniform(low = 1, high = 1.8)/60
                    yield self.env.timeout(gamma_4) # Esperamos a que se ponga el mix
                    # Descontamos Mix
                    if xi_4 > 0:
                        yield self.mix_carnes.get(xi_4)
        if self.logs:
            self.log(f'Se terminó de preparar la pizza {num_pizza} del cliente {cliente}, solicitando horno...')
        # Procedemos a hornear la pizza
        yield self.env.process(self.hornear(cliente, premium, prioridad, num_pizza))
        
        
    def hornear(self, cliente, premium,  prioridad, num_pizza):
        with self.horno.request(priority=prioridad) as horno_request:
            yield horno_request
            if self.logs:
                self.log(f'La pizza {num_pizza} del cliente {cliente} está en el horno.')
            
            # Usar variable antitética si está disponible, sino generar normalmente
            if self.idx_coccion < len(self.uniformes_coccion):
                u = self.uniformes_coccion[self.idx_coccion]
                # Transformación inversa para lognormal
                # numpy lognormal(mean, sigma) genera exp(N(mean, sigma))
                z = norm.ppf(u, loc=2.5, scale=0.2)
                delta = np.exp(z) / 60
            else:
                # numpy: lognormal(mean, sigma) donde mean y sigma son parámetros de la normal subyacente
                delta = self.rng.lognormal(mean=2.5, sigma=0.2)/60
            
            # SIEMPRE incrementar el contador (para contar en simulación preliminar)
            self.idx_coccion += 1
            
            yield self.env.timeout(delta)
            if self.logs:
                self.log(f'La pizza {num_pizza} del cliente {cliente} salió del horno, solicitando embalaje.')
        
        yield self.env.process(self.embalar(cliente, premium, prioridad, num_pizza))
            
            
    def embalar(self, cliente, premium, prioridad, num_pizza):
        with self.estacion_embalaje.request(priority=prioridad) as embalaje_request:
            yield embalaje_request
            
            with self.trabajadores.request(priority=prioridad) as trabajador_request:
                yield trabajador_request
                if self.logs:
                    self.log(f'La pizza {num_pizza} del cliente {cliente} está siendo embalada.')
                epsilon = self.rng.triangular(left = 1.1, mode = 2, right = 2.3)/60
                yield self.env.timeout(epsilon)
                if self.logs:
                    self.log(f'La pizza {num_pizza} del cliente {cliente} ha sido embalada.')
                
            
        
    def despacho(self, cliente, premium, prioridad, inicio_tiempo_orden, valor_orden):
        with self.repartidores.request(priority=prioridad) as repartidor_request:
            yield repartidor_request
            if self.logs:
                self.log(f'El repartidor procede a llevar el pedido del cliente {cliente}.')
            
            # Usar variable antitética si está disponible, sino generar normalmente
            if self.idx_despacho_ida < len(self.uniformes_despacho_ida):
                u = self.uniformes_despacho_ida[self.idx_despacho_ida]
                # Transformación inversa para gamma
                tiempo_local_domicilio = gamma_dist.ppf(u, a=7.5, scale=0.9) / 60
            else:
                tiempo_local_domicilio = self.rng.gamma(shape = 7.5, scale = 0.9)/60
            
            # SIEMPRE incrementar el contador
            self.idx_despacho_ida += 1
            
            yield self.env.timeout(tiempo_local_domicilio)
            if self.logs:
                self.log(f'Llega el repartidor al domicilio del cliente {cliente}.')
                
            # Dejamos de medir tiempo de reposición
            fin_tiempo_orden = self.env.now
            
            finde = self.es_finde(inicio_tiempo_orden)
            # Registramos tiempo total del pedido
            if premium and finde:
                self.tiempos_procesamiento_premium_finde.append(fin_tiempo_orden-inicio_tiempo_orden)
            elif premium and (not finde):
                self.tiempos_procesamiento_premium_semana.append(fin_tiempo_orden-inicio_tiempo_orden)
            elif (not premium) and finde:
                self.tiempos_procesamiento_normales_finde.append(fin_tiempo_orden-inicio_tiempo_orden)
            else:
                self.tiempos_procesamiento_normales_semana.append(fin_tiempo_orden-inicio_tiempo_orden)
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
                        self.log(f'El pedido del cliente {cliente} tuvo un retraso. Se aplica compensación de ${0.2*valor_orden}.')

                if premium and finde:
                    self.pedidos_tardios_premium_finde += 1
                elif premium and (not finde):
                    self.pedidos_tardios_premium_semana += 1
                elif (not premium) and finde:
                    self.pedidos_tardios_normales_finde += 1
                else:
                    self.pedidos_tardios_normales_semana += 1
            else:
                # Pedido entregado a tiempo: sumar ingresos normalmente
                self.ingresos += valor_orden
            
            # Usar variable antitética si está disponible, sino generar normalmente
            if self.idx_despacho_vuelta < len(self.uniformes_despacho_vuelta):
                u = self.uniformes_despacho_vuelta[self.idx_despacho_vuelta]
                # Transformación inversa para gamma
                tiempo_domicilio_local = gamma_dist.ppf(u, a=7.5, scale=0.9) / 60
            else:
                tiempo_domicilio_local = self.rng.gamma(shape = 7.5, scale = 0.9)/60
            
            # SIEMPRE incrementar el contador
            self.idx_despacho_vuelta += 1
            
            yield self.env.timeout(tiempo_domicilio_local)
            if self.logs:
                self.log(f'Llega el repartidor del cliente {cliente} al local.')
                

    def temporizador_revision_salsa(self):
        yield self.env.timeout(10) # Iniciar simulación a las 10 AM 
        
        while True:
            if self.env.now >= self.tiempo_limite:
                break
            tiempo_proxima_revision = self.obtener_tiempo_proxima_revision_salsa(self.env.now)
            yield self.env.timeout(tiempo_proxima_revision) # Revisamos cada 30 minutos en jornada laboral
            if self.env.now >= self.tiempo_limite:
                break
                
            if self.logs:
                self.log(f'Revisión periódica de inventario de salsa de tomate.')

            self.env.process(self.revisar_inventario_salsa())
    
    # Funcion solicitada a Github Copilot
    def obtener_tiempo_proxima_revision_salsa(self, now):
        # Retorna 30 minutos (0.5 horas) si estamos en jornada laboral
        # Si no, salta al día siguiente a las 10 AM + 30 minutos
        
        hora_y_minuto_del_dia = now % 24  # Ejemplo: 14.5 -> 14:30 hrs
        dia = now // 24  # Día desde el inicio de la simulación (empieza en 0)
        
        # Determinar si es fin de semana
        es_finde = (dia % 7) in [5, 6]  # Sábado y domingo
        
        if es_finde:
            # Fin de semana: horario de 10:00 a 01:00 (25 horas)
            if 10 <= hora_y_minuto_del_dia <= 24 or 0 <= hora_y_minuto_del_dia < 1:  # Estamos en jornada laboral
                return 0.5  # 30 minutos
            else:
                # Fuera de jornada: saltar al siguiente día laborable a las 10:30
                if hora_y_minuto_del_dia >= 1:  # Después de la 1 AM
                    # Saltar al mismo día a las 10:30
                    tiempo_hasta_10_30 = 10.5 - hora_y_minuto_del_dia
                else:
                    # Estamos entre 01:00 y 10:00
                    tiempo_hasta_10_30 = 10.5 - hora_y_minuto_del_dia
                
                # Verificar si el siguiente día laborable es también fin de semana
                dia_siguiente = (dia + 1) % 7
                if dia_siguiente in [5, 6]:
                    # Sigue siendo fin de semana
                    return tiempo_hasta_10_30
                else:
                    # Pasamos a día normal
                    return tiempo_hasta_10_30
        else:
            # Día normal: horario de 10:00 a 23:00 (13 horas)
            if 10 <= hora_y_minuto_del_dia < 23:  # Estamos en jornada laboral
                # Verificar que no nos pasemos de las 23:00
                if hora_y_minuto_del_dia + 0.5 <= 23:
                    return 0.5  # 30 minutos
                else:
                    # La próxima revisión sería después de las 23:00
                    # Saltar al siguiente día a las 10:30
                    tiempo_hasta_fin_dia = 24 - hora_y_minuto_del_dia
                    # Verificar si mañana es fin de semana
                    dia_siguiente = (dia + 1) % 7
                    if dia_siguiente in [5, 6]:
                        # Mañana es fin de semana (sábado o domingo)
                        return tiempo_hasta_fin_dia + 10.5
                    else:
                        # Mañana es día normal
                        return tiempo_hasta_fin_dia + 10.5
            else:
                # Fuera de jornada
                if hora_y_minuto_del_dia < 10:
                    # Antes de las 10 AM: esperar hasta las 10:30
                    return 10.5 - hora_y_minuto_del_dia
                else:
                    # Después de las 23:00: saltar al siguiente día a las 10:30
                    tiempo_hasta_fin_dia = 24 - hora_y_minuto_del_dia
                    # Verificar si mañana es fin de semana
                    dia_siguiente = (dia + 1) % 7
                    if dia_siguiente in [5, 6]:
                        # Mañana es fin de semana
                        return tiempo_hasta_fin_dia + 10.5
                    else:
                        # Mañana es día normal
                        return tiempo_hasta_fin_dia + 10.5
    
    def revisar_inventario_salsa(self):
        if self.trabajadores.count < self.cantidad_trabajadores:
            with self.trabajadores.request() as trabajador_request:
                yield trabajador_request
                nivel_actual = self.obtener_nivel_inventario(self.salsa_de_tomate)
                if nivel_actual < self.umbral_reposicion[self.salsa_de_tomate] and not self.en_reposicion[self.salsa_de_tomate]:
                    if self.logs:
                        self.log(f'{self.env.now}: Nivel de salsa de tomate bajo ({nivel_actual} ml). Iniciando reposición.')
                    yield self.env.process(self.proceso_reposicion(self.salsa_de_tomate))
        else: 
            if self.logs:
                self.log(f'{self.env.now}: No hay trabajadores disponibles para revisar inventario de salsa de tomate, se omite esta revisión.')

    def temporizador_revision_inventarios(self):
        yield self.env.timeout(10) # Iniciar simulación a las 10 AM

        while True:
            if self.env.now >= self.tiempo_limite:
                break
            tiempo_proxima_revision = self.obtener_tiempo_proxima_revision_inventarios(self.env.now)
            yield self.env.timeout(tiempo_proxima_revision) # Revisamos cada 45 minutos
            if self.env.now >= self.tiempo_limite:
                break
            if self.logs:
                self.log(f'Revisión periódica de inventarios.')
            self.env.process(self.revisar_inventarios())
    
    # Funcion solicitada a Github Copilot
    def obtener_tiempo_proxima_revision_inventarios(self, now):
        # Retorna 45 minutos (0.75 horas) si estamos en jornada laboral
        # Si no, salta al día siguiente a las 10 AM + 45 minutos
        
        hora_y_minuto_del_dia = now % 24  # Ejemplo: 14.5 -> 14:30 hrs
        dia = now // 24  # Día desde el inicio de la simulación (empieza en 0)
        
        # Determinar si es fin de semana
        es_finde = (dia % 7) in [5, 6]  # Sábado y domingo
        
        if es_finde:
            # Fin de semana: horario de 10:00 a 01:00 (25 horas)
            if 10 <= hora_y_minuto_del_dia < 25:  # Estamos en jornada laboral
                return 0.75  # 45 minutos
            else:
                # Fuera de jornada: saltar al siguiente día laborable a las 10:45
                if hora_y_minuto_del_dia >= 1:  # Después de la 1 AM
                    # Saltar al mismo día a las 10:45
                    tiempo_hasta_10_45 = 10.75 - hora_y_minuto_del_dia
                else:
                    # Estamos entre 01:00 y 10:00
                    tiempo_hasta_10_45 = 10.75 - hora_y_minuto_del_dia
                
                # Verificar si el siguiente día laborable es también fin de semana
                dia_siguiente = (dia + 1) % 7
                if dia_siguiente in [5, 6]:
                    # Sigue siendo fin de semana
                    return tiempo_hasta_10_45
                else:
                    # Pasamos a día normal
                    return tiempo_hasta_10_45
        else:
            # Día normal: horario de 10:00 a 23:00 (13 horas)
            if 10 <= hora_y_minuto_del_dia < 23:  # Estamos en jornada laboral
                # Verificar que no nos pasemos de las 23:00
                if hora_y_minuto_del_dia + 0.75 <= 23:
                    return 0.75  # 45 minutos
                else:
                    # La próxima revisión sería después de las 23:00
                    # Saltar al siguiente día a las 10:45
                    tiempo_hasta_fin_dia = 24 - hora_y_minuto_del_dia
                    # Verificar si mañana es fin de semana
                    dia_siguiente = (dia + 1) % 7
                    if dia_siguiente in [5, 6]:
                        # Mañana es fin de semana (sábado o domingo)
                        return tiempo_hasta_fin_dia + 10.75
                    else:
                        # Mañana es día normal
                        return tiempo_hasta_fin_dia + 10.75
            else:
                # Fuera de jornada
                if hora_y_minuto_del_dia < 10:
                    # Antes de las 10 AM: esperar hasta las 10:45
                    return 10.75 - hora_y_minuto_del_dia
                else:
                    # Después de las 23:00: saltar al siguiente día a las 10:45
                    tiempo_hasta_fin_dia = 24 - hora_y_minuto_del_dia
                    # Verificar si mañana es fin de semana
                    dia_siguiente = (dia + 1) % 7
                    if dia_siguiente in [5, 6]:
                        # Mañana es fin de semana
                        return tiempo_hasta_fin_dia + 10.75
                    else:
                        # Mañana es día normal
                        return tiempo_hasta_fin_dia + 10.75
        

    def revisar_inventarios(self):
        if self.trabajadores.count < self.cantidad_trabajadores:
            with self.trabajadores.request() as trabajador_request:
                yield trabajador_request
                for inventario in self.inventarios:
                    if inventario == self.salsa_de_tomate:
                        continue  # La salsa de tomate se revisa en otro proceso
                    nivel_actual = self.obtener_nivel_inventario(inventario)
                    if nivel_actual < self.umbral_reposicion[inventario] and not self.en_reposicion[inventario]:
                        if self.logs:
                            self.log(f'Nivel de {self.nombres_inventarios[inventario]} bajo ({nivel_actual}). Iniciando reposición.')
                        yield self.env.process(self.proceso_reposicion(inventario))
                    else:
                        if self.logs:
                            self.log(f'Nivel de {self.nombres_inventarios[inventario]} suficiente ({nivel_actual}). No se requiere reposición.')
        else:
            if self.logs:
                self.log(f'No hay trabajadores disponibles para revisar inventarios, se omite esta revisión.')

    def proceso_reposicion(self, inventario):
        if self.logs:
            self.log(f'Iniciando proceso de reposición para {self.nombres_inventarios[inventario]}.')
        
        nivel_actual = self.obtener_nivel_inventario(inventario)
        capacidad = inventario.capacity
        cantidad_a_reponer = capacidad - nivel_actual
        
        if self.logs:
            self.log(f'Cantidad a reponer de {self.nombres_inventarios[inventario]}: {cantidad_a_reponer} unidades.')
        tiempo_reposicion = self.obtener_tiempo_reposicion(inventario)
        if self.logs:
            self.log(f'Tiempo estimado de reposición para {self.nombres_inventarios[inventario]}: {tiempo_reposicion} horas.')
        self.en_reposicion[inventario] = True
        yield self.env.timeout(tiempo_reposicion)
        
        # Redondear cantidad si es inventario discreto
        if inventario in self.inventarios_discretos:
            cantidad_a_reponer = round(cantidad_a_reponer)
        
        yield inventario.put(cantidad_a_reponer)
        
        self.evento_inventario_repuesto[inventario].succeed()
        self.evento_inventario_repuesto[inventario] = self.env.event()
        
        nivel_nuevo = self.obtener_nivel_inventario(inventario)
        if self.logs:
            self.log(f'Reposición de {self.nombres_inventarios[inventario]} completada. Nuevo nivel: {nivel_nuevo} unidades.')

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


def replicas_simulación(iteraciones, tiempo_horas, usar_antiteticas=False):
    """
    Si usar_antiteticas=True, genera pares de réplicas:
    - Réplica normal: usa U para variables antitéticas, semilla 2*i para el resto
    - Réplica antitética: usa 1-U para variables antitéticas, semilla 2*i+1 para el resto
    
    Esto asegura:
    1. Correlación negativa en las variables antitéticas (cocción y despacho)
    2. Independencia en las demás variables aleatorias (semillas diferentes)
    
    Cotas estimadas para 168 horas (1 semana):
    - Cocción: ~1700 (cubre hasta percentil 99)
    - Despacho: ~1000 (cubre hasta percentil 99)
    
    Retorna:
    - lista_resultados: lista con métricas de cada réplica
    - estadisticas: dict con media, varianza y análisis del estimador
    """
    lista_resultados = []
    estimadores_utilidad = []  # Para variables antitéticas: promedios de cada par
    
    if usar_antiteticas:
        # Cotas generosas basadas en observaciones empíricas
        n_coccion = 1700
        n_despacho = 1000
        n_llamada = 1000  # ~900 llamadas atendidas por semana
        n_cantidad_queso = 1700  # Una por cada pizza
        n_tiempo_queso = 1700  # Una por cada pizza
        
        # Generar pares de réplicas con variables antitéticas
        pares = iteraciones // 2
        
        for i in range(pares):
            # Generar números uniformes para las variables antitéticas
            rng_antiteticas = np.random.default_rng(999999 + i)  # Semilla especial para variables antitéticas
            uniformes_coccion = rng_antiteticas.uniform(0, 1, n_coccion)
            uniformes_despacho_ida = rng_antiteticas.uniform(0, 1, n_despacho)
            uniformes_despacho_vuelta = rng_antiteticas.uniform(0, 1, n_despacho)
            uniformes_llamada = rng_antiteticas.uniform(0, 1, n_llamada)
            uniformes_cantidad_queso = rng_antiteticas.uniform(0, 1, n_cantidad_queso)
            uniformes_tiempo_queso = rng_antiteticas.uniform(0, 1, n_tiempo_queso)
            
            # Réplica normal con U
            env = sp.Environment()
            pizzeria = Pizzeria(env)
            pizzeria.iniciar_simulacion(tiempo_horas, 2*i, logs=False,
                                       uniformes_coccion=uniformes_coccion,
                                       uniformes_despacho_ida=uniformes_despacho_ida,
                                       uniformes_despacho_vuelta=uniformes_despacho_vuelta,
                                       uniformes_llamada=uniformes_llamada,
                                       uniformes_cantidad_queso=uniformes_cantidad_queso,
                                       uniformes_tiempo_queso=uniformes_tiempo_queso)
            metricas_normal = pizzeria.obtener_metricas()
            lista_resultados.append(metricas_normal)
            print(f'Réplica {2*i+1} (normal) completada.')
            
            # Réplica antitética con 1-U y semilla diferente para el resto
            uniformes_coccion_anti = 1 - uniformes_coccion
            uniformes_despacho_ida_anti = 1 - uniformes_despacho_ida
            uniformes_despacho_vuelta_anti = 1 - uniformes_despacho_vuelta
            uniformes_llamada_anti = 1 - uniformes_llamada
            uniformes_cantidad_queso_anti = 1 - uniformes_cantidad_queso
            uniformes_tiempo_queso_anti = 1 - uniformes_tiempo_queso
            
            env = sp.Environment()
            pizzeria = Pizzeria(env)
            pizzeria.iniciar_simulacion(tiempo_horas, 2*i+1, logs=False,
                                       uniformes_coccion=uniformes_coccion_anti,
                                       uniformes_despacho_ida=uniformes_despacho_ida_anti,
                                       uniformes_despacho_vuelta=uniformes_despacho_vuelta_anti,
                                       uniformes_llamada=uniformes_llamada_anti,
                                       uniformes_cantidad_queso=uniformes_cantidad_queso_anti,
                                       uniformes_tiempo_queso=uniformes_tiempo_queso_anti)
            metricas_anti = pizzeria.obtener_metricas()
            lista_resultados.append(metricas_anti)
            print(f'Réplica {2*i+2} (antitética) completada.')
            
            # Calcular promedio del par para la utilidad (estimador con variables antitéticas)
            utilidad_promedio_par = (metricas_normal['Utilidad'] + metricas_anti['Utilidad']) / 2
            estimadores_utilidad.append(utilidad_promedio_par)
            
            print("")
            print("--------------------------------")
            print("")
        
        # Calcular estadísticas del estimador con variables antitéticas
        media_estimador = np.mean(estimadores_utilidad)
        varianza_estimador = np.var(estimadores_utilidad, ddof=1)
        
        print("\n" + "="*60)
        print("RESULTADOS CON VARIABLES ANTITÉTICAS")
        print("="*60)
        print(f"Número de pares: {pares}")
        print(f"Media del estimador (utilidad): ${media_estimador:,.2f}")
        print(f"Varianza del estimador: {varianza_estimador:,.2f}")
        print(f"Desviación estándar: ${np.sqrt(varianza_estimador):,.2f}")
        print("="*60 + "\n")
        
        estadisticas = {
            'metodo': 'Variables Antitéticas',
            'n_pares': pares,
            'media': media_estimador,
            'varianza': varianza_estimador,
            'std': np.sqrt(varianza_estimador),
            'estimadores': estimadores_utilidad
        }
        
    else:
        # Réplicas independientes normales (caso base)
        for i in range(iteraciones):
            env = sp.Environment()
            pizzeria = Pizzeria(env)
            pizzeria.iniciar_simulacion(tiempo_horas, i, logs=False)
            metricas = pizzeria.obtener_metricas()
            lista_resultados.append(metricas)
            estimadores_utilidad.append(metricas['Utilidad'])
            print(f'Replica {i+1} completada.')
            print("")
            print("--------------------------------")
            print("")
        
        # Calcular estadísticas del caso base (sin reducción de varianza)
        media_estimador = np.mean(estimadores_utilidad)
        varianza_estimador = np.var(estimadores_utilidad, ddof=1)
        
        print("\n" + "="*60)
        print("RESULTADOS SIN REDUCCIÓN DE VARIANZA (CASO BASE)")
        print("="*60)
        print(f"Número de réplicas: {iteraciones}")
        print(f"Media del estimador (utilidad): ${media_estimador:,.2f}")
        print(f"Varianza del estimador: {varianza_estimador:,.2f}")
        print(f"Desviación estándar: ${np.sqrt(varianza_estimador):,.2f}")
        print("="*60 + "\n")
        
        estadisticas = {
            'metodo': 'Caso Base',
            'n_replicas': iteraciones,
            'media': media_estimador,
            'varianza': varianza_estimador,
            'std': np.sqrt(varianza_estimador),
            'estimadores': estimadores_utilidad
        }

    return lista_resultados, estadisticas
            

if __name__ == "__main__":
    replicas_simulación(50, tiempo_simulacion, True)



    



