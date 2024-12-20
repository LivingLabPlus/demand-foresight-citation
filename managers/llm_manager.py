import streamlit as st
import google.generativeai as genai
from openai import OpenAI

summarize_prompt_template = """分析階段:
仔細閱讀整個章節或資料。
將章節分解成段落。
對每個子句或段落進行分析，判斷是否包含與主題無關的信息。
過濾階段:
基於你在分析階段的判斷，重新整理文本，排除所有無關信息。
確保過濾後的文本保持連貫性和完整性。
輸出階段:
針對每個章節，輸出重寫後的內容。
吸引眼球的標題: 思考如何用一句話概括章節重點，並用更具吸引力的方式表達。
一句話說明重點: 接著用一句話說明本章節的核心概念。
提供更具體的例子和細節: 使用更具體的例子、細節或數據等，讓內容更生動具體深刻。
調整語氣: 避免使用 AI 常用的詞彙，也不要用中國的詞彙，確保使用人類自然口語，不要泛泛而談，要具體。
視覺分隔: 考慮使用項目符號或列表形式來呈現多個觀點，這可以讓信息更具可讀性和吸引力。
簡化語言避免 AI 用語: 避免重複語句或文字，用詞更精準且易於理解，進一步改善各段落之間的連貫性，使過渡更自然。
深層意涵: 在最後一段提供「背後的深層意涵或影響」，用兩句話點出，深層後的深層意義，不要八股。
Hashtags: 添加相關的 hashtags 可以讓你的內容更容易被找到。
記住，目標是找出真正重要的內容。讓內容更清晰、更生動、更具吸引力，不能自己編。
請使用繁體中文和 markdown 格式輸出
<document>{content}</document>"""


class LLMManger:
    def __init__(self):
        self.openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        self.gemini_client = genai.GenerativeModel("gemini-1.5-pro-002")

    def get_embeddings(self, texts, model="text-embedding-3-small"):
        embeddings = self.openai_client.embeddings.create(
            input=texts, model=model)
        embeddings = [d.embedding for d in embeddings.data]
        return embeddings

    def summarize(self, content):
        try:
            prompt = summarize_prompt_template.format(content=content)
            response = self.gemini_client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=8192
                ),
            )
            return response.text
        except Exception as error:
            print("Error while summarization:", error)
            return error
