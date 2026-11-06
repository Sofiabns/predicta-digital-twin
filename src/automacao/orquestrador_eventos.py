import logging
import hashlib
from datetime import datetime
from src.persistencia.database import get_connection
from src.persistencia.evento_repository import registrar_evento
from src.automacao.notificacao_service import enviar_alerta_html

logger = logging.getLogger(__name__)

def orquestrar_transicao(
    motor_id: int,
    tag: str,
    codigo_motor: str,
    severidade: str,
    descricao: str,
    diagnostico: str,
    acao: str
) -> None:
    """
    Executa a transação atômica que atualiza o status e gera o evento.
    Dispara notificação se CRITICO.
    """
    
    status_map = {
        "NORMAL": "operacional",
        "ALERTA": "atencao",
        "CRITICO": "critico"
    }
    
    status_op = status_map.get(severidade, "operacional")
    
    with get_connection() as conn:
        try:
            # 1. Registrar o evento
            query_evento = """
            INSERT INTO eventos_operacionais (
                tag_ativo, codigo_motor, tipo_evento, severidade,
                descricao_anomalia, diagnostico_ia, acao_recomendada
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            conn.execute(query_evento, (tag, codigo_motor, "ANALISE_IA", severidade, descricao, diagnostico, acao))
            
            # 2. Atualizar status na tabela associacoes_ativos
            query_status = "UPDATE associacoes_ativos SET status_operacional = ? WHERE motor_id = ?"
            conn.execute(query_status, (status_op, motor_id))
            
            if severidade == "CRITICO":
                # 3. Registrar Ordem de Manutenção
                query_manut = """
                INSERT INTO manutencoes (motor_id, tipo, status, prioridade, descricao, data_prevista)
                VALUES (?, 'corretiva', 'pendente', 'urgente', ?, CURRENT_TIMESTAMP)
                """
                conn.execute(query_manut, (motor_id, f"IA Prescreve: {acao}"))
                
                # 4. Auditoria Operacional (SHA-256)
                timestamp_str = datetime.now().isoformat()
                hash_input = f"{timestamp_str}{tag}{severidade}".encode('utf-8')
                audit_hash = hashlib.sha256(hash_input).hexdigest()
                
                query_audit = """
                INSERT INTO auditoria_operacional (entidade, entidade_id, acao, origem, detalhes)
                VALUES (?, ?, ?, ?, ?)
                """
                conn.execute(query_audit, (
                    "associacoes_ativos", 
                    motor_id, 
                    "ATUALIZACAO_STATUS_CRITICO", 
                    "IA_PREDICTA", 
                    f"Hash de auditoria: {audit_hash}"
                ))
            
        except Exception as e:
            logger.error("Erro durante a transação de evento: %s", e)
            raise e
            
    logger.info("Transição processada com sucesso: Ativo %s agora está %s", tag, status_op)
    
    if severidade == "CRITICO":
        enviar_alerta_html(tag, severidade, diagnostico, acao)


