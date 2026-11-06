# Manual Normativo de Motores Elétricos Industriais (WEG / ISO)

Este documento centraliza as normas técnicas e protocolos de manutenção preditiva e corretiva para motores elétricos trifásicos industriais operados na planta Predicta. Ele deve ser utilizado para tomada de decisão por algoritmos e engenheiros.

## 1. Severidade de Vibração (ISO 10816-3)
A avaliação da severidade de vibração segue as zonas da norma ISO 10816-3 para máquinas rotativas. A vibração é medida em mm/s (RMS) nos mancais.

*   **Zona A (Normal/Nova):** Vibração perfeitamente aceitável. Valores < 1.5 mm/s. O motor está na sua condição ideal.
*   **Zona B (Aceitável):** Operação contínua irrestrita permitida. Valores entre 1.5 e 2.8 mm/s. Pode indicar início de desgaste, requer monitoramento.
*   **Zona C (Alerta):** Operação contínua restrita. Valores entre 2.8 e 4.5 mm/s. Indica que a máquina não deve operar continuamente neste estado por muito tempo. Ações: planejar parada, verificar alinhamento, inspecionar acoplamento e balanceamento do rotor.
*   **Zona D (Crítico):** Risco iminente de dano severo. Valores > 4.5 mm/s. Ação obrigatória: Desligamento imediato. Causa provável: falha catastrófica de rolamento, eixo empenado, ou falha estrutural severa na base (pé manco).

### Diagnóstico Frequente (Vibração):
- **1x RPM:** Geralmente indica Desbalanceamento do Rotor.
- **2x RPM:** Geralmente indica Desalinhamento (paralelo ou angular).
- **Altas Frequências:** Geralmente aponta para falha de rolamentos (pistas interna/externa ou esferas).

## 2. Limites Térmicos por Classe de Isolamento (NEMA/IEC)
Motores operam sob limites térmicos estritos. A elevação de temperatura do enrolamento (medida pelo PT100) dita a vida útil do motor.
As medições assumem temperatura ambiente máxima de 40°C.

*   **Classe B:** Temperatura máxima absoluta permitida: **130°C**. Ideal operar abaixo de 80°C.
*   **Classe F:** Temperatura máxima absoluta permitida: **155°C**. Ideal operar abaixo de 100°C. (Classe predominante na Predicta).
*   **Classe H:** Temperatura máxima absoluta permitida: **180°C**.

### Causas de Sobreaquecimento (Temperatura Alta):
1. **Sobrecarga Mecânica:** Exigência de conjugado acima da potência nominal do eixo. Aumenta a corrente e eleva a temperatura bruscamente.
2. **Deficiência de Ventilação:** Sujeira nas aletas da carcaça, defletora quebrada ou filtro entupido. Causa aumento lento e linear da temperatura.
3. **Subtensão ou Sobretensão (Alimentação elétrica):** Oscilação na Tensão (V) exige mais Corrente (A) para manter o fluxo de potência, fritando as bobinas.

## 3. Diretrizes de Diagnóstico Integrado
Se a **Temperatura E Vibração** subirem simultaneamente:
Isso quase sempre aponta para sobrecarga severa combinada com desalinhamento ou falta grave de lubrificação nos mancais. O atrito mecânico excessivo aquece a carcaça e causa vibração anômala. Ação: Parar a máquina, drenar a graxa velha, re-lubrificar mancais e checar alinhamento a laser.

## 4. Avaliação de Tensão (V) e Corrente (A)
*   **Corrente (A):** Se a corrente medida ultrapassar a Corrente Nominal em mais de 10% (Fator de Serviço não deve ser usado continuamente), há risco de queima das bobinas.
*   **Tensão (V):** A tensão da rede não deve variar mais que +/- 5%. (Ex: motor 380V não deve operar fora da faixa 361V - 399V).

### Folga Mecânica em Mancal
*   **Sintomas:** Ruído metálico, vibração com múltiplos harmônicos (1x, 2x, 3x RPM).
*   **Causas Comuns:** Desgaste excessivo do alojamento do rolamento, falha de lubrificação prolongada.

### Sobrecarga de Fase (Elétrica)
*   **Sintomas:** Aumento generalizado da temperatura, corrente elétrica acima da nominal em uma ou mais fases.
## 4. Procedimentos de Manutenção Recomendados

### Manutenção Preditiva
*   Análise de vibração espectral mensal.
*   Termografia termográfica do estator e mancais quinzenalmente.
*   Análise de óleo e lubrificantes a cada 3.000 horas de operação.

### Manutenção Corretiva (Ação Imediata)
*   **Alta Vibração (> Zona C):** Realizar alinhamento a laser e inspeção do acoplamento. Substituir rolamentos se houver folga mecânica confirmada.
*   **Alta Temperatura (Acima da Classe):** Reduzir carga operacional imediatamente. Inspecionar aletas de ventilação, verificar desbalanceamento de tensão e medir resistência de isolamento do estator (Megger).
