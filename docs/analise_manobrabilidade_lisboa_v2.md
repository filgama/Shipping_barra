# Análise de Lacunas e Requisitos Avançados para o Sistema de Apoio à Decisão de Manobrabilidade e Atracagem no Porto de Lisboa
## Versão anotada — texto original integral + crítica e complementos

> **Convenção de leitura:** o texto original está preservado na íntegra. Os blocos assinalados com **🔎 CRÍTICA** identificam imprecisões, fragilidades ou pontos a validar; os blocos **➕ COMPLEMENTO** acrescentam conteúdo em falta. Nada do texto original foi removido.

---

> **🔎 CRÍTICA GERAL AO DOCUMENTO (ler primeiro)**
>
> 1. **Secções incompletas:** as secções 5.1 (Janelas de Maré) e 5.2 (Limites de Visibilidade) têm título e frase introdutória mas **não têm corpo** — as "lógicas de processamento" prometidas nunca são enumeradas. Na secção 1.3, o texto anuncia "dois fenómenos catastróficos" e **nunca os descreve**. Estas lacunas são preenchidas nos complementos abaixo.
> 2. **Fontes fracas:** duas das cinco referências são links Scribd (agregadores sem valor normativo) e uma é um artigo de opinião. Para um documento que fundamenta decisões Go/No-Go, as fontes primárias devem ser: PIANC Report 121 (2014), o **Regulamento de Exploração do Porto de Lisboa** e o **Regulamento das Pilotagens** (Edital da Capitania do Porto de Lisboa), tabelas de marés e correntes do **Instituto Hidrográfico**, e as Cartas Náuticas oficiais (série 26xxx do IH). Todos os valores regulamentares citados (20 nós RO-RO, 1.000 GT, 150 m LOA, 5.000 GT, 24 m de boca em Alcântara, calado 10,5 m, folga aérea da Ponte 25 de Abril) **devem ser verificados contra a versão em vigor do regulamento da APL antes de codificação** — o documento cita-os sem referência de artigo.
> 3. **Rigor terminológico/matemático:** o squat **não aumenta "de forma exponencial"** — cresce aproximadamente com o **quadrado da velocidade** (relação quadrática, não exponencial). "Granulometria horária" deve ser "granularidade temporal horária". Estas imprecisões, num documento de engenharia, minam a credibilidade junto de revisores técnicos.
> 4. **Ausência de tratamento de incerteza:** todo o documento assume determinismo (valor previsto vs. limiar). Um sistema Go/No-Go sério deve ser **probabilístico** — previsões meteorológicas e de maré têm intervalos de confiança, e a decisão deve incorporar margens função da incerteza (abordagem UKC probabilístico tipo PIANC, cap. sobre "probabilistic design").
> 5. **Ausência do fator humano e do circuito de decisão:** não se define quem valida o output (piloto? VTS? comandante?), qual o estatuto legal da recomendação algorítmica, nem o mecanismo de *override* documentado. Ver complemento na conclusão.
> 6. **Ausência de variáveis inteiras:** interação navio-navio (passing ship effects), tráfego de ferries Transtejo/Soflusa, condições de embarque do piloto na barra, seichas/ondas de longo período nos cais, fator de rajada, abort points, e integração com PPU/VTS/AIS. Complementos adicionados como **novas secções 6, 7 e 8**.

---

O desenvolvimento de uma ferramenta algorítmica de apoio à decisão orientada para a aproximação, trânsito e atracagem de navios no Porto de Lisboa exige uma arquitetura computacional que transcenda a mera monitorização estática. O sistema atual, centrado no cálculo da folga básica abaixo da quilha (Under Keel Clearance - UKC) através da subtração do calado estático ao nível da maré previsto e na sinalização de limiares meteorológicos simples, apresenta lacunas estruturais severas. A pilotagem de barra e de porto num ambiente estuarino complexo como o rio Tejo requer a integração de variáveis dinâmicas e determinísticas. O Porto de Lisboa caracteriza-se por canais de navegação restritos, forte assimetria de correntes de maré, batimetria variável e constrangimentos logísticos de elevada criticidade, como a Ponte 25 de Abril e as restrições dimensionais de docas históricas.

A transição para um sistema de avaliação Go/No-Go efetivo obriga à incorporação detalhada da mecânica de fluidos, da cinemática dos navios em águas confinadas e do vasto normativo da Administração do Porto de Lisboa (APL). A omissão de vetores hidrodinâmicos e operacionais específicos pode induzir o operador em erro fatal, culminando em abalroamentos, encalhes ou danos estruturais nas infraestruturas portuárias. A presente análise técnica categoriza e disseca exaustivamente as variáveis críticas em falta no atual sistema, elucidando o impacto profundo de cada parâmetro na decisão de execução ou aborto da manobra.

> **➕ COMPLEMENTO (introdução):** Deve declarar-se explicitamente o **âmbito de responsabilidade** da ferramenta: é um *decision support system* (DSS) e não um *decision making system*. A decisão final é sempre do piloto/comandante (SOLAS, ordenamento nacional). Esta distinção condiciona a arquitetura (o sistema recomenda, regista e justifica; não executa) e a gestão de risco jurídico do projeto. Recomenda-se ainda definir desde já os três estados de output — **GO / GO CONDICIONAL (com mitigações listadas) / NO-GO** — em vez do binário Go/No-Go, porque a maior parte dos casos reais resolve-se com mitigação (redução de STW, rebocador adicional, espera pela estofa) e não com aborto puro.

## 1. Efeitos Hidrodinâmicos (A Dimensão Dinâmica da Navegação)

A navegação em águas rasas e em canais restritos altera drasticamente o comportamento hidrodinâmico de qualquer embarcação. O cálculo estático do UKC ignora as forças de pressão assimétricas que atuam sobre o casco em movimento e as respostas cinemáticas do navio face à ondulação atlântica na embocadura da barra e às intensas correntes estuarinas.

### 1.1. Under Keel Clearance (UKC) Dinâmico e o Efeito de Fundão (Squat)

A deslocação de um navio por águas confinadas força o escoamento acelerado da massa de água sob a quilha e ao longo do costado para compensar o volume deslocado. De acordo com o Princípio de Bernoulli, este aumento da velocidade do fluxo fluído resulta numa queda de pressão hidrodinâmica sob o navio, provocando um afundamento vertical dinâmico e uma alteração do caimento longitudinal (trim), fenómeno vulgarmente designado por efeito de fundão ou squat. [1][2]

O squat aumenta de forma exponencial, sendo diretamente proporcional ao quadrado da velocidade do navio em relação à água e intimamente ligado ao coeficiente de bloco (Cb) do casco. Em canais restritos como a Barra Sul do rio Tejo, este afundamento induzido pode atingir valores significativamente superiores aos registados em mar aberto. Para além do afundamento por velocidade, a agitação marítima proveniente do quadrante Noroeste à entrada da barra induz acentuados movimentos de cabeceio (pitch), balanço (roll) e arfagem (heave) que afundam temporariamente partes críticas da quilha, reduzindo a folga efetiva. O sistema atual não contabiliza a profundidade exigida por estes movimentos oscilatórios. [1][2]

