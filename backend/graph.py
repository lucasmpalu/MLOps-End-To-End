import os
from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.embeddings import OpenAIEmbeddings
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import StrOutputParser
from tavily import TavilyClient
import graphviz
import yaml
from pgvector import PGVector

#
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not all([OPENAI_API_KEY, TAVILY_API_KEY]):
    raise ValueError("Faltan credenciales! K8s no inyectaron las variables de entorno.")

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

LLM_SERVER_URL = os.getenv("LLM_SERVER_URL", "http://ollama-service:11434/v1") 

llm = ChatOpenAI(
    base_url=LLM_SERVER_URL,
    model="Lucas-Palu-Llama-3.2-3B-trained",
    api_key="ollama",
    temperature=0.1
)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

vector_db = PGVector(
    embeddings=embeddings,
    collection_name="historiales_clinicos",
    connection=os.getenv("DATABASE_URL"),
    use_jsonb=True,
) 


contenido_RAG = "casos clínicos, sintomas, diagnosticos y que forma confirmación por imágenes se recomienda para cada caso clínico"

class State(TypedDict):
    """Definimos la estructura de nuestro estado (memoria) usando TypedDict para tipado fuerte."""
    pregunta: str
    contenidoInternet: str
    contenidoRAG: str
    historial: list 
    respuesta: str
    next_step: str

def recibe_pregunta(state: State) -> State:

    if not state.get("historial"):
        state["historial"] = []
    
    state["historial"].append(f"Pregunta: {state['pregunta']}")
    print(f"Pregunta recibida: {state['pregunta']}, historial actualizado: {state['historial']}")
    return state

def decision(state: State) -> str:
    

    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", '''Eres un asistente inteligente que decide la mejor estrategia para responder a una pregunta.
        Tienes tres opciones: buscar en internet, buscar en una base de datos RAG o generar una respuesta directa utilizando un modelo de IA. 
        Basas tu decisión en la pregunta recibida.
        En nuestro RAG tenemos información sobre {explicacion_contenido_RAG}, pero no sobre cultura pop o eventos actuales.
        Responde ÚNICAMENTE con una de estas tres opciones: 
         "buscar_en_internet" si es una pregunta que no está en el RAG, 
         "buscar_en_rag" si el contenido puede estar en el RAG el cual contiene las siguientes informaciones {explicacion_contenido_RAG}, o 
         "consultar_llm" si no es una pregunta que tiene que ver con el contenido del RAG ni es algo que se precise buscar en internet.
          No agregues puntos, ni texto extra.'''),
        ("assistant", "Historial de la conversación hasta ahora: {historial}"),
        ("user", "Última pregunta: {pregunta}")
    ])

    chain = chat_prompt | llm | StrOutputParser() 

    pregunta_usuario = state["pregunta"]

    respuesta = chain.invoke({
        "pregunta": pregunta_usuario, 
        "explicacion_contenido_RAG": contenido_RAG,
        "historial": "\n".join(state.get("historial", "No hay historial previo hasta ahora"))
    })

    print(f"Respuesta de la decisión: {respuesta}")
    print("    ")

    return {"next_step": respuesta.strip('"')}


def buscar_en_rag(state: State) -> State:
    documentos_recuperados = vector_db.similarity_search(
        state["pregunta"], 
        k=3
    )

    state["contenidoRAG"] = "\n".join([doc.page_content for doc in documentos_recuperados])
    
    print(f"Documentos recuperados de RDS (PGVector): {state['contenidoRAG']}")
    return state


def buscar_en_internet(state: State) -> State:

    query = state["pregunta"]

    try:
        tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        respuesta = tavily_client.search(query, max_results=3)
        resultados = respuesta.get("results", [])

        if isinstance(resultados, str):
            print(f"Tavily devolvió un error: {resultados}")
            state["contenidoInternet"] = f"No pude buscar en internet. El buscador dijo: {resultados}"
        else:
            contenido_internet = "\n".join([f"Fuente ({res.get('url', 'N/A')}): {res.get('content', '')}" for res in resultados])
            print("Búsqueda en Tavily exitosa!")
            state["contenidoInternet"] = contenido_internet

    except Exception as e:
        print(f"Aviso interno: Falló el nodo de internet. Error: {e}")
        state["contenidoInternet"] = "Información del sistema: No pude acceder a internet en este momento debido a las restricciones de red. Por favor, responde la consulta del usuario usando tu propio conocimiento general de la mejor manera posible."
    
    return state



def consultar_llm(state: State) -> State:

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente inteligente que responde preguntas utilizando tu conocimiento previo."),
        ("user", "Pregunta: {pregunta}"),
        ("assistant", "Historial de la conversación hasta ahora: {historial}")

    ])
    
    chain = prompt_template | llm | StrOutputParser()

    respuesta = chain.invoke({"pregunta": state["pregunta"], "historial": "\n".join(state["historial"])})

    state["respuesta"] = respuesta
    
    return state

def sintetizar_respuesta(state: State) -> State:
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente inteligente que sintetiza respuestas finales a partir de toda la información disponible."),
        ("user", "Pregunta: {pregunta}\nContexto RAG: {contenidoRAG}\nContexto Internet: {contenidoInternet}\nHistorial: {historial}")
    ])
    
    chain = prompt_template | llm | StrOutputParser()
    
    respuesta = chain.invoke({
        "pregunta": state["pregunta"],
        "contenidoRAG": state.get("contenidoRAG", ""),
        "contenidoInternet": state.get("contenidoInternet", ""),
        "historial": "\n".join(state["historial"])
    })

    
    state["respuesta"] = respuesta

    return state

def responder(state: State) -> State:

    respuesta_final = state.get("respuesta", "Sin respuesta")
    state["historial"].append(f"Respuesta: {respuesta_final}")
    return state

graph = StateGraph(State)

graph.add_node("recibe_pregunta", RunnableLambda(recibe_pregunta))
graph.add_node("decision", RunnableLambda(decision))
graph.add_node("buscar_en_internet", RunnableLambda(buscar_en_internet))
graph.add_node("buscar_en_rag", RunnableLambda(buscar_en_rag))
graph.add_node("consultar_llm", RunnableLambda(consultar_llm))
graph.add_node("sintetizar_respuesta", RunnableLambda(sintetizar_respuesta))
graph.add_node("responder", RunnableLambda(responder))

graph.set_entry_point("recibe_pregunta")
graph.add_edge("recibe_pregunta", "decision")
graph.add_conditional_edges(
    "decision",
lambda state: state["next_step"], 
    {   "consultar_llm": "consultar_llm",
        "buscar_en_internet": "buscar_en_internet",
        "buscar_en_rag": "buscar_en_rag",
    }
)
graph.add_edge("consultar_llm", "responder")
graph.add_edge("buscar_en_internet", "sintetizar_respuesta")
graph.add_edge("buscar_en_rag", "sintetizar_respuesta")
graph.add_edge("sintetizar_respuesta", "responder")
graph.add_edge("responder", END)

ejecutable = graph.compile()

