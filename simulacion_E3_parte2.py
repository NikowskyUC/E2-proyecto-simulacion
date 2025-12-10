import numpy as np
import simpy as sp
import math

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
            10: 2,
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
            21: 4,
        }

        self.tasas_finde = {
            10: 2,
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
            23: 4,
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
      - usar_vc: aplica variables de control (Total Pizzas, tiempo cocción, tiempo despacho)
    Si usar_antiteticas=True, n_replicas debe ser PAR (trabajamos por pares).
    """

    # Valores esperados teóricos de las VC (mismo que en tu código de VC)
    E_pizzas = 1589
    E_tiempo_coccion = 12.43
    E_tiempo_despacho = 6.75

    Y = []   # utilidades (o estimador antitético por par)

    # VC1: Total de pizzas
    X_pizzas = []

    # VC2–VC8: tiempos promedio de procesos (en minutos)
    X_llam = []      # Tiempo Promedio Llamada
    X_salsa = []     # Tiempo Promedio Salsa
    X_queso = []     # Tiempo Promedio Queso
    X_pepp = []      # Tiempo Promedio Pepperoni
    X_carnes = []    # Tiempo Promedio Carnes
    X_horno = []     # Tiempo Promedio Coccion
    X_embal = []     # Tiempo Promedio Embalaje
    X_desp = []      # Tiempo Promedio Despacho

    # VC9: tiempo promedio entre llamadas (en horas)
    X_inter = []     # Tiempo Promedio Entre Llamadas

    # VC10: proporción de pedidos premium
    X_prem = []      # Proporcion Premium


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

            # Promedio por par de CADA variable de control
            X_pizzas.append(
                0.5 * (met1["Total Pizzas"] + met2["Total Pizzas"])
            )

            X_llam.append(
                0.5 * (met1["Tiempo Promedio Llamada"] + met2["Tiempo Promedio Llamada"])
            )
            X_salsa.append(
                0.5 * (met1["Tiempo Promedio Salsa"] + met2["Tiempo Promedio Salsa"])
            )
            X_queso.append(
                0.5 * (met1["Tiempo Promedio Queso"] + met2["Tiempo Promedio Queso"])
            )
            X_pepp.append(
                0.5 * (met1["Tiempo Promedio Pepperoni"] + met2["Tiempo Promedio Pepperoni"])
            )
            X_carnes.append(
                0.5 * (met1["Tiempo Promedio Carnes"] + met2["Tiempo Promedio Carnes"])
            )
            X_horno.append(
                0.5 * (met1["Tiempo Promedio Coccion"] + met2["Tiempo Promedio Coccion"])
            )
            X_embal.append(
                0.5 * (met1["Tiempo Promedio Embalaje"] + met2["Tiempo Promedio Embalaje"])
            )
            X_desp.append(
                0.5 * (met1["Tiempo Promedio Despacho"] + met2["Tiempo Promedio Despacho"])
            )

            X_inter.append(
                0.5 * (met1["Tiempo Promedio Entre Llamadas"] + met2["Tiempo Promedio Entre Llamadas"])
            )

            X_prem.append(
                0.5 * (met1["Proporcion Premium"] + met2["Proporcion Premium"])
            )


        n_eff = n_pares

        rho_par = np.corrcoef(utils_1, utils_2)[0, 1]
        print("\n===== DIAGNÓSTICO ANTITÉTICAS =====")
        print(f"Número de pares           = {n_pares}")
        print(f"Correlación utilidad par  = {rho_par:.4f}")
        print("===================================\n")

    else:
        # Réplicas independientes
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


        n_eff = n_replicas

    Y = np.array(Y, dtype=float)

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


    # Caso base (sin VC) sobre estos estimadores (ya sea simples o antitéticos)
    media_simple = np.mean(Y)
    var_simple = np.var(Y, ddof=1) / n_eff
    sd_simple = math.sqrt(var_simple)

    if not usar_vc and not usar_antiteticas:
        print("===== RESULTADOS BASE (sobre estimadores actuales) =====")
        print(f"Número de estimadores      = {n_eff}")
        print(f"Media estimador utilidad   = {media_simple:,.2f}")
        print(f"Varianza del estimador    = {var_simple:,.2f}")
        print(f"Desviación estándar       = {sd_simple:,.2f}")
        print("========================================================\n")

    if not usar_vc:
        return {
            "media": media_simple,
            "varianza": var_simple,
            "std": sd_simple,
            "n_eff": n_eff,
        }

    # --------------------------------------------------------------
    # Variables de control con regresión múltiple
    # --------------------------------------------------------------
        # Matriz de variables de control (11 en total)
    # 1) Total Pizzas
    # 2–8) Tiempos promedio de procesos (min)
    # 9) Tiempo promedio entre llamadas (horas)
    # 10) Proporción premium
    X = np.column_stack([
        X_pizzas,  # VC1
        X_llam,    # VC2
        X_salsa,   # VC3
        X_queso,   # VC4
        X_pepp,    # VC5
        X_carnes,  # VC6
        X_horno,   # VC7
        X_embal,   # VC8
        X_desp,    # VC9
        X_inter,   # VC10
        X_prem,    # VC11
    ])

    # Medias teóricas de las VC (en mismas unidades que las métricas)
    E_llamada = 2.0        # Gamma(4,0.5) minutos
    E_salsa   = 5.0 / 7.2  # Beta(5,2.2) minutos ≈ 0.6944
    E_queso   = (0.9 + 1 + 1.2) / 3          # Triangular(0.9,1,1.2) ≈ 1.0333 min
    E_pepp    = math.exp(0.5 + 0.25**2 / 2)  # Lognormal(0.5,0.25) ≈ 1.70 min
    E_carnes  = (1 + 1.8) / 2                # Uniform(1,1.8) = 1.4 min
    E_horno   = math.exp(2.5 + 0.2**2 / 2)   # Lognormal(2.5,0.2) ≈ 12.43 min
    E_embal   = (1.1 + 2 + 2.3) / 3          # Triangular(1.1,2,2.3) = 1.8 min
    E_desp    = 7.5 * 0.9                    # Gamma(7.5,0.9) = 6.75 min

    # E[X_inter]: tiempo entre llamadas promedio (en horas)
    E_inter   = 0.1430   # mismo valor que usaste en el código ortogonal

    # E[X_prem]: proporción de pedidos premium
    E_prem    = 3.0 / 20.0   # = 0.15

    E_X = np.array([
        E_pizzas,     # Total Pizzas
        E_llamada,    # Tiempo Promedio Llamada (min)
        E_salsa,      # Tiempo Promedio Salsa (min)
        E_queso,      # Tiempo Promedio Queso (min)
        E_pepp,       # Tiempo Promedio Pepperoni (min)
        E_carnes,     # Tiempo Promedio Carnes (min)
        E_horno,      # Tiempo Promedio Coccion (min)
        E_embal,      # Tiempo Promedio Embalaje (min)
        E_desp,       # Tiempo Promedio Despacho (min)
        E_inter,      # Tiempo Promedio Entre Llamadas (horas)
        E_prem,       # Proporcion Premium
    ], dtype=float)


    X_centered = X - E_X
    Y_centered = Y - np.mean(Y)

    beta, *_ = np.linalg.lstsq(X_centered, Y_centered, rcond=None)

    Y_control = Y - X_centered @ beta
    media_control = np.mean(Y_control)
    var_control = np.var(Y_control, ddof=1) / n_eff
    sd_control = math.sqrt(var_control)

    # ==============================================================
    # DIAGNÓSTICO DE VARIABLES DE CONTROL (para 11 VC)
    # ==============================================================

    print("\n===== VARIABLES DE CONTROL (MÚLTIPLES, 11 VARIABLES) =====\n")

    nombres_vc = [
        "Total Pizzas",
        "Tiempo Llamada (min)",
        "Tiempo Salsa (min)",
        "Tiempo Queso (min)",
        "Tiempo Pepperoni (min)",
        "Tiempo Carnes (min)",
        "Tiempo Cocción (min)",
        "Tiempo Embalaje (min)",
        "Tiempo Despacho (min)",
        "Tiempo Entre Llamadas (hrs)",
        "Proporción Premium",
    ]

    # Calcular correlaciones con Y
    corr_list = []
    all_X_arrays = [
        X_pizzas, X_llam, X_salsa, X_queso, X_pepp, X_carnes,
        X_horno, X_embal, X_desp, X_inter, X_prem
    ]

    print("Correlaciones con la utilidad (estimadores Y):")
    print("-------------------------------------------------------------")
    for name, Xj in zip(nombres_vc, all_X_arrays):
        rho = np.corrcoef(Y, Xj)[0, 1]
        corr_list.append(rho)
        print(f"{name:30s}  ρ = {rho: .4f}")
    print("-------------------------------------------------------------\n")

    # Mostrar medios teóricos y betas
    print("Medias teóricas usadas (E[Xj]):")
    print("-------------------------------------------------------------")
    for name, Ej in zip(nombres_vc, E_X):
        print(f"{name:30s}  E[X] = {Ej: .4f}")
    print("-------------------------------------------------------------\n")

    print("Coeficientes β óptimos (regresión múltiple):")
    print("-------------------------------------------------------------")
    for name, bj in zip(nombres_vc, beta):
        print(f"{name:30s}  β = {bj: .4f}")
    print("-------------------------------------------------------------\n")

    # ===================== RESULTADOS FINALES =====================
    print("RESULTADOS CON VARIABLES DE CONTROL (11 VC):")
    print("-------------------------------------------------------------")
    print(f"  Media estimador utilidad     = {media_control:,.2f}")
    print(f"  Varianza del estimador       = {var_control:,.2f}")
    print(f"  Desviación estándar          = {sd_control:,.2f}\n")

    if var_simple > 0 and var_control > 0:
        reduccion = (var_simple - var_control) / var_simple * 100
        factor = var_simple / var_control
        print(f"  ✓ Reducción de varianza      = {reduccion:.2f}%")
        print(f"  ✓ Factor de reducción        = {factor:.2f}x")
    print("==============================================================\n")


    return {
        "media_simple": media_simple,
        "var_simple": var_simple,
        "sd_simple": sd_simple,
        "media_control": media_control,
        "var_control": var_control,
        "sd_control": sd_control,
        "beta": beta,
        "n_eff": n_eff,
    }

if __name__ == "__main__":
    TIEMPO = 168        # 1 semana
    N = 100             # número de réplicas
    print("\n======================================================")
    print("EJECUTANDO COMPARACIÓN COMPLETA DE MÉTODOS")
    print("======================================================\n")

    # ---------------------------------------------------------
    # 1) CASO BASE (sin antitéticas, sin VC)
    # ---------------------------------------------------------
    print("\n### CASO BASE ###\n")
    base = replicas_mixto(
        n_replicas=N,
        tiempo_horas=TIEMPO,
        usar_antiteticas=False,
        usar_vc=False
    )

    media_base = base["media"]
    var_base = base["varianza"]
    sd_base = base["std"]

    print(f"Media caso base       = {media_base:,.2f}")
    print(f"Varianza caso base    = {var_base:,.2f}")
    print(f"Desv. estándar base   = {sd_base:,.2f}")
    print("------------------------------------------------------\n")

    # ---------------------------------------------------------
    # 2) SOLO VC (múltiples variables de control)
    # ---------------------------------------------------------
    print("\n### SOLO VARIABLES DE CONTROL (sin antitéticas) ###\n")
    vc_solo = replicas_mixto(
        n_replicas=N,
        tiempo_horas=TIEMPO,
        usar_antiteticas=False,
        usar_vc=True
    )

    media_vc = vc_solo["media_control"]
    var_vc = vc_solo["var_control"]

    print(f"Media VC              = {media_vc:,.2f}")
    print(f"Varianza VC           = {var_vc:,.2f}")
    print(f"Reducción vs base     = {(var_base - var_vc) / var_base * 100:,.2f}%")
    print("------------------------------------------------------\n")

    # ---------------------------------------------------------
    # 3) SOLO ANTITÉTICAS
    # ---------------------------------------------------------
    print("\n### SOLO ANTITÉTICAS ###\n")
    anti = replicas_mixto(
        n_replicas=N,
        tiempo_horas=TIEMPO,
        usar_antiteticas=True,
        usar_vc=False
    )

    media_anti = anti["media"]
    var_anti = anti["varianza"]

    print(f"Media Antitéticas     = {media_anti:,.2f}")
    print(f"Varianza Antitéticas  = {var_anti:,.2f}")
    print(f"Reducción vs base     = {(var_base - var_anti) / var_base * 100:,.2f}%")
    print("------------------------------------------------------\n")

    # ---------------------------------------------------------
    # 4) ANTITÉTICAS + MULTI VC
    # ---------------------------------------------------------
    print("\n### ANTITÉTICAS + MULTI VC ###\n")
    mix = replicas_mixto(
        n_replicas=N,
        tiempo_horas=TIEMPO,
        usar_antiteticas=True,
        usar_vc=True
    )

    media_mix = mix["media_control"]
    var_mix = mix["var_control"]

    print(f"Media Mixto           = {media_mix:,.2f}")
    print(f"Varianza Mixto        = {var_mix:,.2f}")
    print(f"Reducción vs base     = {(var_base - var_mix) / var_base * 100:,.2f}%")
    print("------------------------------------------------------\n")

    # ---------------------------------------------------------
    # RESUMEN FINAL
    # ---------------------------------------------------------
    print("\n================= RESUMEN FINAL =================")
    print(f"Base:                Var = {var_base:,.2f}")
    print(f"VC solo:             Var = {var_vc:,.2f}   ({(var_base - var_vc)/var_base*100:,.2f}% ↓)")
    print(f"Antitéticas:         Var = {var_anti:,.2f} ({(var_base - var_anti)/var_base*100:,.2f}% ↓)")
    print(f"Antitéticas + VC:    Var = {var_mix:,.2f}  ({(var_base - var_mix)/var_base*100:,.2f}% ↓)")
    print("=====================================================\n")