> **🔎 CRÍTICA (1.1):** "Aumenta de forma exponencial" e "proporcional ao quadrado" são afirmações contraditórias na mesma frase — a segunda está correta. Corrigir para: *"o squat cresce de forma quadrática com a velocidade (∝ V²)"*.
>
> **➕ COMPLEMENTO (1.1) — Fórmulas concretas a implementar:**
> - **Fórmula de Barrass** (padrão da prática de pilotagem): `Squat_max = (Cb × V²) / 100 × K`, com K=2 para águas abertas rasas e K=1 (fator canal) via coeficiente de bloqueio `S = A_navio / A_canal`. Versão completa: `Squat = Cb × S^0.81 × V^2.08 / 20`.
> - **Fórmulas alternativas** para validação cruzada: ICORELS, Eryuzlu, Huuska/Guliev (a PIANC 121 recomenda usar a fórmula adequada à geometria: canal confinado vs. águas abertas rasas vs. canal dragado em zona aberta — a Barra Sul e o Canal do Barreiro caem em categorias diferentes).
> - **Resposta a ondulação (wave response allowance):** o afundamento vertical por pitch/heave/roll deve ser estimado por **RAOs (Response Amplitude Operators)** ou, na ausência de modelo do navio, por regra empírica PIANC (fração da altura significativa Hs em função do rumo relativo ao espetro). O input em tempo real é a boia ondógrafo, mas o sistema precisa também de **período e direção**, não só Hs — ondulação de longo período (swell de 14–18 s típico do quadrante NW) produz muito mais movimento vertical do que vaga curta com a mesma Hs.
> - **Nível de água real vs. previsto:** a maré meteorológica (storm surge/pressão atmosférica) pode desviar o nível real ±0,3–0,5 m face à tabela astronómica. O sistema deve ingerir o **marégrafo em tempo real** (rede do IH/APL — Cascais, Lisboa) e usar a diferença observada-prevista como correção e como termo de incerteza.
> - **UKC probabilístico:** em vez de margem fixa, a PIANC admite abordagem probabilística (probabilidade de toque no fundo < 1/ N trânsitos). Recomenda-se pelo menos parametrizar a margem por troço: barra exposta (margem maior, p.ex. 15–20% do calado) vs. canal interior abrigado (menor, p.ex. 10%), conforme política de UKC que a APL formalizar.

Impacto na Decisão Go/No-Go: A ferramenta tem de transitar obrigatoriamente para um modelo de UKC Dinâmico. Este cálculo deve cruzar o calado estático, a equação de squat para águas restritas e o espetro direcional de ondulação recolhido em tempo real (como os dados da boia ondógrafo Triaxys da APL localizada na Barra Sul a WGS84 38º 37´ 25.2´´N / 09º 23´ 16,8´´W). Caso a projeção do UKC dinâmico seja inferior à margem de segurança estipulada pela Autoridade Portuária para o canal em causa, o sistema deve emitir um bloqueio automático (No-Go) ou, de forma preditiva, recomendar a redução da velocidade de trânsito (Speed Through Water - STW) para colapsar o efeito de squat e restabelecer a margem de segurança. [1][2]

> **➕ COMPLEMENTO (1.1, impacto):** A recomendação de redução de STW tem um **limite inferior de governabilidade**: abaixo de uma velocidade mínima (tipicamente 4–6 nós, dependente do navio e da corrente de través), o navio perde eficácia de leme. O algoritmo deve verificar que a STW recomendada para colapsar o squat **não viola a velocidade mínima de governo** nem o tempo máximo de exposição na barra (mais tempo na barra = mais ciclos de onda = mais exposição). Se não existir STW simultaneamente segura para UKC e para governo, o resultado é NO-GO — não "reduzir velocidade".

### 1.2. Interação Fluida com Limites Físicos: Bank Effect e Bow Cushion

Ao navegar fora do eixo central geométrico de um canal restrito, gera-se uma severa assimetria do fluxo de água entre o costado do navio e a margem mais próxima (ou os taludes batimétricos laterais do canal). A aceleração da água no estreitamento entre o casco e a margem provoca uma violenta queda de pressão na secção da popa, sugando-a em direção ao talude inferior (bank suction). Simultaneamente, a massa de água deslocada pela proa é refletida pela margem, criando uma zona de alta pressão que empurra a proa para o centro do canal (bank cushion). [1][2]

No Porto de Lisboa, o trânsito nos canais de Alcochete, Barreiro ou Alfeite coloca navios de grande porte em extrema proximidade com bancos de areia e lodo. Se um vetor de vento cruzado, ou a manobra de ultrapassagem/cruzamento com outra embarcação forçar o navio a afastar-se do centro do canal, o momento de guinada rotacional induzido pelo bank effect pode subitamente superar a força corretiva gerada pelo leme, resultando numa perda total de governo e inevitável encalhe. [1][2]

Impacto na Decisão Go/No-Go: O algoritmo da ferramenta de apoio à decisão deve integrar a batimetria seccional cruzada (cross-sectional bathymetry) dos canais e avaliar continuamente a relação entre a boca do navio, o calado, a profundidade lateral e a distância física à margem. Se os ventos previstos forçarem um ângulo de deriva (drift angle) que aproxime o navio da zona crítica do bank effect, a ferramenta tem de sinalizar a necessidade imediata de rebocadores de escolta operacionais ou abortar a entrada no canal sob aquelas condições meteorológicas.

> **➕ COMPLEMENTO (1.2):**
> - **Interação navio-navio (passing ship effect):** o documento menciona cruzamentos apenas de passagem. Falta a variável completa: dois navios que se cruzam ou ultrapassam em canal restrito geram forças de sucção/repulsão mútuas análogas ao bank effect, e a PIANC dimensiona a **faixa de passagem (W_p)** para canais de duas vias. O algoritmo deve consultar o **planeamento VTS de tráfego** e proibir/reagendar cruzamentos de navios de grande porte em secções sub-dimensionadas — isto exige integração com a agenda de tráfego do porto, não apenas meteorologia.
> - **Sedimentação e validade da batimetria:** o Tejo é um estuário com forte dinâmica sedimentar. A batimetria "oficial" pode ter meses; o sistema deve registar a **data do último levantamento** por troço e aplicar uma penalização de incerteza (ou bloquear calados-limite) quando o levantamento exceder a validade definida pela APL, especialmente após cheias do Tejo, que alteram os bancos.

### 1.3. O Paradoxo da Corrente de Popa (Following Current)

O alerta empírico da pilotagem local relativamente ao perigo extremo de atracar com corrente de popa está solidamente ancorado nos princípios da física de governo de navios. Atracar com "água na popa" constitui uma das manobras de maior sinistralidade potencial no espetro portuário, devendo ser sistemicamente evitada ou rigorosamente controlada. [1][2]

O processo de atracação exige que o navio reduza a sua velocidade sobre o fundo (Speed Over Ground - SOG) até zero num ponto geográfico muito específico. Quando uma embarcação navega a favor da corrente (corrente de popa), para que o SOG atinja zero, o navio terá de desenvolver velocidade a ré em relação à massa de água envolvente (Speed Through Water - STW < 0). Ao concretizar este diferencial, ocorrem dois fenómenos catastróficos para a manobrabilidade:

