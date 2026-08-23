"""Agentes lógicos del sistema (módulos internos, no microservicios).

Cada agente recibe solo los datos guardados, produce una salida estructurada
y registra su razonamiento en el DecisionLog vía el workflow.
"""
from app.agents.scout import ScoutAgent
from app.agents.researcher import ResearcherAgent
from app.agents.skeptic import SkepticAgent
from app.agents.economist import EconomistAgent
from app.agents.builder import BuilderAgent
from app.agents.compliance import ComplianceAgent
from app.agents.judge import JudgeAgent

__all__ = [
    "ScoutAgent",
    "ResearcherAgent",
    "SkepticAgent",
    "EconomistAgent",
    "BuilderAgent",
    "ComplianceAgent",
    "JudgeAgent",
]
