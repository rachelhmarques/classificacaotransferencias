import pandas as pd
import io
import streamlit as st
from decimal import Decimal, ROUND_HALF_UP

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Conciliador de Transferências",
    page_icon="💼",
    layout="wide"
)

def processar_conciliacao(df):
    """
    Função que processa o DataFrame e retorna os resultados.
    Em vez de imprimir, ela retorna uma lista de strings para exibição.
    """
    output_list = []

    # --- 1. Limpeza e Preparação dos Dados ---
    colunas_necessarias = ['Data movimento', 'Valor (R$)', 'Categoria 1', 'Conta bancária']
    if not all(col in df.columns for col in colunas_necessarias):
        st.error(f"Erro: O arquivo precisa conter as seguintes colunas: {colunas_necessarias}")
        return None

    df['Data movimento'] = pd.to_datetime(df['Data movimento'], format='%d/%m/%Y', errors='coerce')

    if pd.api.types.is_numeric_dtype(df['Valor (R$)']):
        pass # Nenhuma ação necessária se já for numérico
    elif pd.api.types.is_object_dtype(df['Valor (R$)']):
        df['Valor (R$)'] = df['Valor (R$)'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce')

    df.dropna(subset=['Data movimento', 'Valor (R$)'], inplace=True)

    # --- 2. Identificação e Junção das Transferências ---
    transferencias_df = df[df['Categoria 1'].isin(['Transferência de Saída', 'Transferência de Entrada'])].copy()
    transferencias_df['Valor Absoluto'] = transferencias_df['Valor (R$)'].abs()

    saidas = transferencias_df[transferencias_df['Categoria 1'] == 'Transferência de Saída'].copy().rename(columns={'Conta bancária': 'Conta Origem'})
    entradas = transferencias_df[transferencias_df['Categoria 1'] == 'Transferência de Entrada'].copy().rename(columns={'Conta bancária': 'Conta Destino'})

    saidas['Contador'] = saidas.groupby(['Data movimento', 'Valor Absoluto']).cumcount()
    entradas['Contador'] = entradas.groupby(['Data movimento', 'Valor Absoluto']).cumcount()

    conciliado_df = pd.merge(
        saidas, entradas, on=['Data movimento', 'Valor Absoluto', 'Contador'], suffixes=('_saida', '_entrada')
    )

    # --- 4. Agrupamento e Cálculo dos Totais ---
    if conciliado_df.empty:
        return [] # Retorna lista vazia se não houver conciliações
        
    conciliado_df['Mês'] = conciliado_df['Data movimento'].dt.to_period('M')
    resultado = conciliado_df.groupby(['Mês', 'Conta Origem', 'Conta Destino'])['Valor Absoluto'].sum().reset_index()

    # --- 5. Formatação da Saída ---
    resultado = resultado.sort_values('Mês')

    for mes, group in resultado.groupby('Mês'):
        inicio_mes = mes.start_time.strftime('%d/%m/%Y')
        fim_mes = mes.end_time.strftime('%d/%m/%Y')
        output_list.append(f"### {inicio_mes} a {fim_mes}")

        for index, row in group.iterrows():
            valor_total = Decimal(row['Valor Absoluto']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            valor_formatado = f"{valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            output_list.append(f"- **Transferência de {row['Conta Origem']} para {row['Conta Destino']}:** R$ {valor_formatado}")
        output_list.append("---") # Adiciona uma linha divisória

    return output_list

# --- Interface do Streamlit ---
st.title(" Ferramenta de Conciliação de Transferências Bancárias")
st.write("Faça o upload da sua planilha (CSV ou Excel) para ver o resumo das transferências mensais.")

uploaded_file = st.file_uploader(
    "Selecione o arquivo",
    type=['csv', 'xlsx', 'xls']
)

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            # Tenta ler com 'latin-1' que é comum em arquivos do Windows em português
            df = pd.read_csv(uploaded_file, delimiter=';', encoding='latin-1')
        else:
            df = pd.read_excel(uploaded_file)
        
        st.success(f"Arquivo '{uploaded_file.name}' carregado com sucesso!")

        with st.spinner("Processando conciliação..."):
            resultado_conciliacao = processar_conciliacao(df)

        if resultado_conciliacao is not None:
            if not resultado_conciliacao:
                st.warning("Nenhuma transferência entre contas (saída e entrada correspondentes) foi encontrada no arquivo.")
            else:
                st.header("Resultado da Conciliação")
                for line in resultado_conciliacao:
                    st.markdown(line)

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
        st.info("Verifique se o arquivo tem a estrutura esperada e as colunas necessárias.")