> **🔎 CRÍTICA (1.3):** O texto anuncia "dois fenómenos catastróficos" e **não os enumera** — o parágrafo termina abruptamente. Completa-se em baixo.
>
> **➕ COMPLEMENTO (1.3) — Os dois fenómenos em falta:**
> 1. **Perda total de eficácia do leme:** o leme só gera força de sustentação quando banhado por fluxo de água orientado de vante para ré (esteira do hélice em marcha avante). Com STW ≈ 0 ou negativa, o fluxo sobre o leme anula-se ou inverte-se — o navio fica **sem governo direcional** precisamente no momento de máxima exigência de precisão, ficando à mercê da corrente e do vento.
> 2. **Efeitos assimétricos da máquina a ré (transverse thrust / "paddle-wheel effect"):** para travar contra a corrente, o navio é forçado a longos períodos de máquina a ré. Num hélice de passo fixo de rotação à direita, a marcha a ré empurra a popa para bombordo de forma não comandável, induzindo uma guinada imprevisível junto ao cais. Adicionalmente, a corrente de popa **transporta o navio sobre o ponto de atracação** — qualquer atraso na redução traduz-se em sobrevoo do berço com energia cinética residual (a energia de impacto cresce com o quadrado da velocidade residual, com consequências diretas nas defensas e estrutura do cais).

Impacto na Decisão Go/No-Go: A ferramenta deve ingerir dados modelados das correntes de maré do estuário do Tejo com granulometria horária ou sub-horária. Durante a projeção da manobra, se o vetor longitudinal da corrente incidir pela popa do navio com uma intensidade superior a um limiar restrito (e.g., >0.5 a 1.0 nós) no momento e local exatos da atracação, a ferramenta não pode autorizar a manobra por propulsão própria. O output deve ditar um No-Go até à ocorrência do período de estofa da maré ou exigir contratualização extraordinária de rebocadores com bollard pull suficiente para dominar a inércia da embarcação.

> **➕ COMPLEMENTO (1.3, dados):** Fontes concretas para o modelo de correntes: cartas de correntes de maré do **Instituto Hidrográfico** para o estuário do Tejo, modelos hidrodinâmicos operacionais (p.ex. modelos MOHID/Delft3D do estuário mantidos por IST/LNEC/IH) e, idealmente, **ADCPs fixos** em pontos críticos (Cachopos, gargalo da ponte, Alcântara) para assimilação em tempo real. Nota importante: a corrente no Tejo **não é uniforme na coluna de água nem na secção transversal** — junto aos cais existem contra-correntes e turbilhões locais que os modelos de larga escala não resolvem; o sistema deve permitir *overlays* de conhecimento local codificado pelos pilotos (zonas de anomalia conhecida por berço).

## 2. Especificações e Manobrabilidade do Navio

Um sistema de inteligência de manobra cego às especificações arquitetónicas, geométricas e hidrodinâmicas do navio é incapaz de quantificar o impacto dos fenómenos atmosféricos. O navio não é um vetor passivo; as suas características de resposta (área de resistência aerodinâmica, tipo de propulsão e eficiência do aparelho de governo) ditam a amplitude da janela operacional segura.

### 2.1. Área Vélica Exposta (Windage Area) e Forças Transversais

A utilização de limiares meteorológicos absolutos e genéricos (ex: "ventos acima de X nós na barra") é uma falácia operacional. Um vento lateral de 15 nós afeta um navio-tanque totalmente carregado de forma manifestamente distinta da de um navio de cruzeiros ou de um navio RO-RO. A força lateral (abatimento) imposta pelo vento é proporcional ao quadrado da velocidade do vento multiplicado pela área do navio exposta acima da linha de flutuação (windage area).

Navios RO-RO, porta-contentores com estivagem de múltiplos níveis no convés superior e navios de cruzeiro comportam-se balisticamente como velas sólidas contínuas. A própria regulamentação da Autoridade Portuária da APL consagra a proibição perentória de entrada, saída ou qualquer outro movimento de navios RO-RO sempre que a intensidade de vento seja superior a 20 nós. Ignorar esta métrica e aplicar limites genéricos em função do porto, sem cruzamento com o perfil da embarcação, conduzirá invariavelmente a recomendações erróneas. [1][2]

Impacto na Decisão Go/No-Go: O sistema tem de incorporar, por integração de base de dados ou input manual do piloto/agente, a área vélica longitudinal e transversal do navio. O algoritmo matemático deverá calcular a força lateral aerodinâmica em toneladas-força e comparar esse vetor com o somatório das forças de propulsão transversal intrínsecas (hélices de proa/popa) e externas (força de tração estática dos rebocadores). Se o vento induzir uma força que ultrapasse a capacidade máxima de retenção transversal (holding capacity), deduzida de uma margem de reserva tática, o sistema assinala imediatamente a impossibilidade da manobra. No caso de navios RO-RO, qualquer leitura ou previsão acima dos 20 nós gera um bloqueio normativo inultrapassável.

> **🔎 CRÍTICA (2.1):** O limiar de 20 nós para RO-RO é citado sem referência ao artigo do regulamento — **verificar no Regulamento de Exploração da APL em vigor** (e se se aplica a vento médio sustentado ou rajada, e em que estação de medição). A distinção é crítica para implementação.
>
> **➕ COMPLEMENTO (2.1):**
> - **Fórmula de implementação:** `F_vento = ½ × ρ_ar × Cd × A_lateral × V²`, com Cd tipicamente 0,8–1,2 conforme o perfil (valores tabelados em OCIMF MEG4 para petroleiros e em literatura para porta-contentores/cruzeiros). Resultado em Newton → converter para toneladas-força para comparação direta com bollard pull.
> - **Fator de rajada (gust factor):** a decisão não pode usar apenas vento médio (10 min). Uma rajada de 30 s a meio de uma viragem na bacia é o cenário dimensionante. Recomenda-se usar `V_projeto = V_médio × G`, com G≈1,25–1,4 conforme a exposição do local, ou ingerir diretamente as rajadas das estações anemométricas da APL.
> - **Fonte da área vélica:** na prática, a área vélica raramente vem nas bases de dados comerciais. Estratégia pragmática: estimativa paramétrica por tipo de navio e dimensões (LOA × altura estimada acima da linha de água em função do calado atual — a área vélica **varia com o calado/lastro**, um facto que o documento omite: o mesmo navio em lastro tem muito mais área exposta do que carregado).

### 2.2. Tipologia, Superfície e Eficiência do Aparelho de Governo

A eficácia com que um navio descreve o seu círculo de rotação e domina forças externas opostas em canais estritos prende-se visceralmente com o tipo e rácio da área de leme (rudder area ratio). Este rácio representa a superfície do leme dividida pelo produto do comprimento e do calado da embarcação, situando-se geralmente entre os 0.016 e 0.035 na frota mercante.

Para além da área, a morfologia do leme afeta radicalmente a capacidade de rotação em espaços exíguos. Lemes de elevada sustentação (high-lift rudders), como o leme articulado Becker ou o leme Schilling, conseguem descrever ângulos extremos (até 70°-75°), redirecionando o fluxo do propulsor quase transversalmente e permitindo que o navio rode praticamente sobre o próprio eixo. Em absoluto contraste, configurações de duplo hélice com um único leme central (single centre line rudder) apresentam uma governabilidade abismal a baixas velocidades, uma vez que o leme tem de atingir grandes ângulos de deflexão apenas para lograr ser banhado pela esteira de um dos propulsores. [1][2]

