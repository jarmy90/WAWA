"""Bibliotecas del Business Discovery Engine (iteración 004).

Territorios de búsqueda, lentes de innovación y arquetipos de negocio.
Son **espacios para explorar**, nunca afirmaciones de demanda. Cada entrada
es configurable: basta editar estas estructuras o reemplazarlas por una
versión cargada desde configuración en el futuro.

Convención: ``key`` en mayúsculas para lentes/arquetipos y snake_case para
territorios; ``name`` en español (idioma del proyecto).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Territory:
    key: str
    name: str
    description: str
    why_now: str = ""


@dataclass(frozen=True)
class InnovationLens:
    key: str
    name: str
    mechanism: str  # qué hace la lente
    example_prompt: str = ""


@dataclass(frozen=True)
class BusinessArchetype:
    key: str
    name: str
    description: str
    revenue_model: str = ""
    avoid_bias: str = ""  # sesgo de generación a evitar


# ---------------------------------------------------------------------------
# Territorios de búsqueda (31)
# ---------------------------------------------------------------------------
TERRITORIES: tuple[Territory, ...] = (
    Territory("new_human_behaviors", "Nuevos comportamientos humanos", "Comportamientos que están apareciendo o cambiando (trabajo híbrido, creación de contenido, uso de IA) y crean necesidades que antes no existían.", "La IA está cambiando cómo la gente trabaja, estudia y decide: cada cambio nuevo es un territorio sin dueño."),
    Territory("invisible_admin_work", "Trabajo invisible y administrativo", "Horas que los profesionales pierden en papeleo, coordinación, seguimiento y gestión que nadie ve ni factura.", "Las herramientas generalistas resuelven la escritura, no el papeleo de contexto; el trabajo invisible sigue manual."),
    Territory("app_misalignment", "Descoordinación entre aplicaciones", "Datos que viven en herramientas distintas y obligan a copiar, pegar y reconciliar a mano entre ellas.", "Cada empresa usa más SaaS; la descoordinación crece más rápido que las integraciones nativas."),
    Territory("hard_to_verify_info", "Información difícil de verificar", "Afirmaciones, certificados, CVs, reseñas o historiales que son caros o imposibles de comprobar con los medios actuales.", "La IA facilita fabricar contenido creíble; verificar se vuelve más valioso que producir."),
    Territory("high_uncertainty_decisions", "Decisiones con alta incertidumbre", "Decisiones caras donde la gente improvisa por falta de datos o de método.", "Hay más datos que nunca, pero siguen sin llegar a quien decide en el momento."),
    Territory("fragmented_markets", "Mercados fragmentados", "Demanda repartida entre muchos oferentes pequeños sin marca ni curaduría.", "Internet no ha consolidado estos mercados; la curaduría y el estándar siguen sin existir."),
    Territory("underused_assets", "Activos infrautilizados", "Activos ociosos (espacios, equipos, tiempo, datos) que generan cero mientras alguien podría pagar por usarlos.", "El coste de coordinar el uso compartido sigue bajando con software y reputación digital."),
    Territory("strong_identity_communities", "Comunidades con identidad fuerte", "Grupos con lenguaje, normas y necesidades propias que el software genérico ignora.", "Las comunidades de nicho crecen en internet; su software sigue siendo genérico."),
    Territory("expensive_slow_services", "Servicios caros y lentos", "Servicios profesionales donde la espera o el precio excluyen a la mayoría de clientes potenciales.", "Una parte del trabajo de estos servicios es repetible y puede estandarizarse sin sustituir al profesional."),
    Territory("opaque_intermediaries", "Intermediarios opacos", "Cadenas donde el cliente no sabe qué paga ni quién hace realmente el trabajo.", "La trazabilidad digital permite quitar la opacidad sin quitar el intermediario útil."),
    Territory("untapped_public_data", "Datos públicos desaprovechados", "Datos abiertos o públicos que nadie ha convertido en decisión útil para un colectivo concreto.", "El coste de procesar y presentar datos públicos ha caído; la demanda de contexto sigue sin cubrirse."),
    Territory("regulatory_change", "Cambios regulatorios", "Normas nuevas que obligan a empresas y personas a adaptarse rápido y en plazo.", "Cada cambio regulatorio crea una ventana temporal de cumplimiento y confusión."),
    Territory("aging", "Envejecimiento", "Necesidades de personas mayores y de quienes las cuidan (familiares y profesionales).", "La demografía envejece en casi todos los mercados desarrollados; la oferta específica es escasa."),
    Territory("education", "Educación", "Aprender, evaluar y acreditar habilidades fuera de los caminos formales.", "El empleo por habilidades convive con títulos lentos y caros; la verificación práctica queda vacante."),
    Territory("home", "Hogar", "Gestión doméstica: mantenimiento, presupuesto, papeleo, compras recurrentes.", "El hogar sigue siendo el mayor mercado sin automatizar porque nadie lo estandariza."),
    Territory("small_businesses", "Pequeños negocios", "Necesidades operativas de negocios de 1-10 empleados sin equipo de soporte.", "Las herramientas empresariales están pensadas para empresas grandes; el pequeño negocio improvisa."),
    Territory("creators", "Creadores", "Quienes producen contenido, cursos o comunidades y necesitan gestión, distribución y cobro.", "El creador es ahora una pyme de una persona con necesidades de empresa reales."),
    Territory("freelancers", "Autónomos", "Profesionales independientes que facturan, cotizan, persiguen pagos y venden su tiempo.", "El autónomo asume costes de empresa sin herramientas de empresa; la IA añade competencia, no gestión."),
    Territory("real_estate", "Inmobiliario", "Compra, alquiler, mantenimiento y gestión de propiedades por propietarios pequeños.", "El propietario pequeño compite con profesionales con software; la información asimétrica es enorme."),
    Territory("tourism", "Turismo", "Viajes, experiencias y alojamientos; coordinación entre visitantes y locales.", "El viajero quiere experiencias reales y verificadas; los intermediarios actuales están estandarizados."),
    Territory("amateur_sports", "Deporte amateur", "Organización, medición y motivación del deporte no profesional.", "El deportista amateur tiene los datos de los profesionales pero sin entrenador ni tiempo."),
    Territory("local_logistics", "Logística local", "Entregas, reparto y coordinación de última milla en zonas concretas.", "El comercio local necesita logística barata que las grandes redes no cubren."),
    Territory("sustainability_with_incentive", "Sostenibilidad con incentivo económico", "Comportamientos sostenibles que además ahorran o generan dinero.", "La sostenibilidad sin incentivo no se adopta; la que ahorra sí."),
    Territory("digital_trust", "Confianza digital", "Señales de confianza entre desconocidos que negocian online.", "La economía online crece más rápido que los mecanismos de confianza."),
    Territory("fraud_verification", "Fraude y verificación", "Detectar y prevenir fraude, falsificaciones y suplantación en transacciones y documentos.", "La IA abarata el fraude; la verificación automatizada se convierte en necesidad."),
    Territory("loneliness_social_coordination", "Soledad y coordinación social no romántica", "Coordinación de personas que quieren hacer cosas juntas sin plataformas de citas.", "El trabajo remoto y la ciudad dispersan los vínculos; la coordinación local está rota."),
    Territory("new_ai_interfaces", "Nuevas interfaces de IA", "Formas de interactuar con IA que no son un chat: voz, cámara, contexto, agentes.", "El chat es la interfaz más pobre; las interfaces contextuales crean productos nuevos."),
    Territory("agent_services", "Agentes que necesitan servicios de otros agentes", "Servicios que un agente de IA contrataría a otro agente (verificación, ejecución, pagos).", "Los agentes automatizan decisiones; necesitarán verificación y ejecución confiable entre ellos."),
    Territory("machine_economy", "Economía de máquinas", "Transacciones y servicios que ocurren entre máquinas sin intervención humana.", "Sensores y automatización generan decisiones que nadie revisa: la verificación entre máquinas falta."),
    Territory("pay_for_outcome_markets", "Mercados donde pagar por resultado sea posible", "Servicios donde el pago puede vincularse al resultado medible en vez de al tiempo.", "La medición digital permite trasladar el riesgo al oferente; casi nadie lo hace."),
    Territory("ai_proliferation_problems", "Problemas surgidos por la proliferación de IA", "Nuevos problemas que la propia IA crea: contaminación de información, dependencia, verificación de salidas.", "Cuanto más IA se publique, más valdrá saber qué es real, quién lo hizo y si es fiable."),
)


# ---------------------------------------------------------------------------
# Lentes de innovación (30)
# ---------------------------------------------------------------------------
LENSES: tuple[InnovationLens, ...] = (
    InnovationLens("REMOVE_THE_MIDDLEMAN", "Quitar el intermediario", "Conectar directamente a quien tiene el problema con quien lo resuelve, eliminando comisiones y opacidad."),
    InnovationLens("PAY_FOR_OUTCOME", "Pagar por resultado", "El cliente paga solo cuando se produce el resultado acordado, no por el tiempo o el intento."),
    InnovationLens("REVERSE_MARKETPLACE", "Marketplace inverso", "El comprador publica su necesidad y los oferentes compiten por ella, en vez de buscar catálogo."),
    InnovationLens("LIVE_DIGITAL_TWIN", "Gemelo digital en vivo", "Una réplica digital actualizada de un activo físico que permite simular, vigilar y decidir."),
    InnovationLens("TRUST_LAYER", "Capa de confianza", "Añadir reputación, garantía o verificación a una interacción que hoy depende de la fe."),
    InnovationLens("PROOF_BEFORE_PAYMENT", "Prueba antes del pago", "Demostrar capacidad o calidad con una muestra verificable antes de que el cliente se comprometa."),
    InnovationLens("UNUSED_ASSET_TO_INCOME", "Activo ocioso a ingreso", "Convertir capacidad no utilizada (tiempo, espacio, equipo, datos) en un flujo de ingresos."),
    InnovationLens("HUMAN_PLUS_AI_SERVICE", "Servicio humano + IA", "Un profesional respaldado por IA entrega más rápido y barato; la IA sola no basta."),
    InnovationLens("AI_AGENT_INFRASTRUCTURE", "Infraestructura para agentes", "Servicios que los agentes de IA necesitan para operar: identidad, memoria, verificación, ejecución."),
    InnovationLens("COMMUNITY_AS_PRODUCT", "Comunidad como producto", "El valor es la comunidad y su coordinación, no el contenido estático."),
    InnovationLens("DATA_COOPERATIVE", "Cooperativa de datos", "Un grupo aporta datos y comparte el valor generado con ellos, en vez de regalarlos."),
    InnovationLens("AUTOMATE_THE_HANDOFF", "Automatizar el traspaso", "Automatizar el punto donde un trabajo pasa de una persona, herramienta o sistema a otro."),
    InnovationLens("TURN_COMPLIANCE_INTO_PRODUCT", "Convertir cumplimiento en producto", "Una obligación regulatoria o administrativa se convierte en un servicio que la gente paga por resolver."),
    InnovationLens("PERSONAL_MEMORY_ASSET", "Activo de memoria personal", "Un historial acumulado que mejora el servicio con cada uso y que el usuario conserva."),
    InnovationLens("MARKETPLACE_WITHOUT_LISTINGS", "Marketplace sin listados", "Emparejar oferta y demanda sin catálogo público: el sistema propone, no se navega."),
    InnovationLens("PREDICT_BEFORE_PROBLEM", "Predecir antes del problema", "Detectar el fallo o la necesidad antes de que ocurra y avisar a tiempo."),
    InnovationLens("BUNDLE_FRAGMENTED_DEMAND", "Agrupar demanda fragmentada", "Juntar compradores dispersos para que un servicio que no era viable lo sea."),
    InnovationLens("UNBUNDLE_EXPENSIVE_SERVICE", "Desempaquetar servicio caro", "Separar del servicio caro la parte barata y repetible y venderla por separado."),
    InnovationLens("SELL_SAVED_TIME", "Vender tiempo ahorrado", "El producto se vende por las horas que devuelve al cliente, no por la herramienta."),
    InnovationLens("SELL_REDUCED_RISK", "Vender riesgo reducido", "El producto se vende por la reducción de riesgo o incertidumbre que aporta."),
    InnovationLens("VERIFY_THE_OUTPUT", "Verificar la salida", "Comprobar que un resultado (de IA o humano) es correcto, trazable o completo."),
    InnovationLens("CREATE_A_NEW_RITUAL", "Crear un ritual nuevo", "Introducir una práctica recurrente que antes no existía y que el producto acompaña."),
    InnovationLens("ENTERTAINMENT_PLUS_UTILITY", "Entretenimiento + utilidad", "Una experiencia entretenida que además produce un resultado útil."),
    InnovationLens("PUBLIC_PROGRESS_LOOP", "Bucle de progreso público", "Mostrar el avance de forma pública o social para generar compromiso y distribución."),
    InnovationLens("CUSTOMER_BECOMES_DISTRIBUTION", "El cliente es la distribución", "Cada cliente trae al siguiente por el propio uso del producto (compartir, invitar, referir)."),
    InnovationLens("PRODUCT_IMPROVES_WITH_USE", "El producto mejora con el uso", "Cada uso genera datos que mejoran el servicio para ese cliente o para todos."),
    InnovationLens("SERVICE_TO_SOFTWARE_PATH", "Camino servicio → software", "Empezar como servicio manual validado y convertirse en software con cada repetición."),
    InnovationLens("MACHINE_TO_MACHINE_SERVICE", "Servicio máquina a máquina", "Un servicio entregado directamente entre sistemas, sin interfaz humana."),
    InnovationLens("LOCAL_FIRST_ADVANTAGE", "Ventaja local primero", "Construir una ventaja en un territorio geográfico pequeño donde la escala global no llega."),
    InnovationLens("TEMPORARY_MICRO_MARKET", "Micromercado temporal", "Capturar una demanda que solo existe durante una ventana corta de tiempo."),
)


# ---------------------------------------------------------------------------
# Arquetipos de negocio (27)
# ---------------------------------------------------------------------------
ARCHETYPES: tuple[BusinessArchetype, ...] = (
    BusinessArchetype("VERTICAL_SAAS", "SaaS vertical", "Software como servicio para un sector concreto, con flujo de trabajo específico.", "suscripción mensual", "evitar SaaS de productividad genérica sin flujo vertical real"),
    BusinessArchetype("SOFTWARE_ENABLED_SERVICE", "Servicio habilitado por software", "Un servicio entregado por humanos que usan software propio para ser más rápidos y baratos.", "pago por entrega", "evitar agencia manual sin software propio"),
    BusinessArchetype("MARKETPLACE", "Marketplace", "Plataforma que conecta oferta y demanda con comisión por transacción.", "comisión por transacción", "requiere cuña de liquidez; evitar marketplace sin solución al problema del huevo"),
    BusinessArchetype("REVERSE_MARKETPLACE", "Marketplace inverso", "Los compradores publican necesidades y los oferentes compiten.", "comisión por transacción", "evitar confundirlo con un simple formulario de contactos"),
    BusinessArchetype("DATA_PRODUCT", "Producto de datos", "Un dataset, índice o informe de datos procesado que alguien paga por tener.", "licencia o suscripción", "evitar dashboard genérico; el dato debe ser específico y accionable"),
    BusinessArchetype("API", "API", "Capacidad programática que otros desarrolladores o agentes integran.", "pago por uso", "evitar API sin caso de uso concreto"),
    BusinessArchetype("VERIFICATION_TOOL", "Herramienta de verificación", "Comprueba la autenticidad, calidad o trazabilidad de algo.", "pago por verificación", "evitar verificación sin estándar o sin evidencia de demanda"),
    BusinessArchetype("TRUST_PRODUCT", "Producto de confianza", "Reputación, garantías, avales o señales de fiabilidad.", "comisión o suscripción", "el trust se construye lento; no inventar efecto red"),
    BusinessArchetype("SAVINGS_PRODUCT", "Producto de ahorro", "Ayuda a gastar menos o cobrar mejor; se vende por el ahorro demostrado.", "porcentaje del ahorro o tarifa plana", "evitar prometer ahorro sin medición"),
    BusinessArchetype("COMMUNITY_PLATFORM", "Plataforma comunitaria", "Un grupo paga por pertenecer, coordinarse o acceder a lo que genera la comunidad.", "cuota de membresía", "evitar comunidad vacía sin valor de coordinación"),
    BusinessArchetype("AGENT_INFRASTRUCTURE", "Infraestructura para agentes", "Servicios que los agentes de IA contratan: identidad, memoria, verificación, ejecución.", "pago por uso", "evitar asumir que los agentes ya pagan; verificar demanda"),
    BusinessArchetype("VALIDABLE_CONCIERGE", "Concierge validable", "Servicio manual caro de probar que valida la demanda antes de automatizar.", "pago por servicio", "el objetivo es el camino a software, no quedarse en agencia"),
    BusinessArchetype("LOCAL_PRODUCT", "Producto local", "Servicio o producto con ventaja geográfica o de proximidad.", "pago por servicio o suscripción", "la ventaja local debe ser real, no cosmética"),
    BusinessArchetype("SUBSCRIPTION", "Suscripción", "Pago recurrente por un servicio continuo.", "recurrente", "evitar suscripción sin retención razonable"),
    BusinessArchetype("PAY_FOR_RESULT", "Pago por resultado", "El cliente paga solo cuando ocurre el resultado acordado.", "pago por resultado", "requiere resultado medible y honesto"),
    BusinessArchetype("TRANSACTIONAL_PRODUCT", "Producto transaccional", "Se cobra por transacción o uso puntual.", "pago por uso", "evitar transacción sin recurrencia o repetición"),
    BusinessArchetype("MICROINSURANCE_PATTERN", "Microseguro (patrón conceptual)", "Reparto de riesgo entre un grupo; SOLO como patrón de diseño: cualquier uso regulado real se bloquea.", "cuota al grupo", "cualquier aplicación regulada (seguros) queda bloqueada por compliance"),
    BusinessArchetype("PRO_TOOL", "Herramienta para profesionales", "Equipamiento para quien ejerce un oficio y cobra por él.", "licencia", "evitar herramienta sin flujo profesional real"),
    BusinessArchetype("PROSUMER_PRODUCT", "Producto prosumer", "A medio camino entre consumidor y profesional; hobby con pretensiones profesionales.", "pago único o suscripción", "el prosumer paga menos que el profesional; no inflar precio"),
    BusinessArchetype("B2B_LICENSE", "Licencia B2B", "Licencia de software o contenido a empresas.", "licencia anual", "evitar licencia sin caso de uso del comprador interno"),
    BusinessArchetype("WHITE_LABEL", "White label", "Producto que otros venden con su marca.", "licencia por volumen", "evitar white label sin canal de distribución de los revendedores"),
    BusinessArchetype("ACCUMULATIVE_DATASET", "Dataset acumulativo", "Datos que crecen con cada cliente y aumentan el valor del producto.", "suscripción o licencia", "requiere fuente de datos real y legal"),
    BusinessArchetype("BENCHMARKING_NETWORK", "Red de benchmarking", "Un grupo compara sus métricas contra las del resto de forma anónima.", "cuota de membresía", "requiere mínimo de participantes para que el dato valga"),
    BusinessArchetype("COLLABORATIVE_TOOL", "Herramienta colaborativa", "El valor crece cuando varias personas lo usan juntas.", "por usuario", "evitar herramienta colaborativa sin equipo que la necesite"),
    BusinessArchetype("IDLE_ASSET_INCOME", "Activo ocioso a ingreso", "Convierte capacidad no usada en flujo de ingresos.", "comisión o porcentaje", "el coste de coordinación debe ser menor que el ingreso"),
    BusinessArchetype("FRAGMENTED_DEMAND_BUNDLER", "Agrupador de demanda fragmentada", "Junta compradores dispersos para hacer viable una oferta.", "comisión o margen", "requiere canal para llegar a los dispersos"),
    BusinessArchetype("AGENT_SERVICE_PROVIDER", "Proveedor de servicios a agentes", "Un servicio que otro sistema (no humano) consume de forma programática.", "pago por uso o contrato", "evitar asumir demanda de agentes sin evidencia"),
)


def get_territory(key: str) -> Territory | None:
    return next((t for t in TERRITORIES if t.key == key), None)


def get_lens(key: str) -> InnovationLens | None:
    return next((l for l in LENSES if l.key == key), None)


def get_archetype(key: str) -> BusinessArchetype | None:
    return next((a for a in ARCHETYPES if a.key == key), None)


def territory_keys() -> list[str]:
    return [t.key for t in TERRITORIES]


def lens_keys() -> list[str]:
    return [l.key for l in LENSES]


def archetype_keys() -> list[str]:
    return [a.key for a in ARCHETYPES]
