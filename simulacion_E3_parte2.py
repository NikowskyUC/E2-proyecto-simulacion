import numpy as np
import simpy as sp
import math
import csv


# Tiempo de simulación por defecto (1 semana)
tiempo_simulacion = 168  # horas


class Pizzeria:
    """
    Versión combinada:
    - Misma lógica de la versión con variables de control.
    - Además permite usar variables antitéticas en los tiempos entre llamadas
      mediante un stream de uniformes pre-generado.
    """

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
        self.salsa_de_tomate = sp.Container(env, init=15000, capacity=15000)  # continuo: ml
        self.queso_mozzarella = sp.Container(env, init=1000, capacity=1000)   # discreto: unidades
        self.pepperoni = sp.Container(env, init=800, capacity=800)           # discreto: unidades
        self.mix_carnes = sp.Container(env, init=600, capacity=600)          # discreto: unidades

        self.inventarios = [
            self.salsa_de_tomate,
            self.queso_mozzarella,
            self.pepperoni,
            self.mix_carnes,
        ]
        self.nombres_inventarios = {
            self.salsa_de_tomate: "salsa de tomate",
            self.queso_mozzarella: "queso mozzarella",
            self.pepperoni: "pepperoni",
            self.mix_carnes: "mix de carnes",
        }
        self.en_reposicion = {inventario: False for inventario in self.inventarios}
        self.umbral_reposicion = {
            self.salsa_de_tomate: 3000,
            self.queso_mozzarella: 200,
            self.pepperoni: 300,
            self.mix_carnes: 100,
        }

        # Inventarios conceptualmente discretos (para redondear en reposición)
        self.inventarios_discretos = {
            self.queso_mozzarella,
            self.pepperoni,
            self.mix_carnes,
        }

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

        self.costo_fijo_lineas_telefonicas = 50000 * 3  # semanal
        self.costo_fijo_espacio_preparacion = 60000 * 3  # semanal
        self.costo_fijo_horno = 40000 * 10  # semanal
        self.costo_fijo_embalaje = 30000 * 3  # semanal
        self.costos_fijos_semanales = (
            self.costo_fijo_lineas_telefonicas
            + self.costo_fijo_espacio_preparacion
            + self.costo_fijo_horno
            + self.costo_fijo_embalaje
        )

        # Tasas de llegada de llamadas
        self.tasas_dia_normal = {
            10: 1.5,
            11: 4.5,
            12: 9,
            13: 15,
            14: 9,
            15: 10.5,
            16: 9,
            17: 7.5,
            18: 6.75,
            19: 6,
            20: 4.5,
            21: 3,
        }

        self.tasas_finde = {
            10: 2.5,
            11: 10,
            12: 22.5,
            13: 31.25,
            14: 31.25,
            15: 30,
            16: 22.5,
            17: 15,
            18: 13.75,
            19: 12.5,
            20: 11.25,
            21: 10,
            22: 7.5,
            23: 5,
        }

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
        self.ultima_hora_fin_por_dia = {}

        self.ingresos = 0
        self.costos = 0

        self.salario_hora_empleado = 4000
        self.salario_hora_repartidor = 3000
        self.horas_trabajo_dia_normal = 13
        self.horas_trabajo_finde = 15

        self.utilidad = 0

        # Variables de control: registrar tiempos individuales
        self.tiempos_llamada = []
        self.tiempos_salsa = []
        self.tiempos_queso = []
        self.tiempos_pepperoni = []
        self.tiempos_carnes = []
        self.tiempos_horno = []
        self.tiempos_embalaje = []
        self.tiempos_despacho = []

        self.tiempos_entre_llamadas = []

        # Antitéticas en inter-arrivals
        self.usar_antiteticas = False
        self.uniformes_interarrival = []
        self.idx_interarrival = 0

    # ------------------------------------------------------------------
    # Inicialización de la simulación
    # ------------------------------------------------------------------
    def iniciar_simulacion(
        self,
        tiempo_horas,
        seed,
        logs=False,
        usar_antiteticas=False,
        uniformes_interarrival=None,
    ):
        self.tiempo_limite = tiempo_horas + 10  # iniciar 10 AM
        self.logs = logs
        self.log_data = ""

        self.rng = np.random.default_rng(seed)

        self.usar_antiteticas = usar_antiteticas
        self.uniformes_interarrival = (
            uniformes_interarrival if uniformes_interarrival is not None else []
        )
        self.idx_interarrival = 0

        self.evento_termino_simulacion = self.env.event()
        self.pedidos_activos = []

        self.evento_inventario_repuesto = {
            inventario: self.env.event() for inventario in self.inventarios
        }

        self.env.process(self.llegada_llamadas())
        self.env.process(self.temporizador_revision_salsa())
        self.env.process(self.temporizador_revision_inventarios())

        try:
            self.env.run(until=self.evento_termino_simulacion)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Helpers varios
    # ------------------------------------------------------------------
    def obtener_nivel_inventario(self, inventario):
        return inventario.level

    def es_finde(self, now):
        dia = now // 24
        return (dia % 7) in [5, 6]

    # ------------------------------------------------------------------
    # Generador de exponenciales con/ sin antitéticas
    # ------------------------------------------------------------------
    def expon_interarrival(self, tasa):
        """Devuelve una exponencial(1/tasa) usando antitéticas si están activadas."""
        if self.usar_antiteticas and self.idx_interarrival < len(self.uniformes_interarrival):
            u = float(self.uniformes_interarrival[self.idx_interarrival])
            self.idx_interarrival += 1
            return -math.log(1.0 - u) / tasa
        else:
            return self.rng.exponential(1.0 / tasa)

    # ------------------------------------------------------------------
    # Llegadas
    # ------------------------------------------------------------------
    def obtener_tiempo_proxima_llamada(self, now):
        hora_y_minuto_del_dia = now % 24
        hora_del_dia = math.floor(hora_y_minuto_del_dia)
        dia = now // 24

        es_finde = (dia % 7) in [5, 6]

        if es_finde:
            if hora_del_dia < 10:
                tasa = self.tasas_finde[10]
                tiempo_proxima_llamada = 10 - hora_y_minuto_del_dia + self.expon_interarrival(tasa)
            else:
                tasa = self.tasas_finde[hora_del_dia]
                tiempo_proxima_llamada = self.expon_interarrival(tasa)
                if hora_y_minuto_del_dia + tiempo_proxima_llamada > 24:
                    tiempo_para_dia_siguiente = 24 - hora_y_minuto_del_dia + 10
                    dia_siguiente = now + tiempo_para_dia_siguiente
                    tiempo_proxima_llamada = (
                        tiempo_para_dia_siguiente + self.obtener_tiempo_proxima_llamada(dia_siguiente)
                    )
        else:
            if hora_del_dia < 10:
                tasa = self.tasas_dia_normal[10]
                tiempo_proxima_llamada = 10 - hora_y_minuto_del_dia + self.expon_interarrival(tasa)
            elif hora_del_dia > 21:
                tiempo_para_dia_siguiente = 24 - hora_y_minuto_del_dia + 10
                dia_siguiente = now + tiempo_para_dia_siguiente
                dia_siguiente_es_finde = (dia_siguiente // 24) % 7 in [5, 6]
                if dia_siguiente_es_finde:
                    tasa = self.tasas_finde[10]
                else:
                    tasa = self.tasas_dia_normal[10]
                tiempo_proxima_llamada = tiempo_para_dia_siguiente + self.expon_interarrival(tasa)
            else:
                tasa = self.tasas_dia_normal[hora_del_dia]
                tiempo_proxima_llamada = self.expon_interarrival(tasa)
                if hora_y_minuto_del_dia + tiempo_proxima_llamada > 22:
                    tiempo_para_dia_siguiente = 24 - hora_y_minuto_del_dia + 10
                    dia_siguiente = now + tiempo_para_dia_siguiente
                    tiempo_proxima_llamada = (
                        tiempo_para_dia_siguiente + self.obtener_tiempo_proxima_llamada(dia_siguiente)
                    )

        return tiempo_proxima_llamada

    def llegada_llamadas(self):
        yield self.env.timeout(10)  # inicia 10 AM
        cliente = 0

        while True:
            if self.env.now >= self.tiempo_limite:
                if self.pedidos_activos:
                    pedidos_pendientes = [p for p in self.pedidos_activos if not p.triggered]
                    if pedidos_pendientes:
                        try:
                            yield sp.AllOf(self.env, pedidos_pendientes)
                        except:
                            pass
                if not self.evento_termino_simulacion.triggered:
                    self.evento_termino_simulacion.succeed()
                break

            tiempo_proxima_llamada = self.obtener_tiempo_proxima_llamada(self.env.now)
            if self.env.now + tiempo_proxima_llamada >= self.tiempo_limite:
                yield self.env.timeout(self.tiempo_limite - self.env.now)
                continue
            else:
                self.tiempos_entre_llamadas.append(tiempo_proxima_llamada)
                yield self.env.timeout(tiempo_proxima_llamada)

            cliente += 1
            self.llamadas_totales += 1

            if self.lineas_telefonicas.count < 3:
                pedido = self.env.process(self.atender_llamada(cliente))
                self.pedidos_activos.append(pedido)
            else:
                self.llamadas_perdidas += 1

    # ------------------------------------------------------------------
    # Atención, preparación, horno, embalaje, despacho
    # ------------------------------------------------------------------
    def atender_llamada(self, cliente):
        premium = self.rng.choice(a=[True, False], p=[3 / 20, 17 / 20])
        if premium:
            self.pedidos_premium_totales += 1
            prioridad = 1
        else:
            self.pedidos_normales_totales += 1
            prioridad = 2

        beta = self.rng.gamma(shape=4, scale=0.5, size=1)[0] / 60
        self.tiempos_llamada.append(beta * 60)  # minutos
        with self.lineas_telefonicas.request() as linea:
            yield self.env.timeout(beta)

        inicio_tiempo_orden = self.env.now

        if premium:
            cantidad_pizzas_a_preparar = self.rng.choice(a=[1, 2, 3, 4], p=[0.3, 0.4, 0.2, 0.1])
        else:
            cantidad_pizzas_a_preparar = self.rng.choice(a=[1, 2, 3, 4], p=[0.6, 0.2, 0.15, 0.05])

        tipos_pizzas = []
        for _ in range(cantidad_pizzas_a_preparar):
            if premium:
                tipo_pizza = self.rng.choice(a=[1, 2, 3], p=[0.3, 0.6, 0.1])
            else:
                tipo_pizza = self.rng.choice(a=[1, 2, 3], p=[0.1, 0.4, 0.5])
            tipos_pizzas.append(tipo_pizza)

        lista_de_procesos_pizzas = []
        valor_orden = 0
        for i, tipo in enumerate(tipos_pizzas):
            lista_de_procesos_pizzas.append(
                self.env.process(self.preparar_pizza(cliente, premium, i + 1, prioridad, tipo))
            )
            if tipo == 1:
                valor_orden += 7000
            elif tipo == 2:
                valor_orden += 9000
            else:
                valor_orden += 12000

        yield sp.AllOf(self.env, lista_de_procesos_pizzas)
        yield self.env.process(self.despacho(cliente, premium, prioridad, inicio_tiempo_orden, valor_orden))

    def preparar_pizza(self, cliente, premium, num_pizza, prioridad, tipo_pizza):
        if tipo_pizza == 1:
            self.pizzas_queso += 1
        elif tipo_pizza == 2:
            self.pizzas_pepperoni += 1
        elif tipo_pizza == 3:
            self.pizzas_carnes += 1

        with self.estacion_preparacion.request(priority=prioridad) as estacion_request:
            yield estacion_request

            with self.trabajadores.request(priority=prioridad) as trabajador_request:
                yield trabajador_request

                xi_1 = self.rng.exponential(scale=250)
                if xi_1 > self.obtener_nivel_inventario(self.salsa_de_tomate):
                    if not self.en_reposicion[self.salsa_de_tomate]:
                        yield self.env.process(self.proceso_reposicion(self.salsa_de_tomate))
                    else:
                        yield self.evento_inventario_repuesto[self.salsa_de_tomate]

                gamma_1 = self.rng.beta(a=5, b=2.2) / 60
                self.tiempos_salsa.append(gamma_1 * 60)
                yield self.env.timeout(gamma_1)
                yield self.salsa_de_tomate.get(xi_1)

                xi_2 = self.rng.negative_binomial(n=25, p=0.52)
                if xi_2 > self.obtener_nivel_inventario(self.queso_mozzarella):
                    if not self.en_reposicion[self.queso_mozzarella]:
                        yield self.env.process(self.proceso_reposicion(self.queso_mozzarella))
                    else:
                        yield self.evento_inventario_repuesto[self.queso_mozzarella]

                gamma_2 = self.rng.triangular(left=0.9, mode=1, right=1.2) / 60
                self.tiempos_queso.append(gamma_2 * 60)
                yield self.env.timeout(gamma_2)
                yield self.queso_mozzarella.get(xi_2)

                if tipo_pizza == 2 or tipo_pizza == 3:
                    xi_3 = self.rng.poisson(lam=20)
                    if xi_3 > self.obtener_nivel_inventario(self.pepperoni):
                        if not self.en_reposicion[self.pepperoni]:
                            yield self.env.process(self.proceso_reposicion(self.pepperoni))
                        else:
                            yield self.evento_inventario_repuesto[self.pepperoni]

                    gamma_3 = self.rng.lognormal(mean=0.5, sigma=0.25) / 60
                    self.tiempos_pepperoni.append(gamma_3 * 60)
                    yield self.env.timeout(gamma_3)
                    if xi_3 > 0:
                        yield self.pepperoni.get(xi_3)

                if tipo_pizza == 3:
                    xi_4 = self.rng.binomial(n=16, p=0.42)
                    if xi_4 > self.obtener_nivel_inventario(self.mix_carnes):
                        if not self.en_reposicion[self.mix_carnes]:
                            yield self.env.process(self.proceso_reposicion(self.mix_carnes))
                        else:
                            yield self.evento_inventario_repuesto[self.mix_carnes]

                    gamma_4 = self.rng.uniform(low=1, high=1.8) / 60
                    self.tiempos_carnes.append(gamma_4 * 60)
                    yield self.env.timeout(gamma_4)
                    if xi_4 > 0:
                        yield self.mix_carnes.get(xi_4)

        yield self.env.process(self.hornear(cliente, premium, prioridad, num_pizza))

    def hornear(self, cliente, premium, prioridad, num_pizza):
        with self.horno.request(priority=prioridad) as horno_request:
            yield horno_request
            delta = self.rng.lognormal(mean=2.5, sigma=0.2) / 60
            self.tiempos_horno.append(delta * 60)
            yield self.env.timeout(delta)
        yield self.env.process(self.embalar(cliente, premium, prioridad, num_pizza))

    def embalar(self, cliente, premium, prioridad, num_pizza):
        with self.estacion_embalaje.request(priority=prioridad) as embalaje_request:
            yield embalaje_request

            with self.trabajadores.request(priority=prioridad) as trabajador_request:
                yield trabajador_request
                epsilon = self.rng.triangular(left=1.1, mode=2, right=2.3) / 60
                self.tiempos_embalaje.append(epsilon * 60)
                yield self.env.timeout(epsilon)

    def despacho(self, cliente, premium, prioridad, inicio_tiempo_orden, valor_orden):
        with self.repartidores.request(priority=prioridad) as repartidor_request:
            yield repartidor_request

            tiempo_local_domicilio = self.rng.gamma(shape=7.5, scale=0.9) / 60
            self.tiempos_despacho.append(tiempo_local_domicilio * 60)
            yield self.env.timeout(tiempo_local_domicilio)

            fin_tiempo_orden = self.env.now

            finde = self.es_finde(inicio_tiempo_orden)
            if premium and finde:
                self.tiempos_procesamiento_premium_finde.append(fin_tiempo_orden - inicio_tiempo_orden)
            elif premium and (not finde):
                self.tiempos_procesamiento_premium_semana.append(fin_tiempo_orden - inicio_tiempo_orden)
            elif (not premium) and finde:
                self.tiempos_procesamiento_normales_finde.append(fin_tiempo_orden - inicio_tiempo_orden)
            else:
                self.tiempos_procesamiento_normales_semana.append(fin_tiempo_orden - inicio_tiempo_orden)

            dia_fin = int(fin_tiempo_orden // 24)
            hora_fin = fin_tiempo_orden % 24
            dia_jornada = dia_fin if hora_fin >= 10 else max(dia_fin - 1, 0)
            prev = self.ultima_hora_fin_por_dia.get(dia_jornada, -1)
            if hora_fin > prev:
                self.ultima_hora_fin_por_dia[dia_jornada] = hora_fin

            retraso = fin_tiempo_orden - inicio_tiempo_orden > 1
            if retraso:
                if premium:
                    self.compensacion += 0.2 * valor_orden

                if premium and finde:
                    self.pedidos_tardios_premium_finde += 1
                elif premium and (not finde):
                    self.pedidos_tardios_premium_semana += 1
                elif (not premium) and finde:
                    self.pedidos_tardios_normales_finde += 1
                else:
                    self.pedidos_tardios_normales_semana += 1
            else:
                self.ingresos += valor_orden

            tiempo_domicilio_local = self.rng.gamma(shape=7.5, scale=0.9) / 60
            self.tiempos_despacho.append(tiempo_domicilio_local * 60)
            yield self.env.timeout(tiempo_domicilio_local)

    # ------------------------------------------------------------------
    # Procesos de inventario (como antes)
    # ------------------------------------------------------------------
    def temporizador_revision_salsa(self):
        yield self.env.timeout(10)

        while True:
            if self.env.now + 3 >= self.tiempo_limite:
                break
            tiempo_proxima_revision = self.obtener_tiempo_proxima_revision_salsa(self.env.now)
            yield self.env.timeout(tiempo_proxima_revision)
            if self.env.now >= self.tiempo_limite:
                break
            self.env.process(self.revisar_inventario_salsa())

    def obtener_tiempo_proxima_revision_salsa(self, now):
        hora_y_minuto_del_dia = now % 24
        dia = now // 24
        es_finde = (dia % 7) in [5, 6]

        if es_finde:
            if 10 <= hora_y_minuto_del_dia <= 24 or 0 <= hora_y_minuto_del_dia < 1:
                return 0.5
            else:
                if hora_y_minuto_del_dia >= 1:
                    tiempo_hasta_10_30 = 10.5 - hora_y_minuto_del_dia
                else:
                    tiempo_hasta_10_30 = 10.5 - hora_y_minuto_del_dia
                return tiempo_hasta_10_30
        else:
            if 10 <= hora_y_minuto_del_dia < 23:
                if hora_y_minuto_del_dia + 0.5 <= 23:
                    return 0.5
                else:
                    tiempo_hasta_fin_dia = 24 - hora_y_minuto_del_dia
                    return tiempo_hasta_fin_dia + 10.5
            else:
                if hora_y_minuto_del_dia < 10:
                    return 10.5 - hora_y_minuto_del_dia
                else:
                    tiempo_hasta_fin_dia = 24 - hora_y_minuto_del_dia
                    return tiempo_hasta_fin_dia + 10.5

    def revisar_inventario_salsa(self):
        if self.trabajadores.count < self.cantidad_trabajadores:
            with self.trabajadores.request() as trabajador_request:
                yield trabajador_request
                nivel_actual = self.obtener_nivel_inventario(self.salsa_de_tomate)
                if (
                    nivel_actual < self.umbral_reposicion[self.salsa_de_tomate]
                    and not self.en_reposicion[self.salsa_de_tomate]
                ):
                    yield self.env.process(self.proceso_reposicion(self.salsa_de_tomate))

    def temporizador_revision_inventarios(self):
        yield self.env.timeout(10)

        while True:
            if self.env.now >= self.tiempo_limite:
                break
            tiempo_proxima_revision = self.obtener_tiempo_proxima_revision_inventarios(self.env.now)
            yield self.env.timeout(tiempo_proxima_revision)
            if self.env.now >= self.tiempo_limite:
                break
            self.env.process(self.revisar_inventarios())

    def obtener_tiempo_proxima_revision_inventarios(self, now):
        hora_y_minuto_del_dia = now % 24
        dia = now // 24
        es_finde = (dia % 7) in [5, 6]

        if es_finde:
            if 10 <= hora_y_minuto_del_dia < 25:
                return 0.75
            else:
                if hora_y_minuto_del_dia >= 1:
                    tiempo_hasta_10_45 = 10.75 - hora_y_minuto_del_dia
                else:
                    tiempo_hasta_10_45 = 10.75 - hora_y_minuto_del_dia
                return tiempo_hasta_10_45
        else:
            if 10 <= hora_y_minuto_del_dia < 23:
                if hora_y_minuto_del_dia + 0.75 <= 23:
                    return 0.75
                else:
                    tiempo_hasta_fin_dia = 24 - hora_y_minuto_del_dia
                    return tiempo_hasta_fin_dia + 10.75
            else:
                if hora_y_minuto_del_dia < 10:
                    return 10.75 - hora_y_minuto_del_dia
                else:
                    tiempo_hasta_fin_dia = 24 - hora_y_minuto_del_dia
                    return tiempo_hasta_fin_dia + 10.75

    def revisar_inventarios(self):
        if self.trabajadores.count < self.cantidad_trabajadores:
            with self.trabajadores.request() as trabajador_request:
                yield trabajador_request
                for inventario in self.inventarios:
                    if inventario == self.salsa_de_tomate:
                        continue
                    nivel_actual = self.obtener_nivel_inventario(inventario)
                    if nivel_actual < self.umbral_reposicion[inventario] and not self.en_reposicion[inventario]:
                        yield self.env.process(self.proceso_reposicion(inventario))

    def proceso_reposicion(self, inventario):
        nivel_actual = self.obtener_nivel_inventario(inventario)
        capacidad = inventario.capacity
        cantidad_a_reponer = capacidad - nivel_actual
        tiempo_reposicion = self.obtener_tiempo_reposicion(inventario)
        self.en_reposicion[inventario] = True
        yield self.env.timeout(tiempo_reposicion)

        if inventario in self.inventarios_discretos:
            cantidad_a_reponer = round(cantidad_a_reponer)

        yield inventario.put(cantidad_a_reponer)
        self.evento_inventario_repuesto[inventario].succeed()
        self.evento_inventario_repuesto[inventario] = self.env.event()
        self.en_reposicion[inventario] = False

    def obtener_tiempo_reposicion(self, inventario):
        if inventario == self.salsa_de_tomate:
            tiempo = self.rng.weibull(a=1.2) * 10 / 60
        elif inventario == self.queso_mozzarella:
            tiempo = self.rng.lognormal(mean=1.58, sigma=0.25) / 60
        elif inventario == self.pepperoni:
            tiempo = self.rng.weibull(a=1.3) * 3.9 / 60
        elif inventario == self.mix_carnes:
            tiempo = self.rng.exponential(scale=5) / 60
        else:
            tiempo = 0
        return tiempo

    # ------------------------------------------------------------------
    # Métricas + variables de control
    # ------------------------------------------------------------------
    def obtener_metricas(self):
        # ===== Cálculo de horas extras =====
        self.horas_extras = 0
        for dia, hora_fin in self.ultima_hora_fin_por_dia.items():
            es_finde = (dia % 7) in [5, 6]
            if es_finde and 10 > hora_fin > 1:
                self.horas_extras += hora_fin - 1
            elif (not es_finde) and (hora_fin > 23 or hora_fin < 10):
                self.horas_extras += (hora_fin - 23) if hora_fin > 23 else (hora_fin + 1)

        # ===== Cálculo de horas de jornada y semanas =====
        tiempo_simulacion_horas = getattr(self, "tiempo_limite", 10) - 10
        horas_normales = self.calcular_horas_normales(tiempo_simulacion_horas)
        horas_finde = self.calcular_horas_finde(tiempo_simulacion_horas)
        horas_jornada_total = horas_normales + horas_finde

        semanas = int(math.ceil(tiempo_simulacion_horas / 168.0)) if tiempo_simulacion_horas > 0 else 0

        # ===== Costos variables de personal =====
        costo_trabajadores = (
            self.salario_hora_empleado * horas_jornada_total * self.cantidad_trabajadores
        )
        costo_repartidores = (
            self.salario_hora_repartidor * horas_jornada_total * self.cantidad_repartidores
        )

        # Ojo: si quieres incluir horas extras con sobrecosto, agrégalo aquí
        # (esto depende de tu versión "oficial" de costos)

        # ===== Costos totales =====
        self.costos = (
            10_000 * self.llamadas_perdidas
            + 0.3 * 7_000 * self.pizzas_queso
            + 0.3 * 9_000 * self.pizzas_pepperoni
            + 0.3 * 12_000 * self.pizzas_carnes
            + self.costos_fijos_semanales * semanas
            + self.compensacion
            + costo_trabajadores
            + costo_repartidores
        )

        self.utilidad = self.ingresos - self.costos

        # =========================
        # VARIABLES DE CONTROL
        # =========================
        # X1–X8: promedios de tiempos (ya los fuiste guardando en listas)
        # NOTA: supongo que todos estos tiempos ya están en MINUTOS,
        # excepto tiempos_entre_llamadas que está en HORAS.
        tiempo_promedio_llamada   = np.mean(self.tiempos_llamada)   if self.tiempos_llamada   else 0.0  # X1
        tiempo_promedio_salsa     = np.mean(self.tiempos_salsa)     if self.tiempos_salsa     else 0.0  # X2
        tiempo_promedio_queso     = np.mean(self.tiempos_queso)     if self.tiempos_queso     else 0.0  # X3
        tiempo_promedio_pepperoni = np.mean(self.tiempos_pepperoni) if self.tiempos_pepperoni else 0.0  # X4
        tiempo_promedio_carnes    = np.mean(self.tiempos_carnes)    if self.tiempos_carnes    else 0.0  # X5
        tiempo_promedio_coccion   = np.mean(self.tiempos_horno)     if self.tiempos_horno     else 0.0  # X6
        tiempo_promedio_embalaje  = np.mean(self.tiempos_embalaje)  if self.tiempos_embalaje  else 0.0  # X7
        tiempo_promedio_despacho  = np.mean(self.tiempos_despacho)  if self.tiempos_despacho  else 0.0  # X8

        # X9: tiempo promedio entre llamadas (HORAS)
        tiempo_promedio_entre_llamadas = (
            np.mean(self.tiempos_entre_llamadas) if self.tiempos_entre_llamadas else 0.0
        )

        # X10: proporción de pedidos premium
        total_pedidos = self.pedidos_normales_totales + self.pedidos_premium_totales
        proporcion_premium = (
            self.pedidos_premium_totales / total_pedidos if total_pedidos > 0 else 0.0
        )

        # Para compatibilidad con tu VC anterior:
        total_pizzas = self.pizzas_queso + self.pizzas_pepperoni + self.pizzas_carnes

        return {
            # Métrica principal
            "Utilidad": self.utilidad,

            # Variables de control "viejas"
            "Total Pizzas": total_pizzas,
            "Tiempo Promedio Coccion": tiempo_promedio_coccion,
            "Tiempo Promedio Despacho": tiempo_promedio_despacho,

            # Variables de control nuevas (las 10 en total)
            "Tiempo Promedio Llamada": tiempo_promedio_llamada,             # X1
            "Tiempo Promedio Salsa": tiempo_promedio_salsa,                 # X2
            "Tiempo Promedio Queso": tiempo_promedio_queso,                 # X3
            "Tiempo Promedio Pepperoni": tiempo_promedio_pepperoni,         # X4
            "Tiempo Promedio Carnes": tiempo_promedio_carnes,               # X5
            "Tiempo Promedio Embalaje": tiempo_promedio_embalaje,           # X7
            "Tiempo Promedio Entre Llamadas": tiempo_promedio_entre_llamadas,  # X9 (HORAS)
            "Proporcion Premium": proporcion_premium,                       # X10
        }


    # ------------------------------------------------------------------
    # Cálculo de horas normales / finde
    # ------------------------------------------------------------------
    def calcular_horas_normales(self, tiempo_horas: float) -> float:
        if tiempo_horas <= 0:
            return 0.0

        horas = 0.0
        max_dias = int(math.ceil(tiempo_horas / 24.0))
        for k in range(max_dias):
            dia_semana = k % 7
            if dia_semana > 4:
                continue
            inicio_jornada = k * 24.0
            fin_jornada = inicio_jornada + float(self.horas_trabajo_dia_normal)
            comienzo = max(inicio_jornada, 0.0)
            termino = min(fin_jornada, tiempo_horas)
            if termino > comienzo:
                horas += termino - comienzo

        return horas

    def calcular_horas_finde(self, tiempo_horas: float) -> float:
        if tiempo_horas <= 0:
            return 0.0

        horas = 0.0
        max_dias = int(math.ceil(tiempo_horas / 24.0))
        for k in range(max_dias):
            dia_semana = k % 7
            if dia_semana not in [5, 6]:
                continue
            inicio_jornada = k * 24.0
            fin_jornada = inicio_jornada + float(self.horas_trabajo_finde)
            comienzo = max(inicio_jornada, 0.0)
            termino = min(fin_jornada, tiempo_horas)
            if termino > comienzo:
                horas += termino - comienzo

        return horas

def medias_teoricas_VC(pizzeria, prob_premium=3/20, factor_atencion=0.99):
    """
    Calcula las medias teóricas E[X] de TODAS las variables de control, en el
    MISMO orden en que se arma la matriz X en replicas_mixto:

        X = [
          X_pizzas,  # 1) Total Pizzas
          X_llam,    # 2) Tiempo Promedio Llamada (min)
          X_salsa,   # 3) Tiempo Promedio Salsa (min)
          X_queso,   # 4) Tiempo Promedio Queso (min)
          X_pepp,    # 5) Tiempo Promedio Pepperoni (min)
          X_carnes,  # 6) Tiempo Promedio Carnes (min)
          X_horno,   # 7) Tiempo Promedio Cocción (min)
          X_embal,   # 8) Tiempo Promedio Embalaje (min)
          X_desp,    # 9) Tiempo Promedio Despacho (min)
          X_inter,   # 10) Tiempo Promedio Entre Llamadas (horas)
          X_prem     # 11) Proporción Premium
        ]

    Retorna:
        np.array([E_pizzas_totales, E_t_llam, E_t_salsa, E_t_queso, E_t_pepp,
                  E_t_carnes, E_t_horno, E_t_embal, E_t_desp, E_T_inter, E_prop_premium])
    """

    prob_normal = 1 - prob_premium

    # ------------------------------------------------------------------
    # 1) E[Total Pizzas en la semana]
    # ------------------------------------------------------------------
    # 1.a) E[pizzas por pedido premium]  (soporte {1,2,3,4})
    E_pizzas_premium = 1*0.3 + 2*0.4 + 3*0.2 + 4*0.1   # = 2.1

    # 1.b) E[pizzas por pedido normal]  (soporte {1,2,3,4})
    E_pizzas_normal = 1*0.6 + 2*0.2 + 3*0.15 + 4*0.05  # = 1.65

    # 1.c) E[pizzas por pedido] (mezcla premium/normal)
    E_pizzas_por_pedido = prob_premium * E_pizzas_premium + prob_normal * E_pizzas_normal
    #   = 0.15*2.1 + 0.85*1.65 = 1.7175

    # 1.d) E[número de llamadas que llegan por semana]
    tasas_normal = list(pizzeria.tasas_dia_normal.values())  # 12 horas (10–21)
    tasas_finde  = list(pizzeria.tasas_finde.values())       # 14 horas (10–23)

    E_llamadas_dia_normal = sum(tasas_normal)
    E_llamadas_dia_finde  = sum(tasas_finde)

    # 5 días normales + 2 días de finde por semana
    E_llamadas_semana = 5 * E_llamadas_dia_normal + 2 * E_llamadas_dia_finde

    # 1.e) E[pedidos atendidos] ≈ factor_atencion * llamadas que llegan
    E_pedidos_atendidos = factor_atencion * E_llamadas_semana  # ~0.99*935 = 925

    # 1.f) E[Total Pizzas] = E[pedidos atendidos] × E[pizzas por pedido]
    E_pizzas_totales = E_pedidos_atendidos * E_pizzas_por_pedido

    # ------------------------------------------------------------------
    # 2) Tiempos de proceso: medias teóricas de las distribuciones
    # ------------------------------------------------------------------

    # X2: Tiempo de llamada ~ Gamma(4, 0.5) horas  ⇒ *60 → minutos
    shape_llam, scale_llam = 4, 0.5
    E_t_llam = shape_llam * scale_llam * 60

    # X3: Tiempo salsa ~ Beta(a=5, b=2.2) horas ⇒ *60 → minutos
    a_salsa, b_salsa = 5, 2.2
    E_t_salsa = (a_salsa / (a_salsa + b_salsa)) * 60

    # X4: Tiempo queso ~ Triangular(0.9, 1.0, 1.2) minutos
    left_q, mode_q, right_q = 0.9, 1.0, 1.2
    E_t_queso = (left_q + mode_q + right_q) / 3

    # X5: Tiempo pepperoni ~ Lognormal(mean=0.5, sigma=0.25) horas ⇒ *60 → minutos
    mu_pepp, sigma_pepp = 0.5, 0.25
    E_t_pepp = np.exp(mu_pepp + 0.5 * sigma_pepp**2) * 60

    # X6: Tiempo carnes ~ Uniform(1, 1.8) minutos
    a_c, b_c = 1.0, 1.8
    E_t_carnes = (a_c + b_c) / 2

    # X7: Tiempo horno ~ Lognormal(mean=2.5, sigma=0.2) horas ⇒ *60 → minutos
    mu_h, sigma_h = 2.5, 0.2
    E_t_horno = np.exp(mu_h + 0.5 * sigma_h**2) * 60

    # X8: Tiempo embalaje ~ Triangular(1.1, 2.0, 2.3) minutos
    left_e, mode_e, right_e = 1.1, 2.0, 2.3
    E_t_embal = (left_e + mode_e + right_e) / 3

    # X9: Tiempo despacho ~ Gamma(7.5, 0.9) horas ⇒ *60 → minutos
    k_d, theta_d = 7.5, 0.9
    E_t_desp = k_d * theta_d * 60

    # ------------------------------------------------------------------
    # 3) Tiempo entre llamadas (proceso de renovación no homogéneo)
    # ------------------------------------------------------------------
    # E[T] ≈ promedio ponderado de 1/λ por hora de operación

    # Días normales: 10–22h (12 tasas en tasas_dia_normal)
    E_T_normal = np.mean([1.0 / lam for lam in tasas_normal])

    # Fines de semana: 10–23h (14 tasas en tasas_finde)
    E_T_finde = np.mean([1.0 / lam for lam in tasas_finde])

    # Mezcla semanal 5 días normales + 2 finde
    E_T_inter = (5 * E_T_normal + 2 * E_T_finde) / 7  # en horas

    # ------------------------------------------------------------------
    # 4) Proporción de pedidos premium
    # ------------------------------------------------------------------
    E_prop_premium = prob_premium

    # ------------------------------------------------------------------
    # Empaquetar en vector (11 elementos) en el mismo orden que X
    # ------------------------------------------------------------------
    return np.array([
        E_pizzas_totales,  # 1) Total Pizzas
        E_t_llam,          # 2) Tiempo Llamada (min)
        E_t_salsa,         # 3) Tiempo Salsa (min)
        E_t_queso,         # 4) Tiempo Queso (min)
        E_t_pepp,          # 5) Tiempo Pepperoni (min)
        E_t_carnes,        # 6) Tiempo Carnes (min)
        E_t_horno,         # 7) Tiempo Cocción (min)
        E_t_embal,         # 8) Tiempo Embalaje (min)
        E_t_desp,          # 9) Tiempo Despacho (min)
        E_T_inter,         # 10) Tiempo Entre Llamadas (horas)
        E_prop_premium,    # 11) Proporción Premium
    ])



# ======================================================================
# Réplicas: caso base, antitéticas, VC, antitéticas + VC
# ======================================================================

def replicas_mixto(
    n_replicas,
    tiempo_horas,
    usar_antiteticas=False,
    usar_vc=False,
    n_uniformes_inter=5000,
):
    """
    Ejecuta la simulación con las siguientes opciones:
      - usar_antiteticas: aplica variables antitéticas en tiempos entre llamadas
      - usar_vc: aplica variables de control (Total Pizzas)
    Si usar_antiteticas=True, n_replicas debe ser PAR (trabajamos por pares).

    IMPORTANTE:
    - Sin VC: devuelve estadísticos usando TODOS los estimadores Y generados
      (Y = utilidades o promedios antitéticos por par).
    - Con VC (two-stage): los estadísticos "simple" y "control" usan SOLO las
      réplicas de ESTIMACIÓN (n_estim).
    """

    Y = []   # utilidades (o estimador antitético por par)

    # Variables de control que recolectamos de la simulación
    X_pizzas = []   # Total de pizzas

    # (resto de VC que no usamos ahora, pero las dejamos por si amplías a multi-VC)
    X_llam = []
    X_salsa = []
    X_queso = []
    X_pepp = []
    X_carnes = []
    X_horno = []
    X_embal = []
    X_desp = []
    X_inter = []
    X_prem = []

    # --------------------------------------------------------------
    # 1) Generación de réplicas (con o sin antitéticas)
    # --------------------------------------------------------------
    if usar_antiteticas:
        if n_replicas % 2 != 0:
            raise ValueError("Con antitéticas, n_replicas debe ser par.")
        n_pares = n_replicas // 2

        utils_1 = []
        utils_2 = []

        for i in range(n_pares):
            rng_U = np.random.default_rng(123456 + i)
            U_inter = rng_U.uniform(0, 1, n_uniformes_inter)

            seed_global = 900000 + i

            # réplica 1
            env1 = sp.Environment()
            p1 = Pizzeria(env1)
            p1.iniciar_simulacion(
                tiempo_horas,
                seed=seed_global,
                logs=False,
                usar_antiteticas=True,
                uniformes_interarrival=U_inter,
            )
            met1 = p1.obtener_metricas()

            # réplica 2 (antitética)
            env2 = sp.Environment()
            p2 = Pizzeria(env2)
            p2.iniciar_simulacion(
                tiempo_horas,
                seed=seed_global,
                logs=False,
                usar_antiteticas=True,
                uniformes_interarrival=1 - U_inter,
            )
            met2 = p2.obtener_metricas()

            util1 = met1["Utilidad"]
            util2 = met2["Utilidad"]
            utils_1.append(util1)
            utils_2.append(util2)

            # Estimador antitético por par
            Y_par = 0.5 * (util1 + util2)
            Y.append(Y_par)

            # Promedio por par de variables de control
            X_pizzas.append(0.5 * (met1["Total Pizzas"] + met2["Total Pizzas"]))

            X_llam.append(0.5 * (met1["Tiempo Promedio Llamada"] + met2["Tiempo Promedio Llamada"]))
            X_salsa.append(0.5 * (met1["Tiempo Promedio Salsa"] + met2["Tiempo Promedio Salsa"]))
            X_queso.append(0.5 * (met1["Tiempo Promedio Queso"] + met2["Tiempo Promedio Queso"]))
            X_pepp.append(0.5 * (met1["Tiempo Promedio Pepperoni"] + met2["Tiempo Promedio Pepperoni"]))
            X_carnes.append(0.5 * (met1["Tiempo Promedio Carnes"] + met2["Tiempo Promedio Carnes"]))
            X_horno.append(0.5 * (met1["Tiempo Promedio Coccion"] + met2["Tiempo Promedio Coccion"]))
            X_embal.append(0.5 * (met1["Tiempo Promedio Embalaje"] + met2["Tiempo Promedio Embalaje"]))
            X_desp.append(0.5 * (met1["Tiempo Promedio Despacho"] + met2["Tiempo Promedio Despacho"]))
            X_inter.append(0.5 * (met1["Tiempo Promedio Entre Llamadas"] + met2["Tiempo Promedio Entre Llamadas"]))
            X_prem.append(0.5 * (met1["Proporcion Premium"] + met2["Proporcion Premium"]))

        n_eff = n_pares  # número de estimadores Y (uno por par)

        rho_par = np.corrcoef(utils_1, utils_2)[0, 1]
        print("\n===== DIAGNÓSTICO ANTITÉTICAS =====")
        print(f"Número de pares           = {n_pares}")
        print(f"Correlación utilidad par  = {rho_par:.4f}")
        print("===================================\n")

    else:
        # Réplicas independientes (sin antitéticas)
        for i in range(n_replicas):
            env = sp.Environment()
            p = Pizzeria(env)
            p.iniciar_simulacion(tiempo_horas, seed=i, logs=False, usar_antiteticas=False)
            met = p.obtener_metricas()

            Y.append(met["Utilidad"])
            X_pizzas.append(met["Total Pizzas"])

            X_llam.append(met["Tiempo Promedio Llamada"])
            X_salsa.append(met["Tiempo Promedio Salsa"])
            X_queso.append(met["Tiempo Promedio Queso"])
            X_pepp.append(met["Tiempo Promedio Pepperoni"])
            X_carnes.append(met["Tiempo Promedio Carnes"])
            X_horno.append(met["Tiempo Promedio Coccion"])
            X_embal.append(met["Tiempo Promedio Embalaje"])
            X_desp.append(met["Tiempo Promedio Despacho"])
            X_inter.append(met["Tiempo Promedio Entre Llamadas"])
            X_prem.append(met["Proporcion Premium"])

        n_eff = n_replicas  # número de estimadores Y (uno por réplica)

    # Pasamos a arrays numpy
    Y        = np.array(Y,        dtype=float)
    X_pizzas = np.array(X_pizzas, dtype=float)
    X_llam   = np.array(X_llam,   dtype=float)
    X_salsa  = np.array(X_salsa,  dtype=float)
    X_queso  = np.array(X_queso,  dtype=float)
    X_pepp   = np.array(X_pepp,   dtype=float)
    X_carnes = np.array(X_carnes, dtype=float)
    X_horno  = np.array(X_horno,  dtype=float)
    X_embal  = np.array(X_embal,  dtype=float)
    X_desp   = np.array(X_desp,   dtype=float)
    X_inter  = np.array(X_inter,  dtype=float)
    X_prem   = np.array(X_prem,   dtype=float)

    # Estadísticos base sobre TODOS los Y (se usan cuando no hay VC)
    media_simple_all = np.mean(Y)
    s2_simple_all    = np.var(Y, ddof=1)
    var_simple_all   = s2_simple_all / n_eff
    sd_simple_all    = math.sqrt(var_simple_all)

    # --------------------------------------------------------------
    # 2) Caso SIN VC: devolvemos directamente estadísticos base
    # --------------------------------------------------------------
    if not usar_vc:
        # (Opcional: imprimir solo si quieres)
        if not usar_antiteticas:
            print("===== RESULTADOS BASE (sobre estimadores actuales) =====")
            print(f"Número de estimadores      = {n_eff}")
            print(f"Media estimador utilidad   = {media_simple_all:,.2f}")
            print(f"s^2 (base)                 = {s2_simple_all:,.2f}")
            print(f"Varianza del estimador     = {var_simple_all:,.2f}")
            print(f"Desviación estándar        = {sd_simple_all:,.2f}")
            print("========================================================\n")

        return {
            "media": media_simple_all,   # media de Y
            "s2": s2_simple_all,         # varianza muestral de Y
            "varianza": var_simple_all,  # varianza del estimador
            "std": sd_simple_all,
            "n_eff": n_eff,
        }

    # --------------------------------------------------------------
    # 3) CASO CON VC: usamos SOLO Total Pizzas como VC
    # --------------------------------------------------------------
    # Matriz X con una sola VC
    X = X_pizzas.reshape(-1, 1)

    # Medias teóricas de las VC (vector largo, ya calculado)
    E_X_full = medias_teoricas_VC(Pizzeria(sp.Environment()))
    # Índice 0: Total Pizzas
    E_X = np.array([E_X_full[0]])

    # ---------- División Calibración / Estimación ----------
    n_calib = max(1, n_eff // 5)   # 1/5 para calibrar β
    n_estim = n_eff - n_calib      # 4/5 para estimar la media

    if n_estim < 2:
        n_calib = 0
        n_estim = n_eff

    # Partición
    X_calib = X[:n_calib, :] if n_calib > 0 else None
    Y_calib = Y[:n_calib]     if n_calib > 0 else None

    X_estim = X[n_calib:, :]
    Y_estim = Y[n_calib:]

    # ---------- Cálculo de β usando SOLO CALIBRACIÓN ----------
    if n_calib > 0:
        Xc_calib = X_calib - E_X      # centrado con medias teóricas
        Yc_calib = Y_calib - np.mean(Y_calib)
        beta, *_ = np.linalg.lstsq(Xc_calib, Yc_calib, rcond=None)
    else:
        beta = np.zeros(X.shape[1])

    # ---------- Aplicación de VC sobre réplicas de ESTIMACIÓN ----------
    Xc_estim = X_estim - E_X
    Y_control = Y_estim - Xc_estim @ beta

    # Estadísticos base y con VC usando SOLO ESTIMACIÓN
    media_simple_est = np.mean(Y_estim)
    s2_simple_est    = np.var(Y_estim, ddof=1)
    var_simple_est   = s2_simple_est / n_estim
    sd_simple_est    = math.sqrt(var_simple_est)

    media_control = np.mean(Y_control)
    s2_control    = np.var(Y_control, ddof=1)
    var_control   = s2_control / n_estim
    sd_control    = math.sqrt(var_control)

    # --------------------------------------------------------------
    # Diagnóstico VC (1 variable)
    # --------------------------------------------------------------
    print("\n===== VARIABLES DE CONTROL (1 VARIABLE) =====\n")
    print(f"Número total de estimadores   = {n_eff}")
    print(f"  Réplicas de calibración     = {n_calib}")
    print(f"  Réplicas de estimación      = {n_estim}\n")

    nombres_vc = ["Total Pizzas"]

    if n_calib > 1:
        print("Correlación con la utilidad (CALIBRACIÓN):")
        print("-------------------------------------------------------------")
        Xj = X_calib[:, 0]
        rho = np.corrcoef(Y_calib, Xj)[0, 1]
        print(f"{nombres_vc[0]:30s}  ρ = {rho: .4f}")
        print("-------------------------------------------------------------\n")
    else:
        print("No hay suficientes réplicas de calibración para correlaciones.\n")

    print("Medias teóricas usadas (E[Xj]):")
    print("-------------------------------------------------------------")
    print(f"{nombres_vc[0]:30s}  E[X] = {E_X[0]: .4f}")
    print("-------------------------------------------------------------\n")

    print("Coeficientes β (calculados con CALIBRACIÓN):")
    print("-------------------------------------------------------------")
    print(f"{nombres_vc[0]:30s}  β = {beta[0]: .4f}")
    print("-------------------------------------------------------------\n")

    print("RESULTADOS (solo réplicas de ESTIMACIÓN):")
    print("-------------------------------------------------------------")
    print(f"  Media simple (sin VC)       = {media_simple_est:,.2f}")
    print(f"  s^2 simple                  = {s2_simple_est:,.2f}")
    print(f"  Varianza simple             = {var_simple_est:,.2f}")
    print(f"  Desviación estándar simple  = {sd_simple_est:,.2f}\n")

    print("RESULTADOS CON VARIABLES DE CONTROL (1 VC):")
    print("-------------------------------------------------------------")
    print(f"  Media ajustada              = {media_control:,.2f}")
    print(f"  s^2 ajustada                = {s2_control:,.2f}")
    print(f"  Varianza ajustada           = {var_control:,.2f}")
    print(f"  Desviación estándar ajustada= {sd_control:,.2f}\n")

    if var_simple_est > 0 and var_control > 0:
        reduccion = (var_simple_est - var_control) / var_simple_est * 100
        factor = var_simple_est / var_control
        print(f"  ✓ Reducción de varianza      = {reduccion:.2f}%")
        print(f"  ✓ Factor de reducción        = {factor:.2f}x")
    print("==============================================================\n")

    return {
        # Estimador simple (sin VC), usando SOLO ESTIMACIÓN
        "media_simple": media_simple_est,
        "s2_simple": s2_simple_est,
        "var_simple": var_simple_est,
        "sd_simple": sd_simple_est,

        # Estimador con VC
        "media_control": media_control,
        "s2_control": s2_control,
        "var_control": var_control,
        "sd_control": sd_control,

        "beta": beta,
        "n_eff": n_eff,      # total de estimadores Y
        "n_calib": n_calib,
        "n_estim": n_estim,  # estimadores usados en VC
    }

# ======================================================================
# MAIN: resumen global para N = 50, 100, 200
# ======================================================================

if __name__ == "__main__":
    TIEMPO = 168          # 1 semana
    Ns = [50, 100, 200]   # diferentes números de réplicas totales

    # Guardamos todos los resultados en una lista de diccionarios
    resumen = []

    for N in Ns:
        # ---------------------------------------------------------
        # 1) CASO BASE (sin antitéticas, sin VC)
        # ---------------------------------------------------------
        base = replicas_mixto(
            n_replicas=N,
            tiempo_horas=TIEMPO,
            usar_antiteticas=False,
            usar_vc=False
        )

        media_base = base["media"]
        s2_base    = base["s2"]
        var_base   = base["varianza"]
        n_eff_base = base["n_eff"]   # debería ser N

        resumen.append({
            "N": N,
            "Metodo": "Base",
            "n_eff": n_eff_base,
            "Media": media_base,
            "s2": s2_base,
            "Var_est": var_base,
            "Base_s2_mismo_neff": s2_base,
            "Base_Var_mismo_neff": var_base,
            "Red_vs_ref": 0.0,          # por definición
            "Red_vs_base": 0.0,         # por definición
            "Referencia": "—"
        })

        # ---------------------------------------------------------
        # 2) SOLO VARIABLES DE CONTROL (sin antitéticas)
        #    Comparación vs base con el mismo n_eff (n_estim)
        # ---------------------------------------------------------
        vc_solo = replicas_mixto(
            n_replicas=N,
            tiempo_horas=TIEMPO,
            usar_antiteticas=False,
            usar_vc=True
        )

        media_vc = vc_solo["media_control"]
        s2_vc    = vc_solo["s2_control"]
        var_vc   = vc_solo["var_control"]
        n_eff_vc = vc_solo["n_estim"]      # réplicas efectivas usadas en el estimador

        # Base "justo" interno: estos vienen del estimador simple con mismo n_eff
        s2_base_vc  = vc_solo["s2_simple"]
        var_base_vc = vc_solo["var_simple"]
        reduccion_vc = (var_base_vc - var_vc) / var_base_vc * 100

        resumen.append({
            "N": N,
            "Metodo": "VC",
            "n_eff": n_eff_vc,
            "Media": media_vc,
            "s2": s2_vc,
            "Var_est": var_vc,
            "Base_s2_mismo_neff": s2_base_vc,
            "Base_Var_mismo_neff": var_base_vc,
            "Red_vs_ref": reduccion_vc,     # vs Base (mismo n_eff)
            "Red_vs_base": reduccion_vc,    # aquí el ref es base, así que coincide
            "Referencia": "Base (mismo n_eff)"
        })

        # ---------------------------------------------------------
        # 3) SOLO ANTITÉTICAS
        #    Comparación vs base con el mismo n_eff = N/2
        # ---------------------------------------------------------
        anti = replicas_mixto(
            n_replicas=N,
            tiempo_horas=TIEMPO,
            usar_antiteticas=True,
            usar_vc=False
        )

        media_anti = anti["media"]
        s2_anti    = anti["s2"]
        var_anti   = anti["varianza"]
        n_eff_anti = anti["n_eff"]      # número de pares = N/2

        # Base "justo" con el mismo n_eff que antitéticas
        base_anti = replicas_mixto(
            n_replicas=n_eff_anti,
            tiempo_horas=TIEMPO,
            usar_antiteticas=False,
            usar_vc=False
        )
        s2_base_anti  = base_anti["s2"]
        var_base_anti = base_anti["varianza"]

        reduccion_anti = (var_base_anti - var_anti) / var_base_anti * 100

        resumen.append({
            "N": N,
            "Metodo": "Antitéticas",
            "n_eff": n_eff_anti,
            "Media": media_anti,
            "s2": s2_anti,
            "Var_est": var_anti,
            "Base_s2_mismo_neff": s2_base_anti,
            "Base_Var_mismo_neff": var_base_anti,
            "Red_vs_ref": reduccion_anti,    # vs Base (mismo n_eff)
            "Red_vs_base": reduccion_anti,   # referencia absoluta también es base
            "Referencia": "Base (mismo n_eff)"
        })

        # ---------------------------------------------------------
        # 4) ANTITÉTICAS + VC
        #    - Comparación incremental vs "solo antitéticas" (mismo n_eff)
        #    - Reducción TOTAL vs base con el mismo n_eff final
        # ---------------------------------------------------------
        mix = replicas_mixto(
            n_replicas=N,
            tiempo_horas=TIEMPO,
            usar_antiteticas=True,
            usar_vc=True
        )

        media_mix = mix["media_control"]
        s2_mix    = mix["s2_control"]
        var_mix   = mix["var_control"]
        n_eff_mix = mix["n_estim"]      # n_eff efectivo del estimador final

        # Reducción incremental vs Antitéticas (mismo n_eff de estimación)
        var_anti_mismo_n = mix["var_simple"]  # antitéticas sin VC, mismo n_estim
        reduccion_incremental = (var_anti_mismo_n - var_mix) / var_anti_mismo_n * 100

        # ✅ Reducción TOTAL vs Base (mismo n_eff final)
        base_mix = replicas_mixto(
            n_replicas=n_eff_mix,
            tiempo_horas=TIEMPO,
            usar_antiteticas=False,
            usar_vc=False
        )
        s2_base_mix  = base_mix["s2"]
        var_base_mix = base_mix["varianza"]

        reduccion_total = (var_base_mix - var_mix) / var_base_mix * 100

        resumen.append({
            "N": N,
            "Metodo": "Antitéticas + VC",
            "n_eff": n_eff_mix,
            "Media": media_mix,
            "s2": s2_mix,
            "Var_est": var_mix,
            "Base_s2_mismo_neff": s2_base_mix,
            "Base_Var_mismo_neff": var_base_mix,
            "Red_vs_ref": reduccion_incremental,    # vs Antitéticas
            "Red_vs_base": reduccion_total,         # vs Base (mismo n_eff final)
            "Referencia": "Ref: Anti(mismo n_eff), Base(mismo n_eff)"
        })

    # -----------------------------------------------------------------
    # IMPRESIÓN DEL RESUMEN GLOBAL
    # -----------------------------------------------------------------
    print("\n==================== RESUMEN GLOBAL ====================\n")

    for N in Ns:
        print(f"\n-------------------- N = {N} --------------------")
        print(
            f"{'Método':18s} "
            f"{'n_eff':>7s} "
            f"{'Media':>13s} "
            f"{'s^2':>13s} "
            f"{'Var(est)':>13s} "
            f"{'Base s^2':>13s} "
            f"{'Base Var':>13s} "
            f"{'Red.Ref%':>9s} "
            f"{'Red.Base%':>10s}  Ref"
        )
        print("-" * 140)
        for row in resumen:
            if row["N"] == N:
                print(
                    f"{row['Metodo']:18s} "
                    f"{row['n_eff']:7d} "
                    f"{row['Media']:13,.2f} "
                    f"{row['s2']:13,.2f} "
                    f"{row['Var_est']:13,.2f} "
                    f"{row['Base_s2_mismo_neff']:13,.2f} "
                    f"{row['Base_Var_mismo_neff']:13,.2f} "
                    f"{row['Red_vs_ref']:9.2f} "
                    f"{row['Red_vs_base']:10.2f}  "
                    f"{row['Referencia']}"
                )
        print("-" * 140)

    print("\n========================================================\n")

    # -----------------------------------------------------------------
    # EXPORTAR A CSV
    # -----------------------------------------------------------------
    csv_filename = "resumen_resultados_parte2.csv"
    fieldnames = [
        "N",
        "Metodo",
        "n_eff",
        "Media",
        "s2",
        "Var_est",
        "Base_s2_mismo_neff",
        "Base_Var_mismo_neff",
        "Red_vs_ref",
        "Red_vs_base",
        "Referencia",
    ]

    with open(csv_filename, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in resumen:
            writer.writerow(row)

    print(f"Resumen exportado a '{csv_filename}'\n")