Impacto na Decisão Go/No-Go: A ferramenta deve possuir uma ponderação (peso algorítmico) referente à classe de manobrabilidade do navio. Um navio provido de duplo hélice, leme de alto desempenho e excelente resposta propulsiva poderá ver aprovada uma janela de aproximação em condições marginais de correntes de través. Inversamente, um graneleiro convencional, de hélice singular e leme subdimensionado para a boca, submetido às mesmas restrições hidrodinâmicas, receberá do sistema uma ordem expressa de aguardar pela inversão da maré. [1][2]

> **➕ COMPLEMENTO (2.2):** A fonte prática destes dados é o **Pilot Card / Wheelhouse Poster** (obrigatórios pela Res. IMO A.601(15)) e os dados de manobra IMO (círculo de giro, distância de paragem, tempo de inversão de máquina). Recomenda-se que a ferramenta defina **3–4 classes de manobrabilidade** (alinhadas com as categorias PIANC "good/moderate/poor") atribuídas por regras simples sobre o tipo de propulsão/leme, com possibilidade de o piloto reclassificar após a primeira escala — criando gradualmente uma **base de dados institucional de comportamento por navio/IMO number**, que é um dos ativos de maior valor a longo prazo do sistema. Faltam também tipologias modernas no texto: **propulsão azimutal (azipods)** e **CPP (hélices de passo variável)**, cada vez mais comuns em cruzeiros e ferries, com perfis de manobra radicalmente diferentes.

### 2.3. Bloqueio da Esteira (Thruster Wake Blanking)

O advento dos bow thrusters (hélices de proa) transformou profundamente o planeamento da acostagem, minorando em muitas circunstâncias a dependência dos reboques portuários. Contudo, persiste um princípio de hidrodinâmica basilar que não pode ser descurado no cômputo da ferramenta: a eficiência destas unidades propulsivas transversais decresce vertiginosamente assim que a velocidade do navio na água excede os 2 a 3 nós. [1][2]

Quando o fluxo longitudinal de água passa pelo túnel do thruster no costado a velocidades intermédias ou elevadas, a pressão dinâmica da esteira anula o jato transversal (fenómeno de thruster wake blanking), invalidando a sua contribuição para a força lateral.

Impacto na Decisão Go/No-Go: O plano de passagem gerado pelo algoritmo tem de simular as velocidades ao longo da aproximação final. Se a ferramenta detetar que a forte corrente cruzada forçará o navio a manter um STW superior a 3 nós para não abater, o algoritmo deve anular preventivamente a potência declarada dos bow thrusters na equação de forças disponíveis. Ao descartar essa força teórica que não existirá na prática, o sistema irá constatar o défice de força lateral e impor o requisito compulsório de assistência de rebocador na proa.

> **➕ COMPLEMENTO (2.3):** Acrescentar dois degradadores adicionais de thruster frequentemente esquecidos: (a) **imersão do túnel** — em lastro ou com trim de popa acentuado, o túnel de proa pode ficar parcialmente emerso ou em ventilação, reduzindo drasticamente a força efetiva; o algoritmo deve validar a imersão mínima do túnel para o calado declarado; (b) **potência declarada vs. disponível** — thrusters elétricos podem estar limitados por gestão de carga da central elétrica do navio; usar a potência do Pilot Card com fator de desclassificação conservador (p.ex. 80%).

### 2.4. Estabilidade Estática e Impacto Cinético (Metacentric Height - GM)

As condições de estivagem e de lastro definem a altura metacêntrica (GM) da embarcação, ditando se a mesma se comportará como um navio "rijo" (stiff - GM alto) ou "brando" (tender - GM baixo). Num porto sujeito a forte ondulação atlântica na barra exterior, como é o caso de Lisboa, um navio rijo apresentará um período de balanço (roll) muito curto e violento, exacerbando perigosamente o afundamento do ressalto do porão nas extremidades de bombordo e estibordo. Em condições severas, o adernamento lateral induzido subtrai diretamente metros à folga efetiva da quilha, algo totalmente opaco no cálculo do calado puramente estático. [1][2]

> **🔎 CRÍTICA (2.4):** Esta secção não tem parágrafo "Impacto na Decisão Go/No-Go", ao contrário de todas as outras — inconsistência estrutural.
>
> **➕ COMPLEMENTO (2.4) — Impacto na Decisão Go/No-Go (em falta):** O sistema deve calcular o **período natural de balanço** `T_roll ≈ 2π·k / √(g·GM)` (ou pela regra prática `T ≈ 0,8·B/√GM`) e compará-lo com o período de encontro da ondulação na barra para o rumo e velocidade planeados. Se houver proximidade de **ressonância paramétrica ou síncrona** (período de encontro ≈ T_roll ou ≈ T_roll/2), o afundamento do bojo por roll deve ser majorado no cálculo do UKC dinâmico, ou o rumo/velocidade de passagem da barra ajustado para deslocar o período de encontro. O afundamento do bojo por adernamento calcula-se geometricamente: `ΔT_bojo = (B/2)·sin(φ)`, com φ o ângulo de roll previsto — para um navio de 32 m de boca, 5° de roll subtraem ~1,4 m à folga. O GM à chegada deve ser input obrigatório (do agente/comandante, via declaração pré-chegada).

## 3. Logística do Porto e Restrições Físicas do Canal

O enquadramento geográfico do estuário do Tejo possui uma topografia antrópica e natural singular que restringe drasticamente o acesso, especialmente para embarcações que combinam calado profundo com calado aéreo extremado. As lacunas da versão preliminar da ferramenta negligenciam em absoluto a arquitetura dos canais ditada por normas internacionais (PIANC) e a barreira intransponível das infraestruturas suspensas.

### 3.1. Restrições de Calado Aéreo (Air Draft) e Catenárias de Alta Tensão

O estrangulamento primário para a navegação interior no Porto de Lisboa rumo aos terminais a montante é a Ponte 25 de Abril, uma infraestrutura rodoviária e ferroviária que atravessa o gargalo do rio. O vão principal desta ponte suspensa define uma altura livre estática acima do nível de referência da água de 70 metros. No entanto, a passagem segura sob tabuleiros suspensos é um cálculo complexo. Devem ser contabilizadas contingências operacionais como os carros de manutenção permanentemente suspensos no intradorso do tabuleiro, catenárias de alta tensão suplementares (frequentemente cruzando o estuário com alturas na ordem dos 25 a 55 metros) e a flecha da ponte devida à carga rodoviária extrema e dilatação térmica. [1][2]

Um erro comum nos sistemas genéricos é assumir que o aumento do calado dinâmico (squat) é benéfico por aumentar a folga aérea de forma correspondente. As boas práticas de marinharia desaconselham esta presunção; o planeamento do air draft deve isolar o caso mais desfavorável: a embarcação pode sofrer uma falha de propulsão imediata (blackout) debaixo do tabuleiro, anulando instantaneamente o efeito de squat. [1][2]

Impacto na Decisão Go/No-Go: O sistema deverá ser populado com as batimétricas invertidas, registando as cotas de todos os obstáculos verticais. A fórmula rigorosa será: ⁠Folga Aérea = 70m - (Altura da Maré Predita no Instante da Passagem + Altura Máxima Física do Navio acima da Quilha - Calado Estático Atual)⁠. Caso a folga resultante seja inferior a uma margem restrita de segurança normativa (usualmente 2 a 3 metros), o algoritmo bloqueia irrevogavelmente a passagem àquela hora, reagendando a aproximação para a fase mais aproximada de baixa-mar e submetendo a viabilidade aos restantes parâmetros (onde a baixa-mar inevitavelmente estrangulará o UKC). [1][2]

