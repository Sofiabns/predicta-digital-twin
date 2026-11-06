"""Base de conhecimento técnica (mini-RAG).

Indexa duas coleções de documentos:

* ``manuais``     - manuais e guias normativos (data/manuais)
* ``operacional`` - contexto operacional exportado pela automação
                    (data/rag/operacional): estado atual, histórico de eventos e
                    manutenções de cada ativo

A busca usa embeddings (sentence-transformers + FAISS) quando essas bibliotecas
e o modelo estão disponíveis. Caso contrário, cai automaticamente para uma busca
lexical BM25, que não depende de internet nem de GPU. Assim a recuperação de
procedimentos continua funcionando em qualquer ambiente.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANUAIS_DIR = PROJECT_ROOT / "data" / "manuais"
OPERACIONAL_DIR = PROJECT_ROOT / "data" / "rag" / "operacional"

MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSION = 384
TAMANHO_MAX_CHUNK = 700

_STOPWORDS = set(
    "a o as os um uma de da do das dos em no na nos nas por para com sem que e ou se ao aos "
    "e é foi ser sao são esta está como mais menos entre sobre ate até pelo pela quando".split()
)


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return t


def _tokens(texto: str) -> list[str]:
    brutos = re.findall(r"[a-z0-9]+", _normalizar(texto))
    stop = {_normalizar(s) for s in _STOPWORDS}
    return [t for t in brutos if t not in stop and len(t) > 1]


@dataclass
class Trecho:
    texto: str
    fonte: str       # nome do arquivo
    secao: str       # título da seção mais próxima
    colecao: str     # manuais | operacional
    score: float = 0.0

    def referencia(self) -> str:
        return f"{self.fonte} > {self.secao}" if self.secao else self.fonte


def _dividir_em_trechos(conteudo: str, fonte: str, colecao: str) -> list[Trecho]:
    """Quebra o documento por seção/parágrafo, preservando o título da seção."""
    trechos: list[Trecho] = []
    secao = ""
    buffer: list[str] = []

    def fechar() -> None:
        texto = "\n".join(buffer).strip()
        buffer.clear()
        if len(texto) <= 20:
            return
        # divide blocos muito longos respeitando o limite
        while len(texto) > TAMANHO_MAX_CHUNK:
            corte = texto.rfind("\n", 0, TAMANHO_MAX_CHUNK)
            if corte < TAMANHO_MAX_CHUNK // 2:
                corte = texto.rfind(". ", 0, TAMANHO_MAX_CHUNK)
            if corte < TAMANHO_MAX_CHUNK // 2:
                corte = TAMANHO_MAX_CHUNK
            trechos.append(Trecho(texto[:corte].strip(), fonte, secao, colecao))
            texto = texto[corte:].strip()
        if len(texto) > 20:
            trechos.append(Trecho(texto, fonte, secao, colecao))

    for linha in conteudo.splitlines():
        eh_titulo = linha.lstrip().startswith("#") or re.match(r"^\s*SINTOMA\s+\d+", linha)
        if eh_titulo:
            fechar()
            secao = linha.strip().lstrip("#").strip()
            buffer.append(linha)
        else:
            buffer.append(linha)
    fechar()
    return trechos


class _IndiceLexical:
    """BM25 simples, sem dependências externas."""

    def __init__(self, trechos: list[Trecho]):
        self.trechos = trechos
        self.docs = [_tokens(t.texto + " " + t.secao) for t in trechos]
        self.tf = [Counter(d) for d in self.docs]
        n = max(1, len(self.docs))
        self.avgdl = sum(len(d) for d in self.docs) / n if self.docs else 0.0
        df: Counter = Counter()
        for d in self.docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def buscar(self, consulta: str, top_k: int) -> list[Trecho]:
        termos = _tokens(consulta)
        if not termos or not self.docs:
            return []
        k1, b = 1.5, 0.75
        pontuados: list[tuple[float, int]] = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i]) or 1
            score = 0.0
            for termo in termos:
                f = tf.get(termo, 0)
                if not f:
                    continue
                score += self.idf.get(termo, 0.0) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / (self.avgdl or 1)))
            if score > 0:
                pontuados.append((score, i))
        pontuados.sort(reverse=True)
        saida = []
        for score, i in pontuados[:top_k]:
            t = self.trechos[i]
            saida.append(Trecho(t.texto, t.fonte, t.secao, t.colecao, round(score, 4)))
        return saida


class _IndiceSemantico:
    """Embeddings + FAISS. Levanta exceção se as dependências não existirem."""

    _modelo = None

    def __init__(self, trechos: list[Trecho]):
        import faiss  # noqa: WPS433
        import numpy as np

        if _IndiceSemantico._modelo is None:
            from sentence_transformers import SentenceTransformer
            _IndiceSemantico._modelo = SentenceTransformer(MODEL_NAME)
        self.modelo = _IndiceSemantico._modelo
        self.np = np
        self.trechos = trechos
        self.indice = faiss.IndexFlatL2(DIMENSION)
        if trechos:
            emb = self.modelo.encode([t.texto for t in trechos])
            self.indice.add(np.array(emb).astype("float32"))

    def buscar(self, consulta: str, top_k: int) -> list[Trecho]:
        if not self.trechos:
            return []
        q = self.modelo.encode([consulta]).astype("float32")
        dist, idx = self.indice.search(q, min(top_k, len(self.trechos)))
        saida = []
        for d, i in zip(dist[0], idx[0]):
            if 0 <= i < len(self.trechos):
                t = self.trechos[i]
                saida.append(Trecho(t.texto, t.fonte, t.secao, t.colecao, round(float(d), 4)))
        return saida


class BaseConhecimento:
    """Interface única de consulta à base técnica (singleton por processo)."""

    _instance: "BaseConhecimento | None" = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._inicializado = False
        return cls._instance

    def __init__(self, backend: str | None = None):
        if self._inicializado:
            return
        import os

        self.backend_pedido = (backend or os.getenv("PREDICTA_RAG_BACKEND", "auto")).lower()
        self.backend = "lexical"
        self._sem_semantico = False
        self._manuais_dir = Path(os.getenv("PREDICTA_MANUAIS_DIR", MANUAIS_DIR))
        self._oper_dir = Path(os.getenv("PREDICTA_RAG_DIR", OPERACIONAL_DIR))
        self._trechos: dict[str, list[Trecho]] = {"manuais": [], "operacional": []}
        self._indices: dict[str, object] = {}
        self._carregar("manuais")
        self.reindexar_operacional()
        self._inicializado = True

    @classmethod
    def reiniciar(cls) -> None:
        """Descarta a instância atual (usado em testes e após trocar diretórios)."""
        cls._instance = None

    # ------------------------------------------------------------------
    def _ler_diretorio(self, pasta: Path, colecao: str) -> list[Trecho]:
        trechos: list[Trecho] = []
        pasta.mkdir(parents=True, exist_ok=True)
        arquivos = sorted(list(pasta.glob("*.txt")) + list(pasta.glob("*.md")))
        for arq in arquivos:
            try:
                trechos.extend(_dividir_em_trechos(arq.read_text(encoding="utf-8"), arq.name, colecao))
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("Documento ignorado (%s): %s", arq.name, exc)
        return trechos

    def _montar_indice(self, trechos: list[Trecho]):
        if self.backend_pedido in ("auto", "semantico") and not self._sem_semantico:
            try:
                indice = _IndiceSemantico(trechos)
                self.backend = "semantico"
                return indice
            except Exception as exc:  # noqa: BLE001 - biblioteca ou modelo ausentes
                if self.backend_pedido == "semantico":
                    logger.warning("Busca semântica indisponível (%s); usando léxica.", exc)
                else:
                    logger.info("Busca semântica indisponível (%s); usando léxica.", exc)
                self._sem_semantico = True
        return _IndiceLexical(trechos)

    def _carregar(self, colecao: str) -> None:
        pasta = self._manuais_dir if colecao == "manuais" else self._oper_dir
        trechos = self._ler_diretorio(pasta, colecao)
        self._trechos[colecao] = trechos
        self._indices[colecao] = self._montar_indice(trechos)
        logger.info("Base de conhecimento '%s': %d trechos (%s)", colecao, len(trechos), self.backend)

    def reindexar_operacional(self) -> int:
        """Relê o contexto operacional exportado pela automação."""
        self._carregar("operacional")
        return len(self._trechos["operacional"])

    # ------------------------------------------------------------------
    @property
    def total_trechos(self) -> int:
        return sum(len(v) for v in self._trechos.values())

    def buscar_trechos(self, consulta: str, top_k: int = 3, colecao: str | None = None) -> list[Trecho]:
        colecoes = [colecao] if colecao else ["manuais", "operacional"]
        achados: list[Trecho] = []
        for c in colecoes:
            indice = self._indices.get(c)
            if indice is not None:
                achados.extend(indice.buscar(consulta, top_k))  # type: ignore[attr-defined]
        if len(colecoes) > 1:
            # scores de coleções diferentes não são comparáveis: intercala
            por_colecao = [[t for t in achados if t.colecao == c] for c in colecoes]
            intercalados: list[Trecho] = []
            for par in zip(*[iter(x) for x in por_colecao]):
                intercalados.extend(par)
            resto = [t for t in achados if t not in intercalados]
            return (intercalados + resto)[:top_k]
        return achados[:top_k]

    def buscar_contexto(self, query: str, top_k: int = 2) -> List[str]:
        """Compatível com as sprints anteriores: devolve só o texto dos trechos."""
        return [t.texto for t in self.buscar_trechos(query, top_k)]
