"""Motor de evals de Loombit — el instrumento del método (docs/METODO_INGENIERIA_IA_LOOMBIT.md).

No se imaginan los fallos: se codifican los REALES (taxonomía F1-F8 sacada de trazas) y cada
cambio se mide contra ellos. Los casos deterministas corren en CI (tests/test_evals.py); los de
calidad (juez-LLM) corren bajo demanda con LM Studio.
"""