> **🔎 CRÍTICA (3.1):** Dois pontos a validar/precisar. (a) A fórmula está conceptualmente certa mas **omite o datum de referência**: a cota de 70 m deve estar referida a um plano definido (ZH — Zero Hidrográfico, ou nível médio) — se a cota publicada for referida ao nível médio e a maré à ZH, a fórmula sem conversão erra sistematicamente ~2 m. Confirmar na Carta Náutica IH qual o datum da altura livre publicada. (b) A frase "batimétricas invertidas" é jargão pouco rigoroso — o termo correto é **carta de obstáculos verticais / vertical clearance chart**.
>
> **➕ COMPLEMENTO (3.1):** (a) o **calado aéreo do navio também varia com o consumo** de combustível/lastro durante a viagem — usar o valor declarado à chegada, não o de partida; (b) para navios-limite (grandes cruzeiros a demandar Santa Apolónia/Lisboa Cruise Terminal não passam a ponte, mas graneleiros para o Barreiro/CUF e navios para Alcochete sim), considerar a exigência de **confirmação por sensor** (medição laser/rangefinder do air draft real à entrada da barra, prática usada noutros portos com pontes-limite).

### 3.2. Geometria Dinâmica e Largura dos Canais (Diretrizes PIANC)

A Associação Mundial de Infraestruturas de Transporte Marítimo (PIANC) fornece o padrão ouro internacional para o dimensionamento seguro de canais portuários. A largura absoluta do canal em linha reta não é uma constante aceitável num sistema preditivo. De acordo com a PIANC, a largura requerida é o somatório da largura básica de manobra e de diversas margens de correção condicionais:

| Componente | Parâmetro PIANC | Implicação no Cálculo |
|---|---|---|
| W_BM | Faixa Básica de Manobra | Varia de 1.3B (Excelente Manobrabilidade) a 2.0B (Fraca Manobrabilidade) da boca (B) do navio. |
| W_i | Velocidade e Vento | Correções que exigem adição de margens extra se a velocidade for elevada ou se o navio sofrer forte abatimento por vento cruzado (e.g., adicionar 0.4B a 1.2B). |
| W_BR / W_BG | Distância aos Taludes/Margens | Fator crítico para mitigar o Bank Effect. Substratos inclinados requerem menos margem (0.1B a 0.5B) que paredes rígidas (1.3B). |

Impacto na Decisão Go/No-Go: A ferramenta tem de auditar transversalmente cada secção do canal de aproximação escolhido. Se o somatório da faixa básica de manobra com as penalizações de vento atual, correntes oblíquas e o tipo de margem ditar uma largura teórica que exceda a largura física disponível no canal batimétrico, o sistema tem de inviabilizar a manobra.

> **➕ COMPLEMENTO (3.2):** Faltam três componentes PIANC relevantes para o Tejo: **W_p (separação entre navios em canal de duas vias)**, as margens adicionais por **corrente de través e corrente longitudinal** (tabeladas separadamente do vento na PIANC 121, e dominantes no Tejo), e por **auxílios à navegação/visibilidade** (margem maior com balizamento fraco ou navegação noturna). Notar ainda que a PIANC distingue **Concept Design** (as tabelas citadas) de **Detailed Design** (simulação): as tabelas são conservadoras; para os troços mais restritivos justifica-se validação por simulação fast-time/real-time, e os resultados podem ser embebidos na ferramenta como *lookup tables* por troço/navio-tipo.

### 3.3. Configuração e Saturação das Bacias de Rotação

A atracação com proa voltada para a saída exige, invariavelmente, uma manobra de inversão de marcha (turn around) utilizando as bacias de rotação do porto. As diretrizes normativas internacionais da PIANC estipulam que o diâmetro da bacia não é estático; este baliza-se em dimensões de 1.2 a 1.3 vezes o comprimento de fora a fora (LOA) para bacias circulares ou trapezoidais compactas em cenários de tempo calmo, podendo alcançar rácios superiores em áreas expostas a fortes rajadas de vento e correntes persistentes. No Rio Tejo, as condições de geometria estão severamente limitadas, nomeadamente na zona de Alcântara, onde infraestruturas históricas fixam restrições absolutas, como o impedimento rígido de entrada a navios com dimensões de boca superiores a 24 metros. [1][2][3]

Adicionalmente, perante navios de dimensões notáveis, a execução destas manobras em diâmetros limiares torna-se temerária fora de janelas cinéticas favoráveis. Por regulamento interno, navios de comprimento superior a 150 metros são forçados a realizar a sua manobra de atracação na estofa da maré — momento de acalmia corrente — anulando a pressão lateral assimétrica que atuaria rotacionalmente sobre o seu eixo de pivô durante a viragem. [1][2][3]

Impacto na Decisão Go/No-Go: O processamento algorítmico deve cruzar as dimensões do navio com a largura funcional da bacia definida para o local. Se o LOA introduzido superar o fator recomendável da PIANC para a topologia designada (e.g., > 1.2 x LOA numa configuração desprotegida) sem que exista contingente massivo de bollard pull auxiliar, ou violar normas restritas como as bocas de 24m para as docas internas, a admissão na área tem de ser taxativamente refutada. [1][2][3]

> **🔎 CRÍTICA (3.3):** "Saturação" figura no título mas o corpo só trata geometria. A **saturação temporal** (ocupação da bacia/berço por outro navio, janelas de ferries) é uma variável distinta e não tratada — ver complemento na secção 7.
>
> **➕ COMPLEMENTO (3.3):** Confirmar os valores de 24 m (docas de Alcântara) e 150 m/estofa contra o regulamento em vigor da APL, com citação de artigo. Acrescentar a variável **estado de ocupação dos berços adjacentes**: um navio atracado no berço contíguo reduz o diâmetro útil real da bacia de rotação face ao teórico — o sistema deve calcular a bacia **funcional do dia**, não a de projeto.

## 4. Requisitos Auxiliares (A Logística de Tração e Reboque)

A morfologia hidrológica e as restrições logísticas de um porto estuarino forçam a que grande parte das manobras complexas dependa não da propulsão interna, mas do recurso maciço ao serviço de reboques. A sua ausência, desadequação ou ineficiência traduzem-se imediatamente num desvio dos padrões de segurança. [1][2][3]

### 4.1. Cálculo Dinâmico de Força de Tração (Bollard Pull)

O bollard pull (BP) consubstancia a força de tração contínua exercida por um rebocador a velocidade nula, sendo a métrica primária e insubstituível na avaliação da mitigação do risco de desgoverno. É impraticável a existência de uma ferramenta moderna que trabalhe assente em solicitações subjetivas ou indicações generalistas relativas ao número de unidades de socorro/reboque. O cálculo determinístico obriga a estimar o BP total necessário para contrapor simultaneamente a fricção cinemática ditada pelas correntes de maré e o abatimento severo provocado pelos ventos incidentes na área exposta do navio. [1][2][3]

A distribuição destas frotas está intrinsecamente dependente da classe de empresas concessionárias licenciadas para a atividade no porto, bem como da natureza tática das suas unidades. As frotas estacionadas em Lisboa, operadas por entidades referenciadas como a Rebonave ou a ETE, detêm perfis de potência e arquitetura dispersos; é frequente operar com rebocadores portuários que fornecem desde os típicos 8t, ascendendo a unidades mais robustas de 14t, 16t, ou capacidades supracitadas em equipamentos mais recentes e azimutais. [1][2][3]

