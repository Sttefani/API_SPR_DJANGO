# 📚 INSTRUÇÕES PARA IMPORTAÇÃO DE LAUDOS

## 🎯 COMANDOS DISPONÍVEIS

### 1️⃣ IMPORTAR LAUDOS DO HD

Este comando copia os PDFs do HD para o banco de dados Django.

---

## ⚙️ OPÇÕES DE IMPORTAÇÃO

### ✅ OPÇÃO 1: Importar POUCOS (Recomendado para teste)
```bash
# Importa apenas 3 PDFs para testar
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --limite 3

# Importa 10 PDFs
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --limite 10

# Importa 50 PDFs
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --limite 50
```

---

### ✅ OPÇÃO 2: Filtrar por ANO
```bash
# Importa APENAS laudos de 2024
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --ano 2024

# Importa 10 laudos de 2024
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --ano 2024 --limite 10

# Importa 100 laudos de 2023
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --ano 2023 --limite 100
```

---

### ⚠️ OPÇÃO 3: Importar TODOS (CUIDADO!)
```bash
# SEM --limite = importa TODOS os PDFs da pasta!
# Use apenas se tiver certeza e bastante espaço em disco
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/"
```

---

## 2️⃣ INDEXAR LAUDOS (Vetorização)

**IMPORTANTE:** Após importar os PDFs, você DEVE indexá-los para que a IA consiga usá-los!
```bash
# Indexa todos os laudos não processados
python manage.py indexar_laudos

# Forçar reindexação de TODOS (mesmo os já processados)
python manage.py indexar_laudos --forcar
```

---

## 📋 FLUXO COMPLETO RECOMENDADO

### 🧪 TESTE INICIAL (Primeira vez)
```bash
# 1. Importa 1 PDF para teste
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --limite 1

# 2. Indexa esse 1 PDF
python manage.py indexar_laudos

# 3. Teste a API no Postman/Insomnia
# Se funcionar, continue...

# 4. Importa mais 10 PDFs
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --limite 10

# 5. Indexa esses novos PDFs
python manage.py indexar_laudos
```

---

### 🚀 IMPORTAÇÃO EM PRODUÇÃO
```bash
# Importa laudos por ano (recomendado)
python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --ano 2024 --limite 100
python manage.py indexar_laudos

python manage.py importar_laudos_hd "D:/1.1 LAUDOS PERICIAIS/" --ano 2023 --limite 100
python manage.py indexar_laudos

# E assim por diante...
```

---

## ✅ RECURSOS IMPORTANTES

### 🔄 Ignora Duplicados
- O comando verifica se o laudo já existe pelo título
- Se rodar 2x o mesmo comando, ele pula os arquivos já importados

### 📊 Tipos de Exame Detectados Automaticamente
O sistema detecta o tipo de exame pelo nome do arquivo:
- **THC**: Se contém "thc" ou "droga" no nome
- **DNA**: Se contém "dna" no nome
- **BALÍSTICA**: Se contém "balistica" ou "arma" no nome
- **LOCAL DE CRIME**: Se contém "local" ou "crime" no nome
- **GERAL**: Qualquer outro tipo

### 📁 Estrutura de Pastas
Os PDFs são copiados para: `media/laudos_referencia/`

---

## ⚠️ AVISOS IMPORTANTES

1. **Espaço em Disco**: Cada PDF será copiado para o Django, verifique espaço disponível
2. **Tempo de Processamento**: A indexação pode demorar (varia conforme tamanho dos PDFs)
3. **Memória RAM**: Indexar muitos PDFs de uma vez pode consumir bastante memória
4. **Backup**: Sempre mantenha backup dos PDFs originais no HD

---

## 🐛 PROBLEMAS COMUNS

### ❌ "Pasta não encontrada"
- Verifique se o caminho está correto
- Use aspas duplas no caminho: `"D:/pasta/"`
- No Windows, use `/` ou `\\` (não apenas `\`)

### ❌ "Nenhum laudo para processar"
- Você já importou e indexou todos os laudos
- Use `--forcar` para reindexar

### ❌ Erro ao ler PDF
- Alguns PDFs podem estar corrompidos ou protegidos
- O sistema pula esses arquivos e continua com os demais

---

## 📞 SUPORTE

Para mais informações, consulte a documentação do sistema ou contate o desenvolvedor.

---

**Última atualização:** Outubro/2025
```

---

## ✅ **PRONTO!**

Agora você tem um arquivo de instruções completo! Salve esse arquivo como:
```
IA/INSTRUCOES_IMPORTACAO.md