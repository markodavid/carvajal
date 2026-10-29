"""Pipeline de captura y curaduría del corpus web de Carvajal.

Este módulo no importa subpaquetes: hacerlo obligaría a cargar ``langchain``, ``faiss``
y los clientes de LLM cada vez que alguien importa ``carvajal.config`` o ``carvajal.ui``
(la interfaz tardaba minutos en abrir). Los puntos de entrada viven en ``carvajal.cli``.
"""

__all__: list[str] = []