> **➕ COMPLEMENTO (4.1):** O bollard pull nominal **degrada-se com a velocidade** — um rebocador de 50 t de BP estático entrega uma fração disso a 4–6 nós (curva BP-velocidade), e a capacidade de trabalho em modo *indirect towing* depende do tipo (ASD/tractor Voith vs. convencional). Para escolta na barra com ondulação, os rebocadores convencionais de porto podem ser **inutilizáveis por limite de mar** — o sistema deve guardar, por rebocador: tipo, BP estático certificado, limite operacional de Hs, e disponibilidade (manutenção/escala). Acrescentar ainda a variável **ponto de amarração do reboque no navio** (SWL dos cabeços do navio pode ser o elo fraco, não o rebocador).

### 4.2. Número de Unidades, Exigências e Escoltas Normativas

A parametrização do número de meios obedece também a ditames impositivos da APL. Determina a regulamentação em vigor que, nas manobras de entrada, saída ou viragem efetuadas no interior das docas fechadas ou secas, sempre que a arqueação bruta (Gross Tonnage - GT) da embarcação supere o limiar de 1.000 toneladas, o recurso a auxílio de reboque torna-se imperativo, impondo mesmo a utilização supletiva das unidades do porto nos moldes regulados. Além deste condicionalismo estrutural, manobras especiais obrigam à submissão a regras dedicadas; operações de navegação realizadas a montante da Ponte 25 de Abril em terminais sensíveis do estuário, especialmente relativas a embarcações transportando substâncias químicas de alta perigosidade (como o Acrilonitrilo), tornam legalmente compulsório o acompanhamento contínuo por rebocador com potência avalizada de modo prévio. Por fim, episódios pontuais de nevões ou cerrada cerração, os chamados fenómenos de visibilidade restrita, implicam a paragem imediata dos comboios e trens de reboque vulgar, autorizando a continuidade apenas de modo excecional com autorização prévia ou se forem adotadas as rígidas posições "de braço dado", nas quais o horizonte do radar nunca seja comprometido pelo rebocado. [1][2][3]

> **🔎 CRÍTICA (4.2):** "Nevões" em Lisboa é implausível como cenário operacional — o fenómeno de visibilidade restrita relevante no Tejo é o **nevoeiro de advecção** (frequente de madrugada, sobretudo no outono/inverno). Rever a redação. A regra do GT > 1.000 e o caso Acrilonitrilo devem ser citados com artigo do regulamento.

Impacto na Decisão Go/No-Go: A base de dados logística vinculada à ferramenta deverá possuir a inventariação das frotas ativas com respetivos perfis de bollard pull contínuo. Durante o planeamento, o sistema calculará em background a oposição resultante das forças cruzadas. Ao extrair os rebocadores requisitados (e.g., 2 unidades de 16t = 32t) e subtraindo este fator às necessidades de retenção transversal e longitudinal, obtém-se a razão crítica. Se o rácio matemático ⁠(Força Ambiental / BP Acumulado)⁠ ultrapassar um patamar sensível na ordem dos 0.8 (assegurando assim os 20% normais de reserva de contingência sugeridos pelas boas práticas), a aproximação e atracagem tem de ser estancada pelo algoritmo preventivamente. A ferramenta rejeita, de igual modo, a programação da janela horária se for inserido um navio superior a 1.000 GT sem alocação concomitante de assistência na proa ou popa para docas limitadas. [1][2][3]

## 5. Restrições Regulamentares e de Carga

Por último, o esqueleto legislativo e legal que arbitra a triagem do tráfego marítimo no Tejo transcende os meros exercícios teóricos de mecânica de fluidos ou engenharia de arquitetura naval. Abster-se de incorporar as regras coercivas da Capitania e da APL é construir um projeto inexato, que proporá cenários de entrada legalmente interditados e inoperantes de facto.

### 5.1. Janelas de Maré (Estofa, Enchente e Vazante)

A dinâmica e progressão contínua da maré induzem comportamentos assimétricos de corrente. O Regulamento da Autoridade Portuária da APL preconiza uma teia disciplinadora cronométrica rígida baseada nesta variação. O sistema deve traduzir as seguintes lógicas em condições estritas de processamento:

> **🔎 CRÍTICA (5.1):** **Secção sem corpo** — as "lógicas" prometidas não são enumeradas no original.
>
> **➕ COMPLEMENTO (5.1) — Lógicas de processamento em falta:**
> - **Cálculo da estofa local, não tabular:** a estofa da corrente **não coincide** com a preia-mar/baixa-mar do marégrafo (desfasamento que varia por local no estuário, podendo atingir dezenas de minutos entre a barra e o Mar da Palha). O sistema deve usar desfasamentos calibrados por troço (cartas de correntes do IH ou modelo hidrodinâmico), nunca a hora da maré de Cascais diretamente.
> - **Assimetria enchente/vazante:** no Tejo a vazante é tipicamente mais intensa e mais longa que a enchente (reforçada pelo caudal fluvial). Em períodos de **cheia do Tejo (inverno, descargas de barragens espanholas)**, a vazante pode exceder largamente os valores tabelares e a estofa "encolher". O caudal fluvial (dados SNIRH/APA) deve ser input do modelo de correntes.
> - **Marés vivas vs. mortas:** as janelas viáveis variam quinzenalmente; o planner deve projetar as janelas para o ciclo lunar completo, permitindo ao agente escolher ETA com antecedência.
> - **Regras APL a codificar como restrições duras (a validar no regulamento):** >5.000 GT restrito a estofa/enchente; >150 m LOA atracação em estofa (±45 min); calado limite condicionado à altura de maré mínima por canal (regra "tidal window" clássica: `h_maré ≥ calado + UKC_política − sonda_ZH`).

### 5.2. Limites de Visibilidade e Restrições de Períodos Noturnos

Um conjunto propulsor invulnerável não salva um cenário de completa privação visual. O tráfego marítimo pressupõe navegação segura assente, em primeira e última instância, na referenciação exterior.

> **🔎 CRÍTICA (5.2):** **Secção sem corpo** — só existe a frase introdutória.
>
> **➕ COMPLEMENTO (5.2) — Conteúdo em falta:**
> - **Visibilidade:** limiar operacional típico de 1 milha náutica (referido na tabela final) para suspensão de manobras; abaixo disso, entrada/saída sujeita a autorização do Capitão do Porto/VTS. O sistema deve ingerir visibilidade medida (visibilímetros da rede APL/IPMA) e prevista, e distinguir nevoeiro na barra vs. no interior (frequentemente diferentes).
> - **Período noturno:** validar no regulamento quais os terminais/classes de navio com **interdição ou condicionamento noturno** (historicamente, navios de maior porte e cargas perigosas têm restrições de manobra noturna em certos terminais; a passagem da barra de noite com ondulação agrava a exigência). O algoritmo deve calcular nascer/pôr do sol e marcar janelas noturnas como condicionais para as classes aplicáveis.
> - **Embarque do piloto:** variável totalmente ausente do documento — se a ondulação na zona de embarque de pilotos (pilot boarding ground) exceder o limite de segurança da lancha (tipicamente Hs ~2,5–3 m, dependente do meio), **não há manobra possível independentemente de tudo o resto**. Este é frequentemente o fator limitante real na barra de Lisboa em temporais de NW e deve ser um gate de primeiro nível no algoritmo.

