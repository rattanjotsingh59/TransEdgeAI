from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from .structure_outputs import *
from .prompts import *
from config import config_manager

class Agents():
    def __init__(self):
        # Get configuration
        config = config_manager.get_config()
        api_key = config.ai.gemini_api_key

        # Initialize Gemini with API key
        gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            temperature=0.1,
            google_api_key=api_key
        )
        
        # QA assistant chat with API key
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=api_key
        )
        vectorstore = Chroma(persist_directory="db", embedding_function=embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

        # The rest of your agent initialization code remains the same
        email_category_prompt = PromptTemplate(
            template=CATEGORIZE_EMAIL_PROMPT, 
            input_variables=["email"]
        )
        self.categorize_email = (
            email_category_prompt | 
            gemini.with_structured_output(CategorizeEmailOutput)
        )

        generate_query_prompt = PromptTemplate(
            template=GENERATE_RAG_QUERIES_PROMPT, 
            input_variables=["email"]
        )
        self.design_rag_queries = (
            generate_query_prompt | 
            gemini.with_structured_output(RAGQueriesOutput)
        )
        
        qa_prompt = ChatPromptTemplate.from_template(GENERATE_RAG_ANSWER_PROMPT)
        self.generate_rag_answer = (
            {"context": retriever, "question": RunnablePassthrough()}
            | qa_prompt
            | gemini
            | StrOutputParser()
        )

        writer_prompt = ChatPromptTemplate.from_messages([
            ("system", EMAIL_WRITER_PROMPT),
            MessagesPlaceholder("history"),
            ("human", "{email_information}")
        ])
        self.email_writer = (
            writer_prompt | 
            gemini.with_structured_output(WriterOutput)
        )

        proofreader_prompt = PromptTemplate(
            template=EMAIL_PROOFREADER_PROMPT, 
            input_variables=["initial_email", "generated_email"]
        )
        self.email_proofreader = (
            proofreader_prompt | 
            gemini.with_structured_output(ProofReaderOutput) 
        )