### 5.3. Trânsito de Cargas Perigosas (Hazmat) e Condicionantes Extraordinárias

O tecido normativo torna-se marcadamente punitivo e exigente face à passagem de bens enquadrados em riscos ambientais gravíssimos. Transportadores especializados de gás liquefeito, tanto de petróleo como gás natural (LPG/LNG), bem como petroleiros com produtos químicos sofisticados cujas atmosferas internas de tanques não atestem certificação comprovada de total desgaseificação (parâmetros de segurança de O2 > 20,5% e Limite Inferior de Explosividade - LEL < 1%) ou de efetiva inertização (O2 < 8% e em alguns gases de LEL < 2%), padecem de crivos formidáveis. Além do rastreamento VHF (obrigatório manter canal 13 ativo com visibilidade duvidosa), tais tráfegos assumem a posição de super prioridade limitante para o restante porto comercial, sendo acompanhados fisicamente e obrigando as pilotagens a regimes procedimentais de máxima contenção. A área a Este da Torre VTS é interdita à ausência dos pilotos oficias na regência das referidas massas.

| Métrica e Parâmetro Regulamentar | Imposição APL / PIANC (Porto de Lisboa) | Procedimento e Resolução Algorítmica da Manobra (Go/No-Go) |
|---|---|---|
| Arquitetura (Arqueação > 5.000 GT) | Regência vinculativa a operar sob alçada de Estofa ou de Enchente. | Bloqueio incontornável no planner logístico se for projetada sobre o ciclo de maré de vazante (ebb tide). |
| Dimensão Longitudinal (> 150m LOA) | Movimentação final de atracação enclausurada e adstrita à janela de Estofa da Maré. | Exibição de sugestão mandatória temporal que coincida exatamente com a estreita variação de estofa (+/- 45 minutos da tabela marégrafa com correção topográfica local). |
| Superfície Exposta e Vento (Classe RO-RO) | Interdição generalizada com picos sustentados de vento ou rajadas registadas em linha superior aos 20 nós. | Sinalização: If [Tipo=RORO] and [Vento_Max > 20kt] = NO-GO incondicional; Status=Abort. |
| Aparelho de Monitorização / Visuais | Existência de nevoeiro que deprima a visibilidade para limites < 1 milha náutica. | Suspensão automática de predições algorítmicas, emissão de alerta global de "Piloto-Mestre Override" forçando controlo manual externo da validação. |
| Profundidade Estrutural (Calado Máximo) | Navegação e imersão superior aos 10.5 metros aferidos e estáticos. | O algoritmo despacha nota compulsória a requerimento de avaliação especial e sancionamento da Direção de Segurança e Pilotagem do Porto. |

> **🔎 CRÍTICA (5.3):** O canal VHF de trabalho do VTS/pilotagem deve ser confirmado (o documento afirma canal 13 "com visibilidade duvidosa" — verificar os canais oficiais do VTS Lisboa e da estação de pilotos no regulamento/ALRS). O calado de 10,5 m como gatilho de avaliação especial deve indicar **a que canal se aplica** (o valor não pode ser único para toda a rede — o canal da barra e os canais do Barreiro/Alcochete têm sondas muito diferentes).
>
> **➕ COMPLEMENTO (5.3):** Acrescentar as **zonas de segurança móveis** típicas de tráfego hazmat (raio de exclusão em navegação e à atracagem, interdição de cruzamento na passagem da ponte), e o efeito de rede: uma escala LNG/LPG **congela janelas de outros navios** — o planner deve modelar isto como restrição de recurso partilhado (o canal é um recurso com capacidade 1 durante o trânsito hazmat).

---

> **➕ NOVAS SECÇÕES COMPLEMENTARES (variáveis ausentes do documento original)**

## 6. Interação com o Cais e Permanência no Berço (Complemento)

O documento trata a aproximação e a atracagem, mas a decisão Go/No-Go deve estender-se à **viabilidade de permanência segura no berço**:

- **Energia de acostagem:** a energia cinética absorvida pelas defensas `E = ½·m·Cm·v²` (com massa adicionada hidrodinâmica Cm ≈ 1,5–1,8) define a velocidade máxima de aproximação perpendicular ao cais por classe de defensa (norma PIANC WG33/BS 6349). Berços antigos de Lisboa têm defensas com capacidades muito distintas — o limite de velocidade de contacto deve ser parametrizado por berço.
- **Ondas de longo período e seichas:** em cais expostos (Alcântara, Santa Apolónia com temporais de SW), oscilações de longo período causam *surging* dos navios amarrados, rotura de cabos e interrupção de operações. Se o espectro previsto contiver energia significativa em períodos > 25 s, o sistema deve alertar para plano de amarração reforçado ou desaconselhar a escala.
- **Passing ship no berço:** navios de grande porte a transitar no canal geram forças de sucção sobre navios já atracados nas imediações — relevante em Alcântara/Rocha com o corredor de tráfego próximo. Restrição de velocidade de trânsito junto a berços ocupados a codificar.
- **Vento no berço para operações:** gruas de terminal e pórticos têm limites próprios de vento (tipicamente 20–25 m/s stop total, limites inferiores para contentores vazios) — irrelevante para a manobra mas relevante para a decisão comercial de escala, e útil como camada opcional do sistema.

## 7. Tráfego, Recursos Partilhados e Coordenação VTS (Complemento)

O documento modela o navio isolado. Um DSS de porto real decide sobre um **sistema com concorrência**:

- **Tráfego de ferries:** o estuário tem dezenas de travessias diárias Transtejo/Soflusa cruzando perpendicularmente os corredores comerciais (Cais do Sodré–Cacilhas, Belém–Trafaria, Terreiro do Paço–Barreiro/Montijo/Seixalinho). As janelas de manobra de grandes navios em zonas de cruzamento devem ser deconflituadas com os horários de ferries — restrição determinística e conhecida, trivial de codificar e de alto valor.
- **Capacidade do canal como recurso:** trânsitos one-way em troços restritos, prioridade hazmat, e ocupação de bacias de rotação devem ser modelados como recursos com calendário (abordagem de *resource-constrained scheduling*), não apenas como verificações físicas independentes.
- **Integração AIS/VTS:** o sistema deve consumir o feed AIS do VTS para (a) validar em tempo real que o plano aprovado está a ser cumprido (desvios de rumo/velocidade → alerta), e (b) alimentar o módulo de passing ship com o tráfego efetivo, não apenas o planeado.
- **PPU (Portable Pilot Unit):** o output do DSS deve ser exportável para as PPUs dos pilotos (rota, janelas, velocidades-alvo por waypoint, UKC previsto por troço), fechando o ciclo entre planeamento e execução.

## 8. Arquitetura de Decisão, Incerteza e Fator Humano (Complemento)

- **Semântica do output:** substituir o binário por **GO / GO CONDICIONAL / NO-GO**, sendo que GO CONDICIONAL lista explicitamente as mitigações que convertem o estado (n.º e tipo de rebocadores, STW máxima por troço, janela horária, reagendamento para estofa). É este o modo de operação natural de um porto.
- **Propagação de incerteza:** cada input previsto (vento, Hs, corrente, nível de maré) deve carregar a sua incerteza; a decisão deve ser avaliada no **percentil conservador** (p.ex. P90 das forças ambientais vs. P10 das capacidades), e não no valor central. Janelas cuja viabilidade dependa de a previsão acertar exatamente são, na prática, NO-GO.
- **Abort points e plano de contingência:** o plano gerado deve identificar, por trânsito, os **pontos de não retorno** e as ações de contingência em cada troço (fundeadouros de emergência — p.ex. fundeadouros da barra e do Mar da Palha —, rumo de escape, rebocador de escolta em posição). Um Go sem plano de aborto é um plano incompleto.
- **Override e registo:** o piloto/VTS pode sempre sobrepor-se ao sistema, mas todo o override deve ser **registado com justificação** — isto protege juridicamente os intervenientes e cria o dataset de calibração do modelo.
- **Validação e calibração contínua:** cada manobra executada deve ser comparada com a previsão (squat previsto vs. medido por RTK/PPU, forças estimadas vs. rebocadores efetivamente usados). O ciclo previsão-observação-recalibração é o que distingue um DSS credível de uma folha de cálculo glorificada.
- **Governação dos dados de referência:** batimetria, cotas de obstáculos, regulamentos e frota de rebocadores mudam. Definir *owners*, periodicidade de revisão e versionamento dos dados mestres — um Go/No-Go calculado sobre batimetria desatualizada é pior do que nenhum sistema, porque gera falsa confiança.

---

## Conclusões Analíticas para o Algoritmo Estrutural

O delineamento e sucesso de uma ferramenta de Decision Support sofisticada aplicável à aproximação portuária e à finalização perigosa da atracagem em águas do Porto de Lisboa baseia-se na imperiosa metamorfose dos paradigmas estáticos de consulta metereológica para um ecossistema inteiramente interativo, profundamente cinemático e, sobretudo, refém sem escapes dos articulados do regulamento de capitania e da APL. [1][2]

As omissões verificadas na configuração primitiva residiam fundamentalmente na negligência de dois campos de força colossais na regência do navio: a órbita das restrições físicas determinísticas imutáveis (onde constam folgas milimétricas de calados aéreos, secções batimétricas assimétricas penalizadoras segundo a PIANC, e geometria asfixiante de velhas bacias) e a órbita das forças hidrodinâmicas e cinéticas mutáveis e reativas (fricção do squat, declínio acentuado e rotura dos fluxos orientados ao leme perante aproximações nefastas em correntes de popa, e a agressiva pressão transversal que fustiga a área vélica superlativa sob vento lateral).

A preocupação levantada pela pilotagem sênior, de recusa em realizar abordagens críticas encurralados pela mortífera corrente de popa, apresenta integral chancela e robusta fundação na documentação dos tratados de hidrodinâmica de governo e manobrabilidade. O novo sistema a desenhar para a teia portuária do Rio Tejo requererá necessariamente interfaces de dados georreferenciados (shapefiles) capazes de cruzar perfis e vetores contínuos de correntes com o rumo pretendido e a SOG, evidenciando as localizações mortas onde o leme decairá sem efeito sustentável.

Apenas aliando a simulação do efeito afundante e contínuo baseada na fórmula logarítmica iterativa para águas confinadas (UKC dinâmico e exato); a extração severa e imediata da resistência imposta pela arquitetura do vaso comunicante contra o poder opressor de rajadas intensas cruzado num sistema de vetores equilibrados com a exata tração real (Bollard Pull) e a totalidade do catálogo restritivo da APL no tocante às sagradas janelas de tempo, correntes e marés (enfoque nas obrigatoriedades de estofas e proibições de RO-RO a >20 nós); poderá, com propriedade, o software antecipar a margem temporal da manobra, escudando e suportando inequivocamente a pesada responsabilidade da tomada de decisão derradeira do Piloto. Assumirá, no final, o pódio como o expoente mais elevado no garante e prevenção situacional de acidentes e proteção infraestrutural à disposição dos gestores da atividade marítima de elite.

> **🔎 CRÍTICA (conclusão e estilo geral):** O registo é excessivamente barroco para um documento técnico ("mortífera", "sagradas janelas", "poder opressor", "atividade marítima de elite", "vaso comunicante" usado incorretamente). Numa versão para stakeholders (APL, pilotagem, engenharia), recomenda-se reescrita em registo técnico sóbrio — o conteúdo perde credibilidade com adjetivação hiperbólica. Nota: "fórmula logarítmica iterativa" para o squat não corresponde a nenhuma fórmula padrão (Barrass, ICORELS, etc. são algébricas) — corrigir.
>
> **➕ COMPLEMENTO (roadmap sugerido):** Faseamento pragmático: **Fase 1** — motor de regras determinísticas (regulamento APL + janelas de maré + limiares por classe de navio): baixo risco, alto valor imediato. **Fase 2** — UKC dinâmico (squat + resposta a ondulação + marégrafo em tempo real). **Fase 3** — balanço de forças (vento/corrente vs. thrusters/rebocadores) e GO CONDICIONAL com mitigações. **Fase 4** — integração AIS/VTS/PPU, calibração com dados de manobras reais e transição para margens probabilísticas. Cada fase é útil por si e valida a seguinte.

---

## Referências

1. https://www.scribd.com/document/857415592/Marcom-WG30-Superseded-WG49-Approach-Channels-a-Guide-for-Design1997a (Approach Channel Design Guidelines | PDF | Ships | Transport - Scribd)
2. https://shaghool.ir/Files/NAVIGATION-PIANC-Harbour-Approach-Channels-Design-Guidelines-2014.pdf (PIANC Report n° 121 - 2014 Harbour approacH cHannels Design guiDelines)
3. https://www.jornaldaeconomiadomar.com/mares-ilusao-portos-lucidez/ (Reflexões Sobre Portos de Águas Profundas em Portugal - Jornal de Economia do Mar)
4. https://cadettraininginformation.yolasite.com/resources/Ship%20Handling.pdf (Ship Handling.pdf - Cadet Training Information)
5. https://pt.scribd.com/document/625966545/Catenaria-Basica-25-KV-50-HZ (Catenária Ferroviária: Estrutura e Funcionamento)

> **➕ COMPLEMENTO (referências recomendadas a acrescentar):**
> - PIANC Report 121 (2014) — *Harbour Approach Channels Design Guidelines* (fonte primária, edição oficial PIANC, não mirror).
> - PIANC WG 116 — *Safety Aspects Affecting the Berthing Operations of Tankers*; PIANC WG 33 / BS 6349-4 — defensas e energia de acostagem.
> - Barrass, C.B. & Derrett, D.R. — *Ship Stability for Masters and Mates* (fórmulas de squat).
> - IMO Res. A.601(15) — Pilot Card/Wheelhouse Poster; IMO Res. MSC.137(76) — Standards for Ship Manoeuvrability.
> - Regulamento de Exploração do Porto de Lisboa (APL) e Edital da Capitania do Porto de Lisboa — versões em vigor, com citação de artigos para cada regra codificada.
> - Instituto Hidrográfico — Tabelas de Marés, cartas de correntes do estuário do Tejo, cartas náuticas oficiais.
> - OCIMF — *Mooring Equipment Guidelines (MEG4)* — coeficientes de vento/corrente sobre cascos.
